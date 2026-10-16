"""Build a reproducible local-test candidate, without user data or runtimes."""
from __future__ import annotations

import argparse
import hashlib
import io
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tf2reaudio import __version__
from tf2reaudio.util import atomic_write


class BuildError(Exception):
    """An expected packaging error with a readable message."""


RESOURCE_SUFFIXES = {".py", ".js", ".html", ".css", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".ttf"}
REQUIRED = {
    "TF2ReAudio.cmd": "TF2ReAudio.cmd",
    "tf2reaudio.sh": "tf2reaudio.sh",
    "docs/README.md": "README.md",
    "docs/launchers.md": "docs/launchers.md",
    "docs/milestone-wave2.md": "docs/milestone-wave2.md",
    "docs/local-ui-review.md": "docs/local-ui-review.md",
}


def build_zip(root: Path = ROOT, output: Path | None = None) -> tuple[Path, str]:
    root = Path(root)
    output = Path(output) if output is not None else root / "dist" / f"TF2ReAudio-{__version__}.zip"
    sources = []
    for relative, name in REQUIRED.items():
        source = root / Path(relative)
        if not source.is_file() or source.is_symlink():
            raise BuildError(f"Missing package file: {relative}")
        sources.append((source, name))
    package = root / "tf2reaudio"
    for source in package.rglob("*"):
        relative = source.relative_to(root)
        is_module = source.parent == package and source.suffix == ".py"
        is_resource = source.is_relative_to(package / "web") and source.suffix.lower() in RESOURCE_SUFFIXES - {".py"}
        if (source.is_file() and not source.is_symlink() and "__pycache__" not in relative.parts
                and not any(part.startswith(".") for part in relative.parts)
                and (is_module or is_resource)):
            sources.append((source, relative.as_posix()))
    names = {name for _, name in sources}
    for required in ("tf2reaudio/__init__.py", "tf2reaudio/__main__.py", "tf2reaudio/web/index.html"):
        if required not in names:
            raise BuildError(f"Missing package file: {required}")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, name in sorted(sources, key=lambda item: item[1]):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if name == "tf2reaudio.sh" else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, source.read_bytes())
    data = buffer.getvalue()
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(output, data)
    return output, hashlib.sha256(data).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Destination ZIP (default: dist/TF2ReAudio-<version>.zip)")
    args = parser.parse_args(argv)
    try:
        output, digest = build_zip(output=args.output)
    except (BuildError, OSError) as exc:
        print(f"Could not build the ZIP: {exc}", file=sys.stderr)
        return 1
    print(f"Built local-test candidate: {output}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
