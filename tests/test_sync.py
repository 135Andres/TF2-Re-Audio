import copy
import hashlib
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from tf2reaudio import PROTOCOL_VERSION
from tf2reaudio.catalog import build
from tf2reaudio.group import Group
from tf2reaudio.store import Store
from tf2reaudio.sync import GroupStore, SyncServer, sync_once, Syncer, SyncError, join_group, check_host
from tests.test_store import wav


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cat = build(["sound/vo/soldier_medic01.mp3"])
        self.a = Group.create("Friends", "Alice", root=self.root / "a", device_id="a")
        self.sa = Store(self.root / "a" / "collection", "a", self.cat)
        self.host = SyncServer(self.sa, self.a, port=0).start()
        self.addCleanup(self.host.stop)
        self.b = join_group(self.host.url, self.a.create_invite(), "Bob", "b", self.root / "b")
        self.sb = Store(self.root / "b" / "collection", "b", self.cat)

    def record(self, store, group, freq=440):
        take = store.add_take("soldier/medic", wav(freq), group.member_id)
        store.set_active("soldier/medic", take)
        return take

    def request(self, path, method="GET", value=None, token=None, version=PROTOCOL_VERSION):
        raw = value if isinstance(value, bytes) else json.dumps(value).encode() if value is not None else None
        req = urllib.request.Request(self.host.url + path, data=raw, method=method,
                                     headers={"X-TF2RA-Protocol": str(version),
                                              "Content-Type": "application/octet-stream" if isinstance(value, bytes) else "application/json",
                                              "Authorization": "Bearer " + (token or self.b.token)})
        try:
            response = urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, response.headers, response.read()

    def envelope(self):
        return {"protocol_version": PROTOCOL_VERSION, "group_id": self.b.group_id,
                "group": self.b.snapshot(), "collection": self.sb.snapshot()}

    def test_exchange_and_etag_still_pushes_local_changes(self):
        first = self.record(self.sb, self.b)
        result = sync_once(self.sb, self.b, self.host.url, self.b.token)
        self.assertIsNone(result.error)
        self.assertEqual(self.sa.active("soldier/medic"), first)
        self.assertEqual(self.sa.blob(self.sb.take(first)["sha256"]), wav())
        self.assertNotIn("pending_share", self.sb.state("soldier/medic"))
        # A second GET is unchanged (304), but a new local recording still uploads.
        second = self.record(self.sb, self.b, 500)
        result = sync_once(self.sb, self.b, self.host.url, self.b.token)
        self.assertIsNone(result.error)
        self.assertEqual(self.sa.active("soldier/medic"), second)
        status, headers, _ = self.request("/api/snapshot")
        self.assertEqual(status, 200)
        req = urllib.request.Request(self.host.url + "/api/snapshot", headers={
            "Authorization": "Bearer " + self.b.token, "X-TF2RA-Protocol": str(PROTOCOL_VERSION),
            "If-None-Match": headers["ETag"]})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=3)
        self.assertEqual(ctx.exception.code, 304)
        ctx.exception.close()

    def test_auth_protocol_and_private_ui_not_exposed(self):
        self.assertEqual(self.request("/api/snapshot", token="wrong")[0], 401)
        self.assertEqual(self.request("/api/snapshot", version=999)[0], 426)
        self.assertEqual(self.request("/")[0], 404)
        self.assertEqual(self.request("/api/settings")[0], 404)
        self.assertEqual(self.request("/download/TF2ReAudio.zip")[0], 404)

    def test_invalid_hash_wav_and_unreferenced_blob_rejected(self):
        audio = wav()
        sha = hashlib.sha256(audio).hexdigest()
        self.assertEqual(self.request("/api/blob/" + "0" * 64, "PUT", audio)[0], 400)
        bad = b"not audio"
        self.assertEqual(self.request("/api/blob/" + hashlib.sha256(bad).hexdigest(), "PUT", bad)[0], 400)
        self.assertEqual(self.request("/api/blob/../../settings.json", "PUT", audio)[0], 404)
        self.assertEqual(self.request("/api/blob/" + sha)[0], 404)

    def test_unknown_line_foreign_records_and_changed_ids_rejected(self):
        self.record(self.sb, self.b)
        before = self.sa.snapshot()
        bad = self.envelope()
        bad["collection"]["takes"][0]["line_id"] = "../../bad"
        self.assertEqual(self.request("/api/snapshot", "POST", bad)[0], 400)
        bad = self.envelope()
        bad["collection"]["takes"][0]["author_member_id"] = self.a.member_id
        self.assertEqual(self.request("/api/snapshot", "POST", bad)[0], 400)
        self.assertEqual(self.sa.snapshot(), before)
        self.assertIsNone(sync_once(self.sb, self.b, self.host.url, self.b.token).error)
        bad = self.envelope()
        bad["collection"]["takes"][0]["created_at"] += 1
        self.assertEqual(self.request("/api/snapshot", "POST", bad)[0], 400)

    def test_wrong_group_and_forged_admin_change_rejected(self):
        bad = self.envelope()
        bad["group_id"] = "wrong"
        self.assertEqual(self.request("/api/snapshot", "POST", bad)[0], 400)
        bad = self.envelope()
        event = copy.deepcopy(bad["group"]["events"][0])
        event.update(event_id="forged", lamport=100, actor=self.a.member_id, kind="remove", member_id=self.a.member_id)
        bad["group"]["events"].append(event)
        self.assertEqual(self.request("/api/snapshot", "POST", bad)[0], 400)
        with self.assertRaises(SyncError):
            check_host(self.host.url, "wrong")

    def test_many_offline_retakes_and_foreign_retention_do_not_block_sharing(self):
        first = self.record(self.sa, self.a)
        self.assertIsNone(sync_once(self.sb, self.b, self.host.url, self.b.token).error)
        for frequency in range(450, 459):
            last = self.record(self.sb, self.b, frequency)
        self.assertTrue(self.sb.snapshot()["pruned"])
        self.sb = GroupStore(self.sb.root, self.sb.device_id, self.cat)
        result = sync_once(self.sb, self.b, self.host.url, self.b.token)
        self.assertIsNone(result.error, result.error)
        self.assertEqual(self.sa.active("soldier/medic"), last)
        self.assertIsNotNone(self.sa.take(first))
        self.assertNotIn("pending_share", self.sb.state("soldier/medic"))

    def test_member_cannot_prune_active_or_unknown_recording(self):
        take = self.record(self.sb, self.b)
        self.assertIsNone(sync_once(self.sb, self.b, self.host.url, self.b.token).error)
        for target in (take, "0" * 32):
            bad = self.envelope()
            bad["collection"]["pruned"].append(target)
            self.assertEqual(self.request("/api/snapshot", "POST", bad)[0], 400)
        self.assertIsNotNone(self.sa.take(take))

    def test_offline_and_worker_status(self):
        self.record(self.sb, self.b)
        worker = Syncer(self.sb, self.b, self.host.url, self.b.token)
        self.host.stop()
        result = worker.run_once()
        self.assertIsNotNone(result.error)
        self.assertEqual(worker.status, "host_offline")
        self.assertGreater(worker.pending_share, 0)
        self.assertIn("pending_share", self.sb.state("soldier/medic"))

    def test_redemption_rate_limit_ignores_spoofed_proxy_header(self):
        for i in range(6):
            status, _, _ = self.request("/api/redeem", "POST", {"code": "bad", "display_name": "Eve", "device_id": f"e{i}"})
        self.assertEqual(status, 429)


if __name__ == "__main__":
    unittest.main()
