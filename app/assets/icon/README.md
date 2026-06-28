# App icon — Home Vision IDS

A user-supplied emblem: a **camera aperture/shutter wrapping a house** —
"home + surveillance vision". Blue aperture + navy house on a **white** tile.

## Source of truth
- `app_icon.jpeg` — 1024² emblem on a **transparent** background (the mark only).
- `app_icon_master.png` — 1024² flattened preview (emblem over white).
- `generate_icon.py` — rebuilds every platform icon from `app_icon.jpeg`.

## Layout
- **Android adaptive** (`mipmap-anydpi-v26/ic_launcher.xml`):
  - foreground = `@mipmap/ic_launcher_foreground` (the transparent emblem, all 5 densities)
  - background = `@color/ic_launcher_background` = `#FFFFFF` (`res/values/colors.xml`)
  - The emblem sits in the central safe zone, so circle/squircle masking never clips it.
- **Android legacy** `@mipmap/ic_launcher` — emblem flattened over white, 5 densities (pre-API-26).
- **iOS** `AppIcon.appiconset` — emblem flattened over white, all sizes; the 1024 is alpha-free.

## Regenerate
```bash
python app/assets/icon/generate_icon.py   # reads app_icon.jpeg, writes all targets
```
Replace `app_icon.jpeg` with a new 1024² transparent-background mark and re-run.
