import io
import os
import re
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
import zipfile

from tf2reaudio.util import atomic_write
from tools.build_zip import BuildError, REQUIRED, build_zip


class BuildZipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in list(REQUIRED) + ["tf2reaudio/__init__.py", "tf2reaudio/__main__.py", "tf2reaudio/web/index.html", "tf2reaudio/web/app.js"]:
            path = self.root / Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, b"fixture")

    def test_package_is_reproducible_and_excludes_user_data(self):
        for name in ["tf2reaudio/settings.json", "tf2reaudio/rcon_password.txt", "tf2reaudio/__pycache__/server.pyc", "runtime/python.exe", "tf2reaudio/.hidden/private.py", "tf2reaudio/blobs/take.wav", "tf2reaudio/collection/private.py"]:
            path = self.root / Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(path, b"private")
        output, digest = build_zip(self.root)
        data = output.read_bytes()
        second, other_digest = build_zip(self.root, self.root / "second.zip")
        self.assertEqual(second.read_bytes(), data)
        self.assertEqual(digest, other_digest)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), set(REQUIRED.values()) | {
                "tf2reaudio/__init__.py", "tf2reaudio/__main__.py", "tf2reaudio/web/index.html", "tf2reaudio/web/app.js"})
            self.assertEqual(archive.getinfo("tf2reaudio.sh").external_attr >> 16 & 0o777, 0o755)

    def test_missing_ui_fails_before_overwriting_candidate(self):
        output, _ = build_zip(self.root)
        before = output.read_bytes()
        (self.root / "tf2reaudio" / "web" / "index.html").unlink()
        with self.assertRaisesRegex(BuildError, "Missing package file"):
            build_zip(self.root)
        self.assertEqual(output.read_bytes(), before)


class ReleaseArchiveTest(unittest.TestCase):
    def test_extracted_release_has_notices_guides_and_working_cli(self):
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            output, _ = build_zip(root, folder / "release.zip")
            extracted = folder / "Extracted release with spaces"
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                archive.extractall(extracted)
            for name in ("LICENSE", "NOTICE", "docs/group-sharing.md", "docs/windows-security-checklist.md"):
                self.assertTrue((extracted / Path(name)).is_file(), f"Missing release file: {name}")
                self.assertEqual((extracted / Path(name)).read_bytes(), (root / Path(name)).read_bytes())
            readme = (extracted / "README.md").read_text(encoding="utf-8")
            for target in re.findall(r"\]\(([^)]+)\)", readme):
                if "://" not in target and not target.startswith("#"):
                    self.assertTrue((extracted / target.split("#")[0]).is_file(), f"Broken packaged README link: {target}")
            env = {**os.environ, "PYTHONPATH": "", "PYTHONNOUSERSITE": "1",
                   "XDG_DATA_HOME": str(folder / "data"), "APPDATA": str(folder / "data"),
                   "DISPLAY": "", "WAYLAND_DISPLAY": ""}
            for arguments in (["--version"], ["run", "--help"], ["doctor", "--help"]):
                result = subprocess.run([sys.executable, "-m", "tf2reaudio", *arguments],
                                        cwd=extracted, env=env, capture_output=True,
                                        text=True, encoding="utf-8", timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(result.stdout.strip())
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertLessEqual({"tf2reaudio/diagnostics.py", "tf2reaudio/web/diagnostics.js", "docs/launchers.md"}, names)
            self.assertFalse([n for n in names if re.search(r"(^|/)(logs|reports)/|\.jsonl|diagnostics-.*\.zip", n)])
            if os.name != "nt":  # HOME isolation keeps Steam discovery away from a real TF2 (Windows uses the registry)
                bundle_env = {**env, "HOME": str(folder / "home"), "XDG_DATA_HOME": str(folder / "data with spaces")}
                result = subprocess.run([sys.executable, "-m", "tf2reaudio", "doctor", "--bundle"], cwd=extracted,
                                        env=bundle_env, capture_output=True, text=True, encoding="utf-8", timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                saved = Path(result.stdout.split("Diagnostic report saved to: ")[1].splitlines()[0])
                with zipfile.ZipFile(saved) as archive:
                    self.assertIn("tf2: not_found", archive.read("summary.txt").decode("utf-8"))
                result = subprocess.run(["sh", str(extracted / "tf2reaudio.sh"), "--version"],
                                        cwd=folder, env=env, capture_output=True,
                                        text=True, encoding="utf-8", timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
