"""Local collection (PLAN §4): immutable takes, a set_active event log per line, conflicts,
device-local state, and blobs/<sha256>.wav. Replicated data merges as a grow-only union.

Conflict rule: every event records `parent_event_id` (the line's winner when it was created) and
`merges` (the line's other leaf events at that moment). A leaf is an event of the line that no other
event names as parent or in merges. A line is in conflict when it has more than one leaf, i.e. two
events exist and no later event has both in its ancestry. Any new set_active/resolve/undo created
after both were merged points at both leaves, so it resolves the conflict.
"""

import hashlib
import io
import json
import re
import threading
import time
import uuid
import zipfile
from pathlib import Path

from .audio import MAX_BYTES, InvalidWav, inspect_wav
from .util import atomic_write

ORIGINAL = "ORIGINAL"
KEEP_INACTIVE = 5
FORMAT_VERSION = 1

_HEX32 = re.compile(r"[0-9a-f]{32}")
_SHA = re.compile(r"[0-9a-f]{64}")
_NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}")
_VARIANT = re.compile(r"[0-9]{2}")
_BLOB_ENTRY = re.compile(r"blobs/([0-9a-f]{64})\.wav")
_TAKE_KEYS = ("take_id", "sha256", "line_id", "author_member_id", "device_id", "created_at", "lamport")
_EVENT_KEYS = ("event_id", "line_id", "target", "parent_event_id", "merges", "lamport", "device_id")
_MAX_JSON = 50_000_000
_MAX_ZIP_ENTRIES = 10000
_MAX_ZIP_TOTAL_BYTES = 128 * 1024 * 1024


class StoreError(Exception):
    """Expected problem with the collection; the message is shown to the user."""


class UnsupportedFormat(StoreError):
    """Collection uses a newer format; updating the app is required."""


def _is(rx, value) -> bool:
    return isinstance(value, str) and rx.fullmatch(value) is not None


def _is_int(value) -> bool:
    return type(value) is int and 0 <= value < 2**53


def _need(ok, what):
    if not ok:
        raise StoreError(f"Invalid collection data: {what}.")


def _winner(events):
    return max(events, key=lambda e: (e["lamport"], e["device_id"], e["event_id"]), default=None)


def _leaves(events) -> set:
    ids = {e["event_id"] for e in events}
    for e in events:
        ids.discard(e["parent_event_id"])
        ids.difference_update(e["merges"])
    return ids


class Store:
    def __init__(self, root: Path, device_id: str, catalog=None):
        """catalog=None skips line id validation (only for small unit tests)."""
        if not _is(_NAME, device_id):
            raise StoreError("Invalid device id.")
        self.root = Path(root)
        self.device_id = device_id
        self.catalog = catalog
        self.warning = None  # set when collection.json was damaged and restored from the backup
        self._lock = threading.Lock()
        self._blobs = self.root / "blobs"
        self._blobs.mkdir(parents=True, exist_ok=True)
        self._file = self.root / "collection.json"
        self._bak = self.root / "collection.json.bak"
        self._local = self.root / "local.json"
        self._load()

    # ---- persistence ----

    def _load(self):
        self._takes, self._events, self._pruned = {}, {}, set()
        self.warning = None
        if self._file.exists():
            try:
                self._takes, self._events, self._pruned = self._parse(json.loads(self._file.read_bytes()), False)
            except UnsupportedFormat:
                raise
            except (ValueError, StoreError) as main_err:
                # Try backup; UnsupportedFormat must not be treated as corruption.
                try:
                    raw = self._bak.read_bytes()
                    try:
                        self._takes, self._events, self._pruned = self._parse(json.loads(raw), False)
                    except UnsupportedFormat:
                        raise
                except UnsupportedFormat:
                    raise
                except (OSError, ValueError, StoreError) as bak_err:
                    raise StoreError(
                        f"{self._file} and backup are both damaged ({main_err}; backup: {bak_err}). "
                        "Move them away to start an empty collection. Blobs were preserved."
                    ) from None
                atomic_write(self._file, raw)  # so the next backup rotation copies good data
                self.warning = "Your collection file was damaged; the previous version was restored."
        try:
            loc = json.loads(self._local.read_bytes())
            self._overrides, self._unshared = set(loc["overrides"]), set(loc["unshared"])
            self._applied = dict(loc["applied"])
        except (OSError, ValueError, KeyError, TypeError):  # device-local only, safe to reset
            self._overrides, self._unshared, self._applied = set(), set(), {}

    def _dump(self) -> bytes:
        snap = {
            "format_version": FORMAT_VERSION,
            "takes": [self._takes[k] for k in sorted(self._takes)],
            "events": [self._events[k] for k in sorted(self._events)],
            "pruned": sorted(self._pruned),
        }
        return json.dumps(snap, sort_keys=True, indent=1).encode("utf-8")

    def _save(self, collection=True):
        local = {"overrides": sorted(self._overrides), "unshared": sorted(self._unshared), "applied": self._applied}
        try:
            atomic_write(self._local, json.dumps(local, sort_keys=True).encode("utf-8"))
            if collection:
                if self._file.exists():
                    atomic_write(self._bak, self._file.read_bytes())
                atomic_write(self._file, self._dump())
        except BaseException as error:
            self._load()  # keep memory equal to disk
            if isinstance(error, OSError):
                raise StoreError(f"Could not save the collection: {error}") from error
            raise

    # ---- validation ----

    def _check_line(self, line_id):
        if not isinstance(line_id, str) or not 0 < len(line_id) <= 200:
            raise StoreError("Invalid line id.")
        if self.catalog is None:
            return
        base, sep, variant = line_id.partition("#")
        try:
            line = self.catalog.line(base)
        except KeyError:
            raise StoreError(f"Unknown voice line: {line_id!r}.") from None
        if sep:
            stems = {f.rsplit(".", 1)[0] for f in line.files}
            if not (_is(_VARIANT, variant) and 1 <= int(variant) <= len(stems)):
                raise StoreError(f"Unknown voice line variant: {line_id!r}.")

    def _parse(self, snap, check_lines=True):
        """Validate untrusted replicated data. Returns (takes, events, pruned) or raises StoreError."""
        _need(isinstance(snap, dict), "not an object")
        fv = snap.get("format_version", 1)
        _need(type(fv) is int and 1 <= fv <= 2**31 - 1, "bad format_version")
        if fv != FORMAT_VERSION:
            if fv > FORMAT_VERSION:
                raise UnsupportedFormat(f"This collection was saved with a newer app (v{fv}); update the app to open it.")
        takes, events, pruned = (snap.get(k, []) for k in ("takes", "events", "pruned"))
        _need(all(isinstance(x, list) for x in (takes, events, pruned)), "takes, events and pruned must be lists")
        out_t, out_e = {}, {}
        for t in takes:
            _need(isinstance(t, dict), "take is not an object")
            _need(_is(_HEX32, t.get("take_id")), "bad take_id")
            _need(_is(_SHA, t.get("sha256")), "bad sha256")
            _need(_is(_NAME, t.get("author_member_id")) and _is(_NAME, t.get("device_id")), "bad take author")
            _need(_is_int(t.get("created_at")) and _is_int(t.get("lamport")), "bad take numbers")
            if check_lines:
                self._check_line(t.get("line_id"))
            _need(isinstance(t.get("line_id"), str), "bad take line_id")
            out_t[t["take_id"]] = {k: t[k] for k in _TAKE_KEYS}
        for e in events:
            _need(isinstance(e, dict), "event is not an object")
            _need(_is(_HEX32, e.get("event_id")), "bad event_id")
            target, parent, merges = e.get("target"), e.get("parent_event_id"), e.get("merges")
            _need(target == ORIGINAL or _is(_HEX32, target), "bad event target")
            _need(parent is None or _is(_HEX32, parent), "bad parent_event_id")
            _need(isinstance(merges, list) and len(merges) <= 1000 and all(_is(_HEX32, m) for m in merges),
                  "bad merges")
            _need(_is_int(e.get("lamport")) and _is(_NAME, e.get("device_id")), "bad event lamport or device")
            if check_lines:
                self._check_line(e.get("line_id"))
            _need(isinstance(e.get("line_id"), str), "bad event line_id")
            take = out_t.get(target)
            _need(take is None or take["line_id"] == e["line_id"], "event targets a take of another line")
            out_e[e["event_id"]] = {k: e[k] for k in _EVENT_KEYS}
        _need(all(_is(_HEX32, p) for p in pruned), "bad pruned id")
        return out_t, out_e, set(pruned)

    def _blob_path(self, sha) -> Path:
        if not _is(_SHA, sha):
            raise StoreError("Invalid audio hash.")
        return self._blobs / f"{sha}.wav"

    # ---- internal helpers (caller holds the lock) ----

    def _line_events(self, line_id):
        return [e for e in self._events.values() if e["line_id"] == line_id]

    def _active(self, line_id):
        head = _winner(self._line_events(line_id))
        return head and head["target"]

    def _effective(self, line_id):
        """Take to install in the game on this PC, or None for the original audio."""
        active = self._active(line_id)
        return None if active in (None, ORIGINAL) or line_id in self._overrides else active

    def _clock(self) -> int:
        return max([x["lamport"] for x in (*self._takes.values(), *self._events.values())], default=0)

    def _add_event(self, line_id, target) -> str:
        events = self._line_events(line_id)
        head = _winner(events)
        event = {
            "event_id": uuid.uuid4().hex,
            "line_id": line_id,
            "target": target,
            "parent_event_id": head and head["event_id"],
            "merges": sorted(_leaves(events) - {head["event_id"]}) if head else [],
            "lamport": self._clock() + 1,
            "device_id": self.device_id,
        }
        self._events[event["event_id"]] = event
        self._unshared.add(event["event_id"])
        self._commit(line_id)
        return event["event_id"]

    def _commit(self, line_id):
        """Prune the line, save, then delete blobs that no take uses anymore."""
        events = self._line_events(line_id)
        dropped = []
        if len(_leaves(events)) <= 1:  # never prune a line in conflict
            head = _winner(events)
            keep = set()
            if head:  # the active take and the one undo would bring back
                keep.add(head["target"])
                parent = self._events.get(head["parent_event_id"])
                keep.add(parent and parent["target"])
            inactive = sorted((t for t in self._takes.values() if t["line_id"] == line_id and t["take_id"] not in keep),
                              key=lambda t: (t["lamport"], t["take_id"]))
            dropped = inactive[:max(0, len(inactive) - KEEP_INACTIVE)]
        for t in dropped:
            del self._takes[t["take_id"]]
            self._pruned.add(t["take_id"])
        self._save()
        self._drop_blobs({t["sha256"] for t in dropped})

    def _drop_blobs(self, shas):
        used = {t["sha256"] for t in self._takes.values()}
        if self._bak.exists():
            try:
                bak_raw = self._bak.read_bytes()
                bak_snap = json.loads(bak_raw)
                try:
                    bak_takes, _, _ = self._parse(bak_snap, check_lines=False)
                    used |= {t["sha256"] for t in bak_takes.values()}
                except (UnsupportedFormat, ValueError):
                    return
                except StoreError:
                    return
            except (OSError, ValueError):
                return
        for sha in self._present() - used:
            self._blob_path(sha).unlink(missing_ok=True)

    # ---- takes and events ----

    def add_take(self, line_id, wav: bytes, author_member_id) -> str:
        """Store a new take (raises InvalidWav for bad audio). It is not active until set_active."""
        self._check_line(line_id)
        if not _is(_NAME, author_member_id):
            raise StoreError("Invalid member id.")
        inspect_wav(wav)
        sha = hashlib.sha256(wav).hexdigest()
        with self._lock:
            path = self._blob_path(sha)
            if not path.exists():
                try:
                    atomic_write(path, wav)
                except OSError as error:
                    raise StoreError(f"Could not save the recording audio: {error}") from error
            take_id = uuid.uuid4().hex
            self._takes[take_id] = {
                "take_id": take_id, "sha256": sha, "line_id": line_id, "author_member_id": author_member_id,
                "device_id": self.device_id, "created_at": int(time.time()), "lamport": self._clock() + 1,
            }
            self._unshared.add(take_id)
            self._commit(line_id)
        return take_id

    def set_active(self, line_id, take_id_or_original) -> str:
        self._check_line(line_id)
        with self._lock:
            if take_id_or_original != ORIGINAL:
                take = self._takes.get(take_id_or_original)
                if not take or take["line_id"] != line_id:
                    raise StoreError("That recording does not exist for this line.")
            return self._add_event(line_id, take_id_or_original)

    resolve = set_active  # any new event after merging both sides resolves a conflict

    def undo(self, line_id) -> str | None:
        """New event that re-activates the target active before the current one (undo twice = redo)."""
        with self._lock:
            head = _winner(self._line_events(line_id))
            if not head:
                return None
            parent = self._events.get(head["parent_event_id"])
            target = parent["target"] if parent else ORIGINAL
            if target != ORIGINAL and target not in self._takes:
                return None
            return self._add_event(line_id, target)

    def active(self, line_id) -> str | None:
        """Group-wide active take_id, ORIGINAL, or None if never touched. The take or its blob may be missing."""
        with self._lock:
            return self._active(line_id)

    def effective(self, line_id) -> str | None:
        """Take_id to install on this PC (honors the local override), or None for the original audio."""
        with self._lock:
            return self._effective(line_id)

    def take(self, take_id) -> dict | None:
        with self._lock:
            take = self._takes.get(take_id)
            return dict(take) if take else None

    def lines(self) -> list[str]:
        """Every line with takes, events or a local override."""
        with self._lock:
            ids = {x["line_id"] for x in (*self._takes.values(), *self._events.values())}
            return sorted(ids | self._overrides)

    def history(self, line_id) -> list[dict]:
        """Takes of the line, oldest first, each with an "active" flag."""
        with self._lock:
            active = self._active(line_id)
            takes = sorted((t for t in self._takes.values() if t["line_id"] == line_id),
                           key=lambda t: (t["lamport"], t["take_id"]))
            return [dict(t, active=t["take_id"] == active) for t in takes]

    def conflicts(self) -> list[str]:
        with self._lock:
            by_line = {}
            for e in self._events.values():
                by_line.setdefault(e["line_id"], []).append(e)
            return sorted(line for line, events in by_line.items() if len(_leaves(events)) > 1)

    # ---- device-local state ----

    def set_local_override(self, line_id, use_original: bool):
        """'Use original on my PC only'. Never replicated."""
        self._check_line(line_id)
        with self._lock:
            (self._overrides.add if use_original else self._overrides.discard)(line_id)
            self._save(collection=False)

    def state(self, line_id) -> set[str]:
        """Subset of saved_locally, pending_share, pending_apply, applied_requested, conflict, local_override."""
        with self._lock:
            events = self._line_events(line_id)
            mine = [x for x in (*self._takes.values(), *events) if x["line_id"] == line_id]
            flags = set()
            if mine:
                flags.add("saved_locally")
            if any(x.get("take_id", x.get("event_id")) in self._unshared for x in mine):
                flags.add("pending_share")
            if len(_leaves(events)) > 1:
                flags.add("conflict")
            if line_id in self._overrides:
                flags.add("local_override")
            if self._effective(line_id) != self._applied.get(line_id):
                flags.add("pending_apply")
            elif line_id in self._applied:
                flags.add("applied_requested")
            return flags

    def mark_shared(self, ids):
        """Take/event ids that reached the group."""
        with self._lock:
            self._unshared -= set(ids)
            self._save(collection=False)

    def mark_applied(self):
        """Call after the game was asked to reload sounds with the current effective targets."""
        with self._lock:
            ids = {x["line_id"] for x in (*self._takes.values(), *self._events.values())} | self._overrides
            self._applied = {line: self._effective(line) for line in ids}
            self._save(collection=False)

    # ---- replication ----

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(self._dump())

    def merge(self, snapshot: dict) -> list[str]:
        """Union an untrusted snapshot into the collection. Raises StoreError and changes nothing if any
        part is invalid. Returns the lines that received new takes, events or prunes."""
        takes, events, pruned = self._parse(snapshot)
        with self._lock:
            changed, dropped = set(), set()
            new_pruned = pruned - self._pruned
            for take_id in new_pruned:
                self._pruned.add(take_id)
                if take := self._takes.pop(take_id, None):
                    changed.add(take["line_id"])
                    dropped.add(take["sha256"])
            for take_id, take in takes.items():
                if take_id not in self._takes and take_id not in self._pruned:
                    self._takes[take_id] = take  # an existing id keeps the local copy
                    changed.add(take["line_id"])
            for event_id, event in events.items():
                if event_id not in self._events:
                    self._events[event_id] = event
                    changed.add(event["line_id"])
            if changed or new_pruned:
                self._save()
                self._drop_blobs(dropped)
            return sorted(changed)

    # ---- blobs ----

    def blob(self, sha) -> bytes:
        """Audio bytes. Raises KeyError if missing, StoreError if sha is malformed."""
        try:
            return self._blob_path(sha).read_bytes()
        except FileNotFoundError:
            raise KeyError(sha) from None

    def has_blob(self, sha) -> bool:
        return _is(_SHA, sha) and self._blob_path(sha).exists()

    def missing_blobs(self) -> list[str]:
        with self._lock:
            return sorted({t["sha256"] for t in self._takes.values()} - self._present())

    def _present(self) -> set:
        out = set()
        for p in self._blobs.glob("*.wav"):
            if p.is_symlink() or not p.is_file():
                continue
            if _SHA.fullmatch(p.stem):
                out.add(p.stem)
        return out

    def put_blob(self, data: bytes) -> str:
        """Store downloaded audio (raises InvalidWav). Returns its sha256; callers must compare it with
        the hash they asked for. Refuses audio that no take uses."""
        inspect_wav(data)
        sha = hashlib.sha256(data).hexdigest()
        with self._lock:
            if not any(t["sha256"] == sha for t in self._takes.values()):
                raise StoreError("No recording in the collection uses this audio.")
            path = self._blob_path(sha)
            if not path.exists():
                atomic_write(path, data)
        return sha

    # ---- export / import ----

    def export_zip(self, path):
        buf = io.BytesIO()
        with self._lock, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("collection.json", self._dump())
            for sha in sorted({t["sha256"] for t in self._takes.values()} & self._present()):
                z.write(self._blob_path(sha), f"blobs/{sha}.wav")
        atomic_write(Path(path), buf.getvalue())

    def import_zip(self, path) -> list[str]:
        """Merge an exported collection. The whole ZIP is checked before anything is written."""
        snap, blobs = None, {}
        seen: set[str] = set()
        total = 0
        try:
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
                if len(infos) > _MAX_ZIP_ENTRIES:
                    raise StoreError(f"ZIP has too many entries ({len(infos)} > {_MAX_ZIP_ENTRIES}).")
                for info in infos:
                    name = info.filename
                    if name in seen:
                        raise StoreError(f"Duplicate file in collection ZIP: {name!r}.")
                    seen.add(name)
                    if info.is_dir():
                        if name != "blobs/":
                            raise StoreError(f"Unexpected file in collection ZIP: {name!r}.")
                        continue
                    # Path traversal / absolute
                    if name.startswith("/") or name.startswith("\\") or ".." in Path(name).parts:
                        raise StoreError(f"Invalid path in collection ZIP: {name!r}.")
                    total += info.file_size
                    if total > _MAX_ZIP_TOTAL_BYTES:
                        raise StoreError(f"ZIP too large ({total} bytes > {_MAX_ZIP_TOTAL_BYTES}).")
                    if name == "collection.json":
                        if info.file_size > _MAX_JSON:
                            raise StoreError(f"collection.json too large ({info.file_size} bytes).")
                        snap = json.loads(z.read(info))
                    elif (m := _BLOB_ENTRY.fullmatch(name)):
                        if info.file_size > MAX_BYTES:
                            raise StoreError(f"Audio file {name!r} too large ({info.file_size} bytes).")
                        data = z.read(info)
                        inspect_wav(data)
                        if hashlib.sha256(data).hexdigest() != m[1]:
                            raise StoreError(f"Audio file {name!r} does not match its name.")
                        blobs[m[1]] = data
                    elif name != "blobs/":
                        raise StoreError(f"Unexpected file in collection ZIP: {name!r}.")
        except (OSError, ValueError, zipfile.BadZipFile, InvalidWav) as e:
            if isinstance(e, StoreError):
                raise
            raise StoreError(f"Could not read the collection ZIP: {e}") from None
        if snap is None:
            raise StoreError("The ZIP has no collection.json.")
        changed = self.merge(snap)
        for sha in set(self.missing_blobs()) & blobs.keys():
            self.put_blob(blobs[sha])
        return changed
