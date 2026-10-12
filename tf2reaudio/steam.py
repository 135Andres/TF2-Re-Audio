"""Find TF2 installs through Steam and check that one is usable."""
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

VO_VPK = "tf2_sound_vo_english_dir.vpk"
VPK_MAGIC = (0x55AA1234).to_bytes(4, "little")


@dataclass
class InstallCheck:
    ok: bool
    problem: str | None  # "not_found" | "wrong_folder" | "vpk_unreadable" | "not_writable"
    detail: str
    tf: Path | None = None  # the corrected "tf" folder, when it was found


def _steam_roots() -> list[Path]:
    if sys.platform == "win32":
        roots = []
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                roots.append(Path(winreg.QueryValueEx(key, "SteamPath")[0]))
        except (ImportError, OSError):
            pass
        pf86 = os.environ.get("ProgramFiles(x86)")
        if pf86:
            roots.append(Path(pf86) / "Steam")
        return roots
    home = Path.home()
    return [
        home / ".local" / "share" / "Steam",
        home / ".steam" / "steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
    ]


def _library_paths(vdf_text: str) -> list[str]:
    """Library folders listed in libraryfolders.vdf, with VDF escapes (\\\\, \\") undone."""
    # shortcut: only the "path" key format (Steam 2021+), not the older "1" "D:\\Lib" one
    found = re.findall(r'"path"\s+"((?:[^"\\]|\\.)*)"', vdf_text)
    return [re.sub(r"\\(.)", r"\1", p) for p in found]


def find_installs() -> list[Path]:
    """All TF2 "tf" folders found in every Steam library, without duplicates."""
    libraries = []
    for root in _steam_roots():
        libraries.append(root)
        try:
            text = (root / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        libraries += [Path(p) for p in _library_paths(text)]

    installs, seen = [], set()
    for lib in libraries:
        tf = lib / "steamapps" / "common" / "Team Fortress 2" / "tf"
        if not (tf / "gameinfo.txt").is_file():
            continue
        key = os.path.normcase(tf.resolve())
        if key not in seen:
            seen.add(key)
            installs.append(tf)
    return installs


def check_install(tf: Path) -> InstallCheck:
    """Check a "tf" folder (or the "Team Fortress 2" folder above it) for reading voices and writing mods."""
    tf = Path(tf)
    if not tf.is_dir():
        return InstallCheck(False, "not_found", f"Folder not found: {tf}")
    if not (tf / "gameinfo.txt").is_file() and (tf / "tf" / "gameinfo.txt").is_file():
        tf = tf / "tf"
    if not (tf / "gameinfo.txt").is_file():
        return InstallCheck(False, "wrong_folder", f"This is not the Team Fortress 2 folder: {tf}")

    vpk = tf / VO_VPK
    try:
        with open(vpk, "rb") as f:
            if f.read(4) != VPK_MAGIC:
                return InstallCheck(False, "vpk_unreadable", f"The voice file is damaged: {vpk}", tf)
    except OSError as e:
        return InstallCheck(False, "vpk_unreadable", f"Can't read the voice file {vpk}: {e.strerror or e}", tf)

    custom = tf / "custom"
    try:
        custom.mkdir(exist_ok=True)
        with tempfile.TemporaryFile(dir=custom):  # deleted on close
            pass
    except OSError as e:
        return InstallCheck(False, "not_writable", f"Can't write in {custom}: {e.strerror or e}", tf)
    return InstallCheck(True, None, f"TF2 found at {tf}", tf)
