"""Build small synthetic VPK files for tests."""

import struct
import zlib
from pathlib import Path


def make_vpk(dir_vpk: Path, files: dict, version: int = 2, preload: int = 0, external: bool = False) -> Path:
    """Write `dir_vpk` (named like "x_dir.vpk") holding `files` ({"a/b.mp3": bytes}).

    The first `preload` bytes of each file go in the tree; the rest goes after the tree,
    or into "x_000.vpk" when `external` is true.
    """
    dir_vpk = Path(dir_vpk)
    tree_by_ext = {}
    for name, content in files.items():
        folder, _, filename = name.rpartition("/")
        stem, dot, ext = filename.rpartition(".")
        if not dot:
            stem, ext = filename, ""
        tree_by_ext.setdefault(ext or " ", {}).setdefault(folder or " ", []).append((stem, content))

    tree, blob = bytearray(), bytearray()
    for ext, folders in tree_by_ext.items():
        tree += ext.encode() + b"\0"
        for folder, entries in folders.items():
            tree += folder.encode() + b"\0"
            for stem, content in entries:
                head, rest = content[:preload], content[preload:]
                index = 0 if external else 0x7FFF
                tree += stem.encode() + b"\0"
                tree += struct.pack("<IHHIIH", zlib.crc32(content), len(head), index, len(blob), len(rest), 0xFFFF)
                tree += head
                blob += rest
            tree += b"\0"
        tree += b"\0"
    tree += b"\0"

    header = struct.pack("<III", 0x55AA1234, version, len(tree))
    if version == 2:
        header += struct.pack("<IIII", 0 if external else len(blob), 0, 0, 0)
    if external:
        dir_vpk.write_bytes(header + tree)
        prefix = dir_vpk.name.removesuffix(".vpk").removesuffix("_dir")
        dir_vpk.with_name(f"{prefix}_000.vpk").write_bytes(bytes(blob))
    else:
        dir_vpk.write_bytes(header + tree + blob)
    return dir_vpk
