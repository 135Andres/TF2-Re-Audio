import hashlib
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tf2reaudio import tunnel

FIXTURE = Path(__file__).parent / "fixtures" / "cloudflared_ok.txt"  # real cloudflared 2026.10.0 output
FIXTURE_URL = "https://formula-example-johnson-tabs.trycloudflare.com"


class FindUrlTest(unittest.TestCase):
    def test_real_output(self):
        text = FIXTURE.read_text(encoding="utf-8")
        self.assertEqual(tunnel.find_tunnel_url(text), FIXTURE_URL)

    def test_real_output_line_by_line(self):
        lines = FIXTURE.read_text(encoding="utf-8").splitlines()
        found = [u for u in map(tunnel.find_tunnel_url, lines) if u]
        self.assertEqual(found, [FIXTURE_URL])

    def test_ignores_api_host(self):
        # Representative error line (not recorded): cloudflared names the API host when the request fails.
        line = 'ERR failed to request quick Tunnel: Post "https://api.trycloudflare.com/tunnel": dial tcp: i/o timeout'
        self.assertIsNone(tunnel.find_tunnel_url(line))

    def test_no_url(self):
        self.assertIsNone(tunnel.find_tunnel_url("INF Requesting new quick Tunnel on trycloudflare.com..."))


class EnsureCloudflaredTest(unittest.TestCase):
    PAYLOAD = b"fake cloudflared binary"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.asset = "cloudflared-test"
        sha = hashlib.sha256(self.PAYLOAD).hexdigest()
        for p in (
            mock.patch.object(tunnel, "data_dir", return_value=self.dir),
            mock.patch.object(tunnel, "_asset_name", return_value=self.asset),
            mock.patch.dict(tunnel.CLOUDFLARED_SHA256, {self.asset: sha}),
        ):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self._tmp.cleanup()

    def _urlopen(self, data):
        return mock.patch.object(tunnel.urllib.request, "urlopen", return_value=io.BytesIO(data))

    def test_downloads_and_verifies(self):
        with self._urlopen(self.PAYLOAD) as m:
            path = tunnel.ensure_cloudflared()
        self.assertTrue(m.call_args[0][0].startswith("https://github.com/cloudflare/cloudflared/releases/download/"))
        self.assertEqual(path.parent, self.dir / "bin")
        self.assertEqual(path.read_bytes(), self.PAYLOAD)
        if sys.platform != "win32":
            self.assertTrue(os.access(path, os.X_OK))
        self.assertEqual(os.listdir(path.parent), [path.name])

    def test_cached_file_not_redownloaded(self):
        with self._urlopen(self.PAYLOAD):
            first = tunnel.ensure_cloudflared()
        with self._urlopen(b"") as m:
            self.assertEqual(tunnel.ensure_cloudflared(), first)
        m.assert_not_called()

    def test_bad_hash_deletes_and_raises(self):
        with self._urlopen(b"tampered"):
            with self.assertRaises(tunnel.TunnelError):
                tunnel.ensure_cloudflared()
        self.assertEqual(os.listdir(self.dir / "bin"), [])

    def test_corrupt_cache_is_replaced(self):
        with self._urlopen(self.PAYLOAD):
            path = tunnel.ensure_cloudflared()
        path.write_bytes(b"corrupt")
        with self._urlopen(self.PAYLOAD) as m:
            tunnel.ensure_cloudflared()
        m.assert_called_once()
        self.assertEqual(path.read_bytes(), self.PAYLOAD)

    def test_network_error(self):
        with mock.patch.object(tunnel.urllib.request, "urlopen", side_effect=OSError("no route")):
            with self.assertRaises(tunnel.TunnelError):
                tunnel.ensure_cloudflared()



class AssetNameTest(unittest.TestCase):
    def test_current_platform_is_pinned(self):
        if sys.platform in ("win32", "linux"):
            self.assertIn(tunnel._asset_name(), tunnel.CLOUDFLARED_SHA256)

    def test_unsupported_platform(self):
        with mock.patch.object(tunnel.sys, "platform", "darwin"):
            with self.assertRaises(tunnel.TunnelError):
                tunnel._asset_name()


class TunnelProcessTest(unittest.TestCase):
    """Runs a fake cloudflared (a Python child) so the reader/timeout/stop logic is tested without network."""

    def _run(self, script):
        real_popen = subprocess.Popen
        calls = []

        def fake_popen(cmd, **kw):
            calls.append(cmd)
            return real_popen([sys.executable, "-c", script, str(FIXTURE)], **kw)

        p1 = mock.patch.object(tunnel, "ensure_cloudflared", return_value=Path("cloudflared"))
        p2 = mock.patch.object(tunnel.subprocess, "Popen", side_effect=fake_popen)
        p1.start(), p2.start()
        self.addCleanup(p1.stop)
        self.addCleanup(p2.stop)
        return calls

    def test_start_returns_url_and_stop_kills(self):
        calls = self._run(
            "import sys, time\n"
            "sys.stderr.write(open(sys.argv[1], encoding='utf-8').read()); sys.stderr.flush()\n"
            "time.sleep(60)\n"
        )
        t = tunnel.Tunnel(8765)
        self.assertEqual(t.start(timeout=10), FIXTURE_URL)
        self.assertEqual(calls[0][1:], ["tunnel", "--url", "http://127.0.0.1:8765", "--no-autoupdate"])
        self.assertTrue(t.running)
        proc = t._proc
        t.stop()
        self.assertFalse(t.running)
        self.assertIsNotNone(proc.poll())
        t.stop()  # idempotent

    def test_timeout_raises_and_kills(self):
        self._run("import time; print('no link here', flush=True); time.sleep(60)")
        t = tunnel.Tunnel(1)
        start = time.monotonic()
        with self.assertRaises(tunnel.TunnelError):
            t.start(timeout=0.5)
        self.assertLess(time.monotonic() - start, 10)
        self.assertFalse(t.running)

    def test_early_exit_raises(self):
        self._run("import sys; print('ERR failed to request quick Tunnel', flush=True); sys.exit(1)")
        t = tunnel.Tunnel(1)
        start = time.monotonic()
        with self.assertRaises(tunnel.TunnelError) as cm:
            t.start(timeout=20)
        self.assertLess(time.monotonic() - start, 10)
        self.assertIn("failed to request quick Tunnel", str(cm.exception))


@unittest.skipUnless(os.environ.get("NET_TESTS"), "set NET_TESTS=1 to download cloudflared and open a real tunnel")
class RealTunnelTest(unittest.TestCase):
    def test_real_tunnel(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(tunnel, "data_dir", return_value=Path(tmp)):
                t = tunnel.Tunnel(8765)
                try:
                    url = t.start(timeout=60)
                    self.assertRegex(url, tunnel.URL_RE)
                    self.assertTrue(t.running)
                finally:
                    t.stop()
                self.assertFalse(t.running)


if __name__ == "__main__":
    unittest.main()
