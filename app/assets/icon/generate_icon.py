"""Build Android (adaptive + legacy) and iOS launcher icons from the emblem.

Source: app/assets/icon/emblem_source.png — the mark on a transparent
background (camera aperture wrapping a house). Everything is composed on a
solid WHITE background. The emblem is cropped tight and scaled UP so it fills
the icon (no large empty ring around it).

Run from anywhere:  python app/assets/icon/generate_icon.py
"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RES = os.path.join(ROOT, "app/android/app/src/main/res")
IOS = os.path.join(ROOT, "app/ios/Runner/Assets.xcassets/AppIcon.appiconset")
WHITE = (255, 255, 255, 255)

# Emblem fill fraction (of canvas width):
#  - adaptive foreground is masked to the central ~67% circle, so 0.70 fills
#    that circle edge-to-edge without clipping the emblem's outer ring.
#  - legacy/iOS show the whole square, so the emblem can go larger.
FRAC_ADAPTIVE = 0.70
FRAC_SQUARE = 0.86

_src = Image.open(os.path.join(HERE, "emblem_source.png")).convert("RGBA")
_emblem = _src.crop(_src.getchannel("A").getbbox())  # tight crop to the mark


def compose(canvas: int, frac: float) -> Image.Image:
    """White canvas with the emblem centered and scaled to `frac` of the width."""
    out = Image.new("RGBA", (canvas, canvas), WHITE)
    w, h = _emblem.size
    s = (canvas * frac) / max(w, h)
    em = _emblem.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out.alpha_composite(em, ((canvas - em.width) // 2, (canvas - em.height) // 2))
    return out


# Adaptive foreground (108dp base) — fills the launcher circle.
for d, sz in {"mipmap-mdpi": 108, "mipmap-hdpi": 162, "mipmap-xhdpi": 216,
              "mipmap-xxhdpi": 324, "mipmap-xxxhdpi": 432}.items():
    compose(sz, FRAC_ADAPTIVE).save(f"{RES}/{d}/ic_launcher_foreground.png")

# Legacy launcher (48dp base) — flattened, fills the square.
for d, sz in {"mipmap-mdpi": 48, "mipmap-hdpi": 72, "mipmap-xhdpi": 96,
              "mipmap-xxhdpi": 144, "mipmap-xxxhdpi": 192}.items():
    compose(sz, FRAC_SQUARE).convert("RGB").save(f"{RES}/{d}/ic_launcher.png")

# iOS — flattened, fills the square, no alpha.
for name, sz in {
    "Icon-App-1024x1024@1x.png": 1024,
    "Icon-App-20x20@1x.png": 20, "Icon-App-20x20@2x.png": 40, "Icon-App-20x20@3x.png": 60,
    "Icon-App-29x29@1x.png": 29, "Icon-App-29x29@2x.png": 58, "Icon-App-29x29@3x.png": 87,
    "Icon-App-40x40@1x.png": 40, "Icon-App-40x40@2x.png": 80, "Icon-App-40x40@3x.png": 120,
    "Icon-App-60x60@2x.png": 120, "Icon-App-60x60@3x.png": 180,
    "Icon-App-76x76@1x.png": 76, "Icon-App-76x76@2x.png": 152, "Icon-App-83.5x83.5@2x.png": 167,
}.items():
    compose(sz, FRAC_SQUARE).convert("RGB").save(f"{IOS}/{name}")

# Refreshed source/preview with a WHITE background (per request).
compose(1024, FRAC_SQUARE).convert("RGB").save(os.path.join(HERE, "app_icon.jpeg"))
compose(1024, FRAC_SQUARE).convert("RGB").save(os.path.join(HERE, "app_icon_master.png"))
print("icons regenerated (white bg, emblem scaled to fill)")
