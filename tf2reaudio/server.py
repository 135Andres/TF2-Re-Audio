"""Local HTTP API for the TF2 Re-Audio application.

The server is deliberately small and uses only :mod:`http.server`.  It is a
local control surface for the existing CLI modules; collaboration endpoints
are added after the group/sync tasks.  No request is allowed to change state
without the local CSRF header, and the Host header is checked to avoid DNS
rebinding attacks.
"""

from __future__ import annotations

import base64
import binascii
import http.client
import io
import json
import mimetypes
import os
import re
import secrets
import sys
import tempfile
import threading
import time
import urllib.parse
import webbrowser
import zipfile
from collections import deque
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import PROTOCOL_VERSION, __version__, catalog, steam
from .audio import InvalidWav, MAX_BYTES, inspect_wav
from .diagnostics import (ROUTES, STATES, DiagnosticRecorder, DiagnosticsError, base_checks, build_bundle,
                          bundle_name, clean_event, error_code)
from .game import Game
from .group import Group, GroupError
from .sync import GroupStore, SyncServer, Syncer, SyncError, check_host, join_group
from .tunnel import Tunnel, TunnelError
from .store import ORIGINAL, Store, StoreError
from .util import InstanceLock, atomic_write, data_dir, set_low_priority
from .vpk import VpkError, VpkIndex


class ServerError(Exception):
    """An expected local API problem suitable for showing to the user."""


MAX_REQUEST = 64 * 1024
MAX_TAKE_JSON = ((MAX_BYTES + 2) // 3) * 4 + MAX_REQUEST
MAX_ZIP = 64 * 1024 * 1024
MAX_ZIP_EXPANDED = 128 * 1024 * 1024
MAX_DIAG_EVENT = 8192
DIAG_PER_MINUTE = 30
CSRF_HEADER = "X-TF2RA"
# A 200 response can still describe a failed operation.
RESULT_CODES = {"not_running": "game_closed", "auth_failed": "rcon_auth_failed", "error": "rcon_error",
                "install_failed": "install_failed", "not_configured": "rcon_not_configured"}
# PLAN §13.3: CSP for the local UI. base requirement is:
#   default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'
# Added directive:
#   media-src 'self' blob: — audio previews in recorder.js and line previews
#   use URL.createObjectURL(blob) which produces blob: URLs. With only
#   default-src 'self', those <audio src="blob:..."> would be blocked because
#   media-src falls back to default-src. Adding blob: here keeps the page
#   locked to same-origin scripts/styles/images while allowing local audio
#   blobs. No other sources (data:, https:, unsafe-inline) are allowed.
CSP_VALUE = "default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; media-src 'self' blob:"


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _read_json(raw: bytes) -> dict:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ServerError("Request body is not valid JSON.") from exc
    if not isinstance(value, dict):
        raise ServerError("Request body must be a JSON object.")
    return value


def _device_id(root: Path) -> str:
    """Return the stable device id without importing the CLI module."""
    path = root / "settings.json"
    try:
        settings = json.loads(path.read_bytes())
    except (OSError, ValueError):
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    value = settings.get("device_id")
    if not isinstance(value, str) or len(value) != 32 or any(c not in "0123456789abcdef" for c in value):
        import uuid

        value = uuid.uuid4().hex
        settings["device_id"] = value
        atomic_write(path, json.dumps(settings, sort_keys=True, indent=1).encode("utf-8"))
    return value


class LocalApp:
    """Application state shared by the local HTTP handler and its requests."""

    def __init__(self, tf_dir: Path | None = None, root: Path | None = None):
        self.root = Path(root) if root else data_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.diag = DiagnosticRecorder(self.root)
        self._observed = {}
        self._diag_lock = threading.Lock()
        self._diag_times = deque()
        self._diag_repeats = {}
        self._lock = threading.RLock()
        self.game: Game | None = None
        self.catalog = None
        self.vpk: VpkIndex | None = None
        self.setup_error: str | None = None
        self.tf_dir: Path | None = None
        self.connection = "not_configured"
        self.group = None
        self.group_error = None
        self.syncer = None
        self.sync_host = None
        self.tunnel = None
        try:
            self.group = Group.load(self.root)
        except GroupError as exc:
            self.group_error = str(exc)
        chosen = tf_dir or self._saved_tf_dir()
        if chosen is not None:
            try:
                self.configure_tf(chosen)
            except (ServerError, OSError, VpkError, StoreError) as exc:
                self.setup_error = str(exc)
        else:
            self._try_auto_detect()
        code = "ok" if self.game else "tf2_setup_failed" if chosen is not None else "tf2_not_found"
        self.diag.record("server", "tf2_detection", "ok" if self.game else "failed", code)
        self.start_syncer()

    def browser_event(self, payload) -> int:
        """Record one validated browser event; returns the HTTP status (204 or 429)."""
        if set(payload) - {"action", "outcome", "code", "details"}:
            raise ServerError("Unknown diagnostic event field.")
        try:
            event = clean_event({"v": 1, "ts": "2000-01-01T00:00:00Z", "session": "0" * 16, "seq": 1,
                                 "component": "browser", "action": payload.get("action"), "op": None,
                                 "outcome": payload.get("outcome"), "code": payload.get("code"),
                                 "details": payload.get("details", {})}, drop_unknown_details=True)
        except DiagnosticsError as exc:
            raise ServerError(str(exc)) from None
        key, now = (event["action"], event["outcome"], event["code"]), time.monotonic()
        with self._diag_lock:
            first, repeats = self._diag_repeats.get(key, (None, 0))
            if first is not None and now - first < 60:
                self._diag_repeats[key] = (first, repeats + 1)  # aggregated into the next recorded copy
                return HTTPStatus.NO_CONTENT
            while self._diag_times and now - self._diag_times[0] >= 60:
                self._diag_times.popleft()
            if len(self._diag_times) >= DIAG_PER_MINUTE:
                return HTTPStatus.TOO_MANY_REQUESTS
            self._diag_times.append(now)
            self._diag_repeats[key] = (now, 0)
        details = dict(event["details"], **({"count": min(repeats, 10**6)} if repeats else {}))
        self.diag.record("browser", *key, details=details)
        return HTTPStatus.NO_CONTENT

    def diagnostic_checks(self, user_agent: str) -> dict:
        """Path-free status for the support bundle; never repairs, applies or connects."""
        checks = base_checks("app")
        for family, pattern in (("edge", r"Edg/(\d+)"), ("firefox", r"Firefox/(\d+)"), ("chrome", r"Chrome/(\d+)"),
                                ("safari", r"Version/(\d+)[^ ]* .*Safari/")):
            match = re.search(pattern, user_agent)
            if match:
                checks.update(browser_family=family, browser_major=min(int(match.group(1)), 999))
                break
        else:
            checks["browser_family"] = "other"
        with self._lock:
            group = self.group_json()["status"]
            if group in STATES:
                checks["group"] = group
            checks["tf2"] = "ok" if self.game else "not_configured"
            if self.game:
                try:
                    game = self.game
                    checks.update(rcon=self.connection if self.connection in STATES else "unknown",
                                  catalog_lines=sum(len(self.catalog.lines(c)) for c in catalog.CLASSES),
                                  pending_apply=self.pending_apply(), mod_folder=game.mod.exists(),
                                  test_mod=game.test_mod_present(), voices_disabled=game.disabled_dir.is_dir(),
                                  collection_warning=bool(game.store.warning),
                                  restart_required=bool(game.settings.get("restart_required", False)))
                except (OSError, StoreError, ServerError):
                    pass
        return checks

    def _observe(self, value: dict) -> dict:
        """Record status transitions once, not every poll."""
        current = {"tf2_state": value["tf2"], "group_state": value["group"]}
        changed = {k: v for k, v in current.items() if self._observed.get(k) != v and v in STATES}
        self._observed = current
        if changed:
            self.diag.record("server", "state_change", "ok", "state_changed", details=changed)
        return value

    def group_json(self):
        if self.group is None:
            return {"status": "solo", "error": self.group_error, "existing_recordings":
                    len(self.game.store.snapshot()["takes"]) if self.game else 0}
        group = self.group
        hosting = bool(self.sync_host and self.tunnel and self.tunnel.running)
        return {"status": "hosting" if hosting else self.syncer.status if self.syncer else "host_offline",
                "error": self.syncer.error if self.syncer else self.group_error,
                "group_id": group.group_id, "name": group.name, "member_id": group.member_id,
                "is_admin": group.is_admin(group.member_id), "members": group.members(),
                "suggested_voices": group.suggested_voices(), "hosting": hosting,
                "url": group.known_hosts()[0] if group.known_hosts() else None,
                "last_sync": self.syncer.last_sync if self.syncer else None,
                "pending_share": sum("pending_share" in self.game.store.state(line)
                                     for line in self.game.store.lines()) if self.game and not self.sync_host else 0,
                "warning": group.warning}

    def start_syncer(self):
        if self.group and self.game and self.group.known_hosts() and not self.syncer and not self.sync_host:
            self.syncer = Syncer(self.game.store, self.group, self.group.known_hosts()[0], self.group.token,
                                 lock=self._lock)
            self.syncer.start()

    def close_group(self):
        # Called outside the app lock on final shutdown.
        if self.syncer:
            self.syncer.stop()
            self.syncer = None
        if self.tunnel:
            self.tunnel.stop()
            self.tunnel = None
        if self.sync_host:
            self.sync_host.stop()
            self.sync_host = None

    def _prepare_group(self, payload):
        game = self.require_game()
        if self.group is not None or (self.root / "group.json").exists():
            raise ServerError("This installation already belongs to a group.")
        snapshot = game.store.snapshot()
        if (snapshot["takes"] or snapshot["events"]) and payload.get("share_existing") is not True:
            raise ServerError("Choose whether to share your existing recordings before joining or creating a group.")
        if (any(t["device_id"] != game.store.device_id or t["author_member_id"] != "local" for t in snapshot["takes"])
                or any(e["device_id"] != game.store.device_id for e in snapshot["events"])):
            raise ServerError("This collection contains imported authors. Export it and use a fresh installation data folder for this group.")
        if snapshot["takes"] or snapshot["events"]:
            game.store.export_zip(self.root / ("solo-before-group-" + secrets.token_hex(6) + ".zip"))
        return game

    def group_action(self, action, payload):
        if action in ("create", "join"):
            game = self._prepare_group(payload)
            if action == "create":
                self.group = Group.create(payload.get("name"), payload.get("display_name"),
                                          root=self.root, device_id=game.store.device_id)
            else:
                self.group = join_group(payload.get("url"), payload.get("code"), payload.get("display_name"),
                                        game.store.device_id, self.root)
            game.store = GroupStore(game.store.root, game.store.device_id, game.catalog)
            self.start_syncer()
            return self.group_json()
        if not self.group:
            raise ServerError("Create or join a group first.")
        group = self.group
        if action == "invite":
            return {"code": group.create_invite(), "url": self.group_json()["url"]}
        if action in ("remove", "promote", "suggest"):
            if action == "remove":
                group.remove_member(payload.get("member_id"))
            elif action == "promote":
                group.promote(payload.get("member_id"))
            else:
                group.set_suggested_voice(payload.get("class"), payload.get("member_id"))
        elif action == "link":
            check_host(payload.get("url"), group.group_id)
            if self.syncer:
                self.syncer.stop()
                self.syncer = None
            group.set_host_url(payload["url"])
            self.start_syncer()
        elif action == "sync":
            if self.sync_host:
                return {"pushed": 0, "pulled": 0, "conflicts": len(self.game.store.conflicts()), "error": None}
            self.start_syncer()
            if not self.syncer:
                raise ServerError("Enter the host link first.")
            return asdict(self.syncer.run_once())
        elif action == "host":
            enabled = payload.get("enabled")
            if type(enabled) is not bool:
                raise ServerError("enabled must be true or false.")
            if enabled and group.verify_token(group.token) is None:
                raise ServerError("Your group access is no longer valid.")
            if enabled and self.sync_host is None:
                if self.game.store.missing_blobs():
                    raise ServerError("Download missing recordings before hosting.")
                if self.syncer:
                    self.syncer.stop()
                    self.syncer = None
                host = SyncServer(self.game.store, group, lock=self._lock).start()
                tunnel = Tunnel(host.port)
                try:
                    url = tunnel.start()
                    group.set_host_url(url)
                except BaseException:
                    tunnel.stop()
                    host.stop()
                    raise
                self.sync_host, self.tunnel = host, tunnel
            elif not enabled:
                self.close_group()
                self.start_syncer()
        else:
            raise ServerError("Unknown group action.")
        return self.group_json()

    def _saved_tf_dir(self) -> Path | None:
        try:
            settings = json.loads((self.root / "settings.json").read_bytes())
            value = settings.get("tf_path") if isinstance(settings, dict) else None
        except (OSError, ValueError):
            value = None
        return Path(value) if isinstance(value, str) and value else None

    def _try_auto_detect(self) -> None:
        try:
            installs = steam.find_installs()
            for candidate in installs:
                check = steam.check_install(candidate)
                if check.ok:
                    self.configure_tf(check.tf)
                    return
            self.setup_error = "TF2 was not found in your Steam libraries."
        except (ServerError, OSError, VpkError, StoreError) as exc:
            self.setup_error = str(exc)

    def _open(self, tf: Path) -> None:
        tf = Path(tf)
        check = steam.check_install(tf)
        if not check.ok or check.tf is None:
            raise ServerError(check.detail)
        tf = check.tf
        archive = VpkIndex(tf / steam.VO_VPK)
        cat = catalog.build(archive.names())
        store_type = GroupStore if self.group else Store
        store = store_type(self.root / "collection", _device_id(self.root), catalog=cat)
        self.game = Game(tf, store, cat, data=self.root)
        self.catalog = cat
        self.vpk = archive
        self.tf_dir = tf
        self.setup_error = None

    def configure_tf(self, tf: Path) -> None:
        with self._lock:
            if self.group and self.game:
                raise ServerError("Keep the current TF2 folder while connected to this group.")
            if self.tf_dir and Path(tf).resolve() not in {self.tf_dir.resolve(), self.tf_dir.parent.resolve()}:
                if self.game.mod.exists() or self.game.disabled_dir.exists():
                    raise ServerError("Uninstall the current mod before switching TF2 folders. Keep your collection.")
            self._open(Path(tf))
            self.save_settings(tf_path=str(self.tf_dir))
            self.start_syncer()

    def save_settings(self, **changes):
        game = self.require_game()
        updated = dict(game.settings, **changes)
        atomic_write(self.root / "settings.json", _json_bytes(updated))
        game.settings = updated

    def sync_files(self) -> dict:
        """Installation can fail after a successful save; report both outcomes."""
        game = self.require_game()
        created = not game.mod.exists()
        try:
            written = game.sync_files()
            if created and game.mod.exists():
                self.save_settings(restart_required=True)
            return {"written": written, "install_error": None}
        except OSError:
            return {"written": 0, "install_error":
                    "Your recording is saved. Could not install all files; close TF2 and retry Apply."}

    def line_state(self, line_id):
        game = self.require_game()
        return sorted(game.store.state(line_id) - (set() if self.group and not self.sync_host else {"pending_share"}))

    def require_game(self) -> Game:
        if self.game is None:
            raise ServerError(self.setup_error or "TF2 is not configured. Choose the Team Fortress 2 folder first.")
        return self.game

    def line(self, line_id: str):
        game = self.require_game()
        if not isinstance(line_id, str) or not 0 < len(line_id) <= 200:
            raise ServerError("A valid line_id is required.")
        base = line_id.partition("#")[0]
        try:
            return game.catalog.line(base)
        except KeyError:
            raise ServerError(f"Unknown voice line: {line_id!r}.") from None

    def _line_file(self, line_id: str) -> str:
        line = self.line(line_id)
        _, sep, variant = line_id.partition("#")
        if not sep:
            return line.files[0]
        if not re.fullmatch(r"[0-9]{2}", variant) or int(variant) < 1:
            raise ServerError(f"Unknown voice line variant: {line_id!r}.")
        stems = list(dict.fromkeys(path.rsplit(".", 1)[0] for path in line.files))
        index = int(variant) - 1
        if index >= len(stems):
            raise ServerError(f"Unknown voice line variant: {line_id!r}.")
        for path in line.files:
            if path.rsplit(".", 1)[0] == stems[index]:
                return path
        raise ServerError(f"Unknown voice line variant: {line_id!r}.")

    def line_json(self, line) -> dict:
        game = self.require_game()
        stems = list(dict.fromkeys(path.rsplit(".", 1)[0] for path in line.files))
        variants = []
        for index, stem in enumerate(stems, 1):
            line_id = f"{line.id}#{index:02}"
            active = game.store.active(line_id)
            flags = self.line_state(line_id)
            inherited = active is None and "local_override" not in flags
            variants.append({
                "id": line_id,
                "label": line.label,
                "files": [path for path in line.files if path.rsplit(".", 1)[0] == stem],
                "active": active,
                "effective": game.store.effective(line.id if inherited else line_id),
                "state": flags,
                "inherited": inherited,
            })
        return {
            "id": line.id,
            "class": line.cls,
            "label": line.label,
            "category": line.category,
            "files": list(line.files),
            "active": game.store.active(line.id),
            "effective": game.store.effective(line.id),
            "state": self.line_state(line.id),
            "variants": variants,
            "has_recording": any(variant["effective"] for variant in variants),
        }

    def pending_apply(self):
        game = self.require_game()
        # Incoming metadata has not been installed yet, so Game's file counter
        # alone cannot expose the manual Apply action for received recordings.
        pending_lines = sum("pending_apply" in game.store.state(line) for line in game.store.lines())
        return max(game.pending_apply(), pending_lines)

    def state_json(self) -> dict:
        with self._lock:
            if self.game is None:
                return self._observe({
                    "app_version": __version__,
                    "protocol_version": PROTOCOL_VERSION,
                    "tf2": "not_configured",
                    "group": self.group_json()["status"],
                    "collaboration": self.group_json(),
                    "setup_error": self.setup_error,
                    "tf_path": None,
                    "pending_apply": 0,
                })
            game = self.game
            return self._observe({
                "app_version": __version__,
                "protocol_version": PROTOCOL_VERSION,
                "tf2": self.connection,
                "group": self.group_json()["status"],
                    "collaboration": self.group_json(),
                "setup_error": self.setup_error,
                "tf_path": str(game.tf),
                "pending_apply": self.pending_apply(),
                "restart_required": game.settings.get("restart_required", False),
                "disabled": game.disabled_dir.is_dir(),
                "collection_warning": game.store.warning,
                "test_mod_present": game.test_mod_present(),
                "conflicts": game.store.conflicts(),
            })

    def settings_json(self) -> dict:
        game = self.game
        settings = game.settings if game else {}
        return {
            "tf_path": str(self.tf_dir) if self.tf_dir else None,
            "rcon_port": settings.get("rcon_port"),
            "rcon_configured": bool(game and settings.get("rcon_ok_once")),
        }


class _LocalHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can bind an address already used by another app.
    allow_reuse_address = sys.platform != "win32"


class _Handler(BaseHTTPRequestHandler):
    server_version = "TF2ReAudio/0.1"
    protocol_version = "HTTP/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    @property
    def app(self) -> LocalApp:
        return self.server.app  # type: ignore[attr-defined]

    @property
    def local_server(self) -> "LocalServer":
        return self.server.owner  # type: ignore[attr-defined]

    def log_message(self, format, *args):  # noqa: A003 - BaseHTTPRequestHandler API
        return

    def _host_ok(self) -> bool:
        hosts = self.headers.get_all("Host", [])
        return len(hosts) == 1 and hosts[0] in {
            f"127.0.0.1:{self.local_server.port}", f"localhost:{self.local_server.port}"}

    def end_headers(self):  # noqa: N802 - BaseHTTPRequestHandler API
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", CSP_VALUE)
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def _send(self, status: int, body: bytes = b"", content_type: str = "application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, status: int, value: dict):
        self._result = value
        self._send(status, _json_bytes(value))

    def _error(self, status: int, message: str):
        self._json(status, {"error": message})

    def _read_body(self, limit=MAX_REQUEST) -> bytes:
        if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
            raise ServerError("Use one Content-Length header and no Transfer-Encoding.")
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length) if raw_length is not None else -1
        except ValueError:
            raise ServerError("Content-Length must be a number.") from None
        if length < 0:
            raise ServerError("A Content-Length header is required.")
        if length > limit:
            raise ServerError(f"Request is too large (maximum {limit} bytes).")
        data = self.rfile.read(length)
        if len(data) != length:
            raise ServerError("The request body ended before Content-Length.")
        return data

    def _require_write(self):
        if self.headers.get(CSRF_HEADER) != "1":
            raise ServerError(f"Mutating requests require {CSRF_HEADER}: 1.")
        origin = self.headers.get("Origin")
        if origin is not None and origin != "http://" + self.headers.get("Host", ""):
            raise ServerError("Request origin must match the local app.")
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if self.command == "POST" and content_type not in {"application/json", "audio/wav", "application/octet-stream", "application/zip"}:
            raise ServerError("POST requests must use JSON, WAV, or ZIP content type.")

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._host_ok():
            self._error(HTTPStatus.BAD_REQUEST, "Invalid Host header.")
            return
        parsed = urllib.parse.urlsplit(self.path)

        def action():
            with self.app._lock:
                self._get(parsed)
        self._dispatch(parsed, action, (HTTPStatus.NOT_FOUND, "Recording audio is unavailable."))

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._host_ok():
            self._error(HTTPStatus.BAD_REQUEST, "Invalid Host header.")
            return
        parsed = urllib.parse.urlsplit(self.path)
        try:
            self._require_write()  # foreign pages must not be able to fill the logs
            if parsed.path.startswith("/api/diagnostics/"):
                self._diagnostics(parsed.path)
                return
        except ServerError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        def action():
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].lower()
            limit = MAX_REQUEST
            if parsed.path == "/api/take":
                limit = MAX_TAKE_JSON if content_type == "application/json" else MAX_BYTES
            elif parsed.path == "/api/import":
                limit = MAX_ZIP
            raw = self._read_body(limit)
            if parsed.path == "/api/group/sync":
                self._post(parsed, raw)
            else:
                with self.app._lock:
                    self._post(parsed, raw)
        self._dispatch(parsed, action, (HTTPStatus.BAD_REQUEST,
                                        "The requested recording or collection entry is unavailable."))

    def _dispatch(self, parsed, action, key_error):
        self._result, error = None, None
        try:
            action()
        except KeyError as exc:
            error, reply = exc, key_error
        except (ServerError, StoreError, InvalidWav, GroupError, SyncError, TunnelError) as exc:
            error, reply = exc, (HTTPStatus.BAD_REQUEST, str(exc))
        except (OSError, VpkError) as exc:
            error, reply = exc, (HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
        except Exception as exc:
            error, reply = exc, (HTTPStatus.INTERNAL_SERVER_ERROR,
                                 str(exc) or "The local app could not complete that request.")
        if error is None and self.command == "GET":
            return  # reads and polls are not operations
        path = parsed.path
        route = ("take_audio" if path.startswith("/api/take/") else "original" if path.startswith("/api/original/")
                 else path.removeprefix("/api/").replace("/", "_").replace("-", "_"))
        details = {"route": route if route in ROUTES else "other"}
        if error is not None:
            self.app.diag.record("server", "api", "failed", error_code(error), details=details, error=error)
            self._error(*reply)  # after recording, so the log already explains the reply
            return
        result = self._result if isinstance(self._result, dict) else {}
        code = ("install_failed" if result.get("install_error") else RESULT_CODES.get(result.get("result"))
                or ("sync_error" if result.get("error") else None))
        self.app.diag.record("server", "api", "failed" if code else "ok", code or "ok", details=details)

    def _diagnostics(self, path):
        if self.headers.get("Content-Type", "").split(";", 1)[0].lower() != "application/json":
            raise ServerError("Diagnostic requests must use JSON.")
        if path == "/api/diagnostics/event":
            length = self.headers.get("Content-Length", "")
            if length.isdigit() and int(length) > MAX_DIAG_EVENT:
                self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Diagnostic event is too large.")
                return
            self._send(self.app.browser_event(_read_json(self._read_body(MAX_DIAG_EVENT))))
            return
        if path != "/api/diagnostics/export":
            raise ServerError("Unknown API endpoint.")
        payload = _read_json(self._read_body())
        if set(payload) - {"test_results"}:
            raise ServerError("Only test_results can be sent with a diagnostic export.")
        try:
            data = build_bundle(self.app.diag.snapshot(), self.app.diagnostic_checks(self.headers.get("User-Agent", "")),
                                payload.get("test_results", []))
        except DiagnosticsError as exc:
            raise ServerError(str(exc)) from None
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f'attachment; filename="{bundle_name()}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _get(self, parsed):
        path = parsed.path
        if path == "/api/ping":
            self._json(HTTPStatus.OK, {"ok": True, "app": "tf2reaudio", "instance_id": self.local_server.instance_id,
                                      "app_version": __version__, "protocol_version": PROTOCOL_VERSION})
            return
        if path == "/api/installs":
            checks = []
            for tf in steam.find_installs():
                check = steam.check_install(tf)
                checks.append({"tf_path": str(check.tf or tf), "ok": check.ok,
                               "problem": check.problem, "detail": check.detail})
            self._json(200, {"installs": checks})
            return
        if path == "/api/history":
            line_id = urllib.parse.parse_qs(parsed.query).get("line_id", [None])[0]
            self.app._line_file(line_id)
            self._json(200, {"takes": self.app.game.store.history(line_id), "state": self.app.line_state(line_id)})
            return
        if path == "/api/state":
            with self.app._lock:
                self._json(HTTPStatus.OK, self.app.state_json())
            return
        if path == "/api/group":
            self._json(200, self.app.group_json())
            return
        if path == "/api/settings":
            with self.app._lock:
                self._json(HTTPStatus.OK, self.app.settings_json())
            return
        if path == "/api/classes":
            with self.app._lock:
                if self.app.catalog is None:
                    self._json(HTTPStatus.OK, {"classes": [{"id": cls, "name": cls.title(), "lines": 0,
                                                           "completed": 0} for cls in catalog.CLASSES], "configured": False})
                    return
                result = []
                for cls in catalog.CLASSES:
                    lines = self.app.catalog.lines(cls)
                    result.append({"id": cls, "name": cls.title(), "lines": len(lines),
                                   "completed": sum(self.app.line_json(line)["has_recording"] for line in lines)})
                self._json(HTTPStatus.OK, {"classes": result, "configured": True})
            return
        if path == "/api/lines":
            query = urllib.parse.parse_qs(parsed.query)
            cls = query.get("class", [None])[0]
            category = query.get("category", [None])[0]
            with self.app._lock:
                if self.app.catalog is None:
                    raise ServerError("TF2 is not configured.")
                if cls not in catalog.CLASSES:
                    raise ServerError("A valid class is required.")
                if category not in {None, "voice_menu", "pain_death", "domination", "other"}:
                    raise ServerError("Unknown category.")
                lines = self.app.catalog.lines(cls, category)
                self._json(HTTPStatus.OK, {"lines": [self.app.line_json(line) for line in lines]})
            return
        if path == "/api/conflicts":
            game = self.app.require_game()
            self._json(HTTPStatus.OK, {"lines": game.store.conflicts()})
            return
        if path == "/api/export":
            game = self.app.require_game()
            with tempfile.TemporaryDirectory(dir=self.app.root) as temp:
                target = Path(temp) / "collection.zip"
                game.store.export_zip(target)
                data = target.read_bytes()
            self._send(HTTPStatus.OK, data, "application/zip")
            return
        if path.startswith("/api/original/"):
            line_id = urllib.parse.unquote(path.removeprefix("/api/original/"))
            source = self.app._line_file(line_id)
            data = self.app.vpk.read(source)
            content_type = "audio/wav" if source.endswith(".wav") else "audio/mpeg"
            self._send(HTTPStatus.OK, data, content_type)
            return
        if path.startswith("/api/take/"):
            tail = path.removeprefix("/api/take/")
            audio = tail.endswith("/audio")
            metadata = tail.endswith("/metadata")
            take_id = tail.removesuffix("/audio").removesuffix("/metadata")
            game = self.app.require_game()
            take = game.store.take(take_id)
            if not take:
                raise ServerError("Recording not found.")
            if audio:
                self._send(HTTPStatus.OK, game.store.blob(take["sha256"]), "audio/wav")
            else:  # Plain /take/id and /take/id/metadata both return metadata.
                take["state"] = self.app.line_state(take["line_id"])
                self._json(HTTPStatus.OK, take)
            return
        if path == "/":
            if not (self.local_server.static_dir / "index.html").is_file():
                self._send(200, b'<!doctype html><html lang="en"><meta charset="utf-8">'
                           b'<title>TF2 Re-Audio</title><h1>TF2 Re-Audio</h1>'
                           b'<p>The local API is running, but the web interface files were not found in the package.</p>'
                           b'<p><a href="/api/state">View status</a></p></html>', "text/html; charset=utf-8")
                return
            self._static("index.html")
            return
        self._static(path.removeprefix("/"))

    def _static(self, relative: str):
        root = self.local_server.static_dir
        relative = urllib.parse.unquote(relative)
        relative_path = Path(relative)
        if not relative or "\x00" in relative or "\\" in relative or relative_path.is_absolute() or ".." in relative_path.parts:
            self._error(HTTPStatus.NOT_FOUND, "Not found.")
            return
        path = (root / relative_path).resolve()
        if not path.is_file() or not path.is_relative_to(root.resolve()):
            self._error(HTTPStatus.NOT_FOUND, "Not found.")
            return
        body = path.read_bytes()
        self._send(HTTPStatus.OK, body, mimetypes.guess_type(path.name)[0] or "application/octet-stream")

    def _post(self, parsed, raw):
        path = parsed.path
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].lower()
        expected = {"/api/take": {"application/json", "audio/wav"},
                    "/api/import": {"application/zip", "application/octet-stream"}}.get(path, {"application/json"})
        if content_type not in expected:
            raise ServerError("Incorrect Content-Type for this endpoint.")
        if path.startswith("/api/group/"):
            self._json(200, self.app.group_action(path.rsplit("/", 1)[1], _read_json(raw)))
            return
        if self.app.group and (path == "/api/import" or (path == "/api/uninstall" and _read_json(raw).get("delete_collection"))):
            raise ServerError("Keep the group collection intact. Export a backup; importing or deleting a grouped collection is not supported yet.")
        if path == "/api/settings":
            payload = _read_json(raw)
            tf_path = payload.get("tf_path")
            port = payload.get("rcon_port")
            if "rcon_port" in payload and (type(port) is not int or not 1 <= port <= 65535):
                raise ServerError("rcon_port must be between 1 and 65535.")
            with self.app._lock:
                if tf_path is not None:
                    if not isinstance(tf_path, str) or not tf_path:
                        raise ServerError("tf_path must be a non-empty path.")
                    self.app.configure_tf(Path(tf_path))
                if "rcon_port" in payload:
                    self.app.save_settings(rcon_port=port, rcon_ok_once=False)
                    self.app.connection = "not_configured"
                self._json(HTTPStatus.OK, self.app.settings_json())
            return
        if path == "/api/take":
            game = self.app.require_game()
            line_id = self.headers.get("X-Line-ID")
            activation = self.headers.get("X-Activate", "1")
            if activation not in {"0", "1"}:
                raise ServerError("X-Activate must be 0 or 1.")
            activate = activation == "1"
            if content_type == "application/json":
                payload = _read_json(raw)
                line_id = payload.get("line_id", line_id)
                encoded = payload.get("wav_base64")
                if not isinstance(encoded, str):
                    raise ServerError("JSON take requests require wav_base64.")
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise ServerError("wav_base64 is invalid.") from exc
                activate = payload.get("activate", activate)
                if type(activate) is not bool:
                    raise ServerError("activate must be true or false.")
            if not isinstance(line_id, str) or not line_id:
                raise ServerError("A line_id is required.")
            info = inspect_wav(raw)
            take_id = game.store.add_take(line_id, raw, self.app.group.member_id if self.app.group else "local")
            event_id = game.store.set_active(line_id, take_id) if activate else None
            installed = self.app.sync_files()
            self._json(HTTPStatus.CREATED, {"take_id": take_id, "event_id": event_id, **installed,
                                             "audio": asdict(info), "take": game.store.take(take_id),
                                             "state": self.app.line_state(line_id)})
            return
        payload = _read_json(raw) if content_type == "application/json" else {}
        game = self.app.require_game()
        line_actions = {"/api/set-active", "/api/active", "/api/undo", "/api/resolve", "/api/restore",
                        "/api/override", "/api/local-override"}
        if path in line_actions:
            self.app._line_file(payload.get("line_id"))
            for key in ("take_id", "target"):
                if key in payload and not isinstance(payload[key], str):
                    raise ServerError(f"{key} must be a recording id or ORIGINAL.")
        if path in {"/api/set-active", "/api/active"}:
            line_id = payload.get("line_id")
            target = payload.get("take_id", payload.get("target"))
            if target is None:
                raise ServerError("Specify take_id or target (ORIGINAL to restore).")
            event_id = game.store.set_active(line_id, target)
            self._json(HTTPStatus.OK, {"event_id": event_id, **self.app.sync_files(), "state": self.app.line_state(line_id)})
            return
        if path == "/api/undo":
            line_id = payload.get("line_id")
            event_id = game.store.undo(line_id)
            self._json(HTTPStatus.OK, {"event_id": event_id, **self.app.sync_files(), "state": self.app.line_state(line_id)})
            return
        if path in {"/api/resolve", "/api/restore"}:
            line_id = payload.get("line_id")
            target = payload.get("take_id", payload.get("target", ORIGINAL))
            event_id = game.store.resolve(line_id, target)
            self._json(HTTPStatus.OK, {"event_id": event_id, **self.app.sync_files(), "state": self.app.line_state(line_id)})
            return
        if path in {"/api/override", "/api/local-override"}:
            line_id = payload.get("line_id")
            use_original = payload.get("use_original")
            if type(use_original) is not bool:
                raise ServerError("use_original must be true or false.")
            game.store.set_local_override(line_id, use_original)
            self._json(HTTPStatus.OK, {**self.app.sync_files(), "state": self.app.line_state(line_id)})
            return
        if path == "/api/sync-files":
            self._json(HTTPStatus.OK, {**self.app.sync_files(), "pending_apply": game.pending_apply()})
            return
        if path in {"/api/apply", "/api/check-connection"}:
            if path == "/api/apply":
                if game.disabled_dir.exists():
                    raise ServerError("Enable voices before applying changes.")
                if game.store.missing_blobs():
                    raise ServerError("Some recordings have no audio. Import a complete collection before applying.")
                installed = self.app.sync_files()
                if installed["install_error"]:
                    self._json(200, {"result": "install_failed", **installed})
                    return
                result = game.apply()
                self.app.connection = "connected" if result == "sent" else result
            else:
                installed = {"written": 0}
                result = game.status()
                self.app.connection = result
            self._json(HTTPStatus.OK, {"result": result, **installed, "pending_apply": game.pending_apply(),
                                      "restart_required": game.settings.get("restart_required", False)})
            return
        if path == "/api/launch-options":
            self._json(200, {"launch_options": game.launch_options(), "message": "Keep your existing launch options."})
            return
        if path == "/api/remove-test-mod":
            game.remove_test_mod()
            self._json(200, {"removed": True})
            return
        if path == "/api/restart-confirmed":
            # This is a user acknowledgement, not evidence of playback or RCON.
            self.app.save_settings(restart_required=False)
            self._json(200, {"restart_required": False})
            return
        if path == "/api/export":
            raise ServerError("Export uses GET.")
        if path == "/api/import":
            if content_type not in {"application/zip", "application/octet-stream"}:
                raise ServerError("Collection imports require an application/zip body.")
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    entries = archive.infolist()
                    if len(entries) > 10000 or sum(e.file_size for e in entries) > MAX_ZIP_EXPANDED:
                        raise ServerError("The collection ZIP is too large when unpacked.")
                    if len({e.filename for e in entries}) != len(entries):
                        raise ServerError("The collection ZIP has duplicate entries.")
            except zipfile.BadZipFile:
                raise ServerError("The collection ZIP is invalid.") from None
            with tempfile.TemporaryDirectory(dir=self.app.root) as temp:
                source = Path(temp) / "import.zip"
                atomic_write(source, raw)
                changed = game.store.import_zip(source)
            self._json(HTTPStatus.OK, {"changed": changed, **self.app.sync_files()})
            return
        if path == "/api/disable":
            if not game.disabled_dir.exists():
                game.disable()
            self._json(HTTPStatus.OK, {"disabled": True})
            return
        if path == "/api/enable":
            game.enable()
            self._json(HTTPStatus.OK, {"enabled": True, "pending_apply": game.pending_apply()})
            return
        if path == "/api/uninstall":
            if "delete_collection" in payload and type(payload["delete_collection"]) is not bool:
                raise ServerError("delete_collection must be true or false.")
            delete_collection = payload.get("delete_collection") is True
            options = game.uninstall(delete_collection)
            if delete_collection:
                game.store = Store(game.store.root, game.store.device_id, catalog=game.catalog)
            self.app.save_settings(pending_files=0, restart_required=False)
            self._json(HTTPStatus.OK, {"uninstalled": True, "launch_options": options})
            return
        raise ServerError("Unknown API endpoint.")


def existing_instance(root: Path) -> str | None:
    """Return a reachable instance URL, ignoring stale instance metadata."""
    path = Path(root) / "instance.json"
    connection = None
    try:
        value = json.loads(path.read_bytes())
        if not isinstance(value, dict):
            return None
        url = value.get("url")
        port = value.get("port")
        if type(port) is not int or not 1 <= port <= 65535 or url != f"http://127.0.0.1:{port}":
            return None
        identity = value.get("instance_id")
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{32}", identity):
            return None
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)
        connection.request("GET", "/api/ping", headers={"Host": f"127.0.0.1:{port}"})
        response = connection.getresponse()
        data = json.loads(response.read(4096))
        if (response.status == 200 and isinstance(data, dict) and data.get("app") == "tf2reaudio"
                and data.get("instance_id") == identity):
            return url
    except (OSError, ValueError, TypeError, http.client.HTTPException):
        pass
    finally:
        if connection:
            connection.close()
    return None


def run_local(tf_dir=None, port=8440, root=None, browser=True):
    root = Path(root) if root else data_dir()
    root.mkdir(parents=True, exist_ok=True)
    lock = InstanceLock(root)
    diag = DiagnosticRecorder(root)
    server = None
    old_hook = threading.excepthook

    def thread_failed(args):
        if issubclass(args.exc_type, SystemExit):
            return
        diag.record("server", "thread", "failed", error_code(args.exc_value), error=args.exc_value)
        print(f"Error: a background task stopped unexpectedly ({args.exc_type.__name__}). "
              "Run `doctor --bundle` and send the report.", file=sys.stderr, flush=True)
    try:
        if not lock.acquire():
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                url = existing_instance(root)
                if url:
                    diag.record("server", "startup", "ok", "already_running")
                    print(f"TF2 Re-Audio is already running: {url}")
                    if browser:
                        webbrowser.open(url)
                    return 0
                time.sleep(0.1)
            raise ServerError("Another instance is starting or busy. Try opening the app again shortly.")
        set_low_priority()
        threading.excepthook = thread_failed
        try:
            server = LocalServer(LocalApp(tf_dir, root), port=port).start()
        except ServerError as exc:
            diag.record("server", "startup", "failed", "port_unavailable", error=exc)
            raise
        diag.record("server", "startup", "ok", "ok")
        print(f"TF2 Re-Audio is running at {server.url}", flush=True)
        print("Keep this window open. Press Ctrl+C to stop the app.", flush=True)
        if browser:
            webbrowser.open(server.url)
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        threading.excepthook = old_hook
        if server:
            server.stop()
            diag.record("server", "shutdown", "ok", "ok")
        lock.close()
    return 0


class LocalServer:
    """Threaded local server.

    ``port=0`` is useful for tests and lets the OS choose a free port.  The
    normal application asks for 8440 and retries a small range if it is busy.
    """

    def __init__(self, app: LocalApp | None = None, host: str = "127.0.0.1", port: int = 8440,
                 static_dir: Path | None = None):
        if host != "127.0.0.1" or type(port) is not int or not 0 <= port <= 65535:
            raise ServerError("Use 127.0.0.1 and a port between 0 and 65535.")
        self.app = app or LocalApp()
        self.host = host
        self.requested_port = port
        self.instance_id = secrets.token_hex(16)
        package_web = Path(__file__).with_name("web")
        self.static_dir = Path(static_dir) if static_dir else package_web
        self.httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self.httpd is None:
            return self.requested_port
        return int(self.httpd.server_address[1])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> "LocalServer":
        if self.httpd is not None:
            return self
        last_error = None
        ports = [self.requested_port] if self.requested_port == 0 else range(self.requested_port, min(65536, self.requested_port + 10))
        for port in ports:
            try:
                httpd = _LocalHTTPServer((self.host, port), _Handler)
                break
            except OSError as exc:
                last_error = exc
        else:
            raise ServerError(f"Could not open the local server port: {last_error}")
        httpd.daemon_threads = False
        httpd.app = self.app  # type: ignore[attr-defined]
        httpd.owner = self  # type: ignore[attr-defined]
        self.httpd = httpd
        instance = self.app.root / "instance.json"
        try:
            atomic_write(instance, _json_bytes({"pid": os.getpid(), "port": self.port, "url": self.url,
                                            "instance_id": self.instance_id}))
            self._thread = threading.Thread(target=httpd.serve_forever, name="tf2reaudio-local-server", daemon=True)
            self._thread.start()
        except BaseException:
            httpd.server_close()
            self.httpd = None
            raise
        return self

    def serve_forever(self):
        if self.httpd is None:
            self.start()
        while self._thread and self._thread.is_alive():
            self._thread.join(0.2)

    def stop(self):
        httpd = self.httpd
        if httpd is None:
            return
        actual_port = int(httpd.server_address[1])
        httpd.shutdown()
        httpd.server_close()
        self.app.close_group()
        self.httpd = None
        if self._thread:
            self._thread.join()
        instance = self.app.root / "instance.json"
        try:
            current = json.loads(instance.read_bytes())
            if current.get("port") == actual_port and current.get("instance_id") == self.instance_id:
                instance.unlink(missing_ok=True)
        except (OSError, ValueError, AttributeError):
            pass
