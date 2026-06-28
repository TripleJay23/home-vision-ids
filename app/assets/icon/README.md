# App icon — Home Vision IDS

Concept: a security **shield** enclosing a **vision eye** (cyan iris) on a deep-blue
gradient — "home security + computer vision". Ties to the app theme seed `#1565C0`.

## Source of truth
- `app_icon.png` — 1024² Android master (rounded corners, alpha).
- `app_icon_ios.png` — 1024² iOS master (square, **no alpha** — App Store requirement).
- `generate_icon.py` — Pillow generator that draws both masters from scratch.

## Regenerate
The platform icons were produced by drawing the masters, then resizing them into
every density. No SVG rasterizer or `flutter_launcher_icons` is required.

```bash
# 1. draw the masters
python app/assets/icon/generate_icon.py <out_dir>
# 2. resize into android mipmaps + ios appiconset (see scratchpad propagate script)
```

Targets written:
- Android legacy `@mipmap/ic_launcher` — mdpi 48, hdpi 72, xhdpi 96, xxhdpi 144, xxxhdpi 192.
- iOS `AppIcon.appiconset` — all sizes referenced by `Contents.json` (20–1024).

## Notes
- Android uses legacy icons only (no adaptive `mipmap-anydpi-v26`); the manifest
  references `@mipmap/ic_launcher`. To add adaptive icons later, split the mark
  (foreground) from the gradient (background) and add the v26 XML.
