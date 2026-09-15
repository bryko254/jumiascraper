"""Build tiny PNG icons without extra dependencies."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def write_png(path: Path, size: int, rgb: tuple[int, int, int]) -> None:
    raw = b"".join(b"\x00" + (bytes(rgb) * size) for _ in range(size))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")
    path.write_bytes(png)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "extension" / "icons"
    root.mkdir(parents=True, exist_ok=True)
    orange = (246, 139, 30)
    write_png(root / "icon16.png", 16, orange)
    write_png(root / "icon48.png", 48, orange)
    write_png(root / "icon128.png", 128, orange)
    print(f"Wrote icons in {root}")


if __name__ == "__main__":
    main()
