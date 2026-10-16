"""Structured, privacy-safe diagnostic events and the shareable support ZIP.

Every stored value is an enum, a bounded number or a validated identifier, so
passwords, paths, URLs and recordings cannot reach the logs even by mistake.
This module must not import the server, game or group modules.
"""

from __future__ import annotations

import io
import json
import platform
import re
import secrets
import sys
import threading
import time
import traceback
import zipfile
from collections import deque
from pathlib import Path

from . import __version__
from .util import InstanceLock, atomic_write


class DiagnosticsError(Exception):
    """An expected diagnostics problem with a readable message."""


SCHEMA = 1
SEGMENT_CAP = 262144
SEGMENTS = ("events.jsonl.3", "events.jsonl.2", "events.jsonl.1", "events.jsonl")  # oldest first
MAX_EVENT = 4096
RING = 100
MAX_FRAMES = 20
MAX_ZIP = 2097152
KEEP_REPORTS = 3
REPORT_RE = re.compile(r"TF2ReAudio-diagnostics-\d{8}T\d{6}Z-[0-9a-f]{6}\.zip")

COMPONENTS = {"cli", "server", "browser", "sync"}
OUTCOMES = {"start", "ok", "failed", "unsupported", "not_tested", "blocked"}
TEST_OUTCOMES = ("not_tested", "ok", "failed", "unsupported", "blocked")
STEPS = ("launch", "tf2_detection", "microphone", "record", "preview", "save", "apply", "heard_in_tf2",
         "restore", "backup_restore", "sharing")
REASONS = {"permission_denied", "device_missing", "game_closed", "write_denied", "feature_unavailable", "other"}
ACTIONS = {
    # CLI commands
    "run", "host", "doctor", "setup", "import_wav", "apply", "lines",
    # local server lifecycle and API
    "startup", "shutdown", "api", "thread", "state_change", "tf2_detection",
    # browser
    "capabilities", "js_error", "api_request", "microphone", "record", "preview", "save",
    "backup_export", "diagnostics_export", "sharing",
}
ROUTES = {
    "take", "set_active", "active", "undo", "resolve", "restore", "override", "local_override", "sync_files",
    "apply", "check_connection", "launch_options", "remove_test_mod", "restart_confirmed", "import", "export",
    "disable", "enable", "uninstall", "settings", "installs", "history", "original", "take_audio", "state",
    "group", "group_create", "group_join", "group_invite", "group_remove", "group_promote", "group_suggest",
    "group_link", "group_sync", "group_host", "other",
}
STATES = {"connected", "not_running", "not_configured", "auth_failed", "error", "solo", "hosting", "synced",
          "host_offline", "update_required"}

# Stable code -> (what happened, next useful check). Fixed English text only.
CODES = {
    "ok": ("Completed.", ""),
    "started": ("Started.", ""),
    "capabilities_detected": ("Browser capabilities were detected.", ""),
    "state_changed": ("A status shown in the app changed.", ""),
    "recording_started": ("The microphone started recording.", ""),
    "tf2_not_found": ("TF2 was not found in the Steam libraries.",
                      "Choose the Team Fortress 2 folder in Setup & settings, or pass --tf."),
    "tf2_unusable": ("A TF2 folder was found but could not be used.",
                     "Check that Steam finished installing TF2 and that tf/gameinfo.txt exists."),
    "tf2_setup_failed": ("The TF2 folder could not be opened.", "Choose the Team Fortress 2 folder again in Setup & settings."),
    "request_rejected": ("The app rejected a request as invalid.", "Repeat the step once; if it fails again, share this report."),
    "storage_error": ("The local collection could not be read or saved.",
                      "Check free disk space and that the data folder is writable."),
    "invalid_audio": ("A recording was not in the expected WAV format.", "Record again, or try another browser."),
    "group_error": ("A group action failed.", "Check the invitation or ask the group admin."),
    "sync_error": ("Synchronizing with the host failed.", "Check that the host has the app open and sharing enabled."),
    "tunnel_error": ("The sharing tunnel could not start.", "Check the internet connection and try sharing again."),
    "write_denied": ("Windows or Linux denied writing a file.",
                     "Close TF2 and any program using the TF2 folder, then retry. Check folder permissions."),
    "file_in_use": ("A file was locked by another program.", "Close TF2 or the program using the file, then retry."),
    "disk_full": ("The disk is full.", "Free some disk space, then retry."),
    "os_error": ("The operating system reported an error.", "Retry once; share this report if it repeats."),
    "vpk_error": ("TF2's voice file archive could not be read.", "Verify TF2's game files in Steam."),
    "not_found": ("A requested recording or entry was missing.", "Reload the page and retry."),
    "unexpected_error": ("The app hit an unexpected internal error.", "Share this report with the maintainer."),
    "install_failed": ("The recording was saved but TF2's files could not be updated.",
                       "Close TF2 and choose Apply again."),
    "game_closed": ("TF2 was not reachable through RCON.",
                    "Start TF2 with the launch options from Setup & settings, or restart TF2 to load changes."),
    "rcon_auth_failed": ("TF2 rejected the RCON password.", "Copy the launch options into Steam again and restart TF2."),
    "rcon_error": ("TF2 did not answer as expected.", "Restart TF2, then retry Apply."),
    "rcon_not_configured": ("The TF2 connection is not set up yet.", "Copy the launch options into Steam and restart TF2."),
    "port_unavailable": ("The local app port was in use.", "Close other copies of the app or programs using port 8440."),
    "already_running": ("Another copy of the app was already running.", "Use the existing browser tab or window."),
    "interrupted": ("The app was stopped by the user.", ""),
    "permission_denied": ("Microphone permission was denied.",
                          "Allow microphone access for http://127.0.0.1 in the browser's site settings."),
    "device_missing": ("No microphone was found.", "Connect a microphone and select it in the recorder."),
    "device_busy": ("The microphone could not be read.", "Close other apps using the microphone (Discord, games), then retry."),
    "device_constraint": ("The selected microphone did not accept the settings.", "Choose another microphone."),
    "mic_timeout": ("The microphone did not respond in time.", "Check the browser permission prompt and retry."),
    "mic_unknown": ("The microphone could not be opened.", "Check browser permissions and retry."),
    "feature_unavailable": ("This browser lacks a feature the recorder needs.", "Use a current Chrome, Edge or Firefox."),
    "decode_failed": ("The browser could not decode the recording.", "Try another browser or microphone."),
    "preview_failed": ("The browser could not play the recording.", "Check the system audio output and retry."),
    "backend_unreachable": ("The browser could not reach the local app.",
                            "Keep the launcher window open; run doctor --bundle from the launcher if the page stays offline."),
    "unexpected_js_error": ("The page hit an unexpected script error.", "Reload the page and share this report."),
    "bundle_failed": ("A diagnostic report could not be created.", "Check free disk space and retry."),
}

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")
_FUNC = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}|<[a-z]{1,20}>")
_MODULE = re.compile(r"tf2reaudio(\.[a-z_][a-z0-9_]{0,40}){0,3}")
_HEX16 = re.compile(r"[0-9a-f]{16}")
_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_VERSION = re.compile(r"[0-9A-Za-z.+-]{1,32}")
_RELEASE = re.compile(r"[0-9A-Za-z._+-]{0,64}")


def _int(low, high):
    return lambda v: type(v) is int and low <= v <= high


def _enum(values):
    return lambda v: isinstance(v, str) and v in values


def _bool(v):
    return type(v) is bool


DETAILS = {
    "route": _enum(ROUTES), "status": _int(100, 599), "count": _int(0, 10**6), "duration_ms": _int(0, 86400000),
    "written": _int(0, 10**6), "step": _enum(set(STEPS)), "reason": _enum(REASONS),
    "tf2_state": _enum(STATES), "group_state": _enum(STATES),
    "get_user_media": _bool, "media_recorder": _bool, "audio_context": _bool, "secure_context": _bool,
}
CHECKS = {
    "source": _enum({"cli", "app"}),
    "app_version": lambda v: isinstance(v, str) and bool(_VERSION.fullmatch(v)),
    "python": lambda v: isinstance(v, str) and bool(_VERSION.fullmatch(v)),
    "os_family": _enum({"windows", "linux", "macos", "other"}),
    "os_release": lambda v: isinstance(v, str) and bool(_RELEASE.fullmatch(v)),
    "browser_family": _enum({"chrome", "edge", "firefox", "safari", "other"}),
    "browser_major": _int(0, 999),
    "tf2": _enum({"ok", "not_found", "unusable", "not_configured"}),
    "rcon": _enum(STATES | {"unknown"}), "group": _enum(STATES),
    "voice_files": _int(0, 10**7), "catalog_lines": _int(0, 10**7), "pending_apply": _int(0, 10**7),
    "mod_folder": _bool, "test_mod": _bool, "collection_warning": _bool, "restart_required": _bool,
    "voices_disabled": _bool,
}


def _check_fields(values, schema, what, drop_unknown=False):
    if not isinstance(values, dict):
        raise DiagnosticsError(f"{what} must be an object.")
    clean = {}
    for key, value in values.items():
        if key not in schema:
            if drop_unknown:
                continue
            raise DiagnosticsError(f"Unknown {what} field.")
        if not schema[key](value):
            raise DiagnosticsError(f"Invalid {what} value for {key}.")
        clean[key] = value
    return clean


def _clean_error(error):
    if not isinstance(error, dict) or not isinstance(error.get("type"), str) or not _IDENT.fullmatch(error["type"]):
        raise DiagnosticsError("Invalid error details.")
    clean = {"type": error["type"]}
    for key in ("errno", "winerror"):
        if key in error:
            if not _int(-(2**31), 2**32)(error[key]):
                raise DiagnosticsError("Invalid error number.")
            clean[key] = error[key]
    frames = error.get("frames", [])
    if not isinstance(frames, list) or len(frames) > MAX_FRAMES:
        raise DiagnosticsError("Invalid stack locations.")
    for frame in frames:
        if not (isinstance(frame, list) and len(frame) == 3 and isinstance(frame[0], str) and _MODULE.fullmatch(frame[0])
                and isinstance(frame[1], str) and _FUNC.fullmatch(frame[1]) and _int(1, 10**6)(frame[2])):
            raise DiagnosticsError("Invalid stack locations.")
    if frames:
        clean["frames"] = frames
    return clean


def clean_event(event: dict, *, drop_unknown_details=False) -> dict:
    """Return the event rebuilt from validated fields only, or raise DiagnosticsError."""
    if not isinstance(event, dict):
        raise DiagnosticsError("Event must be an object.")
    checks = [("v", lambda v: v == SCHEMA), ("ts", lambda v: isinstance(v, str) and _TS.fullmatch(v)),
              ("session", lambda v: isinstance(v, str) and _HEX16.fullmatch(v)), ("seq", _int(1, 2**53)),
              ("component", _enum(COMPONENTS)), ("action", _enum(ACTIONS)), ("outcome", _enum(OUTCOMES)),
              ("code", _enum(CODES)), ("op", lambda v: v is None or (isinstance(v, str) and _HEX16.fullmatch(v)))]
    clean = {}
    for key, valid in checks:
        if not valid(event.get(key)):
            raise DiagnosticsError(f"Invalid event field: {key}.")
        clean[key] = event.get(key)
    clean["details"] = _check_fields(event.get("details", {}), DETAILS, "detail", drop_unknown_details)
    if event.get("error") is not None:
        clean["error"] = _clean_error(event["error"])
    return clean


def _encode(event) -> bytes:
    return json.dumps(event, sort_keys=True, separators=(",", ":")).encode("ascii") + b"\n"


def error_info(error: BaseException) -> dict:
    """Exception class, numeric OS error and package-relative stack locations; never the message."""
    name = type(error).__name__
    info = {"type": name if _IDENT.fullmatch(name) else "UnknownError"}
    if isinstance(error, OSError):
        if type(error.errno) is int:
            info["errno"] = error.errno
        if type(getattr(error, "winerror", None)) is int:
            info["winerror"] = error.winerror
    package = Path(__file__).resolve().parent
    frames = []
    for frame in traceback.extract_tb(error.__traceback__):
        try:
            relative = Path(frame.filename).resolve().relative_to(package)
        except (ValueError, OSError):
            continue
        module = ".".join(("tf2reaudio", *relative.with_suffix("").parts))
        if _MODULE.fullmatch(module):
            frames.append([module, frame.name if _FUNC.fullmatch(frame.name) else "<unknown>", frame.lineno or 1])
    if frames:
        info["frames"] = frames[-MAX_FRAMES:]
    return info


def error_code(error: BaseException) -> str:
    """Stable code for an exception, based on its class and OS error number only."""
    if isinstance(error, OSError):
        if error.errno == 28:
            return "disk_full"
        if getattr(error, "winerror", None) in (32, 33):
            return "file_in_use"
        if isinstance(error, PermissionError):
            return "write_denied"
        return "os_error"
    named = {"ServerError": "request_rejected", "Problem": "request_rejected", "StoreError": "storage_error",
             "InvalidWav": "invalid_audio", "GroupError": "group_error", "SyncError": "sync_error",
             "TunnelError": "tunnel_error", "VpkError": "vpk_error", "KeyError": "not_found",
             "RconNotRunning": "game_closed", "RconAuthError": "rcon_auth_failed", "RconError": "rcon_error",
             "DiagnosticsError": "bundle_failed", "KeyboardInterrupt": "interrupted"}
    for cls in type(error).__mro__:
        if cls.__name__ in named:
            return named[cls.__name__]
    return "unexpected_error"


class _State:
    """Writer shared by every recorder for one data folder in this process."""

    def __init__(self, root: Path):
        self.logs = root / "logs"
        self.lock = threading.Lock()
        self.session = secrets.token_hex(8)
        self.seq = 0
        self.ring = deque(maxlen=RING)
        self.unwritten = deque(maxlen=RING)
        self.persistence = "ok"
        self.last_errno = None
        self.rejected = 0
        self.dropped = 0

    def flush(self):
        """Write pending lines; any failure keeps them in memory. Caller holds self.lock."""
        if not self.unwritten:
            return
        try:
            # Opened per flush so no handle outlives the write (Windows cannot delete open files).
            self.logs.mkdir(parents=True, exist_ok=True)
            file_lock = InstanceLock(self.logs, "events.lock")
        except OSError as exc:
            self.persistence, self.last_errno = "degraded", exc.errno
            return
        if not file_lock.acquire():
            file_lock.close()
            self.persistence = "contended"
            return
        try:
            current = self.logs / SEGMENTS[-1]
            existing = b"" if current.is_symlink() or not current.exists() else current.read_bytes()
            data = b"".join(self.unwritten)
            if len(existing) + len(data) > SEGMENT_CAP:
                for older, newer in zip(SEGMENTS, SEGMENTS[1:]):
                    path = self.logs / newer
                    if path.exists() or path.is_symlink():
                        path.replace(self.logs / older)
                existing = b""
                while len(data) > SEGMENT_CAP:
                    data = data[data.index(b"\n") + 1:]
                    self.dropped += 1
            atomic_write(current, existing + data)
            self.unwritten.clear()
            self.persistence, self.last_errno = "ok", None
        except OSError as exc:
            self.persistence, self.last_errno = "degraded", exc.errno
        finally:
            file_lock.close()


_STATES: dict[Path, _State] = {}
_STATES_LOCK = threading.Lock()


class DiagnosticRecorder:
    def __init__(self, root: Path):
        key = Path(root).absolute()
        with _STATES_LOCK:
            self._s = _STATES.setdefault(key, _State(key))

    @property
    def session(self) -> str:
        return self._s.session

    def record(self, component: str, action: str, outcome: str, code: str, *, operation_id: str | None = None,
               details: dict | None = None, error: BaseException | None = None) -> None:
        """Store one event. Never raises: diagnostics must not break the operation being diagnosed."""
        state = self._s
        with state.lock:
            state.seq += 1
            event = {"v": SCHEMA, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "session": state.session,
                     "seq": state.seq, "component": component, "action": action, "outcome": outcome, "code": code,
                     "op": operation_id, "details": details or {}}
            try:
                if error is not None:
                    event["error"] = error_info(error)
                event = clean_event(event)
                line = _encode(event)
                if len(line) > MAX_EVENT:
                    raise DiagnosticsError("Event too large.")
            except Exception:
                state.rejected += 1
                return
            state.ring.append(event)
            state.unwritten.append(line)
            try:
                state.flush()
            except Exception:
                state.persistence = "degraded"

    def snapshot(self) -> dict:
        state = self._s
        with state.lock:
            try:
                state.flush()
            except Exception:
                state.persistence = "degraded"
            ring = list(state.ring)
            status = {"persistence": state.persistence, "last_errno": state.last_errno, "rejected": state.rejected,
                      "dropped": state.dropped, "unwritten": len(state.unwritten)}
        events, omitted_events, omitted_segments = {}, 0, 0
        for name in SEGMENTS:
            path = state.logs / name
            try:
                if not path.exists() and not path.is_symlink():
                    continue
                if path.is_symlink() or not path.is_file() or path.stat().st_size > SEGMENT_CAP:
                    omitted_segments += 1
                    continue
                raw = path.read_bytes()
            except OSError:
                omitted_segments += 1
                continue
            lines = raw.split(b"\n")
            omitted_events += lines.pop() != b""  # a final line without newline is incomplete
            for line in lines:
                try:
                    if len(line) >= MAX_EVENT:
                        raise DiagnosticsError("oversized")
                    event = clean_event(json.loads(line))
                except (ValueError, DiagnosticsError):
                    omitted_events += 1
                    continue
                events[(event["session"], event["seq"])] = event
        for event in ring:
            events.setdefault((event["session"], event["seq"]), event)
        ordered = sorted(events.values(), key=lambda e: (e["ts"], e["session"], e["seq"]))
        return {"session": state.session, "events": ordered, "omitted_events": omitted_events,
                "omitted_segments": omitted_segments, **status}


def base_checks(source: str) -> dict:
    os_family = {"win32": "windows", "linux": "linux", "darwin": "macos"}.get(sys.platform, "other")
    release = platform.release()
    return {"source": source, "app_version": __version__, "python": platform.python_version(), "os_family": os_family,
            "os_release": release if _RELEASE.fullmatch(release) else ""}


def bundle_name() -> str:
    return f"TF2ReAudio-diagnostics-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{secrets.token_hex(3)}.zip"


def clean_test_results(test_results) -> list[dict]:
    """Validate tester-entered outcomes and fill every unobserved step with not_tested."""
    if not isinstance(test_results, list) or len(test_results) > len(STEPS):
        raise DiagnosticsError(f"test_results must be a list of at most {len(STEPS)} entries.")
    given = {}
    for item in test_results:
        if not isinstance(item, dict) or set(item) - {"step", "outcome", "reason"}:
            raise DiagnosticsError("Each test result needs step, outcome and an optional reason.")
        step, outcome, reason = item.get("step"), item.get("outcome"), item.get("reason")
        if (not isinstance(step, str) or step not in STEPS or step in given
                or not isinstance(outcome, str) or outcome not in TEST_OUTCOMES
                or (reason is not None and (not isinstance(reason, str) or reason not in REASONS))):
            raise DiagnosticsError("Invalid or repeated test result.")
        given[step] = {"step": step, "outcome": outcome, "source": "tester", **({"reason": reason} if reason else {})}
    return [given.get(step, {"step": step, "outcome": "not_tested", "source": "default"}) for step in STEPS]


def _summary(created, checks, events, status, results) -> str:
    lines = ["TF2 Re-Audio diagnostic report", f"Created (UTC): {created}", ""]
    lines += [f"{key}: {str(value).lower() if type(value) is bool else value}" for key, value in checks.items()]
    lines.append("")
    if status["persistence"] == "ok":
        lines.append("Diagnostic storage: ok")
    else:
        errno = f", errno {status['last_errno']}" if status["last_errno"] is not None else ""
        lines.append(f"Diagnostic storage: {status['persistence']}{errno} (some events exist only in memory)")
    lost = status["omitted_events"] + status["dropped"] + status["rejected"]
    lines.append(f"Events included: {len(events)}; omitted or unreadable: {lost}; "
                 f"unreadable log files: {status['omitted_segments']}")
    failures = [e for e in events if e["outcome"] in ("failed", "unsupported", "blocked")]
    lines += ["", "Last problem:"]
    if failures:
        last = failures[-1]
        what, check = CODES[last["code"]]
        error = last.get("error", {})
        number = "".join(f", {k} {error[k]}" for k in ("errno", "winerror") if k in error)
        lines += [f"  {last['ts']}  {last['component']}/{last['action']}: {last['outcome']} ({last['code']}"
                  f"{', ' + error['type'] if error else ''}{number})", f"  What happened: {what}"]
        if check:
            lines.append(f"  Next check: {check}")
        lines += ["", "Recent problems (newest last):"]
        lines += [f"  {e['ts']}  {e['component']}/{e['action']}: {e['outcome']} ({e['code']})" for e in failures[-10:]]
    else:
        lines.append("  No failed operation was recorded.")
    lines += ["", "Tester results (manual confirmation; not_tested means nobody confirmed it):"]
    lines += [f"  {r['step']}: {r['outcome']}{' (' + r['reason'] + ')' if 'reason' in r else ''}" for r in results]
    lines += ["", "This report contains no recordings, passwords, invitation codes, links, IP addresses, names or",
              "folder paths. Sending an apply request does not prove a voice was heard in TF2.", ""]
    return "\n".join(lines)


def build_bundle(snapshot: dict, checks: dict, test_results: list[dict]) -> bytes:
    """The bounded support ZIP, built in memory from revalidated data only."""
    checks = _check_fields(checks, CHECKS, "check")
    results = clean_test_results(test_results)
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("events"), list):
        raise DiagnosticsError("Invalid diagnostics snapshot.")
    status = {"persistence": snapshot.get("persistence") if snapshot.get("persistence") in ("ok", "degraded", "contended") else "degraded",
              "last_errno": snapshot.get("last_errno") if _int(-(2**31), 2**32)(snapshot.get("last_errno")) else None}
    for key in ("omitted_events", "omitted_segments", "rejected", "dropped", "unwritten"):
        status[key] = snapshot.get(key) if _int(0, 2**31)(snapshot.get(key)) else 0
    events = []
    for event in snapshot["events"]:
        try:
            events.append(clean_event(event))
        except DiagnosticsError:
            status["omitted_events"] += 1
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    while True:
        files = {
            "summary.txt": _summary(created, checks, events, status, results).encode("utf-8"),
            "manifest.json": json.dumps({"schema": SCHEMA, "created": created, "events": len(events), **status,
                                         "files": ["summary.txt", "manifest.json", "events.jsonl", "test-results.json"]},
                                        indent=1, sort_keys=True).encode("utf-8") + b"\n",
            "events.jsonl": b"".join(_encode(e) for e in events),
            "test-results.json": json.dumps({"checks": checks, "results": results}, indent=1).encode("utf-8") + b"\n",
        }
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(zipfile.ZipInfo(name, date_time=time.gmtime()[:6]), data, zipfile.ZIP_DEFLATED)
        data = buffer.getvalue()
        if len(data) <= MAX_ZIP:
            return data
        if not events:
            raise DiagnosticsError("The diagnostic report is too large.")
        cut = max(1, len(events) // 10)  # drop the oldest events and say so
        events = events[cut:]
        status["omitted_events"] += cut


def save_bundle(root: Path, data: bytes) -> Path:
    """Save under root/reports, keeping only the newest three generated reports."""
    reports = Path(root) / "reports"
    try:
        reports.mkdir(parents=True, exist_ok=True)
        path = reports / bundle_name()
        atomic_write(path, data)
        # The random filename suffix does not indicate creation order. Always
        # preserve the report returned to the caller, including timestamp ties.
        older = sorted((p for p in reports.iterdir() if p != path and REPORT_RE.fullmatch(p.name)
                        and p.is_file() and not p.is_symlink()), key=lambda p: (p.stat().st_mtime_ns, p.name))
        for old in older[:max(0, len(older) - (KEEP_REPORTS - 1))]:
            old.unlink(missing_ok=True)
    except OSError as exc:
        raise DiagnosticsError(f"Could not save the diagnostic report: {exc.strerror or exc.__class__.__name__}.") from None
    return path
