"""Build Android (adaptive + legacy) and iOS launcher icons from the emblem.

Source: app/assets/icon/app_icon.jpeg — a centered emblem on a transparent
background (a camera aperture wrapping a house). Background layer: solid white.

Run from anywhere:  python app/assets/icon/generate_icon.py
"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))  # repo root
RES = os.path.join(ROOT, "app/android/app/src/main/res")
IOS = os.path.join(ROOT, "app/ios/Runner/Assets.xcassets/AppIcon.appiconset")
WHITE = (255, 255, 255, 255)

fg = Image.open(os.path.join(HERE, "app_icon.jpeg")).convert("RGBA")  # transparent emblem
comp = Image.new("RGBA", fg.size, WHITE)
comp.alpha_composite(fg)
comp_rgb = comp.convert("RGB")  # flattened, no alpha (legacy Android + iOS)

# Adaptive foreground (108dp base) — keeps transparency; emblem sits in the
# central safe zone so launcher masking never clips it.
for d, sz in {"mipmap-mdpi": 108, "mipmap-hdpi": 162, "mipmap-xhdpi": 216,
              "mipmap-xxhdpi": 324, "mipmap-xxxhdpi": 432}.items():
    fg.resize((sz, sz), Image.LANCZOS).save(f"{RES}/{d}/ic_launcher_foreground.png")

# Legacy launcher (48dp base) — flattened over white for pre-API-26 devices.
for d, sz in {"mipmap-mdpi": 48, "mipmap-hdpi": 72, "mipmap-xhdpi": 96,
              "mipmap-xxhdpi": 144, "mipmap-xxxhdpi": 192}.items():
    comp.resize((sz, sz), Image.LANCZOS).save(f"{RES}/{d}/ic_launcher.png")

# iOS — flattened over white, no alpha (App Store requirement on the 1024).
for name, sz in {
    "Icon-App-1024x1024@1x.png": 1024,
    "Icon-App-20x20@1x.png": 20, "Icon-App-20x20@2x.png": 40, "Icon-App-20x20@3x.png": 60,
    "Icon-App-29x29@1x.png": 29, "Icon-App-29x29@2x.png": 58, "Icon-App-29x29@3x.png": 87,
    "Icon-App-40x40@1x.png": 40, "Icon-App-40x40@2x.png": 80, "Icon-App-40x40@3x.png": 120,
    "Icon-App-60x60@2x.png": 120, "Icon-App-60x60@3x.png": 180,
    "Icon-App-76x76@1x.png": 76, "Icon-App-76x76@2x.png": 152, "Icon-App-83.5x83.5@2x.png": 167,
}.items():
    comp_rgb.resize((sz, sz), Image.LANCZOS).save(f"{IOS}/{name}")

comp_rgb.save(os.path.join(HERE, "app_icon_master.png"))  # flattened preview master
print("icons regenerated")
