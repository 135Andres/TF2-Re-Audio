import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tf2reaudio import util
from tf2reaudio.__main__ import main
from tests.fixtures.make_vpk import make_vpk
from tests.test_rcon import FakeRcon, free_port
from tests.test_store import wav

PW = "0123456789abcdef"
NAMES = [f"sound/vo/soldier_medic0{i}.mp3" for i in (1, 2, 3)] + [
    "sound/vo/soldier_thanks01.mp3",
    "sound/vo/soldier_painsharp01.mp3",
    "sound/vo/scout_go01.mp3",
]


class CliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        env = mock.patch.dict(os.environ, {"XDG_DATA_HOME": str(self.tmp / "xdg"), "APPDATA": str(self.tmp / "xdg")})
        env.start()
        self.addCleanup(env.stop)
        self.tf = self.tmp / "Team Fortress 2" / "tf"
        self.tf.mkdir(parents=True)
        (self.tf / "gameinfo.txt").write_text("x", encoding="utf-8")
        make_vpk(self.tf / "tf2_sound_vo_english_dir.vpk", {n: b"orig" for n in NAMES})
        installs = mock.patch("tf2reaudio.steam.find_installs", return_value=[self.tf])  # never the real TF2
        installs.start()
        self.addCleanup(installs.stop)
        self.data = util.data_dir()
        self.write_settings(free_port())  # nothing listens unless a test starts FakeRcon

    def tearDown(self):
        self._tmp.cleanup()

    def write_settings(self, port, **extra):
        path = self.data / "settings.json"
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        settings = {**old, "rcon_password": PW, "rcon_port": port, **extra}
        (self.data / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    def settings(self) -> dict:
        return json.loads((self.data / "settings.json").read_text(encoding="utf-8"))

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def wav_file(self, data=None) -> Path:
        path = self.tmp / "beep.wav"
        path.write_bytes(wav() if data is None else data)
        return path

    # ---- doctor ----

    def test_doctor_never_prints_password(self):
        code, out, err = self.run_cli("doctor", "--copy")
        self.assertEqual(code, 0, out + err)
        report = (self.data / "doctor-report.txt").read_text(encoding="utf-8")
        for text in (out, err, report):
            self.assertNotIn(PW, text)
            self.assertNotIn("rcon_password", text)
        self.assertIn(str(self.data / "doctor-report.txt"), out)
        self.assertIn("Voice file archive: readable (6 files)", report)
        self.assertIn("RCON: not set up yet", report)
        self.assertIn("Phase 0 test folder (custom/tf2reaudio_test): not present", report)
        self.assertIn("Changes waiting for apply: 0 files", report)
        self.assertEqual(self.settings()["rcon_password"], PW)

    def test_doctor_connected_and_test_folder(self):
        (self.tf / "custom" / "tf2reaudio_test").mkdir(parents=True)
        with FakeRcon(password=PW) as srv:
            self.write_settings(srv.port)
            code, out, _ = self.run_cli("doctor", "--tf", str(self.tf.parent))
        self.assertEqual(code, 0)
        self.assertNotIn(PW, out)
        self.assertIn("RCON: connected", out)
        self.assertIn("Folder from --tf: OK", out)
        self.assertIn("tf2reaudio_test): present", out)

    def test_doctor_without_tf2(self):
        with mock.patch("tf2reaudio.steam.find_installs", return_value=[]):
            code, out, _ = self.run_cli("doctor")
        self.assertEqual(code, 1)
        self.assertIn("TF2 installs found by Steam: 0", out)
        self.assertIn("--tf", out)

    # ---- setup ----

    def test_setup_prints_launch_options(self):
        (self.tf / "custom" / "tf2reaudio_test").mkdir(parents=True)
        code, out, _ = self.run_cli("setup")
        self.assertEqual(code, 0)
        self.assertIn(f"+rcon_password {PW}", out)
        self.assertIn("Properties > General > Launch Options", out)
        self.assertIn("Keep any options you already have; add these at the end.", out)
        self.assertIn("setup --remove-test-mod", out)
        self.assertTrue((self.tf / "custom" / "tf2reaudio_test").is_dir())
        code, out, _ = self.run_cli("setup", "--remove-test-mod")
        self.assertEqual(code, 0)
        self.assertIn("Removed the Phase 0 test folder", out)
        self.assertFalse((self.tf / "custom" / "tf2reaudio_test").exists())

    def test_bad_tf_folder(self):
        code, _, err = self.run_cli("setup", "--tf", str(self.tmp / "nope"))
        self.assertEqual(code, 1)
        self.assertIn("Folder not found", err)

    # ---- import-wav ----

    def test_import_wav_installs_every_variant(self):
        data = wav()
        code, out, err = self.run_cli("import-wav", "soldier/medic", str(self.wav_file(data)))
        self.assertEqual(code, 0, err)
        self.assertIn("Wrote 3 file(s)", out)
        self.assertIn("Run `apply` (or restart TF2) to hear it.", out)
        self.assertIn("restart it once", out)
        for name in NAMES[:3]:
            self.assertEqual((self.tf / "custom" / "tf2reaudio" / name).read_bytes(), data)
        settings = self.settings()
        self.assertRegex(settings["device_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(settings["rcon_password"], PW)
        self.assertEqual(settings["pending_files"], 3)
        code, out, _ = self.run_cli("import-wav", "soldier/medic", str(self.wav_file(wav(500))))
        self.assertNotIn("restart it once", out)
        self.assertEqual(self.settings()["device_id"], settings["device_id"])

    def test_import_invalid_wav(self):
        code, out, err = self.run_cli("import-wav", "soldier/medic", str(self.wav_file(b"not audio")))
        self.assertEqual(code, 1)
        self.assertIn("This WAV can't be used: Not a WAV file", err)
        self.assertFalse((self.tf / "custom" / "tf2reaudio").exists())

    def test_import_unknown_line_and_missing_file(self):
        code, _, err = self.run_cli("import-wav", "soldier/nope", str(self.wav_file()))
        self.assertEqual(code, 1)
        self.assertIn("Unknown voice line: 'soldier/nope'", err)
        self.assertIn("lines soldier", err)
        code, _, err = self.run_cli("import-wav", "soldier/medic", str(self.tmp / "missing.wav"))
        self.assertEqual(code, 1)
        self.assertIn("Can't read", err)

    # ---- lines ----

    def test_lines(self):
        code, out, _ = self.run_cli("lines", "soldier")
        self.assertEqual(code, 0)
        self.assertIn("soldier/medic", out)
        self.assertIn("MEDIC!", out)
        self.assertIn("soldier/pain_sharp", out)
        self.assertNotIn("scout/", out)
        code, out, _ = self.run_cli("lines", "soldier", "--category", "pain_death")
        self.assertNotIn("soldier/medic", out)
        self.assertIn("soldier/pain_sharp", out)

    # ---- apply ----

    def test_apply_sent(self):
        self.run_cli("import-wav", "soldier/medic", str(self.wav_file()))
        with FakeRcon(password=PW) as srv:
            self.write_settings(srv.port)
            code, out, _ = self.run_cli("apply")
        self.assertEqual(code, 0)
        self.assertIn("TF2 is reloading its sounds", out)
        self.assertIn("snd_restart", srv.commands)
        self.assertEqual(self.settings()["pending_files"], 0)

    def test_apply_not_running(self):
        code, out, _ = self.run_cli("apply")
        self.assertEqual(code, 1)
        self.assertIn("TF2 is not reachable", out)

    def test_apply_wrong_password(self):
        with FakeRcon(password="fedcba9876543210") as srv:
            self.write_settings(srv.port)
            code, out, _ = self.run_cli("apply")
        self.assertEqual(code, 1)
        self.assertIn("TF2 rejected the password", out)
        self.assertNotIn(PW, out)

    def test_run_and_host(self):
        with mock.patch("tf2reaudio.__main__.run_local", return_value=0) as run:
            self.assertEqual(self.run_cli("run", "--no-browser", "--port", "0")[0], 0)
            run.assert_called_once_with(None, 0, browser=False)
        self.assertEqual(self.run_cli("host")[0], 1)


if __name__ == "__main__":
    unittest.main()
