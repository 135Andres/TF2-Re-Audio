"""Minimal Source RCON client for the local TF2 game (connects to 127.0.0.1 only)."""
import socket
import struct
import time

AUTH = 3
AUTH_RESPONSE = 2
EXECCOMMAND = 2
RESPONSE_VALUE = 0
MAX_BODY = 4096

_AUTH_ID = 1
_COMMAND_ID = 2
_END_ID = 3


class RconError(Exception):
    """RCON failed: connection dropped, no answer in time or invalid data."""


class RconNotRunning(RconError):
    """Nothing is listening for RCON (TF2 closed or started without the launch options)."""


class RconAuthFailed(RconError):
    """The game rejected the RCON password."""


def launch_options(password: str, port: int = 27015) -> str:
    return f"-usercon +ip 127.0.0.1 +hostport {port} +rcon_password {password} +net_start"


def send(command: str, password: str, port: int = 27015, timeout: float = 3.0) -> str:
    """Run a console command in TF2 and return its output ("" if it printed nothing).

    The whole call, connection included, never takes much longer than `timeout` seconds.
    """
    deadline = time.monotonic() + timeout
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    except OSError as e:
        raise RconNotRunning(
            f"TF2 is not reachable over RCON on port {port}. "
            "Is the game running with the launch options?"
        ) from e
    try:
        with sock:
            return _talk(sock, command, password, deadline)
    except TimeoutError as e:
        raise RconError("TF2 did not answer over RCON in time.") from e
    except OSError as e:
        raise RconError(f"The RCON connection to TF2 failed: {e}") from e


def _talk(sock, command, password, deadline):
    sock.sendall(_packet(_AUTH_ID, AUTH, password))
    while True:  # the server sends an empty RESPONSE_VALUE before the AUTH_RESPONSE
        req_id, kind, _ = _read_packet(sock, deadline)
        if kind == AUTH_RESPONSE:
            break
    if req_id == -1:
        raise RconAuthFailed("TF2 rejected the RCON password. Copy the launch options again.")
    # Long output arrives in several packets. The server answers packets in order, so the
    # echo of the empty RESPONSE_VALUE sent after the command marks the end of the output.
    sock.sendall(_packet(_COMMAND_ID, EXECCOMMAND, command) + _packet(_END_ID, RESPONSE_VALUE, ""))
    parts = []
    while True:
        req_id, kind, body = _read_packet(sock, deadline)
        if req_id == _END_ID:
            return "".join(parts)
        if req_id == _COMMAND_ID and kind == RESPONSE_VALUE:
            parts.append(body)


def _packet(req_id, kind, body):
    data = struct.pack("<ii", req_id, kind) + body.encode("utf-8") + b"\0\0"
    return struct.pack("<i", len(data)) + data


def _read_packet(sock, deadline):
    (size,) = struct.unpack("<i", _recv_exact(sock, 4, deadline))
    if not 10 <= size <= MAX_BODY + 10:
        raise RconError(f"TF2 sent an invalid RCON packet (size {size}).")
    data = _recv_exact(sock, size, deadline)
    req_id, kind = struct.unpack("<ii", data[:8])
    return req_id, kind, data[8:-2].decode("utf-8", "replace")


def _recv_exact(sock, n, deadline):
    """Read exactly n bytes, tolerating fragments; raise if the peer closes or time runs out."""
    buf = bytearray()
    while len(buf) < n:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        sock.settimeout(remaining)
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise RconError("TF2 closed the RCON connection unexpectedly.")
        buf += chunk
    return bytes(buf)
