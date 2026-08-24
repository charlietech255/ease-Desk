"""User preferences and configuration management for ease-Desk."""

from __future__ import annotations

import configparser
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "easedesk"
CONFIG_FILE = CONFIG_DIR / "settings.ini"

_default_settings = {
    "Personalization": {
        "wallpaper_path": "",
        "wallpaper_mode": "fill",
        "solid_color": "#0b0e14",
        "theme_mode": "dark",
        "dock_position": "left",
        "panel_position": "top",
        "clock_format": "24h",
    },
    "Dock": {
        "pinned_apps": "ease-desk-files,browser,ease-desk-terminal,ease-desk-media-player,ease-desk-settings,ease-desk-task-manager"
    }
}

def _get_parser() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read_dict(_default_settings)
    if CONFIG_FILE.exists():
        parser.read(CONFIG_FILE)
    return parser

def get(section: str, key: str, fallback: str = "") -> str:
    parser = _get_parser()
    return parser.get(section, key, fallback=fallback)

def set(section: str, key: str, value: str) -> None:
    parser = _get_parser()
    if not parser.has_section(section):
        parser.add_section(section)
    parser.set(section, key, value)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w") as f:
        parser.write(f)

def get_pinned_apps() -> list[str]:
    apps_str = get("Dock", "pinned_apps", "ease-desk-files,browser,ease-desk-terminal,ease-desk-media-player,ease-desk-settings,ease-desk-task-manager")
    return [a.strip() for a in apps_str.split(",") if a.strip()]

def pin_app(app_id: str) -> None:
    apps = get_pinned_apps()
    if app_id not in apps:
        apps.append(app_id)
        set("Dock", "pinned_apps", ",".join(apps))

def unpin_app(app_id: str) -> None:
    apps = get_pinned_apps()
    if app_id in apps:
        apps.remove(app_id)
        set("Dock", "pinned_apps", ",".join(apps))
