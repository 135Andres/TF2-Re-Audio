import os
import sys
import tempfile
from pathlib import Path


def data_dir() -> Path:
    """Per-user data folder (created if missing)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        path = base / "TF2ReAudio"
    else:
        base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
        path = Path(base) / "tf2reaudio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write(path, data: bytes) -> None:
    """Write data to path so readers see either the old or the new file, never a partial one."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_low_priority() -> None:
    """Lower this process's CPU priority so TF2 is not affected. Silently does nothing on failure."""
    try:
        if sys.platform == "win32":
            import ctypes

            BELOW_NORMAL_PRIORITY_CLASS = 0x4000
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS)
        else:
            os.nice(10)
    except Exception:
        pass


class InstanceLock:
    """OS-managed lifetime lock; released even after a process crash.

    The empty lock file is never replaced or unlinked: all processes must lock
    the same inode. It contains no persistent application data.
    """

    def __init__(self, root, name="instance.lock"):
        path = Path(root, name)
        if not path.exists():
            atomic_write(path, b"0")
        self.file = path.open("r+b")
        if self.file.seek(0, 2) == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        self.acquired = False

    def acquire(self):
        try:
            if sys.platform == "win32":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        self.acquired = True
        return True

    def release(self):
        if self.acquired:
            if sys.platform == "win32":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
        self.acquired = False

    def close(self):
        self.release()
        self.file.close()
