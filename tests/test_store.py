import itertools
import json
import math
import os
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tf2reaudio.audio import RATE, InvalidWav
from tf2reaudio.catalog import build
from tf2reaudio.store import KEEP_INACTIVE, ORIGINAL, Store, StoreError

FIXTURE = Path(__file__).parent / "fixtures" / "vo_index.txt"
LINE = "soldier/medic"
OTHER = "scout/thanks"


def wav(freq=440) -> bytes:
    """A distinct valid take per frequency."""
    n = RATE // 10
    pcm = struct.pack(f"<{n}h", *(int(8000 * math.sin(2 * math.pi * freq * i / RATE)) for i in range(n)))
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, RATE, RATE * 2, 2, 16)
    body = b"WAVE" + fmt + struct.pack("<4sI", b"data", len(pcm)) + pcm
    return b"RIFF" + struct.pack("<I", len(body)) + body


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = build(FIXTURE.read_text(encoding="utf-8").split())

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._n = 0

    def tearDown(self):
        self._tmp.cleanup()

    def store(self, device, name=None) -> Store:
        return Store(self.tmp / (name or device), device, catalog=self.catalog)

    def take(self, store, line=LINE, activate=True) -> str:
        self._n += 1
        take_id = store.add_take(line, wav(300 + 10 * self._n), "member1")
        if activate:
            store.set_active(line, take_id)
        return take_id

    def files(self, store):
        return sorted(p.name for p in store.root.rglob("*"))


class LocalTest(Base):
    def test_set_active_history_and_reopen(self):
        s = self.store("a")
        self.assertIsNone(s.active(LINE))
        t1 = self.take(s)
        t2 = self.take(s, activate=False)
        self.assertEqual(s.active(LINE), t1)
        hist = s.history(LINE)
        self.assertEqual([h["take_id"] for h in hist], [t1, t2])
        self.assertEqual([h["active"] for h in hist], [True, False])
        self.assertEqual(hist[0]["author_member_id"], "member1")
        again = Store(s.root, "a", catalog=self.catalog)
        self.assertEqual(again.snapshot(), s.snapshot())
        self.assertEqual(again.state(LINE), s.state(LINE))

    def test_undo_and_redo(self):
        s = self.store("a")
        self.assertIsNone(s.undo(LINE))
        t1 = self.take(s)
        t2 = self.take(s)
        s.undo(LINE)
        self.assertEqual(s.active(LINE), t1)
        s.undo(LINE)  # undoing the undo is a redo
        self.assertEqual(s.active(LINE), t2)
        s.set_active(LINE, ORIGINAL)
        s.undo(LINE)
        self.assertEqual(s.active(LINE), t2)
        s2 = self.store("b")
        self.take(s2)
        s2.undo(LINE)
        self.assertEqual(s2.active(LINE), ORIGINAL)
        self.assertEqual(s.conflicts(), [])

    def test_line_validation(self):
        s = self.store("a")
        for bad in ["soldier/nope", "", None, "soldier/medic#04", "soldier/medic#2", "soldier/medic#00",
                    "soldier/medic#0x", "soldier/medic#01#01", "../../x"]:
            with self.assertRaises(StoreError, msg=bad):
                s.add_take(bad, wav(), "m")
        t = s.add_take("soldier/medic#03", wav(), "m")
        s.set_active("soldier/medic#03", t)
        s.add_take("soldier/raw/mvm/norm/soldier_mvm_medic01", wav(), "m")
        with self.assertRaises(StoreError):
            s.set_active(LINE, t)  # take of another line
        with self.assertRaises(StoreError):
            s.set_active(LINE, "0" * 32)
        with self.assertRaises(InvalidWav):
            s.add_take(LINE, b"RIFFnope", "m")
        with self.assertRaises(StoreError):
            s.add_take(LINE, wav(), "bad/member")

    def test_states(self):
        s = self.store("a")
        self.assertEqual(s.state(LINE), set())
        t1 = self.take(s)
        self.assertEqual(s.state(LINE), {"saved_locally", "pending_share", "pending_apply"})
        self.assertEqual(s.effective(LINE), t1)
        s.mark_shared([e["event_id"] for e in s.snapshot()["events"]] + [t1])
        s.mark_applied()
        self.assertEqual(s.state(LINE), {"saved_locally", "applied_requested"})
        s.set_local_override(LINE, True)
        self.assertEqual(s.effective(LINE), None)
        self.assertEqual(s.active(LINE), t1)
        self.assertEqual(s.state(LINE), {"saved_locally", "local_override", "pending_apply"})
        self.assertNotIn("override", json.dumps(s.snapshot()))
        reopened = Store(s.root, "a", catalog=self.catalog)
        self.assertIn("local_override", reopened.state(LINE))
        self.assertEqual(s.lines(), [LINE])

    def test_pruning_keeps_five_inactive_and_tombstones(self):
        s = self.store("a")
        old = self.store("b")
        takes = [self.take(s) for _ in range(2)]
        old.merge(s.snapshot())
        stale = old.snapshot()
        takes += [self.take(s) for _ in range(7)]
        kept = [h["take_id"] for h in s.history(LINE)]
        # active + the one undo returns to + KEEP_INACTIVE more
        self.assertEqual(kept, takes[-(KEEP_INACTIVE + 2):])
        snap = s.snapshot()
        self.assertEqual(set(snap["pruned"]), set(takes[:2]))
        for t in takes[:2]:
            self.assertFalse(any(f.startswith(t) for f in self.files(s)))
        self.assertEqual(len(list((s.root / "blobs").iterdir())), KEEP_INACTIVE + 2)
        self.assertEqual(s.merge(stale), [])  # the stale copy does not bring them back
        self.assertEqual([h["take_id"] for h in s.history(LINE)], kept)
        old.merge(snap)  # and they vanish on the stale device too
        self.assertIsNone(old.take(takes[0]))
        self.assertEqual(old.snapshot(), snap)

    def test_no_pruning_in_conflict(self):
        a, b = self.store("a"), self.store("b")
        base = self.take(a)
        b.merge(a.snapshot())
        self.take(a)
        self.take(b)
        a.merge(b.snapshot())
        self.assertEqual(a.conflicts(), [LINE])
        for _ in range(8):
            self.take(a, activate=False)
        self.assertEqual(len(a.history(LINE)), 11)
        self.assertIn(base, [h["take_id"] for h in a.history(LINE)])

    def test_corrupt_collection_restores_backup(self):
        s = self.store("a")
        t1 = self.take(s)
        good = s.snapshot()
        self.take(s, OTHER, activate=False)  # one write: the backup now holds `good`
        (s.root / "collection.json").write_bytes(b'{"takes": [')
        r = Store(s.root, "a", catalog=self.catalog)
        self.assertIsNotNone(r.warning)
        self.assertEqual(r.snapshot(), good)
        self.assertEqual(r.active(LINE), t1)
        self.take(r)  # the next write must not rotate the corrupt file into the backup
        json.loads((s.root / "collection.json.bak").read_bytes())
        self.assertIsNone(Store(s.root, "a", catalog=self.catalog).warning)

    def test_corrupt_without_backup_raises(self):
        root = self.tmp / "x"
        root.mkdir()
        (root / "collection.json").write_bytes(b"\xff\xfe garbage")
        with self.assertRaises(StoreError):
            Store(root, "a")

    def test_failed_write_leaves_no_temp_files(self):
        s = self.store("a")
        t1 = self.take(s)
        t2 = self.take(s, activate=False)
        before = s.snapshot()
        with mock.patch("tf2reaudio.util.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                s.set_active(LINE, t2)
        self.assertFalse([f for f in self.files(s) if f.endswith(".tmp")])
        self.assertEqual(s.active(LINE), t1)
        self.assertEqual(s.snapshot(), before)
        self.assertEqual(Store(s.root, "a", catalog=self.catalog).snapshot(), before)


class MergeTest(Base):
    def converge(self, *stores):
        for x in stores:
            for y in stores:
                y.merge(x.snapshot())

    def test_commutative_and_idempotent(self):
        a, b, c = self.store("a"), self.store("b"), self.store("c")
        self.take(a)
        self.converge(a, b, c)
        self.take(a)
        self.take(b)  # concurrent with a's second take
        self.take(c, OTHER)
        c.set_active(OTHER, ORIGINAL)
        snaps = [a.snapshot(), b.snapshot(), c.snapshot()]
        results = []
        for i, order in enumerate(itertools.permutations(snaps)):
            fresh = self.store(f"p{i}")
            for snap in order:
                fresh.merge(snap)
            results.append((fresh.snapshot(), fresh.active(LINE), fresh.active(OTHER), fresh.conflicts()))
            self.assertEqual(fresh.merge(snaps[0]), [])  # merging again changes nothing
            self.assertEqual(fresh.snapshot(), results[-1][0])
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(results[0][3], [LINE])
        ab, ba = self.store("ab"), self.store("ba")
        ab.merge(snaps[0]); ab.merge(snaps[1])
        ba.merge(snaps[1]); ba.merge(snaps[0])
        self.assertEqual(ab.snapshot(), ba.snapshot())

    def test_concurrent_conflict_keeps_both_and_same_winner(self):
        a, b = self.store("a"), self.store("b")
        self.take(a)
        b.merge(a.snapshot())
        ta = self.take(a)
        tb = self.take(b)
        self.converge(a, b)
        for s in (a, b):
            self.assertEqual(s.conflicts(), [LINE])
            self.assertIn("conflict", s.state(LINE))
            self.assertTrue({ta, tb} <= {h["take_id"] for h in s.history(LINE)})
        self.assertEqual(a.active(LINE), tb)  # same lamport, device "b" > "a"
        self.assertEqual(b.active(LINE), tb)
        a.resolve(LINE, ta)
        self.converge(a, b)
        for s in (a, b):
            self.assertEqual(s.conflicts(), [])
            self.assertEqual(s.active(LINE), ta)
            self.assertIn(tb, [h["take_id"] for h in s.history(LINE)])

    def test_two_edits_against_one_is_still_a_conflict(self):
        a, b = self.store("a"), self.store("b")
        self.take(a)
        b.merge(a.snapshot())
        self.take(a)
        self.take(a)  # higher lamport and descends from a's branch, but never saw b's edit
        self.take(b)
        self.converge(a, b)
        self.assertEqual(a.conflicts(), [LINE])
        b.set_active(LINE, ORIGINAL)  # any new event after merging resolves
        self.converge(a, b)
        self.assertEqual((a.conflicts(), a.active(LINE)), ([], ORIGINAL))

    def test_stale_device_does_not_revert_original_restore(self):
        a, b = self.store("a"), self.store("b")
        self.take(a)
        stale = a.snapshot()
        b.merge(stale)
        b.set_active(LINE, ORIGINAL)
        a.merge(stale)
        b.merge(stale)
        a.merge(b.snapshot())
        b.merge(a.snapshot())
        for s in (a, b):
            self.assertEqual(s.active(LINE), ORIGINAL)
            self.assertEqual(s.conflicts(), [])
        s = self.store("c")
        s.merge(b.snapshot())
        s.merge(stale)
        self.assertEqual(s.active(LINE), ORIGINAL)

    def test_missing_blob_and_put_blob(self):
        a, b = self.store("a"), self.store("b")
        t = self.take(a)
        sha = a.take(t)["sha256"]
        self.assertEqual(b.merge(a.snapshot()), [LINE])
        self.assertEqual(b.active(LINE), t)
        self.assertEqual(b.missing_blobs(), [sha])
        self.assertFalse(b.has_blob(sha))
        with self.assertRaises(KeyError):
            b.blob(sha)
        with self.assertRaises(InvalidWav):
            b.put_blob(b"nope")
        with self.assertRaises(StoreError):
            b.put_blob(wav(12345))  # valid audio that no take uses
        self.assertEqual(b.put_blob(a.blob(sha)), sha)
        self.assertEqual(b.missing_blobs(), [])
        self.assertEqual(b.blob(sha), a.blob(sha))
        for bad in ["../" * 5 + "etc/passwd", "A" * 64, None]:
            self.assertFalse(b.has_blob(bad))
            with self.assertRaises(StoreError):
                b.blob(bad)

    def test_malicious_snapshots_rejected(self):
        a, b = self.store("a"), self.store("b")
        t = self.take(a)
        self.take(b, OTHER)
        good = a.snapshot()
        take, event = good["takes"][0], good["events"][0]

        def with_take(**kw):
            return {"takes": [dict(take, **kw)], "events": [], "pruned": []}

        def with_event(**kw):
            return {"takes": [take], "events": [dict(event, **kw)], "pruned": []}

        bad = [
            None, [], "x", {"takes": {}}, {"events": [1]}, {"pruned": ["../x"]},
            with_take(take_id="../../evil"), with_take(take_id=1), with_take(sha256="../../../etc/passwd"),
            with_take(sha256="A" * 64), with_take(sha256=["x"]), with_take(line_id="soldier/nope"),
            with_take(line_id="soldier/medic#09"), with_take(line_id=None), with_take(lamport="1"),
            with_take(lamport=True), with_take(lamport=-1), with_take(lamport=2**60), with_take(created_at=1.5),
            with_take(device_id="a/b"), with_take(author_member_id=""),
            with_event(event_id="x"), with_event(target="../x"), with_event(target=None),
            with_event(parent_event_id=5), with_event(merges="abc"), with_event(merges=[None]),
            with_event(line_id=OTHER), with_event(line_id="nope"), with_event(lamport=None),
            with_event(device_id={"a": 1}),
            {"takes": [take], "events": [event, {"event_id": "f" * 32}], "pruned": []},
        ]
        before, files = b.snapshot(), sorted(p.read_bytes() for p in b.root.rglob("*") if p.is_file())
        for snap in bad:
            with self.assertRaises(StoreError, msg=repr(snap)):
                b.merge(snap)
        self.assertEqual(b.snapshot(), before)
        self.assertEqual(sorted(p.read_bytes() for p in b.root.rglob("*") if p.is_file()), files)
        self.assertEqual(b.merge(good), [LINE])
        self.assertEqual(b.active(LINE), t)


class ZipTest(Base):
    def test_roundtrip(self):
        a, b = self.store("a"), self.store("b")
        self.take(a)
        self.take(a, OTHER)
        path = self.tmp / "export.zip"
        a.export_zip(path)
        self.assertEqual(b.import_zip(path), sorted([LINE, OTHER]))
        self.assertEqual(b.snapshot(), a.snapshot())
        self.assertEqual(b.missing_blobs(), [])

    def test_bad_entries_rejected(self):
        a, b = self.store("a"), self.store("b")
        self.take(a)
        snap = json.dumps(a.snapshot())
        sha = a.snapshot()["takes"][0]["sha256"]
        cases = [
            {"collection.json": snap, "../evil.wav": b"x"},
            {"collection.json": snap, "blobs/../../evil.wav": b"x"},
            {"collection.json": snap, "/abs/evil.wav": b"x"},
            {"collection.json": snap, "blobs\\..\\evil.wav": b"x"},
            {"collection.json": snap, f"blobs/{sha}.wav": wav(1)},  # hash mismatch
            {"collection.json": "{"},
            {f"blobs/{sha}.wav": a.blob(sha)},
        ]
        before = b.snapshot()
        for i, entries in enumerate(cases):
            path = self.tmp / f"bad{i}.zip"
            with zipfile.ZipFile(path, "w") as z:
                for name, data in entries.items():
                    z.writestr(name, data)
            with self.assertRaises(StoreError, msg=list(entries)):
                b.import_zip(path)
            self.assertEqual(b.snapshot(), before)
        (self.tmp / "notzip.zip").write_bytes(b"hello")
        with self.assertRaises(StoreError):
            b.import_zip(self.tmp / "notzip.zip")
        self.assertFalse((self.tmp / "evil.wav").exists())
        self.assertEqual(sorted(os.listdir(b.root / "blobs")), [])


if __name__ == "__main__":
    unittest.main()
