import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tf2reaudio import diagnostics
from tf2reaudio.diagnostics import (DiagnosticRecorder, DiagnosticsError, SEGMENT_CAP, build_bundle, clean_event,
                                    save_bundle)

SECRETS = ["hunter2-password", "C:\\Users\\alice\\secret", "/home/alice/secret", "https://evil.example/#code",
           "192.168.1.20", "inv-CODE-123", "Alice\r\nInjected", "ñandú" * 500]
ENTRIES = {"summary.txt", "manifest.json", "events.jsonl", "test-results.json"}


def checks():
    return diagnostics.base_checks("cli")


def entries(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


class DiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rec = DiagnosticRecorder(self.root)
        self.logs = self.root / "logs"

    def disk(self):
        return b"".join(p.read_bytes() for p in self.logs.glob("events.jsonl*"))

    def assert_no_secrets(self, data):
        for secret in SECRETS:
            self.assertNotIn(secret.encode("utf-8"), data)
            self.assertNotIn(secret.encode("ascii", "backslashreplace"), data)

    def test_unknown_fields_and_sensitive_strings_never_reach_disk_or_export(self):
        for secret in SECRETS:
            self.rec.record("server", "api", "failed", secret)
            self.rec.record("server", secret, "failed", "ok")
            self.rec.record(secret, "api", "failed", "ok")
            self.rec.record("server", "api", "failed", "ok", operation_id=secret)
            self.rec.record("server", "api", "failed", "ok", details={"route": secret})
            self.rec.record("server", "api", "failed", "ok", details={"password": secret, "status": 500})
            self.rec.record("server", "api", "failed", "unexpected_error", error=RuntimeError(secret))
            self.rec.record("server", "api", "failed", "write_denied",
                            error=PermissionError(13, secret, secret))
        self.assert_no_secrets(self.disk())
        snap = self.rec.snapshot()
        self.assertTrue(snap["events"])
        self.assertGreater(snap["rejected"], 0)
        bad = dict(snap["events"][0], extra=SECRETS[0], details={"route": "take", "url": SECRETS[3]})
        data = build_bundle({**snap, "events": snap["events"] + [bad]}, checks(), [])
        files = entries(data)
        self.assertEqual(set(files), ENTRIES)
        for content in files.values():
            self.assert_no_secrets(content)
        events = [json.loads(line) for line in files["events.jsonl"].splitlines()]
        self.assertTrue(all(set(e) <= {"v", "ts", "session", "seq", "component", "action", "outcome", "code", "op",
                                       "details", "error"} for e in events))
        self.assertIn({"type": "PermissionError", "errno": 13}, [
            {k: v for k, v in e.get("error", {}).items() if k != "frames"} for e in events])
        with self.assertRaises(DiagnosticsError):
            build_bundle(snap, {**checks(), "path": "/home/alice"}, [])
        with self.assertRaises(DiagnosticsError):
            build_bundle(snap, checks(), [{"step": "save", "outcome": "failed", "note": SECRETS[0]}])

    def test_rotation_bounds_four_files(self):
        for i in range(6000):
            self.rec.record("server", "api", "failed", "unexpected_error", details={"count": i, "route": "take"},
                            error=ValueError())
        files = sorted(p.name for p in self.logs.glob("events.jsonl*"))
        self.assertEqual(files, ["events.jsonl", "events.jsonl.1", "events.jsonl.2", "events.jsonl.3"])
        for name in files:
            self.assertLessEqual((self.logs / name).stat().st_size, SEGMENT_CAP)
        for line in self.disk().splitlines():
            self.assertLessEqual(len(line), diagnostics.MAX_EVENT)
            clean_event(json.loads(line))

    def test_threads_and_two_processes_do_not_corrupt_lines(self):
        script = ("import sys; from pathlib import Path; from tf2reaudio.diagnostics import DiagnosticRecorder as R\n"
                  "r = R(Path(sys.argv[1]))\n"
                  "for i in range(300): r.record('cli', 'doctor', 'ok', 'ok', details={'count': i})\n")
        child = subprocess.Popen([sys.executable, "-c", script, str(self.root)],
                                 cwd=Path(__file__).resolve().parent.parent)
        threads = [threading.Thread(target=lambda: [self.rec.record("server", "api", "ok", "ok") for _ in range(100)])
                   for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(child.wait(30), 0)
        for line in self.disk().splitlines():
            clean_event(json.loads(line))
        snap = self.rec.snapshot()
        self.assertEqual(snap["omitted_events"], 0)
        self.assertEqual(sum(e["session"] == self.rec.session for e in snap["events"]), 400)

    def test_failed_replace_preserves_primary_and_memory_events(self):
        self.rec.record("server", "api", "ok", "ok")
        before = self.disk()
        with mock.patch("tf2reaudio.diagnostics.atomic_write", side_effect=OSError(28, "No space left")):
            self.rec.record("server", "api", "failed", "disk_full")  # must not raise
            snap = self.rec.snapshot()
        self.assertEqual(self.disk(), before)
        self.assertEqual(snap["persistence"], "degraded")
        self.assertEqual(snap["last_errno"], 28)
        self.assertEqual(snap["events"][-1]["code"], "disk_full")
        self.assertIn(b"degraded, errno 28", entries(build_bundle(snap, checks(), []))["summary.txt"])
        self.assertEqual(self.rec.snapshot()["persistence"], "ok")  # pending events flushed later
        self.assertIn(b"disk_full", self.disk())

    def test_readonly_logs_do_not_break_record(self):
        with mock.patch("tf2reaudio.diagnostics.atomic_write", side_effect=PermissionError(13, "denied")), \
                mock.patch.object(Path, "mkdir", side_effect=PermissionError(13, "denied")):
            other = DiagnosticRecorder(self.root / "elsewhere")
            other.record("cli", "doctor", "ok", "ok")
            self.assertEqual(other.snapshot()["persistence"], "degraded")
            self.assertEqual(len(other.snapshot()["events"]), 1)

    def test_export_during_rotation_is_valid(self):
        stop = threading.Event()

        def writer():
            while not stop.is_set():
                self.rec.record("server", "api", "ok", "ok", details={"route": "take"})
        thread = threading.Thread(target=writer)
        thread.start()
        try:
            for _ in range(20):
                files = entries(build_bundle(DiagnosticRecorder(self.root).snapshot(), checks(), []))
                for line in files["events.jsonl"].splitlines():
                    clean_event(json.loads(line))
        finally:
            stop.set()
            thread.join()

    def test_oversized_corrupt_or_symlinked_logs_are_omitted(self):
        self.rec.record("server", "api", "ok", "ok")
        (self.logs / "events.jsonl.1").write_bytes(b"{not json}\n" + b"x" * 5000 + b"\n" + b'{"v":1')
        (self.logs / "events.jsonl.2").write_bytes(b"x" * (SEGMENT_CAP + 1))
        target = self.root / "outside.txt"
        target.write_text(json.dumps(self.rec.snapshot()["events"][0]) + "\n", encoding="utf-8")
        try:
            (self.logs / "events.jsonl.3").symlink_to(target)
        except OSError:
            (self.logs / "events.jsonl.3").write_bytes(b"x" * (SEGMENT_CAP + 1))  # Windows without symlink rights
        snap = self.rec.snapshot()
        self.assertEqual(snap["omitted_events"], 3)
        self.assertEqual(snap["omitted_segments"], 2)
        self.assertEqual(len(snap["events"]), 1)
        self.assertIn(b"unreadable log files: 2", entries(build_bundle(snap, checks(), []))["summary.txt"])

    def test_bundle_retention_keeps_three_owned_files(self):
        reports = self.root / "reports"
        reports.mkdir()
        (reports / "notes.txt").write_text("keep", encoding="utf-8")
        (reports / "TF2ReAudio-diagnostics-mine.zip").write_text("keep", encoding="utf-8")
        old = [reports / f"TF2ReAudio-diagnostics-2020010{i}T000000Z-abcdef.zip" for i in range(1, 5)]
        for path in old:
            path.write_bytes(b"old")
        data = build_bundle(self.rec.snapshot(), checks(), [{"step": "save", "outcome": "failed", "reason": "write_denied"}])
        saved = save_bundle(self.root, data)
        self.assertEqual(saved.read_bytes(), data)
        names = {p.name for p in reports.iterdir()}
        self.assertEqual(names, {"notes.txt", "TF2ReAudio-diagnostics-mine.zip", old[2].name, old[3].name, saved.name})
        results = json.loads(entries(data)["test-results.json"])["results"]
        self.assertEqual(len(results), len(diagnostics.STEPS))
        self.assertIn({"step": "save", "outcome": "failed", "source": "tester", "reason": "write_denied"}, results)
        self.assertIn({"step": "heard_in_tf2", "outcome": "not_tested", "source": "default"}, results)
        with mock.patch("tf2reaudio.diagnostics.atomic_write", side_effect=PermissionError(13, "Permission denied")):
            with self.assertRaisesRegex(DiagnosticsError, "Permission denied"):
                save_bundle(self.root, data)

    def test_bundle_stays_under_cap(self):
        many = [dict(clean_event({"v": 1, "ts": "2026-01-01T00:00:00Z", "session": "0" * 16, "seq": i + 1,
                                  "component": "server", "action": "api", "outcome": "failed",
                                  "code": "unexpected_error", "op": os.urandom(8).hex(),
                                  "error": {"type": "ValueError", "frames": [["tf2reaudio.server", "f" + os.urandom(20).hex(), j + 1] for j in range(20)]}}))
                for i in range(6000)]
        data = build_bundle({"events": many, "persistence": "ok"}, checks(), [])
        self.assertLessEqual(len(data), diagnostics.MAX_ZIP)
        self.assertGreater(json.loads(entries(data)["manifest.json"])["omitted_events"], 0)


if __name__ == "__main__":
    unittest.main()
