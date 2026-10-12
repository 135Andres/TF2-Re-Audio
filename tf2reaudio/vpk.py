"""Read Valve VPK (v1/v2) archives: list file names and extract their contents."""

import struct
import zlib
from pathlib import Path

SIGNATURE = 0x55AA1234
IN_DIR = 0x7FFF  # archive index meaning "data lives in the _dir.vpk itself"
_ENTRY = struct.Struct("<IHHIIH")  # crc, preload_len, archive_index, offset, length, terminator


class VpkError(Exception):
    pass


class VpkIndex:
    def __init__(self, dir_vpk: Path):
        self.path = Path(dir_vpk)
        try:
            with open(self.path, "rb") as f:
                head = f.read(12)
                if len(head) < 12:
                    raise VpkError(f"{self.path.name} is truncated (incomplete header).")
                sig, version, tree_size = struct.unpack("<III", head)
                if sig != SIGNATURE:
                    raise VpkError(f"{self.path.name} is not a VPK file.")
                if version not in (1, 2):
                    raise VpkError(f"{self.path.name} has unsupported VPK version {version}.")
                self._data_start = 12 + (16 if version == 2 else 0) + tree_size
                f.seek(self._data_start - tree_size)
                tree = f.read(tree_size)
        except OSError as e:
            raise VpkError(f"Cannot read {self.path}: {e.strerror or e}") from e
        if len(tree) < tree_size:
            raise VpkError(f"{self.path.name} is truncated (incomplete file index).")
        self._entries = _parse_tree(tree, self.path.name)

    def names(self) -> list[str]:
        return list(self._entries)

    def __contains__(self, name) -> bool:
        return name in self._entries

    def read(self, name: str) -> bytes:
        try:
            crc, preload, index, offset, length = self._entries[name]
        except KeyError:
            raise VpkError(f"{name} is not in {self.path.name}.") from None
        data = b""
        if length:
            if index == IN_DIR:
                path, offset = self.path, self._data_start + offset
            else:
                prefix = self.path.name.removesuffix(".vpk").removesuffix("_dir")
                path = self.path.with_name(f"{prefix}_{index:03d}.vpk")
            try:
                with open(path, "rb") as f:
                    f.seek(offset)
                    data = f.read(length)
            except OSError as e:
                raise VpkError(f"Cannot read {path}: {e.strerror or e}") from e
            if len(data) < length:
                raise VpkError(f"{path.name} is truncated (data for {name} is incomplete).")
        data = preload + data
        if zlib.crc32(data) != crc:
            raise VpkError(f"{name} in {self.path.name} is corrupted (CRC mismatch).")
        return data


def _parse_tree(tree: bytes, label: str) -> dict:
    """Parse the directory tree; every read is bounds-checked so bad input raises instead of hanging."""
    pos = 0
    entries = {}

    def cstr() -> str:
        nonlocal pos
        end = tree.find(b"\0", pos)
        if end < 0:
            raise VpkError(f"{label} is truncated or corrupted (unterminated name in file index).")
        s = tree[pos:end].decode("utf-8", "replace")
        pos = end + 1
        return s

    while ext := cstr():
        while folder := cstr():
            while stem := cstr():
                if pos + _ENTRY.size > len(tree):
                    raise VpkError(f"{label} is truncated or corrupted (incomplete file entry).")
                crc, plen, index, offset, length, term = _ENTRY.unpack_from(tree, pos)
                pos += _ENTRY.size
                if term != 0xFFFF or pos + plen > len(tree):
                    raise VpkError(f"{label} is truncated or corrupted (bad file entry).")
                preload = tree[pos : pos + plen]
                pos += plen
                # " " is how VPK stores an empty folder (root) or an empty extension.
                name = stem if ext == " " else f"{stem}.{ext}"
                if folder != " ":
                    name = f"{folder}/{name}"
                entries[name] = (crc, preload, index, offset, length)
    return entries
