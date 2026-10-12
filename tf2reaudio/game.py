"""Bridge with the game: installs the active takes in tf/custom/tf2reaudio, asks TF2 to reload sounds
over RCON, and disables or uninstalls the mod."""

import hashlib
import json
import os
import re
import secrets
import shutil
from pathlib import Path

from . import rcon
from .util import atomic_write, data_dir

MOD_DIR = "tf2reaudio"  # tf/custom/tf2reaudio/sound/vo/...
TEST_MOD_DIR = "tf2reaudio_test"  # the Phase 0 experiment
DEFAULT_PORT = 27015

_KEEP = object()  # take or blob not here yet: leave the installed file as it is
_PASSWORD = re.compile(r"[0-9a-f]{16}")


class Game:
    def __init__(self, tf_dir: Path, store, catalog, data: Path | None = None):
        """data: folder for settings.json and disabled_mod (default util.data_dir())."""
        self.tf = Path(tf_dir)
        self.store = store
        self.catalog = catalog
        self.data = Path(data) if data else data_dir()
        self.mod = self.tf / "custom" / MOD_DIR
        self.disabled_dir = self.data / "disabled_mod"
        self._settings_path = self.data / "settings.json"
        self._mod_new = False
        self.settings = self._load_settings()

    # ---- settings ----

    def _load_settings(self) -> dict:
        try:
            s = json.loads(self._settings_path.read_bytes())
            if not isinstance(s, dict):
                raise ValueError
        except (OSError, ValueError):
            s = {}
        port, pending = s.get("rcon_port"), s.get("pending_files")
        fixed = {
            "rcon_password": s["rcon_password"] if _is_password(s.get("rcon_password")) else secrets.token_hex(8),
            "rcon_port": port if type(port) is int and 0 < port < 65536 else DEFAULT_PORT,
            "rcon_ok_once": s.get("rcon_ok_once") is True,
            "pending_files": pending if type(pending) is int and pending >= 0 else 0,
        }
        if any(s.get(k) != v for k, v in fixed.items()):
            s.update(fixed)  # unknown keys are kept for other modules
            self.settings = s
            self._set()
        return s

    def _set(self, **changes):
        self.settings.update(changes)
        self.data.mkdir(parents=True, exist_ok=True)
        atomic_write(self._settings_path, json.dumps(self.settings, indent=1, sort_keys=True).encode("utf-8"))

    def launch_options(self) -> str:
        return rcon.launch_options(self.settings["rcon_password"], self.settings["rcon_port"])

    # ---- files ----

    def _dest(self, rel) -> Path:
        """Resolved destination of a catalog path inside the mod's sound/vo; ValueError for anything else."""
        if not (isinstance(rel, str) and rel.startswith("sound/vo/") and self.catalog.is_vo_path(rel)):
            raise ValueError(f"Not a voice file: {rel!r}")
        dest = (self.mod / rel).resolve()
        if not dest.is_relative_to(self.mod.resolve() / "sound" / "vo"):
            raise ValueError(f"Path leaves the mod folder: {rel!r}")
        return dest

    def _source(self, variant, base):
        """A per-variant line ("soldier/medic#02") decides its file once it was ever set or overridden."""
        store = self.store
        return variant if store.active(variant) is not None or "local_override" in store.state(variant) else base

    def _wanted(self) -> dict:
        """Resolved destination -> sha256 to install, None for the original audio, or _KEEP."""
        store = self.store
        ids = set(store.lines())
        want = {}
        for base in sorted({i.partition("#")[0] for i in ids}):
            try:
                line = self.catalog.line(base)
            except KeyError:
                continue
            stems = list(dict.fromkeys(f.rsplit(".", 1)[0] for f in line.files))  # .mp3/.wav twins share a stem
            for rel in line.files:
                variant = f"{base}#{stems.index(rel.rsplit('.', 1)[0]) + 1:02d}"
                try:
                    dest = self._dest(rel)
                except ValueError:
                    continue
                take_id = store.effective(self._source(variant, base) if variant in ids else base)
                take = take_id and store.take(take_id)
                if take_id is None:
                    want[dest] = None
                elif take and store.has_blob(take["sha256"]):
                    want[dest] = take["sha256"]
                else:
                    want[dest] = _KEEP
        return want

    def sync_files(self) -> int:
        """Make tf/custom/tf2reaudio match the collection. Returns the number of files written or removed.
        Does nothing while the mod is disabled."""
        if self.disabled_dir.is_dir():
            return 0
        created = not self.mod.exists()
        want = self._wanted()
        changed = 0
        try:
            for dest, sha in want.items():
                if sha is _KEEP:
                    continue
                if sha is None:
                    if dest.is_file():
                        dest.unlink()
                        changed += 1
                    continue
                if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() == sha:
                    continue
                try:
                    data = self.store.blob(sha)
                except KeyError:  # pruned since _wanted()
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(dest, data)
                changed += 1
            vo = self.mod / "sound" / "vo"
            inside = self.mod.resolve() / "sound" / "vo"
            for dirpath, _, names in os.walk(vo):
                for name in names:
                    path = Path(dirpath, name).resolve()
                    if path not in want and path.is_relative_to(inside):  # stale: no line maps to it
                        path.unlink()
                        changed += 1
        finally:
            if changed:
                self._set(pending_files=self.settings["pending_files"] + changed)
            if created and self.mod.exists():
                self._note_new_folder()
        return changed

    def pending_apply(self) -> int:
        """Files changed in tf/custom since the last successful apply()."""
        return self.settings["pending_files"]

    # ---- RCON ----

    def apply(self) -> str:
        """Ask TF2 to reload sounds: "sent" | "not_running" | "auth_failed" | "error"."""
        try:
            self._rcon("snd_restart")
        except rcon.RconAuthFailed:
            return "auth_failed"
        except rcon.RconNotRunning:
            return "not_running"
        except rcon.RconError:
            return "error"
        self.store.mark_applied()
        self._set(pending_files=0, rcon_ok_once=True)
        return "sent"

    def status(self) -> str:
        """"connected" | "not_running" | "not_configured" (never connected yet) | "auth_failed"."""
        try:
            self._rcon("echo")
        except rcon.RconAuthFailed:
            return "auth_failed"
        except rcon.RconNotRunning:
            return "not_running" if self.settings["rcon_ok_once"] else "not_configured"
        except rcon.RconError:
            return "not_running"  # something listens but does not answer like TF2
        if not self.settings["rcon_ok_once"]:
            self._set(rcon_ok_once=True)
        return "connected"

    def _rcon(self, command):
        return rcon.send(command, self.settings["rcon_password"], self.settings["rcon_port"], timeout=3.0)

    def _note_new_folder(self):
        self._mod_new = self.status() not in ("not_running", "not_configured")

    def mod_folder_is_new(self) -> bool:
        """Hint for "Restart TF2 once": this process created the mod folder while TF2 answered (or refused
        the password) over RCON, and no check has seen TF2 closed since. TF2 only mounts tf/custom
        folders at startup. Without RCON set up, a running TF2 looks closed, so this can miss it."""
        if self._mod_new and self.status() in ("not_running", "not_configured"):
            self._mod_new = False
        return self._mod_new

    # ---- test mod, disable, uninstall ----

    def test_mod_present(self) -> bool:
        return (self.tf / "custom" / TEST_MOD_DIR).is_dir()

    def remove_test_mod(self):
        path = self.tf / "custom" / TEST_MOD_DIR
        if path.is_dir():
            shutil.rmtree(path)

    def disable(self):
        """Move the mod out of tf/custom into data_dir()/disabled_mod. sync_files() pauses until enable()."""
        if self.disabled_dir.exists():
            shutil.rmtree(self.disabled_dir)
        if self.mod.exists():
            shutil.move(str(self.mod), str(self.disabled_dir))  # works across drives
        else:
            self.disabled_dir.mkdir(parents=True)

    def enable(self):
        """Move the mod back into tf/custom and bring it up to date."""
        if self.disabled_dir.is_dir():
            if self.mod.exists():
                shutil.rmtree(self.mod)
            self.mod.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(self.disabled_dir), str(self.mod))
            self._note_new_folder()
        self.sync_files()

    def uninstall(self, delete_collection: bool) -> str:
        """Remove the mod (enabled, disabled and test copies) and optionally the local collection.
        Returns the launch options the user should remove from Steam."""
        for path in (self.mod, self.disabled_dir, self.tf / "custom" / TEST_MOD_DIR):
            if path.exists():
                shutil.rmtree(path)
        root = self.store.root
        if delete_collection and (root / "blobs").is_dir():  # only ever delete a real store folder
            shutil.rmtree(root)
        return self.launch_options()


def _is_password(value) -> bool:
    return isinstance(value, str) and _PASSWORD.fullmatch(value) is not None
