from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any


def _write_png(path: Path, width: int, height: int, rgb_data: list[list[tuple[int, int, int]]]) -> Path:
    """Write a tiny PNG image without external dependencies."""
    path.parent.mkdir(parents=True, exist_ok=True)

    raw = bytearray()
    for row in range(height):
        raw.append(0)
        for col in range(width):
            r, g, b = rgb_data[row][col]
            raw.extend((r, g, b))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack('!I', len(data)) + tag + data + struct.pack('!I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(bytes(raw), level=9))
    png += chunk(b'IEND', b'')

    path.write_bytes(png)
    return path


def generate_report_image(page_number: int, findings: list[dict[str, Any]], output_path: str | Path) -> Path:
    """Create a simple marked-up report page image for a selected page."""
    target = Path(output_path)
    width = 1200
    height = 800
    image = [[(255, 255, 255) for _ in range(width)] for _ in range(height)]

    for y in range(60, height, 130):
        for x in range(40, width - 40, 120):
            if x < width - 120:
                for yy in range(y, min(y + 28, height)):
                    for xx in range(x, min(x + 90, width)):
                        image[yy][xx] = (230, 240, 250)

    page_findings = [f for f in findings if int(f.get("page", 1)) == int(page_number)]
    for index, finding in enumerate(page_findings):
        verdict = str(finding.get("verdict", "unknown"))
        y0 = 90 + index * 120
        x0 = 80
        w = 1040
        h = 70
        color = (40, 167, 69) if verdict == "fine" else (220, 53, 69) if verdict == "not_fine" else (255, 193, 7)
        for yy in range(y0, min(y0 + h, height)):
            for xx in range(x0, min(x0 + w, width)):
                image[yy][xx] = color

        label = str(finding.get("item", "item"))
        status = str(finding.get("verdict", "unknown")).replace("_", " ").title()
        for yy in range(y0 + 12, min(y0 + 58, height)):
            for xx in range(x0 + 18, min(x0 + 260, width)):
                if 0 <= yy < height and 0 <= xx < width:
                    image[yy][xx] = (255, 255, 255) if (yy + xx) % 2 == 0 else (255, 255, 255)

    title = f"Marked drawing — page {page_number}"
    # The PNG is intentionally simple and deterministic; the frontend only needs a valid image URL.
    return _write_png(target, width, height, image)
