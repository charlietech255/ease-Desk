"""High-quality GTK Icon Theme and Cairo Vector Fallback Engine for ease-Desk.

Provides crisp, theme-aware Pixbufs for all file types, system devices, and desktop
shortcuts. Guarantees 100% reliable rendering with zero missing font glyphs.
"""

from __future__ import annotations

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gtk

# Category to standard FreeDesktop GTK Icon Theme names
THEME_ICON_MAP = {
    "folder": ["folder", "folder-symbolic", "inode-directory"],
    "home": ["user-home", "folder-home", "user-home-symbolic", "folder"],
    "desktop": ["user-desktop", "desktop", "user-home", "folder"],
    "documents": ["folder-documents", "document-open", "folder"],
    "downloads": ["folder-download", "download", "folder"],
    "projects": ["folder-development", "folder-projects", "folder"],
    "text": ["text-x-generic", "document-edit", "accessories-text-editor"],
    "image": ["image-x-generic", "image-png", "image-jpeg"],
    "archive": ["package-x-generic", "archive-zip", "utilities-archive-manager"],
    "php": ["text-x-script", "text-x-generic"],
    "javascript": ["text-x-javascript", "text-x-script", "text-x-generic"],
    "html": ["text-html", "applications-internet", "text-x-generic"],
    "css": ["text-css", "text-x-generic"],
    "json": ["text-x-generic", "text-plain"],
    "config": ["preferences-system", "system-run", "accessories-text-editor"],
    "script": ["application-x-executable", "text-x-script", "system-run"],
    "database": ["server-database", "drive-harddisk", "drive-removable-media"],
    "pdf": ["x-office-document", "document-viewer", "text-x-generic"],
    "audio": ["audio-x-generic", "audio-mpeg", "multimedia-player"],
    "video": ["video-x-generic", "video-mp4", "multimedia-player"],
    "link": ["emblem-symbolic-link", "emblem-default", "link"],
    "other": ["text-x-generic", "text-plain"],
    "computer": ["computer", "video-display", "preferences-desktop-display", "drive-harddisk"],
    "webroot": ["applications-internet", "network-server", "folder-remote", "applications-web"],
    "server": ["network-server", "computer", "drive-harddisk"],
    "trash": ["user-trash", "trash-empty"],
    "drive": ["drive-harddisk", "media-flash", "drive-removable-media"],
}

_PIXBUF_CACHE: dict[tuple[str, int], GdkPixbuf.Pixbuf] = {}


def get_icon_pixbuf(key: str, size: int = 48) -> GdkPixbuf.Pixbuf:
    """Retrieve a cached Pixbuf for the specified icon key and pixel size."""
    cache_key = (key.lower(), size)
    if cache_key in _PIXBUF_CACHE:
        return _PIXBUF_CACHE[cache_key]

    theme = Gtk.IconTheme.get_default()
    names = THEME_ICON_MAP.get(key.lower(), [key, "text-x-generic"])

    # 1. Attempt lookup from GTK Icon Theme
    if theme:
        for name in names:
            if theme.has_icon(name):
                try:
                    pb = theme.load_icon(name, size, Gtk.IconLookupFlags.FORCE_SIZE)
                    if pb:
                        _PIXBUF_CACHE[cache_key] = pb
                        return pb
                except Exception:
                    pass

    # 2. Render Cairo Vector Fallback Icon
    pb = _render_cairo_fallback(key.lower(), size)
    _PIXBUF_CACHE[cache_key] = pb
    return pb


def _render_cairo_fallback(key: str, size: int) -> GdkPixbuf.Pixbuf:
    """Render a crisp, modern vector icon onto an ARGB32 Cairo surface and return a Pixbuf."""
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(surface)

    # Scale coordinate system to standard 100x100
    ctx.scale(size / 100.0, size / 100.0)

    if key in ("folder", "home", "desktop", "documents", "downloads", "projects"):
        _draw_folder(ctx, key)
    elif key in ("computer", "server"):
        _draw_computer(ctx)
    elif key in ("webroot", "html"):
        _draw_webroot(ctx)
    elif key in ("drive", "database"):
        _draw_drive(ctx)
    elif key in ("image",):
        _draw_image(ctx)
    elif key in ("archive",):
        _draw_archive(ctx)
    elif key in ("script", "php", "javascript"):
        _draw_script(ctx)
    elif key in ("config",):
        _draw_config(ctx)
    elif key in ("video",):
        _draw_video(ctx)
    elif key in ("audio",):
        _draw_audio(ctx)
    elif key in ("trash",):
        _draw_trash(ctx)
    else:
        _draw_file(ctx, key)

    # Convert Cairo surface to GdkPixbuf
    surface.flush()
    data = surface.get_data()
    stride = surface.get_stride()

    return GdkPixbuf.Pixbuf.new_from_data(
        bytes(data),
        GdkPixbuf.Colorspace.RGB,
        True,
        8,
        size,
        size,
        stride,
    )


# ---------------------------------------------------- Vector Icon Primitives
def _draw_folder(ctx: cairo.Context, key: str) -> None:
    # Back folder tab
    ctx.set_source_rgb(0.92, 0.65, 0.20)  # Amber gold
    ctx.rectangle(12, 22, 36, 16)
    ctx.fill()

    # Back folder body
    ctx.rectangle(12, 30, 76, 52)
    ctx.fill()

    # Front folder flap
    ctx.set_source_rgb(0.98, 0.76, 0.28)  # Bright amber
    ctx.move_to(12, 42)
    ctx.line_to(88, 42)
    ctx.line_to(84, 82)
    ctx.line_to(12, 82)
    ctx.close_path()
    ctx.fill()

    # Subtle highlight
    ctx.set_source_rgba(1.0, 1.0, 1.0, 0.35)
    ctx.rectangle(14, 44, 70, 4)
    ctx.fill()


def _draw_computer(ctx: cairo.Context) -> None:
    # Monitor frame
    ctx.set_source_rgb(0.20, 0.26, 0.38)  # Slate dark
    ctx.rectangle(14, 18, 72, 48)
    ctx.fill()

    # Screen display
    ctx.set_source_rgb(0.12, 0.53, 0.90)  # Tech cyan-blue
    ctx.rectangle(20, 24, 60, 36)
    ctx.fill()

    # Screen shine line
    ctx.set_source_rgba(1.0, 1.0, 1.0, 0.25)
    ctx.rectangle(20, 24, 60, 8)
    ctx.fill()

    # Stand
    ctx.set_source_rgb(0.28, 0.35, 0.48)
    ctx.rectangle(44, 66, 12, 12)
    ctx.rectangle(30, 78, 40, 6)
    ctx.fill()


def _draw_webroot(ctx: cairo.Context) -> None:
    # Outer circle (Globe)
    ctx.set_source_rgb(0.10, 0.65, 0.85)  # Cyan blue
    ctx.arc(50, 50, 36, 0, 2 * 3.14159)
    ctx.fill()

    # Globe latitude/longitude grid
    ctx.set_source_rgb(0.95, 0.98, 1.0)
    ctx.set_line_width(4)
    ctx.arc(50, 50, 36, 0, 2 * 3.14159)
    ctx.stroke()

    # Horizontal equator
    ctx.move_to(14, 50)
    ctx.line_to(86, 50)
    ctx.stroke()

    # Longitude ellipse
    ctx.save()
    ctx.translate(50, 50)
    ctx.scale(0.45, 1.0)
    ctx.arc(0, 0, 36, 0, 2 * 3.14159)
    ctx.restore()
    ctx.stroke()


def _draw_drive(ctx: cairo.Context) -> None:
    # Drive body
    ctx.set_source_rgb(0.25, 0.32, 0.42)
    ctx.rectangle(18, 26, 64, 48)
    ctx.fill()

    # Front face plate
    ctx.set_source_rgb(0.35, 0.44, 0.56)
    ctx.rectangle(22, 30, 56, 40)
    ctx.fill()

    # LED lights
    ctx.set_source_rgb(0.20, 0.85, 0.35)  # Green LED
    ctx.arc(32, 50, 4, 0, 2 * 3.14159)
    ctx.fill()

    ctx.set_source_rgb(0.20, 0.60, 0.95)  # Blue LED
    ctx.arc(46, 50, 4, 0, 2 * 3.14159)
    ctx.fill()


def _draw_file(ctx: cairo.Context, key: str) -> None:
    # Document sheet
    ctx.set_source_rgb(0.92, 0.94, 0.98)
    ctx.move_to(22, 16)
    ctx.line_to(62, 16)
    ctx.line_to(78, 32)
    ctx.line_to(78, 84)
    ctx.line_to(22, 84)
    ctx.close_path()
    ctx.fill()

    # Folded corner
    ctx.set_source_rgb(0.72, 0.76, 0.84)
    ctx.move_to(62, 16)
    ctx.line_to(62, 32)
    ctx.line_to(78, 32)
    ctx.close_path()
    ctx.fill()

    # Text lines
    ctx.set_source_rgb(0.55, 0.60, 0.72)
    ctx.rectangle(30, 42, 40, 4)
    ctx.rectangle(30, 52, 40, 4)
    ctx.rectangle(30, 62, 28, 4)
    ctx.fill()


def _draw_image(ctx: cairo.Context) -> None:
    # Image frame
    ctx.set_source_rgb(0.88, 0.40, 0.65)  # Magenta/purple
    ctx.rectangle(18, 20, 64, 60)
    ctx.fill()

    # Sun / Circle
    ctx.set_source_rgb(1.0, 0.90, 0.30)
    ctx.arc(36, 38, 8, 0, 2 * 3.14159)
    ctx.fill()

    # Mountains
    ctx.set_source_rgb(0.98, 0.98, 1.0)
    ctx.move_to(22, 74)
    ctx.line_to(44, 46)
    ctx.line_to(58, 64)
    ctx.line_to(76, 42)
    ctx.line_to(78, 74)
    ctx.close_path()
    ctx.fill()


def _draw_archive(ctx: cairo.Context) -> None:
    # Cardboard package box
    ctx.set_source_rgb(0.78, 0.58, 0.36)
    ctx.rectangle(18, 24, 64, 52)
    ctx.fill()

    # Tape strip
    ctx.set_source_rgb(0.92, 0.82, 0.62)
    ctx.rectangle(44, 24, 12, 52)
    ctx.rectangle(18, 46, 64, 8)
    ctx.fill()


def _draw_script(ctx: cairo.Context) -> None:
    # Terminal badge
    ctx.set_source_rgb(0.16, 0.20, 0.28)
    ctx.rectangle(18, 22, 64, 56)
    ctx.fill()

    # Terminal prompt `>_`
    ctx.set_source_rgb(0.25, 0.88, 0.45)  # Neon green
    ctx.set_line_width(5)
    ctx.move_to(28, 36)
    ctx.line_to(42, 50)
    ctx.line_to(28, 64)
    ctx.stroke()

    ctx.rectangle(48, 60, 16, 5)
    ctx.fill()


def _draw_config(ctx: cairo.Context) -> None:
    # Gear
    ctx.set_source_rgb(0.45, 0.52, 0.62)
    ctx.arc(50, 50, 28, 0, 2 * 3.14159)
    ctx.fill()

    # Gear teeth
    for i in range(8):
        ctx.save()
        ctx.translate(50, 50)
        ctx.rotate(i * (3.14159 / 4.0))
        ctx.rectangle(-6, -34, 12, 12)
        ctx.fill()
        ctx.restore()

    # Center hole
    ctx.set_source_rgb(0.12, 0.16, 0.22)
    ctx.arc(50, 50, 12, 0, 2 * 3.14159)
    ctx.fill()


def _draw_video(ctx: cairo.Context) -> None:
    # Film slate
    ctx.set_source_rgb(0.85, 0.25, 0.32)
    ctx.rectangle(18, 22, 64, 56)
    ctx.fill()

    # Play triangle
    ctx.set_source_rgb(1.0, 1.0, 1.0)
    ctx.move_to(42, 36)
    ctx.line_to(64, 50)
    ctx.line_to(42, 64)
    ctx.close_path()
    ctx.fill()


def _draw_audio(ctx: cairo.Context) -> None:
    # Music disc
    ctx.set_source_rgb(0.55, 0.35, 0.85)
    ctx.arc(50, 50, 32, 0, 2 * 3.14159)
    ctx.fill()

    # Inner disc
    ctx.set_source_rgb(0.25, 0.15, 0.45)
    ctx.arc(50, 50, 14, 0, 2 * 3.14159)
    ctx.fill()

    ctx.set_source_rgb(1.0, 1.0, 1.0)
    ctx.arc(50, 50, 4, 0, 2 * 3.14159)
    ctx.fill()


def _draw_trash(ctx: cairo.Context) -> None:
    # Trash can body
    ctx.set_source_rgb(0.55, 0.60, 0.68)
    ctx.rectangle(26, 32, 48, 50)
    ctx.fill()

    # Lid
    ctx.set_source_rgb(0.40, 0.45, 0.54)
    ctx.rectangle(20, 24, 60, 8)
    ctx.rectangle(42, 18, 16, 6)
    ctx.fill()
