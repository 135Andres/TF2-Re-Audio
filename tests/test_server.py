import io
import http.client
import json
import socket
import sys
from contextlib import redirect_stdout
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock
from concurrent.futures import ThreadPoolExecutor

from tests.fixtures.make_vpk import make_vpk
from tests.test_rcon import FakeRcon
from tests.test_store import wav
from tf2reaudio.server import LocalApp, LocalServer, InstanceLock, existing_instance, run_local
from tf2reaudio.rcon import RconNotRunning
from tf2reaudio.util import atomic_write


NAMES = [
    "sound/vo/soldier_medic01.mp3",
    "sound/vo/soldier_medic02.mp3",
    "sound/vo/soldier_medic03.mp3",
    "sound/vo/soldier_thanks01.mp3",
]


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rcon_patch = mock.patch("tf2reaudio.game.rcon.send", side_effect=RconNotRunning("Game closed."))
        self.rcon_patch.start()
        self.addCleanup(self.rcon_patch.stop)
        installs = mock.patch("tf2reaudio.steam.find_installs", return_value=[])
        installs.start()
        self.addCleanup(installs.stop)
        self.root = Path(self.tmp.name) / "data"
        self.tf = Path(self.tmp.name) / "Team Fortress 2" / "tf"
        self.tf.mkdir(parents=True)
        (self.tf / "gameinfo.txt").write_text("x", encoding="utf-8")
        make_vpk(self.tf / "tf2_sound_vo_english_dir.vpk", {name: b"original" for name in NAMES})
        self.app = LocalApp(self.tf, self.root)
        self.server = LocalServer(self.app, port=0)
        self.server.start()
        self.addCleanup(self.server.stop)

    def request(self, path, method="GET", body=None, content_type="application/json", headers=None):
        request = urllib.request.Request(self.server.url + path, method=method, data=body)
        if body is not None:
            request.add_header("Content-Type", content_type)
        if method == "POST":
            request.add_header("X-TF2RA", "1")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, response.headers, response.read()

    def json(self, path, method="GET", payload=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        status, _, data = self.request(path, method, body)
        return status, json.loads(data)

    def test_ping_state_and_catalog(self):
        status, data = self.json("/api/ping")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        status, data = self.json("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(data["tf2"], "not_configured")  # no RCON has answered yet
        status, data = self.json("/api/lines?class=soldier&category=voice_menu")
        self.assertEqual(status, 200)
        self.assertEqual(data["lines"][0]["id"], "soldier/medic")

    def test_responses_cannot_be_framed(self):
        for path in ("/", "/api/state", "/missing"):
            with self.subTest(path=path):
                _, headers, _ = self.request(path)
                self.assertEqual(headers.get("X-Frame-Options"), "DENY")

    def test_security_headers_on_all_responses(self):
        from tf2reaudio.server import CSP_VALUE
        # PLAN §13.3 requires CSP, nosniff, Referrer-Policy on every response,
        # and Cache-Control no-store on API. Verify on success paths, error
        # paths, static fallback and audio endpoints. CSP includes media-src
        # blob: so <audio src="blob:..."> previews from recorder.js work; the
        # four required directives remain present and no inline/remote scripts
        # are allowed.
        self.assertIn("default-src 'self'", CSP_VALUE)
        self.assertIn("script-src 'self'", CSP_VALUE)
        self.assertIn("object-src 'none'", CSP_VALUE)
        self.assertIn("base-uri 'none'", CSP_VALUE)
        self.assertIn("media-src 'self' blob:", CSP_VALUE)

        def assert_headers(path, method="GET", body=None, content_type="application/json", headers=None):
            status, got, data = self.request(path, method, body, content_type, headers)
            self.assertEqual(got.get("X-Frame-Options"), "DENY")
            self.assertEqual(got.get("X-Content-Type-Options"), "nosniff")
            self.assertEqual(got.get("Referrer-Policy"), "no-referrer")
            self.assertEqual(got.get("Content-Security-Policy"), CSP_VALUE)
            # Cache-Control is no-store for all API/static responses in this
            # local server (API requirement; static also no-store avoids any
            # disk cache of collection state leaking via browser cache).
            self.assertEqual(got.get("Cache-Control"), "no-store")
            return status, got, data

        assert_headers("/api/ping")
        assert_headers("/api/state")
        assert_headers("/")
        assert_headers("/missing")
        assert_headers("/api/original/soldier%2Fmedic")
        # Error JSON response must carry the same headers, not just success.
        assert_headers("/api/set-active", "POST", json.dumps({"line_id": "soldier/medic", "take_id": "abc"}).encode())
        assert_headers("/api/undo", "POST", json.dumps({"line_id": "soldier/medic#99"}).encode())
        # Invalid Content-Type is rejected before the handler body, still headers.
        status, got, _ = self.request("/api/apply", "POST", b"{}", "text/plain")
        self.assertEqual(status, 400)
        self.assertEqual(got.get("Content-Security-Policy"), CSP_VALUE)
        self.assertEqual(got.get("Cache-Control"), "no-store")
        # Host check failure also goes through _error -> must still send headers.
        request = urllib.request.Request(self.server.url + "/api/ping", headers={"Host": "evil.test"})
        try:
            urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.headers.get("Content-Security-Policy"), CSP_VALUE)
            self.assertEqual(exc.headers.get("Referrer-Policy"), "no-referrer")
            self.assertEqual(exc.headers.get("Cache-Control"), "no-store")
            exc.close()
        # Audio blob and export endpoints are API too — must be no-store and CSP.
        take = self.save_take()
        assert_headers(f"/api/take/{take['take_id']}/audio")
        status, got, _ = self.request("/api/export")
        self.assertEqual(status, 200)
        self.assertEqual(got.get("Content-Security-Policy"), CSP_VALUE)
        self.assertEqual(got.get("Cache-Control"), "no-store")

    def test_unknown_recording_is_a_clear_client_error(self):
        status, data = self.json("/api/set-active", "POST", {
            "line_id": "soldier/medic", "take_id": "abc"})
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "That recording does not exist for this line.")

    def test_variant_details_include_inheritance_and_overrides(self):
        take = self.save_take()
        self.json("/api/override", "POST", {"line_id": "soldier/medic#02", "use_original": True})
        _, data = self.json("/api/lines?class=soldier")
        line = next(line for line in data["lines"] if line["id"] == "soldier/medic")
        first, second, third = line["variants"]
        self.assertEqual(first["id"], "soldier/medic#01")
        self.assertEqual(first["effective"], take["take_id"])
        self.assertTrue(first["inherited"])
        self.assertFalse(second["inherited"])
        self.assertIsNone(second["effective"])
        self.assertEqual(second["files"], [NAMES[1]])
        self.assertEqual(third["effective"], take["take_id"])
        self.assertTrue(line["has_recording"])
        self.json("/api/restore", "POST", {"line_id": "soldier/medic"})
        variant_take = self.app.game.store.add_take("soldier/medic#01", wav(), "local")
        self.app.game.store.set_active("soldier/medic#01", variant_take)
        _, classes = self.json("/api/classes")
        self.assertEqual(next(item for item in classes["classes"] if item["id"] == "soldier")["completed"], 1)

    def test_unavailable_post_entry_is_a_clear_client_error(self):
        with mock.patch.object(self.app.game.store, "undo", side_effect=KeyError("abc")):
            status, data = self.json("/api/undo", "POST", {"line_id": "soldier/medic"})
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "The requested recording or collection entry is unavailable.")

    def test_windows_server_does_not_reuse_addresses(self):
        from tf2reaudio.server import _LocalHTTPServer
        self.assertEqual(_LocalHTTPServer.allow_reuse_address, sys.platform != "win32")

    def test_restart_acknowledgement_does_not_claim_apply_or_playback(self):
        self.save_take()
        before = self.json("/api/state")[1]
        self.assertTrue(before["restart_required"])
        status, _ = self.json("/api/restart-confirmed", "POST", {})
        self.assertEqual(status, 200)
        after = self.json("/api/state")[1]
        self.assertFalse(after["restart_required"])
        self.assertEqual(after["pending_apply"], before["pending_apply"])
        self.assertEqual(after["tf2"], before["tf2"])
        self.assertIn("pending_apply", self.app.game.store.state("soldier/medic"))

    def test_original_and_host_check(self):
        status, headers, data = self.request("/api/original/soldier%2Fmedic")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "audio/mpeg")
        self.assertEqual(data, b"original")

        request = urllib.request.Request(self.server.url + "/api/ping", headers={"Host": "example.test"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(ctx.exception.code, 400)
        ctx.exception.close()

    def test_take_active_undo_and_audio(self):
        status, _, data = self.request(
            "/api/take",
            "POST",
            wav(),
            "audio/wav",
            {"X-Line-ID": "soldier/medic", "X-Activate": "1"},
        )
        payload = json.loads(data)
        self.assertEqual(status, 201)
        self.assertEqual(payload["written"], 3)
        take_id = payload["take_id"]

        status, take = self.json(f"/api/take/{take_id}/metadata")
        self.assertEqual(status, 200)
        self.assertEqual(take["line_id"], "soldier/medic")
        status, _, audio = self.request(f"/api/take/{take_id}/audio")
        self.assertEqual(status, 200)
        self.assertEqual(audio, wav())

        status, data = self.json("/api/undo", "POST", {"line_id": "soldier/medic"})
        self.assertEqual(status, 200)
        self.assertEqual(self.app.game.store.active("soldier/medic"), "ORIGINAL")
        self.assertGreater(self.json("/api/state")[1]["pending_apply"], 0)

    def test_write_requires_csrf_and_apply(self):
        request = urllib.request.Request(self.server.url + "/api/apply", method="POST", data=b"{}")
        request.add_header("Content-Type", "application/json")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(ctx.exception.code, 400)
        ctx.exception.close()

        self.rcon_patch.stop()
        with FakeRcon(password=self.app.game.settings["rcon_password"]) as rcon:
            self.app.game._set(rcon_port=rcon.port)
            status, data = self.json("/api/check-connection", "POST", {})
            self.assertEqual(status, 200)
            self.assertEqual(data["result"], "connected")
            status, data = self.json("/api/apply", "POST", {})
            self.assertEqual(data["result"], "sent")
            self.assertIn("snd_restart", rcon.commands)

    def test_export_import_and_instance_file(self):
        request = urllib.request.Request(self.server.url + "/api/take", method="POST", data=b'{"line_id":"soldier/medic","wav_base64":""}')
        request.add_header("Content-Type", "application/json")
        request.add_header("X-TF2RA", "1")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(ctx.exception.code, 400)  # invalid audio is rejected before any write
        ctx.exception.close()
        status, headers, data = self.request("/api/export")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/zip")
        self.assertGreater(len(data), 20)
        instance = json.loads((self.root / "instance.json").read_text(encoding="utf-8"))
        self.assertEqual(instance["port"], self.server.port)

    def save_take(self, freq=440):
        status, _, raw = self.request("/api/take", "POST", wav(freq), "audio/wav", {"X-Line-ID": "soldier/medic"})
        self.assertEqual(status, 201, raw)
        return json.loads(raw)

    def test_history_override_restore_and_export_roundtrip(self):
        take = self.save_take()
        self.assertNotIn("pending_share", take["state"])
        status, history = self.json("/api/history?line_id=soldier%2Fmedic")
        self.assertEqual(history["takes"][0]["take_id"], take["take_id"])
        self.json("/api/override", "POST", {"line_id": "soldier/medic", "use_original": True})
        self.assertFalse((self.app.game.mod / NAMES[0]).exists())
        self.json("/api/override", "POST", {"line_id": "soldier/medic", "use_original": False})
        self.assertEqual((self.app.game.mod / NAMES[0]).read_bytes(), wav())
        status, _, archive = self.request("/api/export")
        self.json("/api/uninstall", "POST", {"delete_collection": True})
        self.assertEqual(self.app.game.store.history("soldier/medic"), [])
        status, _, body = self.request("/api/import", "POST", archive, "application/zip")
        self.assertEqual(status, 200, body)
        self.assertEqual(self.app.game.store.blob(take["take"]["sha256"]), wav())
        self.json("/api/restore", "POST", {"line_id": "soldier/medic"})
        self.assertFalse((self.app.game.mod / NAMES[0]).exists())

    def test_install_failure_keeps_take_and_retry_installs(self):
        with mock.patch.object(self.app.game, "sync_files", side_effect=PermissionError("locked")):
            take = self.save_take()
            self.assertIsNotNone(take["install_error"])
            _, result = self.json("/api/apply", "POST", {})
            self.assertEqual(result["result"], "install_failed")
        self.assertIsNotNone(self.app.game.store.take(take["take_id"]))
        self.json("/api/sync-files", "POST", {})
        self.assertEqual((self.app.game.mod / NAMES[0]).read_bytes(), wav())

    def test_invalid_payloads_never_change_collection(self):
        before = self.app.game.store.snapshot()
        for path, payload in [
            ("/api/undo", {"line_id": []}),
            ("/api/set-active", {"line_id": "soldier/medic"}),
            ("/api/set-active", {"line_id": "soldier/medic", "target": {}}),
            ("/api/override", {"line_id": "soldier/medic", "use_original": "false"}),
            ("/api/restore", {"line_id": "soldier/medic#99"}),
            ("/api/settings", {"rcon_port": True}),
            ("/api/settings", {"tf_path": ""}),
        ]:
            with self.subTest(path=path, payload=payload):
                status, data = self.json(path, "POST", payload)
                self.assertEqual(status, 400, data)
        status, _, _ = self.request("/api/take", "POST", b"bad", "audio/wav", {"X-Line-ID": "soldier/medic"})
        self.assertEqual(status, 400)
        self.assertEqual(self.app.game.store.snapshot(), before)

    def test_invalid_payloads_return_security_headers_and_no_store(self):
        # Request-validation gaps (§13.3: add tests including error responses).
        # Every 400 produced by the request guards must still carry the
        # security headers and no-store — users see errors in the local UI but
        # the browser must not cache them.
        from tf2reaudio.server import CSP_VALUE
        failures = [
            ("/api/undo", {"line_id": []}),
            ("/api/set-active", {"line_id": "soldier/medic"}),
            ("/api/override", {"line_id": "soldier/medic", "use_original": "no"}),
            ("/api/restore", {"line_id": "soldier/medic#99"}),
            ("/api/settings", {"rcon_port": "bad"}),
        ]
        for path, payload in failures:
            with self.subTest(path=path):
                status, headers, _ = self.request(path, "POST", json.dumps(payload).encode())
                self.assertEqual(status, 400)
                self.assertEqual(headers.get("Content-Security-Policy"), CSP_VALUE)
                self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")
                self.assertEqual(headers.get("Cache-Control"), "no-store")
                self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        # Bad WAV body (directly necessary: take endpoint validation).
        status, headers, _ = self.request("/api/take", "POST", b"not a wav", "audio/wav", {"X-Line-ID": "soldier/medic"})
        self.assertEqual(status, 400)
        self.assertEqual(headers.get("Content-Security-Policy"), CSP_VALUE)
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        # Missing line_id on JSON take.
        status, headers, _ = self.request("/api/take", "POST", json.dumps({"wav_base64": ""}).encode())
        self.assertEqual(status, 400)
        self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_host_origin_content_type_and_limits(self):
        for host in ("evil.test", f"evil@127.0.0.1:{self.server.port}", f"localhost:{self.server.port}/x"):
            self.assertEqual(self.request("/api/ping", headers={"Host": host})[0], 400)
        self.assertEqual(self.request("/api/apply", "POST", b"{}", headers={"Origin": "https://evil.test"})[0], 400)
        self.assertEqual(self.request("/api/apply", "POST", b"{}", "text/plain")[0], 400)
        self.assertEqual(self.request("/api/take", "POST", b"", "audio/wav", {"Content-Length": "1000001"})[0], 400)
        # Send the rejected request in one write: urllib's chunk encoder can
        # race the server closing the connection before its final chunk.
        with socket.create_connection(("127.0.0.1", self.server.port), timeout=5) as sock:
            request = (f"POST /api/apply HTTP/1.1\r\nHost: 127.0.0.1:{self.server.port}\r\n"
                       "X-TF2RA: 1\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n"
                       "\r\n2\r\n{}\r\n0\r\n\r\n").encode("ascii")
            sock.sendall(request)
            response = http.client.HTTPResponse(sock)
            response.begin()
            self.assertEqual(response.status, 400)
            response.read()
            response.close()

    def test_settings_recovery_secrets_and_no_rcon_polling(self):
        app = LocalApp(self.tf / "missing", self.root / "other")
        self.assertIsNone(app.game)
        app.configure_tf(self.tf.parent)
        app.save_settings(rcon_port=12345)
        reopened = LocalApp(root=app.root)
        self.assertEqual(reopened.tf_dir, self.tf)
        self.assertEqual(reopened.game.settings["rcon_port"], 12345)
        with mock.patch("tf2reaudio.game.rcon.send") as send:
            _, state = self.json("/api/state")
            _, settings = self.json("/api/settings")
            send.assert_not_called()
        password = self.app.game.settings["rcon_password"]
        self.assertNotIn(password, json.dumps([state, settings]))
        _, options = self.json("/api/launch-options", "POST", {})
        self.assertIn(password, options["launch_options"])
        self.json("/api/settings", "POST", {"rcon_port": 12345})
        self.assertEqual(LocalApp(root=self.root).tf_dir, self.tf)

    def test_disable_is_idempotent_and_enable_restores(self):
        self.save_take()
        self.json("/api/disable", "POST", {})
        self.json("/api/disable", "POST", {})
        self.assertEqual((self.app.game.disabled_dir / NAMES[0]).read_bytes(), wav())
        self.assertEqual(self.json("/api/apply", "POST", {})[0], 400)
        self.json("/api/enable", "POST", {})
        self.assertEqual((self.app.game.mod / NAMES[0]).read_bytes(), wav())

    def test_concurrent_saves_keep_both_and_install_winner(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            takes = list(pool.map(self.save_take, (440, 500)))
        self.assertEqual(len(self.app.game.store.history("soldier/medic")), 2)
        active = self.app.game.store.take(self.app.game.store.active("soldier/medic"))
        self.assertEqual((self.app.game.mod / NAMES[0]).read_bytes(), self.app.game.store.blob(active["sha256"]))

    def test_instance_identity_cleanup_and_port_fallback(self):
        self.assertEqual(existing_instance(self.root), self.server.url)
        path = self.root / "instance.json"
        record = json.loads(path.read_bytes())
        atomic_write(path, json.dumps(dict(record, instance_id="0" * 32)).encode("utf-8"))
        self.assertIsNone(existing_instance(self.root))
        atomic_write(path, json.dumps(record).encode("utf-8"))
        app = LocalApp(self.tf, self.root / "second")
        second = LocalServer(app, port=self.server.port).start()
        try:
            self.assertNotEqual(second.port, self.server.port)
        finally:
            second.stop()
        self.server.stop()
        self.assertFalse(path.exists())

    def test_single_instance_lock_and_cli_reopens_existing(self):
        first, second = InstanceLock(self.root), InstanceLock(self.root)
        try:
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            with redirect_stdout(io.StringIO()), mock.patch("tf2reaudio.server.webbrowser.open") as browser:
                self.assertEqual(run_local(root=self.root), 0)
                browser.assert_called_once_with(self.server.url)
        finally:
            first.close()
            second.close()
        third = InstanceLock(self.root)
        try:
            self.assertTrue(third.acquire())
        finally:
            third.close()

    def test_run_starts_without_ui_and_cleans_up_on_interrupt(self):
        root = self.root / "run"
        with redirect_stdout(io.StringIO()), mock.patch("tf2reaudio.server.set_low_priority"), \
                mock.patch("tf2reaudio.server.LocalServer.serve_forever", side_effect=KeyboardInterrupt), \
                mock.patch("tf2reaudio.server.webbrowser.open") as browser:
            self.assertEqual(run_local(self.tf, port=0, root=root), 0)
            browser.assert_called_once()
        self.assertFalse((root / "instance.json").exists())

    def test_static_fallback_and_traversal(self):
        self.assertEqual(self.request("/")[0], 200)
        web = self.root / "web"
        web.mkdir()
        atomic_write(web / "index.html", b"<h1>fixture</h1>")
        atomic_write(self.root / "secret.txt", b"private")
        self.server.static_dir = web
        self.assertEqual(self.request("/")[2], b"<h1>fixture</h1>")
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/settings.json", "/%00"):
            self.assertEqual(self.request(path)[0], 404)

    def test_framework_error_responses_carry_security_headers(self):
        from tf2reaudio.server import CSP_VALUE

        expected = {
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
            "content-security-policy": CSP_VALUE,
            "referrer-policy": "no-referrer",
        }
        for method, extra, status in (
            ("DELETE", "", 501),
            ("HEAD", "", 501),
            ("GET", "X-Big: " + "x" * 70000 + "\r\n", 431),
        ):
            with self.subTest(method=method, status=status):
                with socket.create_connection(("127.0.0.1", self.server.port), timeout=5) as sock:
                    sock.sendall((
                        f"{method} /api/state HTTP/1.1\r\n"
                        f"Host: 127.0.0.1:{self.server.port}\r\n"
                        f"{extra}Connection: close\r\n\r\n"
                    ).encode("ascii"))
                    # Read the complete wire response: HTTPResponse(method="HEAD")
                    # would hide an incorrectly transmitted HEAD response body.
                    with sock.makefile("rb") as stream:
                        wire = stream.read()
                raw_headers, body = wire.split(b"\r\n\r\n", 1)
                lines = raw_headers.decode("iso-8859-1").split("\r\n")
                self.assertEqual(int(lines[0].split()[1]), status)
                pairs = [line.split(":", 1) for line in lines[1:]]
                headers = {key.lower(): value.strip() for key, value in pairs}
                for key, value in expected.items():
                    self.assertEqual(headers.get(key), value)
                    self.assertEqual(sum(name.lower() == key for name, _ in pairs), 1)
                self.assertGreater(int(headers["content-length"]), 0)
                if method == "HEAD":
                    self.assertEqual(body, b"")
                else:
                    self.assertEqual(len(body), int(headers["content-length"]))


if __name__ == "__main__":
    unittest.main()
