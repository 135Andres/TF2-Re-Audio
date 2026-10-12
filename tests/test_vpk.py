import tempfile
import time
import unittest
from pathlib import Path

from tests.fixtures.make_vpk import make_vpk
from tf2reaudio.vpk import VpkError, VpkIndex

FILES = {
    "sound/vo/soldier_medic01.mp3": b"ID3" + bytes(range(256)) * 4,
    "sound/vo/scout_no01.mp3": b"ID3short",
    "readme.txt": b"root file",
    "sound/empty.wav": b"",
}


class VpkTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "test_dir.vpk"

    def tearDown(self):
        self._tmp.cleanup()

    def check_all(self, **kw):
        make_vpk(self.path, FILES, **kw)
        index = VpkIndex(self.path)
        self.assertEqual(sorted(index.names()), sorted(FILES))
        for name, content in FILES.items():
            self.assertIn(name, index)
            self.assertEqual(index.read(name), content)
        self.assertNotIn("sound/vo/missing.mp3", index)

    def test_v1_data_in_dir(self):
        self.check_all(version=1)

    def test_v2_data_in_dir(self):
        self.check_all(version=2)

    def test_preload(self):
        self.check_all(preload=10)

    def test_external_archive(self):
        self.check_all(external=True)
        self.assertTrue((self.dir / "test_000.vpk").exists())

    def test_preload_and_external_v1(self):
        self.check_all(version=1, preload=5, external=True)

    def test_unknown_name(self):
        make_vpk(self.path, FILES)
        with self.assertRaises(VpkError):
            VpkIndex(self.path).read("nope.mp3")

    def test_missing_file(self):
        with self.assertRaises(VpkError):
            VpkIndex(self.dir / "absent_dir.vpk")

    def test_missing_archive(self):
        make_vpk(self.path, FILES, external=True)
        (self.dir / "test_000.vpk").unlink()
        index = VpkIndex(self.path)
        with self.assertRaises(VpkError):
            index.read("readme.txt")

    def test_bad_signature_and_version(self):
        self.path.write_bytes(b"\0" * 64)
        with self.assertRaises(VpkError):
            VpkIndex(self.path)
        make_vpk(self.path, FILES)
        raw = bytearray(self.path.read_bytes())
        raw[4] = 7
        self.path.write_bytes(raw)
        with self.assertRaises(VpkError):
            VpkIndex(self.path)

    def test_bad_crc(self):
        make_vpk(self.path, FILES)
        raw = bytearray(self.path.read_bytes())
        raw[-1] ^= 0xFF  # last data byte belongs to some file with data after the tree
        self.path.write_bytes(raw)
        index = VpkIndex(self.path)
        failed = []
        for name in FILES:
            try:
                index.read(name)
            except VpkError:
                failed.append(name)
        self.assertEqual(len(failed), 1)

    def test_truncated_anywhere_raises_fast(self):
        for version in (1, 2):
            make_vpk(self.path, FILES, version=version, preload=4)
            full = self.path.read_bytes()
            tree_end = len(full) - sum(max(len(c) - 4, 0) for c in FILES.values())
            for cut in range(tree_end):
                self.path.write_bytes(full[:cut])
                start = time.perf_counter()
                with self.assertRaises(VpkError, msg=f"v{version} cut at {cut}"):
                    VpkIndex(self.path)
                self.assertLess(time.perf_counter() - start, 0.1)

    def test_truncated_data_raises_on_read(self):
        make_vpk(self.path, FILES)
        self.path.write_bytes(self.path.read_bytes()[:-1])
        index = VpkIndex(self.path)
        with self.assertRaises(VpkError):
            for name in FILES:
                index.read(name)


if __name__ == "__main__":
    unittest.main()
