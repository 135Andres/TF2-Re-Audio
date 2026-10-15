import io
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
