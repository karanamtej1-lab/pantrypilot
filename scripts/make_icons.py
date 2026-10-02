"""Draw PantryPilot's app icon (a white map pin on teal) as SVG and PNG files.

Run from the project folder:   python scripts/make_icons.py
Writes into frontend/icons/. Uses only Python's standard library (no image packages).

Files:
  icon.svg               sharp at any size (browser tab, modern browsers)
  icon-192.png           Android home screen   (rounded corners)
  icon-512.png           install screens        (rounded corners)
  icon-maskable-512.png  Android adaptive icon  (full square; Android crops the shape)
  apple-touch-icon.png   iPhone home screen, 180x180 (full square; iOS rounds it)
"""

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "frontend" / "icons"

TEAL = (44, 110, 99)     # --accent in style.css
WHITE = (255, 255, 255)

# Shapes in a 0..1 square. The pin sits inside the central 80% "safe zone",
# so Android's circle/squircle masks never cut it off.
PIN_CENTER = (0.5, 0.42)
PIN_RADIUS = 0.2
PIN_TIP = (0.5, 0.80)
HOLE_RADIUS = 0.085
CORNER = 0.22            # rounded-corner radius for the non-maskable icons


def tangent_points():
    """Where straight lines from the pin's tip touch the circle."""
    cx, cy = PIN_CENTER
    d = PIN_TIP[1] - cy
    beta = math.acos(PIN_RADIUS / d)      # angle from straight-down to the tangent point
    dx, dy = PIN_RADIUS * math.sin(beta), PIN_RADIUS * math.cos(beta)
    return (cx - dx, cy + dy), (cx + dx, cy + dy)


LEFT, RIGHT = tangent_points()


def in_triangle(x, y, a, b, c):
    def side(p, q):
        return (q[0] - p[0]) * (y - p[1]) - (q[1] - p[1]) * (x - p[0])
    s1, s2, s3 = side(a, b), side(b, c), side(c, a)
    return (s1 >= 0 and s2 >= 0 and s3 >= 0) or (s1 <= 0 and s2 <= 0 and s3 <= 0)


def in_pin(x, y):
    cx, cy = PIN_CENTER
    dist2 = (x - cx) ** 2 + (y - cy) ** 2
    if dist2 <= HOLE_RADIUS ** 2:
        return False                      # the hole in the middle of the pin
    return dist2 <= PIN_RADIUS ** 2 or in_triangle(x, y, LEFT, RIGHT, PIN_TIP)


def in_background(x, y, rounded):
    if not rounded:
        return True
    r = CORNER
    nx = min(max(x, r), 1 - r)            # nearest point of the inner (un-rounded) square
    ny = min(max(y, r), 1 - r)
    return (x - nx) ** 2 + (y - ny) ** 2 <= r * r


def render(size, rounded, samples=4):
    """RGBA pixels, with 4x4 samples per pixel for smooth (anti-aliased) edges."""
    rows = []
    step = 1 / (size * samples)
    for py in range(size):
        row = bytearray()
        for px in range(size):
            bg = pin = 0
            for sy in range(samples):
                y = (py * samples + sy + 0.5) * step
                for sx in range(samples):
                    x = (px * samples + sx + 0.5) * step
                    if in_background(x, y, rounded):
                        bg += 1
                        pin += in_pin(x, y)
            total = samples * samples
            alpha = bg / total
            if bg == 0:
                row += bytes((0, 0, 0, 0))
                continue
            mix = pin / bg                # share of the visible area that is white pin
            color = [round(TEAL[i] * (1 - mix) + WHITE[i] * mix) for i in range(3)]
            row += bytes((*color, round(alpha * 255)))
        rows.append(bytes(row))
    return rows


def write_png(path, size, rows):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + row for row in rows)  # filter byte 0 (none) before each row
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))  # 8-bit RGBA
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    path.write_bytes(png)


def write_svg(path):
    s = 512
    p = lambda v: round(v * s, 2)  # noqa: E731
    (lx, ly), (rx, ry), (tx, ty) = LEFT, RIGHT, PIN_TIP
    cx, cy = PIN_CENTER
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}">\n'
        f'  <rect width="{s}" height="{s}" rx="{p(CORNER)}" fill="rgb{TEAL}"/>\n'
        f'  <path fill="#fff" fill-rule="evenodd" d="M{p(lx)} {p(ly)} '
        f'A{p(PIN_RADIUS)} {p(PIN_RADIUS)} 0 1 1 {p(rx)} {p(ry)} L{p(tx)} {p(ty)} Z '
        f'M{p(cx - HOLE_RADIUS)} {p(cy)} a{p(HOLE_RADIUS)} {p(HOLE_RADIUS)} 0 1 0 {p(2 * HOLE_RADIUS)} 0 '
        f'a{p(HOLE_RADIUS)} {p(HOLE_RADIUS)} 0 1 0 {p(-2 * HOLE_RADIUS)} 0Z"/>\n'
        f'</svg>\n'
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    write_svg(OUT / "icon.svg")
    for name, size, rounded in [("icon-192.png", 192, True), ("icon-512.png", 512, True),
                                ("icon-maskable-512.png", 512, False), ("apple-touch-icon.png", 180, False)]:
        write_png(OUT / name, size, render(size, rounded))
        print("wrote", name)


if __name__ == "__main__":
    main()
