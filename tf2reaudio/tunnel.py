"""Cloudflare Quick Tunnel: download a pinned cloudflared and expose a local port."""
import atexit
import hashlib
import os
import platform
import re
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

from .util import atomic_write, data_dir

CLOUDFLARED_VERSION = "2026.10.0"
# SHA-256 from the official release notes (github.com/cloudflare/cloudflared/releases/tag/2026.10.0).
CLOUDFLARED_SHA256 = {
    "cloudflared-windows-amd64.exe": "86aee4017b26625cee8484c113558f48effa4cd47f7aa05fcf425604e5d2b23c",
    "cloudflared-linux-amd64": "d33ff2d14475178d2012c2c56beba87389ac5ded27649519f198a7d3134a99db",
    "cloudflared-linux-arm64": "e6422b9d4f72d3194bc5a38676f13667c06666523217b842a877d72a80b5ac08",
}
DOWNLOAD_URL = "https://github.com/cloudflare/cloudflared/releases/download/{version}/{asset}"

URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
# cloudflared also logs the quick-tunnel API host (e.g. in errors); that is never the public link.
_NOT_A_TUNNEL = {"https://api.trycloudflare.com"}


class TunnelError(Exception):
    pass


def _asset_name() -> str:
    machine = platform.machine().lower()
    arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine)
    os_name = {"win32": "windows", "linux": "linux"}.get(sys.platform)
    name = f"cloudflared-{os_name}-{arch}" + (".exe" if os_name == "windows" else "")
    if name not in CLOUDFLARED_SHA256:
        raise TunnelError(f"Hosting is not supported on this system ({sys.platform}, {machine}).")
    return name


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_tunnel_url(text: str) -> str | None:
    """Return the first public trycloudflare.com link in cloudflared output, or None."""
    for m in URL_RE.finditer(text):
        if m.group(0) not in _NOT_A_TUNNEL:
            return m.group(0)
    return None


def ensure_cloudflared() -> Path:
    """Return the path to the pinned cloudflared, downloading and verifying it once."""
    asset = _asset_name()
    expected = CLOUDFLARED_SHA256[asset]
    bin_dir = data_dir() / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    path = bin_dir / asset.replace("cloudflared-", f"cloudflared-{CLOUDFLARED_VERSION}-")
    if path.exists():
        if _sha256_file(path) == expected:
            return path
        path.unlink()  # corrupt or tampered: fetch again
    url = DOWNLOAD_URL.format(version=CLOUDFLARED_VERSION, asset=asset)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
    except OSError as e:
        raise TunnelError(f"Could not download cloudflared (check your internet connection): {e}") from None
    atomic_write(path, data)
    if _sha256_file(path) != expected:
        path.unlink()
        raise TunnelError("Downloaded cloudflared failed the SHA-256 check and was deleted. Try again later.")
    if sys.platform != "win32":
        path.chmod(0o755)
    return path


class Tunnel:
    def __init__(self, local_port: int):
        self.local_port = local_port
        self.url: str | None = None
        self._proc: subprocess.Popen | None = None
        self._tail: list[str] = []

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self, timeout: float = 30) -> str:
        """Start cloudflared and return the public https://xxxx.trycloudflare.com link."""
        if self.running and self.url:
            return self.url
        self.stop()
        exe = ensure_cloudflared()
        self.url = None
        self._tail = []
        found = threading.Event()
        cmd = [str(exe), "tunnel", "--url", f"http://127.0.0.1:{self.local_port}", "--no-autoupdate"]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except OSError as e:
            self._proc = None
            raise TunnelError(f"Could not start cloudflared: {e}") from None
        # shortcut: atexit misses hard kills of the app; upgrade to a Job object / PR_SET_PDEATHSIG if orphans show up.
        atexit.register(self.stop)
        threading.Thread(target=self._read_output, args=(self._proc, found), daemon=True).start()

        if not found.wait(timeout) or not self.url:
            tail = "".join(self._tail[-5:]).strip()
            exited = not self.running
            self.stop()
            reason = "cloudflared exited" if exited else f"No tunnel link after {timeout:g} seconds"
            raise TunnelError(f"{reason}. The tunnel service may be down; try again later." + (f"\n{tail}" if tail else ""))
        return self.url

    def _read_output(self, proc: subprocess.Popen, found: threading.Event) -> None:
        # Keep draining after the link is found so cloudflared never blocks on a full pipe.
        with proc.stdout:
            for line in proc.stdout:
                if found.is_set():
                    continue
                self._tail = (self._tail + [line])[-20:]
                url = find_tunnel_url(line)
                if url:
                    self.url = url
                    found.set()
        found.set()  # process ended: wake start() if it is still waiting

    def stop(self) -> None:
        proc, self._proc = self._proc, None
        atexit.unregister(self.stop)
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
