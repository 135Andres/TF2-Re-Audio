"""Trusted-replica group membership. Local bearer secrets never enter snapshots."""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from .catalog import CLASSES
from .util import atomic_write, data_dir

FORMAT_VERSION = 1
MAX_EVENTS = 50000
_ID = re.compile(r"[A-Za-z0-9_.-]{1,64}")
_SHA = re.compile(r"[0-9a-f]{64}")
_TUNNEL_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com")


class GroupError(Exception):
    """An expected membership or persistence problem, safe to show in the UI."""


def _need(condition, message):
    if not condition:
        raise GroupError(message)


def _identifier(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _label(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= 80 and not any(ord(c) < 32 for c in value)


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_url(url):
    """Return the normalized host link: a quick-tunnel HTTPS origin or loopback HTTP.

    Other HTTPS hosts are refused so a hostile link cannot point the app at
    internal addresses (127.0.0.1:8443, 169.254.169.254, LAN devices).
    """
    _need(isinstance(url, str) and len(url) <= 2048, "Enter a valid host link.")
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError:
        raise GroupError("Enter a valid host link.") from None
    host = parsed.hostname or ""
    tunnel = (parsed.scheme == "https" and _TUNNEL_HOST.fullmatch(host) is not None
              and host != "api.trycloudflare.com" and port in (None, 443))
    # shortcut: loopback HTTP stays allowed for fixtures and same-PC testing; it can only reach
    # /api/hello on this PC before group_id must match. Gate it behind a developer flag if that changes.
    loopback = parsed.scheme == "http" and host == "127.0.0.1" and port is not None
    _need((tunnel or loopback) and not parsed.username and not parsed.password and not parsed.query
          and not parsed.fragment and parsed.path in ("", "/"),
          "Use the host's https://….trycloudflare.com link.")
    return f"https://{host}" if tunnel else f"http://127.0.0.1:{port}"


class Group:
    def __init__(self, root, record):
        self.root = Path(root)
        self._lock = threading.RLock()
        self.warning = None
        self._record = record
        self._validate(record["snapshot"])
        _need(_identifier(record.get("member_id")) and _identifier(record.get("device_id"))
              and isinstance(record.get("token"), str), "Invalid local group credentials.")

    @classmethod
    def create(cls, name, my_display_name, *, root=None, device_id=None):
        _need(_label(name) and _label(my_display_name), "Group and display names must contain 1–80 characters.")
        root = Path(root) if root is not None else data_dir()
        _need(not (root / "group.json").exists(), "This installation already belongs to a group.")
        device = device_id or uuid.uuid4().hex
        _need(_identifier(device), "Invalid device id.")
        member, token, group_id = uuid.uuid4().hex, secrets.token_hex(32), uuid.uuid4().hex
        event = {"event_id": uuid.uuid4().hex, "lamport": 1, "actor": member, "kind": "create",
                 "member_id": member, "device_id": device, "display_name": my_display_name.strip(),
                 "token_hash": _hash(token), "name": name.strip()}
        record = {"format_version": FORMAT_VERSION, "member_id": member, "device_id": device,
                  "token": token, "hosts": [], "snapshot": {"format_version": FORMAT_VERSION,
                  "group_id": group_id, "events": [event]}}
        result = cls(root, record)
        result._persist(record)
        return result

    @classmethod
    def load(cls, root=None):
        root = Path(root) if root is not None else data_dir()
        path = root / "group.json"
        if not path.exists():
            return None
        def read(source):
            record = json.loads(source.read_bytes())
            _need(isinstance(record, dict), "Invalid group file.")
            version = record.get("format_version")
            _need(version == FORMAT_VERSION and type(version) is int, "Update the app to read this group format.")
            return cls(root, record)
        try:
            return read(path)
        except GroupError as exc:
            if "Update the app" in str(exc):
                raise
        except (OSError, ValueError, KeyError, TypeError):
            pass
        try:
            recovered = read(root / "group.json.bak")
        except (OSError, ValueError, KeyError, TypeError, GroupError):
            raise GroupError("The group file and backup cannot be read. Your recordings were preserved.") from None
        try:
            atomic_write(path, json.dumps(recovered._record, sort_keys=True).encode("utf-8"))
        except OSError:
            raise GroupError("Could not save the recovered group. Check free space and folder permissions.") from None
        recovered.warning = "Your group file was damaged; the previous version was restored."
        return recovered

    @classmethod
    def join(cls, snapshot, member_id, token, device_id, root, *, host_url=None):
        root = Path(root)
        _need(not (root / "group.json").exists(), "This installation already belongs to a group.")
        result = cls(root, {"format_version": FORMAT_VERSION, "member_id": member_id, "token": token,
                          "device_id": device_id, "hosts": [validate_url(host_url)] if host_url else [], "snapshot": copy.deepcopy(snapshot)})
        _need(result.verify_token(token) == member_id and result.devices().get(device_id) == member_id,
              "The host returned invalid membership credentials.")
        result._persist(result._record)
        return result

    @property
    def group_id(self):
        return self._record["snapshot"]["group_id"]

    @property
    def member_id(self):
        return self._record["member_id"]

    @property
    def device_id(self):
        return self._record["device_id"]

    @property
    def token(self):
        return self._record["token"]

    @property
    def name(self):
        return self._state()["name"]

    def _validate(self, snapshot):
        _need(isinstance(snapshot, dict) and type(snapshot.get("format_version")) is int
              and snapshot["format_version"] == FORMAT_VERSION, "Update the app to read this group format.")
        _need(_identifier(snapshot.get("group_id")), "Invalid group identity.")
        events = snapshot.get("events")
        _need(isinstance(events, list) and 0 < len(events) <= MAX_EVENTS, "Invalid group event count.")
        seen = set()
        for event in events:
            _need(isinstance(event, dict) and _identifier(event.get("event_id"))
                  and _identifier(event.get("actor")) and type(event.get("lamport")) is int
                  and 0 < event["lamport"] < 2**53 and event["event_id"] not in seen,
                  "Invalid group event.")
            seen.add(event["event_id"])
        return self._reduce(events)

    @staticmethod
    def _reduce(events):
        state = {"members": {}, "invites": {}, "used": set(), "removed": set(), "cast": {}, "name": ""}
        for e in sorted(events, key=lambda e: (e["lamport"], e["event_id"])):
            kind = e.get("kind")
            admin = state["members"].get(e["actor"], {}).get("role") == "admin"
            if kind == "create":
                _need(not state["name"] and e["lamport"] == 1 and e.get("member_id") == e["actor"]
                      and _label(e.get("name")), "Invalid group creation event.")
                state["name"] = e["name"]
            elif kind == "invite":
                _need(admin and isinstance(e.get("code_hash"), str) and _SHA.fullmatch(e["code_hash"])
                      and type(e.get("expires")) is int and e["expires"] > 0, "Invalid invitation event.")
                state["invites"][e["code_hash"]] = e
            elif kind == "join":
                inv = state["invites"].get(e.get("code_hash"))
                _need(inv is not None and type(e.get("redeemed_at")) is int
                      and 0 <= e["redeemed_at"] <= inv["expires"], "Invalid invitation redemption.")
                state["used"].add(e["code_hash"])
            elif kind in ("remove", "promote"):
                _need(admin and e.get("member_id") in state["members"], "Only an admin can change members.")
                if kind == "remove":
                    state["removed"].add(e["member_id"])
                else:
                    state["members"][e["member_id"]]["role"] = "admin"
            elif kind == "cast":
                _need(admin and e.get("cls") in CLASSES and (e.get("member_id") is None or e.get("member_id") in state["members"]),
                      "Only an admin can assign a suggested voice.")
                state["cast"][e["cls"]] = e["member_id"]
            else:
                raise GroupError("Unknown group event.")
            if kind in ("create", "join"):
                _need(_identifier(e.get("member_id")) and _identifier(e.get("device_id"))
                      and _label(e.get("display_name")) and isinstance(e.get("token_hash"), str)
                      and _SHA.fullmatch(e["token_hash"]) and e["member_id"] not in state["members"]
                      and not any(m["device_id"] == e["device_id"] for m in state["members"].values()),
                      "Invalid or duplicated group member.")
                state["members"][e["member_id"]] = {k: e[k] for k in ("member_id", "device_id", "display_name", "token_hash")}
                state["members"][e["member_id"]]["role"] = "admin" if kind == "create" else "member"
        _need(bool(state["name"]), "The group has no creation event.")
        return state

    def _state(self):
        return self._validate(self._record["snapshot"])

    def _persist(self, record):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "group.json"
        try:
            if path.exists():
                atomic_write(self.root / "group.json.bak", path.read_bytes())
            atomic_write(path, json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8"))
        except OSError:
            raise GroupError("Could not save group data. Check free space and folder permissions.") from None
        self._record = copy.deepcopy(record)

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._record["snapshot"])

    def merge(self, snapshot, actor=None, *, dry_run=False):
        with self._lock:
            self._validate(snapshot)
            _need(snapshot["group_id"] == self.group_id, "This link belongs to another group.")
            old = {e["event_id"]: e for e in self._record["snapshot"]["events"]}
            for e in snapshot["events"]:
                if e["event_id"] in old:
                    _need(old[e["event_id"]] == e, "A group event changed under an existing id.")
                else:
                    if actor is not None:
                        _need(e["actor"] == actor and self.is_admin(actor)
                              and e["kind"] in ("invite", "remove", "promote", "cast"),
                              "This member cannot upload that group change.")
                    old[e["event_id"]] = e
            updated = copy.deepcopy(self._record)
            updated["snapshot"]["events"] = sorted(old.values(), key=lambda e: e["event_id"])
            self._validate(updated["snapshot"])
            if updated != self._record and not dry_run:
                self._persist(updated)

    def _event(self, kind, **fields):
        updated = copy.deepcopy(self._record)
        events = updated["snapshot"]["events"]
        events.append(dict(event_id=uuid.uuid4().hex, lamport=max(e["lamport"] for e in events) + 1,
                           actor=self.member_id, kind=kind, **fields))
        self._validate(updated["snapshot"])
        self._persist(updated)

    def _admin(self):
        _need(self.is_admin(self.member_id), "Only an admin can perform this action.")

    def create_invite(self, ttl_hours=24):
        with self._lock:
            self._admin()
            _need(type(ttl_hours) in (int, float) and 0 < ttl_hours <= 168, "Invitation lifetime must be 1–168 hours.")
            alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
            chars = "".join(secrets.choice(alphabet) for _ in range(12))
            code = "TF2-" + "-".join(chars[i:i+4] for i in range(0, 12, 4))
            self._event("invite", code_hash=_hash(code), expires=int(time.time() + ttl_hours * 3600))
            return code

    def redeem_invite(self, code, display_name, device_id=None):
        with self._lock:
            _need(_label(display_name) and _identifier(device_id or "device"), "Enter a valid display name and device.")
            _need(isinstance(code, str) and len(code) <= 80, "Invalid invitation code.")
            digest = _hash(code.strip().upper())
            state = self._state()
            inv = state["invites"].get(digest)
            _need(inv is not None, "Invalid invitation code.")
            _need(digest not in state["used"], "This invitation has already been used.")
            _need(time.time() <= inv["expires"], "This invitation has expired. Ask an admin for a new one.")
            member, token = uuid.uuid4().hex, secrets.token_hex(32)
            self._event("join", code_hash=digest, redeemed_at=int(time.time()), member_id=member,
                        token_hash=_hash(token), display_name=display_name.strip(), device_id=device_id or uuid.uuid4().hex)
            return member, token

    def verify_token(self, token):
        if not isinstance(token, str) or len(token) > 256:
            return None
        digest = _hash(token)
        with self._lock:
            state = self._state()
            for mid, member in state["members"].items():
                if hmac.compare_digest(digest, member["token_hash"]) and mid not in state["removed"]:
                    return mid
        return None

    def members(self):
        with self._lock:
            state = self._state()
            return [{k: v for k, v in member.items() if k != "token_hash"}
                    for mid, member in state["members"].items() if mid not in state["removed"]]

    def devices(self):
        return {m["device_id"]: m["member_id"] for m in self.members()}

    def is_admin(self, member_id):
        return any(m["member_id"] == member_id and m["role"] == "admin" for m in self.members())

    def remove_member(self, member_id):
        with self._lock:
            self._admin()
            _need(member_id != self.member_id or sum(m["role"] == "admin" for m in self.members()) > 1,
                  "The last admin cannot leave the group.")
            self._event("remove", member_id=member_id)

    def promote(self, member_id):
        with self._lock:
            self._admin()
            self._event("promote", member_id=member_id)

    def set_suggested_voice(self, cls, member_id):
        with self._lock:
            self._admin()
            self._event("cast", cls=cls, member_id=member_id)

    def suggested_voices(self):
        with self._lock:
            state = self._state()
            return {cls: mid for cls, mid in state["cast"].items() if mid is not None and mid not in state["removed"]}

    def known_hosts(self):
        with self._lock:
            return list(self._record.get("hosts", []))

    def set_host_url(self, url):
        url = validate_url(url)
        with self._lock:
            updated = copy.deepcopy(self._record)
            updated["hosts"] = [url] + [u for u in updated.get("hosts", []) if u != url][:9]
            self._persist(updated)
