import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tf2reaudio.catalog import build
from tf2reaudio.group import Group
from tf2reaudio.store import Store, ORIGINAL
from tf2reaudio.sync import SyncServer, sync_once, join_group, SyncError
from tests.test_store import wav


class IntegrationSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.catalog = build(["sound/vo/soldier_medic01.mp3"])
        self.groups = [Group.create("Friends", "A", root=self.root / "a", device_id="a")]
        self.stores = [Store(self.root / "a" / "collection", "a", self.catalog)]
        self.host = SyncServer(self.stores[0], self.groups[0]).start()
        self.addCleanup(self.host.stop)
        for name in ("b", "c"):
            self.groups.append(join_group(self.host.url, self.groups[0].create_invite(), name, name, self.root / name))
            self.stores.append(Store(self.root / name / "collection", name, self.catalog))
        for i in (1, 2):
            self.sync(i)

    def sync(self, index, host=None):
        result = sync_once(self.stores[index], self.groups[index], (host or self.host).url, self.groups[index].token)
        self.assertIsNone(result.error, result.error)
        return result

    def record(self, index, freq):
        take = self.stores[index].add_take("soldier/medic", wav(freq), self.groups[index].member_id)
        self.stores[index].set_active("soldier/medic", take)
        return take

    def test_offline_restart_reconnect_then_conflict_and_resolution(self):
        b = self.record(1, 440)
        c = self.record(2, 500)
        self.stores[1] = Store(self.root / "b" / "collection", "b", self.catalog)
        self.groups[1] = Group.load(self.root / "b")
        self.sync(1)
        self.sync(2)
        self.sync(1)
        for store in self.stores:
            self.assertIsNotNone(store.take(b))
            self.assertIsNotNone(store.take(c))
            self.assertEqual(store.conflicts(), ["soldier/medic"])
            self.assertEqual(store.blob(store.take(c)["sha256"]), wav(500))
        self.assertEqual(len({s.active("soldier/medic") for s in self.stores}), 1)
        self.stores[1].resolve("soldier/medic", b)
        self.sync(1)
        self.sync(2)
        for store in self.stores:
            self.assertEqual(store.active("soldier/medic"), b)
            self.assertEqual(store.conflicts(), [])

    def test_stale_take_does_not_undo_original_and_host_change_keeps_group(self):
        self.record(1, 440)
        self.sync(1)
        self.sync(2)
        self.stores[0].set_active("soldier/medic", ORIGINAL)
        self.sync(2)
        self.sync(1)
        self.assertEqual(self.stores[0].active("soldier/medic"), ORIGINAL)
        replacement = SyncServer(self.stores[2], self.groups[2]).start()
        self.addCleanup(replacement.stop)
        gid = self.groups[0].group_id
        for i in (0, 1):
            self.groups[i].set_host_url(replacement.url)
            self.sync(i, replacement)
            self.assertEqual(self.groups[i].group_id, gid)
            self.assertEqual(self.stores[i].active("soldier/medic"), ORIGINAL)

    def test_removal_propagates_to_replacement_host(self):
        self.groups[0].remove_member(self.groups[2].member_id)
        result = sync_once(self.stores[2], self.groups[2], self.host.url, self.groups[2].token)
        self.assertEqual(result.status, "auth_failed")
        self.sync(1)
        replacement = SyncServer(self.stores[1], self.groups[1]).start()
        self.addCleanup(replacement.stop)
        result = sync_once(self.stores[2], self.groups[2], replacement.url, self.groups[2].token)
        self.assertEqual(result.status, "auth_failed")

    def test_wire_disconnect_during_blob_and_lost_acknowledgment_retry(self):
        from tf2reaudio import sync as module
        take = self.record(0, 440)
        send = module._Handler._send
        def cut(handler, status, value=None, raw=None, etag=None):
            if raw and handler.path.startswith("/api/blob/"):
                handler.send_response(200)
                handler.send_header("Content-Length", str(len(raw)))
                handler.end_headers()
                handler.wfile.write(raw[:len(raw) // 2])
                handler.wfile.flush()
                handler.connection.shutdown(socket.SHUT_RDWR)
                return
            return send(handler, status, value, raw, etag)
        before = self.stores[1].snapshot()
        with patch.object(module._Handler, "_send", new=cut):
            result = sync_once(self.stores[1], self.groups[1], self.host.url, self.groups[1].token)
        self.assertIsNotNone(result.error)
        self.assertEqual(self.stores[1].snapshot(), before)
        self.sync(1)
        self.assertEqual(self.stores[1].active("soldier/medic"), take)
        new_take = self.record(1, 500)
        request = module._request
        def lost_ack(url, path, *args, **kwargs):
            response = request(url, path, *args, **kwargs)
            if path == "/api/snapshot" and len(args) >= 2 and args[1] == "POST":
                raise SyncError("The connection closed after commit.")
            return response
        with patch.object(module, "_request", side_effect=lost_ack):
            result = sync_once(self.stores[1], self.groups[1], self.host.url, self.groups[1].token)
        self.assertIsNotNone(result.error)
        self.assertEqual(self.stores[0].active("soldier/medic"), new_take)
        self.assertIn("pending_share", self.stores[1].state("soldier/medic"))
        self.sync(1)
        self.assertNotIn("pending_share", self.stores[1].state("soldier/medic"))

    def test_interrupted_download_never_commits_metadata_and_next_attempt_succeeds(self):
        take = self.record(0, 440)
        from tf2reaudio import sync as module
        original = module._request
        def interrupted(url, path, *args, **kwargs):
            if path.startswith("/api/blob/"):
                raise SyncError("The transfer was interrupted.")
            return original(url, path, *args, **kwargs)
        before = self.stores[1].snapshot()
        with patch.object(module, "_request", side_effect=interrupted):
            result = sync_once(self.stores[1], self.groups[1], self.host.url, self.groups[1].token)
        self.assertIsNotNone(result.error)
        self.assertEqual(self.stores[1].snapshot(), before)
        self.sync(1)
        self.assertEqual(self.stores[1].active("soldier/medic"), take)
        self.assertEqual(self.stores[1].blob(self.stores[1].take(take)["sha256"]), wav(440))


if __name__ == "__main__":
    unittest.main()
