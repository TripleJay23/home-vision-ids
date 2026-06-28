"""Render the Home Vision IDS app icon (Concept A: shield + eye) with Pillow.

Draws at 4x supersample then downsamples (crisp antialiasing). Produces two
1024 masters: Android (rounded corners, alpha) and iOS (square, opaque).
"""
import sys
from PIL import Image, ImageDraw

SS = 4
SZ = 1024 * SS

TOP = (0x0D, 0x47, 0xA1)      # deep blue
BOT = (0x1E, 0x88, 0xE5)      # lighter blue
WHITE = (255, 255, 255, 255)
CYAN = (0x29, 0xB6, 0xF6, 255)
PUPIL = (0x0D, 0x2B, 0x5E, 255)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(sz):
    g = Image.new("RGB", (sz, sz))
    px = g.load()
    for y in range(sz):
        c = lerp(TOP, BOT, y / (sz - 1))
        for x in range(sz):
            px[x, y] = c
    return g


def qbezier(p0, c, p1, n=24):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0]
        y = u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1]
        pts.append((x, y))
    return pts


def scale(pts):
    return [(x * SS, y * SS) for (x, y) in pts]


def shield_points():
    # Coordinates in 1024 space (from Concept A SVG, normalized).
    top = (512, 182)
    ur = (745, 273)
    rsh = (745, 523)
    tip = (512, 876)
    lsh = (279, 523)
    ul = (279, 273)
    pts = [top, ur, rsh]
    pts += qbezier(rsh, (745, 785), tip)        # right shoulder -> tip
    pts += qbezier(tip, (279, 785), lsh)         # tip -> left shoulder
    pts += [ul, top]
    return pts


def eye_polygon():
    left = (364, 506)
    right = (660, 506)
    top = qbezier(left, (512, 398), right)       # upper lid
    bot = qbezier(right, (512, 614), left)        # lower lid
    return top + bot


def draw_mark(img):
    d = ImageDraw.Draw(img)
    # Shield as a thick white outline.
    d.line(scale(shield_points()), fill=WHITE, width=34 * SS, joint="curve")
    # Eye: white almond, cyan iris, dark pupil, tiny catchlight.
    d.polygon(scale(eye_polygon()), fill=WHITE)
    cx, cy = 512 * SS, 506 * SS
    r_iris, r_pup = 63 * SS, 26 * SS
    d.ellipse([cx - r_iris, cy - r_iris, cx + r_iris, cy + r_iris], fill=CYAN)
    d.ellipse([cx - r_pup, cy - r_pup, cx + r_pup, cy + r_pup], fill=PUPIL)
    cl = 11 * SS
    d.ellipse([cx - 20 * SS - cl, cy - 18 * SS - cl, cx - 20 * SS + cl, cy - 18 * SS + cl], fill=WHITE)


def rounded_mask(sz, radius):
    m = Image.new("L", (sz, sz), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, sz - 1, sz - 1], radius=radius, fill=255)
    return m


def build_android():
    base = gradient(SZ).convert("RGBA")
    base.putalpha(rounded_mask(SZ, int(229 * SS)))   # ~22.4% squircle-ish corners
    draw_mark(base)
    return base.resize((1024, 1024), Image.LANCZOS)


def build_ios():
    base = gradient(SZ).convert("RGBA")              # full square, no rounding
    draw_mark(base)
    return base.convert("RGB").resize((1024, 1024), Image.LANCZOS)


if __name__ == "__main__":
    out = sys.argv[1]
    build_android().save(f"{out}/master_android_1024.png")
    build_ios().save(f"{out}/master_ios_1024.png")
    print("wrote masters to", out)
