import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from tf2reaudio import steam


def make_tf2(library: Path, vpk: bytes | None = steam.VPK_MAGIC + b"rest") -> Path:
    """Fake TF2 install inside a Steam library; returns its "tf" folder."""
    tf = library / "steamapps" / "common" / "Team Fortress 2" / "tf"
    (tf / "custom").mkdir(parents=True)
    (tf / "gameinfo.txt").write_text("GameInfo {}", encoding="utf-8")
    if vpk is not None:
        (tf / steam.VO_VPK).write_bytes(vpk)
    return tf


def write_vdf(root: Path, paths: list[str]) -> None:
    body = "".join(
        f'\t"{i}"\n\t{{\n\t\t"path"\t\t"{p}"\n\t\t"apps"\n\t\t{{\n\t\t\t"440"\t\t"1"\n\t\t}}\n\t}}\n'
        for i, p in enumerate(paths)
    )
    vdf = root / "steamapps" / "libraryfolders.vdf"
    vdf.parent.mkdir(parents=True, exist_ok=True)
    vdf.write_text(f'"libraryfolders"\n{{\n{body}}}\n', encoding="utf-8")


def vdf_escape(path: Path) -> str:
    return str(path).replace("\\", "\\\\")


class TmpCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class CheckInstallTest(TmpCase):
    def test_ok_with_tf_folder(self):
        tf = make_tf2(self.dir)
        result = steam.check_install(tf)
        self.assertTrue(result.ok)
        self.assertIsNone(result.problem)
        self.assertEqual(result.tf, tf)
        self.assertEqual(os.listdir(tf / "custom"), [])  # write probe cleaned up

    def test_root_folder_is_corrected_to_tf(self):
        tf = make_tf2(self.dir)
        result = steam.check_install(tf.parent)
        self.assertTrue(result.ok)
        self.assertEqual(result.tf, tf)

    def test_not_found(self):
        result = steam.check_install(self.dir / "missing")
        self.assertEqual((result.ok, result.problem), (False, "not_found"))

    def test_wrong_folder(self):
        result = steam.check_install(self.dir)
        self.assertEqual((result.ok, result.problem), (False, "wrong_folder"))

    def test_vpk_missing(self):
        tf = make_tf2(self.dir, vpk=None)
        self.assertEqual(steam.check_install(tf).problem, "vpk_unreadable")

    def test_vpk_damaged(self):
        tf = make_tf2(self.dir, vpk=b"junk")
        self.assertEqual(steam.check_install(tf).problem, "vpk_unreadable")

    def test_not_writable(self):
        tf = make_tf2(self.dir)
        with mock.patch("tf2reaudio.steam.tempfile.TemporaryFile", side_effect=PermissionError(13, "Permission denied")):
            result = steam.check_install(tf)
        self.assertEqual((result.ok, result.problem), (False, "not_writable"))
        self.assertIn("Permission denied", result.detail)

    def test_missing_custom_is_created(self):
        tf = make_tf2(self.dir)
        (tf / "custom").rmdir()
        self.assertTrue(steam.check_install(tf).ok)
        self.assertTrue((tf / "custom").is_dir())


class LibraryPathsTest(unittest.TestCase):
    def test_windows_paths_are_unescaped(self):
        text = '"libraryfolders"\n{\n"0" { "path" "C:\\\\Program Files (x86)\\\\Steam" }\n"1" { "path" "D:\\\\SteamLibrary" }\n}'
        self.assertEqual(steam._library_paths(text), ["C:\\Program Files (x86)\\Steam", "D:\\SteamLibrary"])

    def test_escaped_quote(self):
        self.assertEqual(steam._library_paths('"path" "/a \\"b\\""'), ['/a "b"'])


class FindInstallsTest(TmpCase):
    def test_several_libraries(self):
        root = self.dir / "Steam"
        lib2, lib3 = self.dir / "Lib2", self.dir / "Lib3"
        tf1, tf2 = make_tf2(root), make_tf2(lib2)
        lib3.mkdir()  # library without TF2
        write_vdf(root, [vdf_escape(root), vdf_escape(lib2), vdf_escape(lib3)])
        with mock.patch("tf2reaudio.steam._steam_roots", return_value=[root, self.dir / "nope"]):
            self.assertEqual(steam.find_installs(), [tf1, tf2])

    def test_symlinked_roots_are_not_duplicated(self):
        home = self.dir
        real = home / ".local" / "share" / "Steam"
        tf = make_tf2(real)
        write_vdf(real, [vdf_escape(real)])
        (home / ".steam").mkdir()
        try:
            os.symlink(real, home / ".steam" / "steam", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not available")
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(Path, "home", return_value=home):
            self.assertEqual(steam.find_installs(), [tf])

    def test_windows_roots(self):
        class Key:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        fake_winreg = types.SimpleNamespace(
            HKEY_CURRENT_USER=1,
            OpenKey=lambda hive, sub: Key(),
            QueryValueEx=lambda key, name: ("c:/program files (x86)/steam", 1),
        )
        env = {"ProgramFiles(x86)": "C:\\Program Files (x86)"}
        with mock.patch.object(sys, "platform", "win32"), mock.patch.dict(sys.modules, {"winreg": fake_winreg}), \
                mock.patch.dict(os.environ, env):
            roots = steam._steam_roots()
        self.assertEqual(roots, [Path("c:/program files (x86)/steam"), Path("C:\\Program Files (x86)") / "Steam"])

    def test_windows_without_registry_key(self):
        def open_key(hive, sub):
            raise FileNotFoundError(sub)

        fake_winreg = types.SimpleNamespace(HKEY_CURRENT_USER=1, OpenKey=open_key)
        with mock.patch.object(sys, "platform", "win32"), mock.patch.dict(sys.modules, {"winreg": fake_winreg}), \
                mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(steam._steam_roots(), [])


if __name__ == "__main__":
    unittest.main()
