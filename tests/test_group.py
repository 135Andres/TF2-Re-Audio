import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tf2reaudio.group import Group, GroupError, validate_url
from tf2reaudio.util import atomic_write


class GroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.a = Group.create("Friends", "Alice", root=self.root / "a", device_id="device-a")

    def join(self, name="Bob", device="device-b"):
        member, token = self.a.redeem_invite(self.a.create_invite(), name, device)
        return Group.join(self.a.snapshot(), member, token, device, self.root / device)

    def test_host_links_limited_to_quick_tunnel_or_loopback(self):
        self.assertEqual(validate_url(" HTTPS://Formula-Tabs.trycloudflare.com/ "), "https://formula-tabs.trycloudflare.com")
        self.assertEqual(validate_url("https://a.trycloudflare.com:443"), "https://a.trycloudflare.com")
        self.assertEqual(validate_url("http://127.0.0.1:8441/"), "http://127.0.0.1:8441")
        for bad in ("https://127.0.0.1:8443", "https://[::1]", "https://169.254.169.254", "https://192.168.1.5",
                    "https://api.trycloudflare.com", "https://a.trycloudflare.com:8443", "https://a.trycloudflare.com.evil.test",
                    "https://evil-trycloudflare.com", "https://user:pw@a.trycloudflare.com", "https://a.trycloudflare.com/?x=1",
                    "https://a.trycloudflare.com/#x", "https://a.trycloudflare.com/api", "http://a.trycloudflare.com",
                    "http://127.0.0.1", "http://localhost:8441", "http://[::1]:8441", "ftp://a.trycloudflare.com",
                    "https://a.trycloudflare.com\\@evil.test", "https://a_b.trycloudflare.com", None, ""):
            with self.subTest(bad=bad), self.assertRaises(GroupError):
                validate_url(bad)

    def test_identity_and_secret_survive_restart_but_not_replication(self):
        loaded = Group.load(self.root / "a")
        self.assertEqual(loaded.group_id, self.a.group_id)
        self.assertTrue(loaded.is_admin(loaded.member_id))
        self.assertEqual(loaded.verify_token(loaded.token), loaded.member_id)
        self.assertIsNone(loaded.verify_token("wrong"))
        self.assertNotIn(loaded.token, json.dumps(loaded.snapshot()))
        self.assertEqual(loaded.snapshot(), self.a.snapshot())

    def test_invitation_single_use_expiry_and_hash_only(self):
        with patch("tf2reaudio.group.time.time", return_value=100):
            code = self.a.create_invite(ttl_hours=1)
            self.assertNotIn(code, json.dumps(self.a.snapshot()))
        with patch("tf2reaudio.group.time.time", return_value=3701):
            with self.assertRaisesRegex(GroupError, "expired"):
                self.a.redeem_invite(code, "Bob", "b")
        code = self.a.create_invite()
        self.a.redeem_invite(code, "Bob", "b")
        with self.assertRaisesRegex(GroupError, "used"):
            self.a.redeem_invite(code, "Eve", "c")

    def test_member_permissions_promotion_and_revocation(self):
        b = self.join()
        for action in (b.create_invite, lambda: b.remove_member(self.a.member_id),
                       lambda: b.promote(b.member_id), lambda: b.set_suggested_voice("soldier", b.member_id)):
            with self.assertRaisesRegex(GroupError, "admin"):
                action()
        self.a.promote(b.member_id)
        b.merge(self.a.snapshot())
        self.assertTrue(b.is_admin(b.member_id))
        stale = b.snapshot()
        self.a.remove_member(b.member_id)
        b.merge(self.a.snapshot())
        b.merge(stale)
        self.assertIsNone(b.verify_token(b.token))
        self.assertFalse(b.is_admin(b.member_id))

    def test_no_last_admin_removal_and_cast_validation(self):
        with self.assertRaises(GroupError):
            self.a.remove_member(self.a.member_id)
        b = self.join()
        self.a.set_suggested_voice("soldier", b.member_id)
        self.assertEqual(self.a.suggested_voices()["soldier"], b.member_id)
        with self.assertRaises(GroupError):
            self.a.set_suggested_voice("../../bad", b.member_id)

    def test_merge_rejects_wrong_group_changed_ids_and_forged_admin(self):
        b = self.join()
        other = Group.create("Other", "Eve", root=self.root / "other")
        with self.assertRaises(GroupError):
            self.a.merge(other.snapshot())
        bad = copy.deepcopy(b.snapshot())
        bad["events"][0]["name"] = "Forged"
        with self.assertRaises(GroupError):
            self.a.merge(bad)
        self.a.promote(b.member_id)
        b.merge(self.a.snapshot())
        b.create_invite()
        with self.assertRaises(GroupError):
            self.a.merge(b.snapshot(), actor="not-bob")

    def test_atomic_failure_preserves_memory_and_recovery(self):
        before = self.a.snapshot()
        with patch("tf2reaudio.group.atomic_write", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(GroupError, "save"):
                self.a.create_invite()
        self.assertEqual(self.a.snapshot(), before)
        self.a.create_invite()
        atomic_write(self.root / "a" / "group.json", b"broken")
        recovered = Group.load(self.root / "a")
        self.assertEqual(recovered.group_id, self.a.group_id)
        self.assertIsNotNone(recovered.warning)

    def test_future_schema_never_falls_back_or_overwrites(self):
        path = self.root / "a" / "group.json"
        record = json.loads(path.read_bytes())
        record["format_version"] = 999
        raw = json.dumps(record).encode()
        atomic_write(path, raw)
        with self.assertRaisesRegex(GroupError, "Update"):
            Group.load(self.root / "a")
        self.assertEqual(path.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
