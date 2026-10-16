"""Optional trusted-host synchronization; no game installation or UI is exposed here."""
from __future__ import annotations

import copy
import hashlib
import http.client
import json
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import PROTOCOL_VERSION, __version__
from .audio import MAX_BYTES, InvalidWav, inspect_wav
from .group import Group, GroupError, validate_url
from .store import Store, StoreError
from .util import atomic_write

MAX_SNAPSHOT = 16 * 1024 * 1024
MAX_RECORDS = 50000
MAX_CONNECTIONS = 8
HEADER_DEADLINE, BODY_DEADLINE, REQUEST_DEADLINE = 5, 20, 25
_SHA = re.compile(r"[0-9a-f]{64}")


class SyncError(Exception):
    """Expected sync failure without credentials or raw transport details."""
    def __init__(self, message, status="host_offline"):
        super().__init__(message)
        self.status = status


@dataclass
class SyncResult:
    pushed: int = 0
    pulled: int = 0
    conflicts: int = 0
    error: str | None = None
    status: str = "synced"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _object(raw):
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        raise SyncError("The sync data is not valid JSON.") from None
    if not isinstance(result, dict):
        raise SyncError("The sync data must be an object.")
    return result


class GroupStore(Store):
    """Preserve shared history until T8 provides an authenticated pruning contract.

    Solo Store retention is unchanged. This adapter overrides the existing
    commit hook rather than modifying the storage owner's implementation.
    """
    def _commit(self, line_id):
        self._save()

    def state(self, line_id):
        flags = super().state(line_id)
        with self._lock:
            shareable = {t["take_id"] for t in self._takes.values() if t["line_id"] == line_id}
            shareable.update(e["event_id"] for e in self._events.values()
                             if e["line_id"] == line_id and e["target"] not in self._pruned)
            if shareable & self._unshared:
                flags.add("pending_share")
            else:
                # Historical solo events whose audio was already pruned are
                # preserved locally, but never queued as shared recordings.
                flags.discard("pending_share")
        return flags


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request(url, path, token=None, method="GET", value=None, etag=None, limit=MAX_SNAPSHOT):
    try:
        url = validate_url(url)
    except GroupError as exc:
        raise SyncError(str(exc)) from None
    headers = {"X-TF2RA-Protocol": str(PROTOCOL_VERSION)}
    if token:
        headers["Authorization"] = "Bearer " + token
    if etag:
        headers["If-None-Match"] = etag
    if value is not None:
        headers["Content-Type"] = "application/octet-stream" if isinstance(value, bytes) else "application/json"
    data = value if isinstance(value, bytes) else _json(value) if value is not None else None
    req = urllib.request.Request(url + path, data=data, method=method, headers=headers)
    # Ignore environment proxies for loopback, and never forward bearer tokens on redirects.
    handlers = [_NoRedirect()]
    if url.startswith("http://127.0.0.1:"):
        handlers.append(urllib.request.ProxyHandler({}))
    try:
        try:
            response = urllib.request.build_opener(*handlers).open(req, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            if response.status == 304:
                return 304, response.headers, b""
            if response.status == 401:
                raise SyncError("Your group access is no longer valid. Ask an admin for a new invitation.", "auth_failed")
            if response.status == 426:
                raise SyncError("Update the app to synchronize with this group.", "update_required")
            raw = response.read(limit + 1)
            declared = response.headers.get("Content-Length")
            if declared is not None and (not declared.isdigit() or int(declared) != len(raw)):
                raise SyncError("The transfer was interrupted. Your recordings are saved here.")
            if len(raw) > limit:
                raise SyncError("The host response exceeds the sync size limit.")
            if not 200 <= response.status < 300:
                message = "The host could not accept this sync request."
                if response.headers.get("Content-Type", "").startswith("application/json"):
                    message = _object(raw).get("error", message)
                raise SyncError(message if isinstance(message, str) else "Invalid host response.")
            return response.status, response.headers, raw
    except (OSError, http.client.HTTPException, ValueError):
        raise SyncError("The host is offline or the transfer was interrupted. Your recordings are saved here.") from None


def check_host(url, group_id=None):
    _, _, raw = _request(url, "/api/hello")
    hello = _object(raw)
    if hello.get("protocol_version") != PROTOCOL_VERSION:
        raise SyncError("Update the app to synchronize with this group.", "update_required")
    if not isinstance(hello.get("group_id"), str) or (group_id is not None and hello["group_id"] != group_id):
        raise SyncError("This link belongs to another group.")
    return hello


def join_group(url, code, display_name, device_id, root):
    if (Path(root) / "group.json").exists():
        raise SyncError("This installation already belongs to a group.")
    hello = check_host(url)
    _, _, raw = _request(url, "/api/redeem", method="POST",
                         value={"code": code, "display_name": display_name, "device_id": device_id})
    value = _object(raw)
    try:
        if value["group"]["group_id"] != hello["group_id"]:
            raise SyncError("The host group changed while joining. Try again.")
        group = Group.join(value["group"], value["member_id"], value["token"], device_id, root, host_url=url)
        return group
    except (KeyError, TypeError):
        raise SyncError("The host returned incomplete membership data.") from None


def _install_audio(store, blobs):
    """Stage validated content before metadata. Caller serializes collection mutations.

    Store.put_blob intentionally refuses unreferenced audio. This adapter honors
    its existing on-disk layout without changing the T8 owner's source files.
    """
    for sha, audio in blobs.items():
        if not _SHA.fullmatch(sha) or hashlib.sha256(audio).hexdigest() != sha:
            raise SyncError("The recording hash does not match its audio.")
        inspect_wav(audio)
        atomic_write(store.root / "blobs" / (sha + ".wav"), audio)


def _envelope(store, group):
    return {"protocol_version": PROTOCOL_VERSION, "group_id": group.group_id,
            "group": group.snapshot(), "collection": store.snapshot()}


def _validate(store, group, envelope, actor=None):
    if envelope.get("protocol_version") != PROTOCOL_VERSION:
        raise SyncError("Update the app to synchronize with this group.", "update_required")
    if envelope.get("group_id") != group.group_id:
        raise SyncError("This link belongs to another group.")
    remote_group, incoming = envelope.get("group"), envelope.get("collection")
    group.merge(remote_group, actor=actor, dry_run=True)
    if not isinstance(incoming, dict) or any(not isinstance(incoming.get(k), list) for k in ("takes", "events", "pruned")):
        raise SyncError("Invalid collection snapshot.")
    if sum(len(incoming[k]) for k in ("takes", "events", "pruned")) > MAX_RECORDS:
        raise SyncError("The collection exceeds the sync record limit.")
    # Reuse the Store owner's validation, without committing untrusted metadata.
    store._parse(incoming)
    current = store.snapshot()
    devices = group.devices()
    all_takes = {t["take_id"]: t for t in current["takes"]}
    for field, key in (("takes", "take_id"), ("events", "event_id")):
        old = {r[key]: r for r in current[field]}
        seen = set()
        for record in incoming[field]:
            rid = record[key]
            if rid in seen:
                raise SyncError("Duplicate immutable record id.")
            seen.add(rid)
            if rid in old:
                if old[rid] != record:
                    raise SyncError("A recording or event changed under an existing id.")
            elif actor is not None:
                if devices.get(record["device_id"]) != actor:
                    raise SyncError("A member can only upload their own new recordings and events. Synchronize a replacement host first.")
                if field == "takes" and record["author_member_id"] not in (actor, "local"):
                    raise SyncError("A member cannot upload a recording attributed to someone else.")
            if field == "takes":
                all_takes[rid] = record
    pruned = set(current["pruned"]) | set(incoming["pruned"])
    if actor is not None and set(incoming["pruned"]) - set(current["pruned"]):
        raise SyncError("Clients cannot delete shared recording history. Only known pruning records may be echoed.")
    for event in incoming["events"]:
        target = event["target"]
        if target == "ORIGINAL" or target in pruned:
            continue
        take = all_takes.get(target)
        if not take or take["line_id"] != event["line_id"]:
            raise SyncError("A line event references an unavailable or unrelated recording.")
    return incoming


class _HTTPServer(ThreadingHTTPServer):
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True
    request_queue_size = MAX_CONNECTIONS

    def __init__(self, *args):
        super().__init__(*args)
        self._slots = threading.BoundedSemaphore(MAX_CONNECTIONS)

    def process_request(self, request, client_address):
        # Admit before spawning a worker so slow peers cannot create unbounded threads.
        if not self._slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request, client_address):
        if not isinstance(sys.exc_info()[1], OSError):
            super().handle_error(request, client_address)  # Peer disconnects stay quiet.


class _Busy(Exception):
    pass


class SyncServer:
    def __init__(self, store, group, port=0, *, lock=None):
        self.store, self.group, self.port = store, group, port
        self.httpd = None
        self._thread = None
        self._lock = lock or threading.RLock()
        self._attempts = {}

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        if self.httpd:
            return self
        try:
            self.httpd = _HTTPServer(("127.0.0.1", self.port), _Handler)
        except OSError:
            raise SyncError("Could not open the group sync port.") from None
        self.httpd.owner = self
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True, name="tf2reaudio-sync-host")
        self._thread.start()
        return self

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            self._thread.join(timeout=6)


class _Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)
        self._started = time.monotonic()
        self._arm(HEADER_DEADLINE)

    def _arm(self, seconds):
        # A socket timeout only bounds inactivity; this bounds a peer that drips bytes.
        self._watchdog = threading.Timer(max(seconds, 0), self._expire)
        self._watchdog.daemon = True
        self._watchdog.start()

    def _expire(self):
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _remaining(self):
        return REQUEST_DEADLINE - (time.monotonic() - self._started)

    def parse_request(self):
        ok = super().parse_request()  # Reads the headers, so it stays under the header deadline.
        self._watchdog.cancel()
        self._arm(self._remaining())
        return ok

    def finish(self):
        self._watchdog.cancel()
        try:
            super().finish()
        except OSError:
            pass

    def log_message(self, *args):
        pass  # Do not log bearer tokens, invitation codes or paths.

    def _send(self, status, value=None, raw=None, etag=None):
        data = raw if raw is not None else _json(value or {})
        self.send_response(status)
        self.send_header("Content-Type", "audio/wav" if raw is not None else "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if etag:
            self.send_header("ETag", etag)
        self.end_headers()
        if data:
            self.wfile.write(data)

    def _body(self, maximum):
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not lengths[0].isdigit():
            raise SyncError("A single Content-Length is required; chunked transfers are not supported.")
        size = int(lengths[0])
        if not 0 <= size <= maximum:
            raise SyncError("The request exceeds the sync size limit.")
        deadline = time.monotonic() + min(BODY_DEADLINE, self._remaining())
        chunks, received = [], 0
        while received < size:
            chunk = self.rfile.read1(min(65536, size - received))
            if not chunk or time.monotonic() > deadline:
                raise SyncError("The transfer was interrupted. Retry the recording.")
            chunks.append(chunk)
            received += len(chunk)
        return b"".join(chunks)

    @contextmanager
    def _locked(self):
        """Wait for the shared app lock only within the request deadline."""
        lock = self.server.owner._lock
        if not lock.acquire(timeout=max(self._remaining(), 0.01)):
            raise _Busy()
        try:
            yield
        finally:
            lock.release()

    def _run(self):
        try:
            self._dispatch()
        except _Busy:
            try:
                self._send(503, {"error": "The host is busy. Try again soon."})
            except OSError:
                pass
        except OSError:
            pass  # Includes peer disconnects while writing an error response.

    def _dispatch(self):
        owner = self.server.owner
        try:
            if self.headers.get("X-TF2RA-Protocol") != str(PROTOCOL_VERSION):
                self._send(426, {"error": "Update the app"})
                return
            if self.command == "GET" and self.path == "/api/hello":
                self._send(200, {"group_id": owner.group.group_id, "protocol_version": PROTOCOL_VERSION,
                                 "app_version": __version__})
                return
            if self.command == "POST" and self.path in ("/api/redeem", "/api/redeem-invite"):
                now = time.monotonic()
                # Trust the socket address only. Behind a tunnel this deliberately shares a bucket.
                address = self.client_address[0]
                with self._locked():
                    if len(owner._attempts) > 1024:
                        owner._attempts = {ip: q for ip, q in owner._attempts.items() if q and q[-1] > now - 60}
                    attempts = owner._attempts.setdefault(address, deque())
                    while attempts and attempts[0] <= now - 60:
                        attempts.popleft()
                    if len(attempts) >= 5:
                        self._send(429, {"error": "Too many invitation attempts. Try again in one minute."})
                        return
                    attempts.append(now)
                # Read untrusted bodies without holding the lock shared with the local UI.
                body = _object(self._body(4096))
                with self._locked():
                    mid, token = owner.group.redeem_invite(body.get("code"), body.get("display_name"), body.get("device_id"))
                    snapshot = owner.group.snapshot()
                self._send(200, {"member_id": mid, "token": token, "group": snapshot})
                return
            auth = self.headers.get_all("Authorization", [])
            token = auth[0][7:] if len(auth) == 1 and auth[0].startswith("Bearer ") else None
            actor = owner.group.verify_token(token) if token else None
            if actor is None:
                self._send(401, {"error": "Group access is no longer valid."})
                return
            body = None
            if self.command == "POST" and self.path == "/api/snapshot":
                body = self._body(MAX_SNAPSHOT)
            elif self.command == "PUT" and self.path.startswith("/api/blob/") and _SHA.fullmatch(self.path[10:]):
                body = self._body(MAX_BYTES)
                if hashlib.sha256(body).hexdigest() != self.path[10:]:
                    raise SyncError("The recording hash does not match its audio.")
                inspect_wav(body)
            with self._locked():
                # Membership may have changed while the body was read.
                if owner.group.verify_token(token) != actor:
                    reply = (401, {"error": "Group access is no longer valid."})
                else:
                    reply = self._authorized(owner, actor, body)
            # Write outside the lock so a slow reader cannot stall the local UI.
            self._send(*reply)
        except (SyncError, GroupError, StoreError, InvalidWav, ValueError, TypeError, RecursionError) as exc:
            status = 426 if isinstance(exc, SyncError) and exc.status == "update_required" else 400
            self._send(status, {"error": str(exc) if isinstance(exc, (SyncError, GroupError, StoreError, InvalidWav)) else "Invalid sync data."})
        except KeyError:
            self._send(400, {"error": "Upload all recording audio before sharing its metadata."})

    def _authorized(self, owner, actor, body):
        """Run under the app lock; return the _send arguments."""
        if self.path == "/api/snapshot":
            if self.command == "GET":
                snapshot = _envelope(owner.store, owner.group)
                etag = '"' + hashlib.sha256(_json(snapshot)).hexdigest() + '"'
                if self.headers.get("If-None-Match") == etag:
                    return (304, None, b"", etag)
                return (200, snapshot, None, etag)
            if self.command == "POST":
                envelope = _object(body)
                incoming = _validate(owner.store, owner.group, envelope, actor)
                staged = {}
                inbox = owner.store.root.parent / "sync-inbox" / actor
                for take in incoming["takes"]:
                    sha = take["sha256"]
                    if owner.store.has_blob(sha):
                        audio = owner.store.blob(sha)
                    else:
                        try:
                            audio = (inbox / (sha + ".wav")).read_bytes()
                        except OSError:
                            raise SyncError("Upload all recording audio before sharing its metadata.") from None
                    if hashlib.sha256(audio).hexdigest() != sha:
                        raise SyncError("The recording hash does not match its audio.")
                    inspect_wav(audio)
                    staged[sha] = audio
                _install_audio(owner.store, staged)
                owner.group.merge(envelope["group"], actor=actor)
                owner.store.merge(incoming)
                for sha in staged:
                    (inbox / (sha + ".wav")).unlink(missing_ok=True)
                ids = [t["take_id"] for t in incoming["takes"]] + [e["event_id"] for e in incoming["events"]]
                return (200, {"acknowledged": ids})
        if self.path.startswith("/api/blob/") and _SHA.fullmatch(self.path[10:]):
            sha = self.path[10:]
            if self.command == "GET":
                if not any(t["sha256"] == sha for t in owner.store.snapshot()["takes"]):
                    return (404, {"error": "Recording audio is unavailable."})
                return (200, None, owner.store.blob(sha))
            if self.command == "PUT":
                if not owner.store.has_blob(sha):
                    inbox = owner.store.root.parent / "sync-inbox" / actor
                    inbox.mkdir(parents=True, exist_ok=True)
                    files = list(inbox.glob("*.wav"))
                    if (len(files) >= 10000 or sum(p.stat().st_size for p in files) + len(body) > 128 * 1024 * 1024) and not (inbox / (sha + ".wav")).exists():
                        raise SyncError("Too many incomplete uploads. Complete a sync before uploading more audio.")
                    atomic_write(inbox / (sha + ".wav"), body)
                return (200, {"sha256": sha})
        return (404, {"error": "This group endpoint does not exist."})

    do_GET = do_POST = do_PUT = _run


def sync_once(store, group, url, token, *, lock=None, stop=None):
    result = SyncResult()
    def check_cancelled():
        if stop is not None and stop.is_set():
            raise SyncError("Synchronization stopped. Your recordings are saved here.")
    try:
        check_cancelled()
        check_host(url, group.group_id)
        cache = getattr(group, "_sync_etags", {})
        _, headers, raw = _request(url, "/api/snapshot", token, etag=cache.get(url))
        if raw:
            envelope = _object(raw)
            incoming = _validate(store, group, envelope)
            before = store.snapshot()
            before_ids = {r.get("take_id", r.get("event_id")) for k in ("takes", "events") for r in before[k]}
            staged = {}
            for take in incoming["takes"]:
                check_cancelled()
                if not store.has_blob(take["sha256"]):
                    _, _, audio = _request(url, "/api/blob/" + take["sha256"], token, limit=MAX_BYTES)
                    if hashlib.sha256(audio).hexdigest() != take["sha256"]:
                        raise SyncError("Downloaded audio failed the SHA-256 check.")
                    inspect_wav(audio)
                    staged[take["sha256"]] = audio
            with lock or nullcontext():
                check_cancelled()
                _validate(store, group, envelope)
                _install_audio(store, staged)
                group.merge(envelope["group"])
                store.merge(incoming)
            result.pulled = sum(r.get("take_id", r.get("event_id")) not in before_ids
                                for k in ("takes", "events") for r in incoming[k])
            cache[url] = headers.get("ETag")
            group._sync_etags = cache
            remote_pruned = getattr(group, "_sync_remote_pruned", {})
            remote_pruned[url] = set(incoming["pruned"])
            group._sync_remote_pruned = remote_pruned
            remote_blobs = getattr(group, "_sync_remote_blobs", {})
            remote_blobs[url] = {t["sha256"] for t in incoming["takes"]}
            group._sync_remote_blobs = remote_blobs
        if group.verify_token(token) is None:
            raise SyncError("Your group access is no longer valid.", "auth_failed")
        outgoing = _envelope(store, group)
        # A legacy solo Store may already have pruned private history. Those
        # declarations are not authority to delete records on another device.
        collection = outgoing["collection"]
        local_pruned = set(collection["pruned"])
        collection["pruned"] = sorted(local_pruned & getattr(group, "_sync_remote_pruned", {}).get(url, set()))
        omitted = local_pruned - set(collection["pruned"])
        collection["events"] = [e for e in collection["events"] if e["target"] not in omitted]
        uploaded = set(getattr(group, "_sync_remote_blobs", {}).get(url, set()))
        for take in outgoing["collection"]["takes"]:
            if take["sha256"] in uploaded:
                continue
            check_cancelled()
            # Uploading is idempotent and bounded; the host verifies both hash and WAV.
            audio = store.blob(take["sha256"])
            _request(url, "/api/blob/" + take["sha256"], token, "PUT", audio)
            uploaded.add(take["sha256"])
        check_cancelled()
        _, _, raw = _request(url, "/api/snapshot", token, "POST", outgoing)
        acknowledged = _object(raw).get("acknowledged")
        ids = {r.get("take_id", r.get("event_id")) for k in ("takes", "events") for r in outgoing["collection"][k]}
        if not isinstance(acknowledged, list) or any(not isinstance(i, str) or i not in ids for i in acknowledged):
            raise SyncError("The host returned an invalid sharing acknowledgment.")
        result.pushed = len(acknowledged)
        with lock or nullcontext():
            check_cancelled()
            store.mark_shared(acknowledged)
        result.conflicts = len(store.conflicts())
    except SyncError as exc:
        result.error, result.status = str(exc), exc.status
    except (GroupError, StoreError, InvalidWav, KeyError, OSError, ValueError, TypeError, RecursionError):
        result.error = "Could not validate or save synchronized recordings. Your local recordings were preserved."
        result.status = "host_offline"
    return result


class Syncer:
    def __init__(self, store, group, url, token, *, lock=None):
        self.store, self.group, self.url, self.token = store, group, url, token
        self.last_sync = None
        self.status = "host_offline"
        self.error = None
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._mutation_lock = lock

    @property
    def pending_share(self):
        return sum("pending_share" in self.store.state(line) for line in self.store.lines())

    def run_once(self):
        with self._lock:
            result = sync_once(self.store, self.group, self.url, self.token, lock=self._mutation_lock, stop=self._stop)
            self.status, self.error = result.status, result.error
            if not result.error:
                self.last_sync = time.time()
            return result

    def start(self):
        if self._thread and self._thread.is_alive():
            return self
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="tf2reaudio-sync-client")
        self._thread.start()
        return self

    def _run(self):
        delay = 15
        while not self._stop.is_set():
            result = self.run_once()
            delay = min(delay * 2, 120) if result.error else 15
            if self._stop.wait(delay):
                break

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=6)
