"""Shared Wallpaper Utilities for ease-Desk.

Provides wallpaper catalog presets, solid color themes, display modes,
configuration management, thumbnail generator, and Cairo color helpers.
"""

from __future__ import annotations

import json
import os
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_DIR = os.path.expanduser("~/.config/ease-desk")
CONFIG_FILE = os.path.join(CONFIG_DIR, "desktop_config.json")
WALLPAPER_DIR = os.path.join(ROOT, "desktop", "assets", "wallpapers")
DEFAULT_WALLPAPER = os.path.join(WALLPAPER_DIR, "charlie-tech.png")

# Preset wallpapers shipped with ease-Desk
WALLPAPER_PRESETS: list[tuple[str, str]] = [
    ("Charlie Tech (Default)", os.path.join(WALLPAPER_DIR, "charlie-tech.png")),
    ("Kali Cyber Waves", os.path.join(WALLPAPER_DIR, "kali-waves.png")),
    ("Kali Purple Cubes", os.path.join(WALLPAPER_DIR, "kali-cubes-purple.jpg")),
]

# Preset solid color themes
SOLID_COLOR_PRESETS: list[tuple[str, str]] = [
    ("Obsidian Dark", "#0b0e14"),
    ("Deep Slate", "#0f172a"),
    ("Cyber Navy", "#1e1b4b"),
    ("Dark Emerald", "#042f2e"),
    ("Charcoal Zinc", "#18181b"),
]

# Supported wallpaper display modes
WALLPAPER_MODES: list[tuple[str, str]] = [
    ("fill", "Fill / Crop (Cover Screen)"),
    ("fit", "Fit (Preserve Aspect Ratio)"),
    ("stretch", "Stretch to Screen"),
    ("center", "Center Original"),
    ("solid", "Solid Color"),
]

IMAGE_EXTENSIONS: tuple[str, ...] = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".svg",
    ".gif",
)

_THUMBNAIL_CACHE: dict[tuple[str, int, int], Any] = {}


def hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    """Convert hex color string (e.g. '#0b0e14') to RGB floats (0.0 to 1.0)."""
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return (0.043, 0.055, 0.078)  # default #0b0e14
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        return (0.043, 0.055, 0.078)


def is_image_file(path: str) -> bool:
    """Return True if path is an existing file with an image extension."""
    if not path or not isinstance(path, str):
        return False
    _, ext = os.path.splitext(path.lower())
    return ext in IMAGE_EXTENSIONS and os.path.isfile(path)


def get_wallpaper_config(config_path: str = CONFIG_FILE) -> dict[str, Any]:
    """Read wallpaper configuration from desktop_config.json."""
    default_conf: dict[str, Any] = {
        "wallpaper": DEFAULT_WALLPAPER,
        "wallpaper_mode": "fill",
        "solid_color": "#0b0e14",
    }

    if not os.path.exists(config_path):
        return default_conf

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return default_conf

            wp = data.get("wallpaper")
            mode = data.get("wallpaper_mode", "fill")
            color = data.get("solid_color", "#0b0e14")

            # Fallback if wallpaper file does not exist
            if not wp or (mode != "solid" and not os.path.exists(wp)):
                wp = DEFAULT_WALLPAPER

            valid_modes = {m[0] for m in WALLPAPER_MODES}
            if mode not in valid_modes:
                mode = "fill"

            return {
                "wallpaper": wp,
                "wallpaper_mode": mode,
                "solid_color": color,
            }
    except Exception:
        return default_conf


def set_wallpaper(
    path: str | None,
    mode: str = "fill",
    solid_color: str | None = None,
    config_path: str = CONFIG_FILE,
) -> bool:
    """Update wallpaper path, mode, and solid color in configuration file."""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    # Read existing config to preserve other keys (like items)
    current_data: dict[str, Any] = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    current_data = loaded
        except Exception:
            current_data = {}

    if path:
        current_data["wallpaper"] = os.path.abspath(os.path.expanduser(path))
    elif "wallpaper" not in current_data:
        current_data["wallpaper"] = DEFAULT_WALLPAPER

    current_data["wallpaper_mode"] = mode
    if solid_color:
        current_data["solid_color"] = solid_color

    try:
        # Atomic write via temp file
        tmp_path = f"{config_path}.tmp.{os.getpid()}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=2)
        os.replace(tmp_path, config_path)
        return True
    except Exception:
        return False


def cycle_next_wallpaper(config_path: str = CONFIG_FILE) -> tuple[str, str]:
    """Cycle to the next preset wallpaper in the list and save to config."""
    conf = get_wallpaper_config(config_path)
    current_wp = conf.get("wallpaper", DEFAULT_WALLPAPER)

    preset_paths = [p[1] for p in WALLPAPER_PRESETS if os.path.exists(p[1])]
    if not preset_paths:
        return ("Default", DEFAULT_WALLPAPER)

    try:
        idx = preset_paths.index(current_wp)
        next_idx = (idx + 1) % len(preset_paths)
    except ValueError:
        next_idx = 0

    next_path = preset_paths[next_idx]
    next_name = next(
        (name for name, path in WALLPAPER_PRESETS if path == next_path),
        "Wallpaper",
    )

    set_wallpaper(next_path, mode="fill", config_path=config_path)
    return (next_name, next_path)


def get_thumbnail_pixbuf(
    image_path: str,
    target_w: int = 140,
    target_h: int = 88,
) -> Any:
    """Generate or retrieve a cached GdkPixbuf.Pixbuf thumbnail."""
    key = (image_path, target_w, target_h)
    if key in _THUMBNAIL_CACHE:
        return _THUMBNAIL_CACHE[key]

    if not os.path.exists(image_path):
        return None

    try:
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf

        # Load at scale preserving aspect ratio
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            image_path,
            target_w,
            target_h,
            True,
        )
        if pixbuf is not None:
            _THUMBNAIL_CACHE[key] = pixbuf
            return pixbuf
    except Exception:
        pass
    return None
