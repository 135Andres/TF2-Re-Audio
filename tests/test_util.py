import contextlib
import errno
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tf2reaudio import util


class AtomicWriteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_and_replaces(self):
        target = self.dir / "a.json"
        util.atomic_write(target, b"one")
        util.atomic_write(target, b"two")
        self.assertEqual(target.read_bytes(), b"two")
        self.assertEqual(os.listdir(self.dir), ["a.json"])

    def test_failure_leaves_old_file_and_no_temp(self):
        target = self.dir / "a.json"
        target.write_bytes(b"old")
        with mock.patch("tf2reaudio.util.os.replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                util.atomic_write(target, b"new")
        self.assertEqual(target.read_bytes(), b"old")
        self.assertEqual(os.listdir(self.dir), ["a.json"])

    def test_full_disk_during_write_preserves_old_file(self):
        target = self.dir / "collection.json"
        util.atomic_write(target, b"previous collection")
        fdopen = os.fdopen

        @contextlib.contextmanager
        def full_disk(fd, mode):
            with fdopen(fd, mode) as stream:
                failing = mock.Mock(wraps=stream)
                failing.write.side_effect = OSError(errno.ENOSPC, "No space left on device")
                yield failing

        with mock.patch("tf2reaudio.util.os.fdopen", side_effect=full_disk):
            with self.assertRaises(OSError) as raised:
                util.atomic_write(target, b"new collection")
        self.assertEqual(raised.exception.errno, errno.ENOSPC)
        self.assertEqual(target.read_bytes(), b"previous collection")
        self.assertEqual(list(self.dir.iterdir()), [target])

    def test_fsync_failure_preserves_old_file(self):
        target = self.dir / "collection.json"
        util.atomic_write(target, b"previous collection")
        with mock.patch("tf2reaudio.util.os.fsync", side_effect=OSError(errno.EIO, "Disk error")):
            with self.assertRaises(OSError) as raised:
                util.atomic_write(target, b"new collection")
        self.assertEqual(raised.exception.errno, errno.EIO)
        self.assertEqual(target.read_bytes(), b"previous collection")
        self.assertEqual(list(self.dir.iterdir()), [target])

    @unittest.skipIf(os.name == "nt", "POSIX file permissions")
    def test_private_permissions_on_create_and_replace(self):
        target = self.dir / "settings.json"
        util.atomic_write(target, b"private")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        target.chmod(0o644)
        util.atomic_write(target, b"still private")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)


class DataDirTest(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "Linux/XDG behavior")
    def test_honors_xdg_data_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"XDG_DATA_HOME": tmp}):
                path = util.data_dir()
            self.assertEqual(path, Path(tmp) / "tf2reaudio")
            self.assertTrue(path.is_dir())

    @unittest.skipUnless(sys.platform == "win32", "Windows only")
    def test_uses_appdata_on_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                path = util.data_dir()
            self.assertEqual(path, Path(tmp) / "TF2ReAudio")
            self.assertTrue(path.is_dir())


class LowPriorityTest(unittest.TestCase):
    def test_never_raises(self):
        with mock.patch("tf2reaudio.util.os.nice", side_effect=OSError("denied"), create=True):
            util.set_low_priority()


if __name__ == "__main__":
    unittest.main()
