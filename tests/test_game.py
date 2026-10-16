import json
import os
import tempfile
import unittest
from pathlib import Path

from tf2reaudio import game as game_mod
from tf2reaudio.catalog import Line, build
from tf2reaudio.game import Game
from tf2reaudio.store import ORIGINAL, Store
from tests.test_mp3 import as_installed
from tests.test_rcon import FakeRcon, free_port
from tests.test_store import FIXTURE, wav

MEDIC = [f"sound/vo/soldier_medic0{i}.mp3" for i in (1, 2, 3)]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = build(FIXTURE.read_text(encoding="utf-8").split())

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.tf = self.tmp / "tf"
        (self.tf / "custom").mkdir(parents=True)
        self.store = Store(self.tmp / "collection", "dev1", catalog=self.catalog)
        self.game = self.make_game()
        self.game.settings["rcon_port"] = free_port()  # nothing listens unless a test starts FakeRcon
        self._n = 0

    def tearDown(self):
        self._tmp.cleanup()

    def make_game(self, store=None, catalog=None):
        return Game(self.tf, store or self.store, catalog or self.catalog, data=self.tmp / "data")

    def activate(self, line="soldier/medic", store=None) -> bytes:
        store = store or self.store
        self._n += 1
        data = wav(300 + 10 * self._n)
        store.set_active(line, store.add_take(line, data, "member1"))
        return data

    def installed(self, rel) -> bytes | None:
        path = self.game.mod / rel
        return path.read_bytes() if path.exists() else None

    def all_files(self, root) -> list[Path]:
        return [Path(d, n) for d, _, names in os.walk(root) for n in names]


class SyncTest(Base):
    def test_writes_every_variant_then_idempotent(self):
        data = self.activate()
        self.assertEqual(self.game.sync_files(), 3)
        for rel in MEDIC:
            self.assertEqual(self.installed(rel), as_installed(rel, data))
        self.assertEqual(self.game.sync_files(), 0)
        self.assertEqual(self.game.pending_apply(), 3)

    def test_mp3_and_wav_twins(self):
        data = self.activate("scout/go_left")
        self.assertEqual(self.game.sync_files(), 6)
        for i in (1, 2, 3):
            for ext in ("mp3", "wav"):
                rel = f"sound/vo/scout_headleft0{i}.{ext}"
                self.assertEqual(self.installed(rel), as_installed(rel, data))

    def test_original_and_local_override_remove_files(self):
        self.activate()
        self.game.sync_files()
        self.store.set_local_override("soldier/medic", True)
        self.assertEqual(self.game.sync_files(), 3)
        self.assertIsNone(self.installed(MEDIC[0]))
        self.store.set_local_override("soldier/medic", False)
        self.assertEqual(self.game.sync_files(), 3)
        self.store.set_active("soldier/medic", ORIGINAL)
        self.assertEqual(self.game.sync_files(), 3)
        self.assertEqual(self.all_files(self.game.mod), [])

    def test_missing_blob_keeps_installed_file(self):
        old = self.activate()
        self.game.sync_files()
        self.activate()
        take = self.store.take(self.store.effective("soldier/medic"))
        (self.store.root / "blobs" / f"{take['sha256']}.wav").unlink()
        self.assertEqual(self.game.sync_files(), 0)
        self.assertEqual(self.installed(MEDIC[0]), as_installed(MEDIC[0], old))

    def test_per_variant_override(self):
        base = self.activate()
        var = self.activate("soldier/medic#02")
        self.assertEqual(self.game.sync_files(), 3)
        self.assertEqual([self.installed(r) for r in MEDIC], [as_installed(r, d) for r, d in zip(MEDIC, [base, var, base])])
        self.store.set_active("soldier/medic#02", ORIGINAL)  # the variant keeps priority
        self.assertEqual(self.game.sync_files(), 1)
        self.assertEqual([self.installed(r) for r in MEDIC], [as_installed(MEDIC[0], base), None, as_installed(MEDIC[2], base)])

    def test_variant_of_twins_covers_mp3_and_wav(self):
        var = self.activate("scout/go_left#03")
        self.assertEqual(self.game.sync_files(), 2)
        self.assertEqual(self.installed("sound/vo/scout_headleft03.wav"), var)
        self.assertEqual(self.installed("sound/vo/scout_headleft03.mp3"), as_installed(".mp3", var))

    def test_stale_files_removed_only_under_sound_vo(self):
        self.activate()
        self.game.sync_files()
        stale = self.game.mod / "sound" / "vo" / "old" / "gone.mp3"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"x")
        other = self.game.mod / "readme.txt"
        other.write_bytes(b"keep")
        self.assertEqual(self.game.sync_files(), 1)
        self.assertFalse(stale.exists())
        self.assertTrue(other.exists())
        self.assertIsNotNone(self.installed(MEDIC[0]))


class EvilCatalog:
    """Catalog that maps a crafted line to paths outside sound/vo and claims they are all valid."""

    def __init__(self, files):
        self.files = files

    def line(self, line_id):
        return Line(line_id, "soldier", "evil", "other", self.files)

    def is_vo_path(self, path):
        return True


class MaliciousTest(Base):
    def test_never_writes_outside_mod_sound_vo(self):
        files = [
            "sound/vo/../../../../evil1.mp3",
            "sound/vo/../../evil2.mp3",
            "../evil3.mp3",
            str(self.tmp / "evil4.mp3"),
            "sound/evil5.mp3",
            "materials/evil6.vmt",
            "sound/vo/ok.mp3",
        ]
        store = Store(self.tmp / "evil_store", "dev1", catalog=None)  # no line validation
        data = self.activate("../../crafted", store=store)
        game = self.make_game(store, EvilCatalog(files))
        self.assertEqual(game.sync_files(), 1)
        installed = as_installed(".mp3", data)
        written = [p for p in self.all_files(self.tmp) if p.read_bytes() in (data, installed)]
        copies = [p for p in written if p.parent.name in ("blobs", "mp3")]  # collection and encoder cache
        self.assertEqual(sorted(set(written) - set(copies)), [game.mod / "sound" / "vo" / "ok.mp3"])

    def test_rejects_paths_the_real_catalog_does_not_know(self):
        class Lying(EvilCatalog):
            def is_vo_path(self, path):
                return path in self.real

        cat = Lying(["sound/vo/soldier_medic01.mp3", "sound/vo/not_in_vpk.mp3"])
        cat.real = self.catalog._names
        store = Store(self.tmp / "s2", "dev1", catalog=None)
        self.activate("x", store=store)
        game = self.make_game(store, cat)
        self.assertEqual(game.sync_files(), 1)
        self.assertFalse((game.mod / "sound" / "vo" / "not_in_vpk.mp3").exists())

    @unittest.skipIf(os.name == "nt", "symlinks need extra rights on Windows")
    def test_symlinked_sound_folder_is_not_followed(self):
        outside = self.tmp / "outside"
        (outside / "vo").mkdir(parents=True)
        (outside / "vo" / "victim.mp3").write_bytes(b"precious")
        self.game.mod.mkdir()
        (self.game.mod / "sound").symlink_to(outside, target_is_directory=True)
        self.activate()
        self.assertEqual(self.game.sync_files(), 0)
        self.assertEqual(sorted(p.name for p in self.all_files(outside)), ["victim.mp3"])


class RconTest(Base):
    def serve(self, **kw):
        srv = FakeRcon(password=kw.pop("password", self.game.settings["rcon_password"]), **kw)
        self.game.settings["rcon_port"] = srv.port
        return srv

    def test_apply_sent_marks_applied(self):
        self.activate()
        self.game.sync_files()
        self.assertIn("pending_apply", self.store.state("soldier/medic"))
        with self.serve() as srv:
            self.assertEqual(self.game.apply(), "sent")
        self.assertEqual(srv.commands, ["snd_restart"])
        self.assertEqual(self.game.pending_apply(), 0)
        self.assertNotIn("pending_apply", self.store.state("soldier/medic"))
        self.assertEqual(self.make_game().pending_apply(), 0)  # persisted

    def test_apply_failures(self):
        self.activate()
        self.game.sync_files()
        self.assertEqual(self.game.apply(), "not_running")
        with self.serve(password="other"):
            self.assertEqual(self.game.apply(), "auth_failed")
        with self.serve(handler=lambda srv, conn: None):  # closes right away
            self.assertEqual(self.game.apply(), "error")
        self.assertEqual(self.game.pending_apply(), 3)
        self.assertIn("pending_apply", self.store.state("soldier/medic"))

    def test_status(self):
        self.assertEqual(self.game.status(), "not_configured")
        with self.serve(password="other"):
            self.assertEqual(self.game.status(), "auth_failed")
        self.assertEqual(self.game.status(), "not_configured")
        with self.serve() as srv:
            self.assertEqual(self.game.status(), "connected")
        self.assertEqual(srv.commands, ["echo"])
        self.assertEqual(self.game.status(), "not_running")
        self.assertEqual(self.make_game().settings["rcon_ok_once"], True)

    def test_mod_folder_is_new(self):
        with self.serve():
            self.activate()
            self.game.sync_files()
            self.assertTrue(self.game.mod_folder_is_new())
        self.assertFalse(self.game.mod_folder_is_new())  # TF2 seen closed: next start mounts it
        with self.serve():
            self.assertFalse(self.game.mod_folder_is_new())

    def test_mod_folder_created_with_tf2_closed_is_not_new(self):
        self.activate()
        self.game.sync_files()
        self.assertFalse(self.game.mod_folder_is_new())


class SettingsTest(Base):
    def test_password_generated_once_and_persisted(self):
        pw = self.game.settings["rcon_password"]
        self.assertRegex(pw, r"^[0-9a-f]{16}$")
        again = self.make_game()
        self.assertEqual(again.settings["rcon_password"], pw)
        self.assertEqual(again.settings["rcon_port"], game_mod.DEFAULT_PORT)
        self.assertIn(pw, again.launch_options())

    def test_bad_settings_repaired_and_unknown_keys_kept(self):
        path = self.tmp / "data" / "settings.json"
        path.write_text(json.dumps({"rcon_password": "x; quit", "rcon_port": "1", "auto_apply": True}), encoding="utf-8")
        g = self.make_game()
        self.assertRegex(g.settings["rcon_password"], r"^[0-9a-f]{16}$")
        self.assertEqual(g.settings["rcon_port"], 27015)
        self.assertTrue(json.loads(path.read_bytes())["auto_apply"])
        path.write_bytes(b"\xff not json")
        self.assertRegex(self.make_game().settings["rcon_password"], r"^[0-9a-f]{16}$")


class ModFolderTest(Base):
    def test_disable_enable_round_trip(self):
        data = self.activate()
        self.game.sync_files()
        self.game.disable()
        self.assertFalse(self.game.mod.exists())
        self.assertTrue((self.tmp / "data" / "disabled_mod" / MEDIC[0]).is_file())
        self.activate("scout/go_left")
        self.assertEqual(self.game.sync_files(), 0)  # paused while disabled
        self.assertFalse(self.game.mod.exists())
        self.game.disable()  # twice is fine
        self.game.enable()
        self.assertEqual(self.installed(MEDIC[0]), as_installed(MEDIC[0], data))
        self.assertIsNotNone(self.installed("sound/vo/scout_headleft01.wav"))
        self.assertFalse(self.game.disabled_dir.exists())
        self.assertEqual(self.game.sync_files(), 0)

    def test_disable_before_anything_installed(self):
        self.game.disable()
        self.activate()
        self.assertEqual(self.game.sync_files(), 0)
        self.game.enable()
        self.assertIsNotNone(self.installed(MEDIC[0]))

    def test_test_mod(self):
        self.assertFalse(self.game.test_mod_present())
        (self.tf / "custom" / "tf2reaudio_test" / "sound").mkdir(parents=True)
        self.assertTrue(self.game.test_mod_present())
        self.game.remove_test_mod()
        self.assertFalse(self.game.test_mod_present())
        self.game.remove_test_mod()

    def test_uninstall(self):
        self.activate()
        self.game.sync_files()
        self.game.disable()
        self.game.enable()
        self.game.disable()
        self.game.mod.mkdir()
        options = self.game.uninstall(delete_collection=False)
        self.assertIn(self.game.settings["rcon_password"], options)
        self.assertFalse(self.game.mod.exists() or self.game.disabled_dir.exists())
        self.assertTrue(self.store.root.exists())
        self.game.uninstall(delete_collection=True)
        self.assertFalse(self.store.root.exists())
        self.assertTrue((self.tf / "custom").is_dir())


if __name__ == "__main__":
    unittest.main()
