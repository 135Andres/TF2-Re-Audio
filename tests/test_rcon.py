import socket
import struct
import threading
import time
import unittest

from tf2reaudio import rcon


class FakeRcon:
    """Fake TF2 RCON server on 127.0.0.1 with a random free port. Reusable by other tests.

        with FakeRcon(password="pw", responses={"status": "ok"}) as srv:
            rcon.send("status", "pw", port=srv.port)   # -> "ok"
            srv.commands                               # -> ["status"]

    chunk=1 sends every packet one byte at a time. handler(srv, conn) replaces the normal
    protocol to simulate a misbehaving server; it should return once srv.stopped is set.
    """

    def __init__(self, password="secret", responses=None, chunk=None, handler=None):
        self.password = password
        self.responses = responses or {}
        self.chunk = chunk
        self.handler = handler or FakeRcon.serve
        self.commands = []
        self.stopped = threading.Event()
        self._sock = socket.create_server(("127.0.0.1", 0))
        self._sock.settimeout(0.05)
        self.port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.stopped.set()
        self._thread.join()
        self._sock.close()

    def _run(self):
        while not self.stopped.is_set():
            try:
                conn, _ = self._sock.accept()
            except TimeoutError:
                continue
            with conn:
                try:
                    self.handler(self, conn)
                except (OSError, rcon.RconError):
                    pass  # client went away

    def write(self, conn, req_id, kind, body=""):
        data = rcon._packet(req_id, kind, body)
        if not self.chunk:
            return conn.sendall(data)
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        for i in range(0, len(data), self.chunk):
            conn.sendall(data[i : i + self.chunk])
            time.sleep(0.001)  # let the client see the fragments separately

    def serve(self, conn):
        while True:
            req_id, kind, body = rcon._read_packet(conn, time.monotonic() + 5)
            if kind == rcon.AUTH:
                self.write(conn, req_id, rcon.RESPONSE_VALUE)
                self.write(conn, req_id if body == self.password else -1, rcon.AUTH_RESPONSE)
            elif kind == rcon.EXECCOMMAND:
                self.commands.append(body)
                out = self.responses.get(body, "")
                for i in range(0, max(len(out), 1), rcon.MAX_BODY):
                    self.write(conn, req_id, rcon.RESPONSE_VALUE, out[i : i + rcon.MAX_BODY])
            elif kind == rcon.RESPONSE_VALUE:  # mirrored, then followed by a 0x01 packet like srcds
                self.write(conn, req_id, rcon.RESPONSE_VALUE)
                self.write(conn, req_id, rcon.RESPONSE_VALUE, "\0\0\0\x01")


def free_port():
    with socket.create_server(("127.0.0.1", 0)) as s:
        return s.getsockname()[1]


class RconTest(unittest.TestCase):
    TIMEOUT = 1.0

    def assert_fails_fast(self, exc, srv, password="secret", msg=""):
        start = time.monotonic()
        with self.assertRaisesRegex(exc, msg):
            rcon.send("snd_restart", password, port=srv.port, timeout=self.TIMEOUT)
        self.assertLess(time.monotonic() - start, self.TIMEOUT + 1)

    def test_launch_options(self):
        self.assertEqual(
            rcon.launch_options("pw", 27016),
            "-usercon +ip 127.0.0.1 +hostport 27016 +rcon_password pw +net_start",
        )

    def test_sends_command(self):
        with FakeRcon() as srv:
            self.assertEqual(rcon.send("snd_restart", "secret", port=srv.port), "")
        self.assertEqual(srv.commands, ["snd_restart"])

    def test_multi_packet_response(self):
        out = "a" * 5000 + "end"
        with FakeRcon(responses={"cvarlist": out}) as srv:
            self.assertEqual(rcon.send("cvarlist", "secret", port=srv.port), out)

    def test_fragmented_one_byte_at_a_time(self):
        with FakeRcon(responses={"echo hi": "hi\n"}, chunk=1) as srv:
            self.assertEqual(rcon.send("echo hi", "secret", port=srv.port), "hi\n")

    def test_wrong_password(self):
        with FakeRcon() as srv:
            self.assert_fails_fast(rcon.RconAuthFailed, srv, password="wrong")
        self.assertEqual(srv.commands, [])

    def test_not_running(self):
        start = time.monotonic()
        with self.assertRaises(rcon.RconNotRunning):
            rcon.send("snd_restart", "secret", port=free_port(), timeout=self.TIMEOUT)
        self.assertLess(time.monotonic() - start, self.TIMEOUT + 1)

    def test_closes_mid_body(self):
        def handler(srv, conn):
            rcon._read_packet(conn, time.monotonic() + 5)
            conn.sendall(struct.pack("<iii", 20, 1, rcon.RESPONSE_VALUE))

        with FakeRcon(handler=handler) as srv:
            self.assert_fails_fast(rcon.RconError, srv, msg="closed")

    def test_never_answers(self):
        with FakeRcon(handler=lambda srv, conn: srv.stopped.wait()) as srv:
            self.assert_fails_fast(rcon.RconError, srv, msg="in time")

    def test_endless_packets_still_time_out(self):
        def handler(srv, conn):
            while not srv.stopped.is_set():
                srv.write(conn, 0, rcon.RESPONSE_VALUE)

        with FakeRcon(handler=handler) as srv:
            self.assert_fails_fast(rcon.RconError, srv)

    def test_invalid_packet_size(self):
        for size in (9, rcon.MAX_BODY + 11, -1):
            def handler(srv, conn, size=size):
                conn.sendall(struct.pack("<i", size) + b"\0" * 10)
                srv.stopped.wait()

            with self.subTest(size=size), FakeRcon(handler=handler) as srv:
                self.assert_fails_fast(rcon.RconError, srv, msg="invalid")


if __name__ == "__main__":
    unittest.main()
