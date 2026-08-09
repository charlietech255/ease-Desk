"""High-quality GTK Icon Theme and Cairo Vector Fallback Engine for ease-Desk.

Provides crisp, theme-aware Pixbufs for all file types, system devices, and desktop
shortcuts. Guarantees 100% reliable rendering with zero missing font glyphs.
"""

from __future__ import annotations

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gtk

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
    "terminal": ["org.gnome.Terminal", "utilities-terminal", "terminal", "xterm"],
    "task_manager": ["org.gnome.SystemMonitor", "utilities-system-monitor", "system-monitor", "preferences-system"],
    "activity": ["org.gnome.SystemMonitor", "utilities-system-monitor", "system-monitor"],
    "browser": ["google-chrome", "chromium-browser", "firefox", "org.gnome.Epiphany", "epiphany", "web-browser", "applications-internet", "browser"],
    "editor": ["accessories-text-editor", "text-editor", "document-edit", "text-x-generic"],
    "settings": ["preferences-system", "system-settings", "preferences-desktop"],
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
    elif key in ("terminal", "cli", "bash", "console"):
        _draw_terminal(ctx)
    elif key in ("task_manager", "activity", "process", "monitor"):
        _draw_task_manager(ctx)
    elif key in ("browser", "web", "internet", "chromium", "firefox"):
        _draw_browser(ctx)
    elif key in ("editor", "text_editor", "code"):
        _draw_editor(ctx)
    elif key in ("settings", "preferences"):
        _draw_settings(ctx)
    elif key in ("computer", "server"):
        _draw_computer(ctx)
    elif key in ("webroot", "html"):
        _draw_webroot(ctx)
    elif key in ("drive", "database"):
        _draw_drive(ctx)
    elif key in ("image",):
        _draw_image(ctx)
    elif key in ("archive", "zip", "tar"):
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
    pb = Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)
    if pb is not None:
        return pb

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
# Professional, minimalistic, flat line-art style (GNOME Symbolic inspired)

def _setup_stroke(ctx: cairo.Context) -> None:
    ctx.set_source_rgb(0.65, 0.68, 0.78)  # Minimalist slate/silver
    ctx.set_line_width(4.5)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)

def _draw_folder(ctx: cairo.Context, key: str) -> None:
    _setup_stroke(ctx)
    ctx.set_source_rgb(0.53, 0.70, 0.98) # subtle blue for folders
    ctx.move_to(16, 26)
    ctx.line_to(38, 26)
    ctx.line_to(48, 38)
    ctx.line_to(84, 38)
    ctx.line_to(84, 80)
    ctx.line_to(16, 80)
    ctx.close_path()
    ctx.stroke()

def _draw_computer(ctx: cairo.Context) -> None:
    _setup_stroke(ctx)
    ctx.rectangle(16, 20, 68, 48)
    ctx.stroke()
    ctx.move_to(36, 80)
    ctx.line_to(64, 80)
    ctx.stroke()
    ctx.move_to(50, 68)
    ctx.line_to(50, 80)
    ctx.stroke()

def _draw_webroot(ctx: cairo.Context) -> None:
    _setup_stroke(ctx)
    ctx.arc(50, 50, 32, 0, 2 * 3.14159)
    ctx.stroke()
    ctx.save()
    ctx.translate(50, 50)
    ctx.scale(0.4, 1.0)
    ctx.arc(0, 0, 32, 0, 2 * 3.14159)
    ctx.restore()
    ctx.stroke()
    ctx.move_to(18, 50)
    ctx.line_to(82, 50)
    ctx.stroke()

def _draw_drive(ctx: cairo.Context) -> None:
    _setup_stroke(ctx)
    ctx.rectangle(24, 20, 52, 60)
    ctx.stroke()
    ctx.move_to(24, 64)
    ctx.line_to(76, 64)
    ctx.stroke()
    ctx.arc(50, 72, 3, 0, 2 * 3.14159)
    ctx.fill()

def _draw_file(ctx: cairo.Context, key: str) -> None:
    _setup_stroke(ctx)
    ctx.move_to(24, 16)
    ctx.line_to(56, 16)
    ctx.line_to(76, 36)
    ctx.line_to(76, 84)
    ctx.line_to(24, 84)
    ctx.close_path()
    ctx.stroke()
    ctx.move_to(56, 16)
    ctx.line_to(56, 36)
    ctx.line_to(76, 36)
    ctx.stroke()

def _draw_image(ctx: cairo.Context) -> None:
    _draw_file(ctx, "image")
    _setup_stroke(ctx)
    ctx.arc(42, 50, 4, 0, 2 * 3.14159)
    ctx.stroke()
    ctx.move_to(30, 70)
    ctx.line_to(46, 56)
    ctx.line_to(56, 66)
    ctx.line_to(64, 60)
    ctx.line_to(70, 68)
    ctx.stroke()

def _draw_archive(ctx: cairo.Context) -> None:
    _setup_stroke(ctx)
    ctx.rectangle(20, 24, 60, 56)
    ctx.stroke()
    ctx.move_to(20, 42)
    ctx.line_to(80, 42)
    ctx.stroke()
    ctx.move_to(40, 24)
    ctx.line_to(40, 52)
    ctx.stroke()
    ctx.move_to(60, 24)
    ctx.line_to(60, 52)
    ctx.stroke()

def _draw_script(ctx: cairo.Context) -> None:
    _draw_file(ctx, "script")
    _setup_stroke(ctx)
    ctx.move_to(36, 46)
    ctx.line_to(44, 54)
    ctx.line_to(36, 62)
    ctx.stroke()
    ctx.move_to(48, 62)
    ctx.line_to(60, 62)
    ctx.stroke()

def _draw_config(ctx: cairo.Context) -> None:
    _draw_file(ctx, "config")
    _setup_stroke(ctx)
    ctx.arc(50, 56, 8, 0, 2 * 3.14159)
    ctx.stroke()
    import math
    for i in range(4):
        angle = i * (math.pi / 2)
        ctx.save()
        ctx.translate(50, 56)
        ctx.rotate(angle)
        ctx.move_to(0, -8)
        ctx.line_to(0, -14)
        ctx.stroke()
        ctx.restore()

def _draw_video(ctx: cairo.Context) -> None:
    _draw_file(ctx, "video")
    _setup_stroke(ctx)
    ctx.move_to(42, 46)
    ctx.line_to(58, 56)
    ctx.line_to(42, 66)
    ctx.close_path()
    ctx.stroke()

def _draw_audio(ctx: cairo.Context) -> None:
    _draw_file(ctx, "audio")
    _setup_stroke(ctx)
    ctx.arc(42, 64, 6, 0, 2 * 3.14159)
    ctx.stroke()
    ctx.move_to(48, 64)
    ctx.line_to(48, 46)
    ctx.line_to(62, 42)
    ctx.line_to(62, 50)
    ctx.stroke()

def _draw_trash(ctx: cairo.Context) -> None:
    _setup_stroke(ctx)
    ctx.move_to(20, 24)
    ctx.line_to(80, 24)
    ctx.stroke()
    ctx.move_to(30, 24)
    ctx.line_to(34, 80)
    ctx.line_to(66, 80)
    ctx.line_to(70, 24)
    ctx.stroke()
    ctx.move_to(40, 20)
    ctx.line_to(60, 20)
    ctx.stroke()
    ctx.move_to(42, 34)
    ctx.line_to(44, 70)
    ctx.stroke()
    ctx.move_to(58, 34)
    ctx.line_to(56, 70)
    ctx.stroke()

def _draw_terminal(ctx: cairo.Context) -> None:
    _setup_stroke(ctx)
    ctx.rectangle(16, 22, 68, 56)
    ctx.stroke()
    ctx.move_to(26, 38)
    ctx.line_to(36, 48)
    ctx.line_to(26, 58)
    ctx.stroke()
    ctx.move_to(42, 58)
    ctx.line_to(56, 58)
    ctx.stroke()

def _draw_task_manager(ctx: cairo.Context) -> None:
    _setup_stroke(ctx)
    ctx.rectangle(16, 22, 68, 56)
    ctx.stroke()
    ctx.move_to(24, 50)
    ctx.line_to(34, 50)
    ctx.line_to(42, 34)
    ctx.line_to(54, 66)
    ctx.line_to(62, 50)
    ctx.line_to(72, 50)
    ctx.stroke()

def _draw_browser(ctx: cairo.Context) -> None:
    _setup_stroke(ctx)
    ctx.rectangle(16, 20, 68, 60)
    ctx.stroke()
    ctx.move_to(16, 34)
    ctx.line_to(84, 34)
    ctx.stroke()
    ctx.arc(50, 58, 14, 0, 2 * 3.14159)
    ctx.stroke()
    ctx.move_to(36, 58)
    ctx.line_to(64, 58)
    ctx.stroke()

def _draw_editor(ctx: cairo.Context) -> None:
    _setup_stroke(ctx)
    ctx.rectangle(16, 20, 68, 60)
    ctx.stroke()
    ctx.move_to(16, 32)
    ctx.line_to(84, 32)
    ctx.stroke()
    ctx.move_to(32, 46)
    ctx.line_to(68, 46)
    ctx.stroke()
    ctx.move_to(32, 56)
    ctx.line_to(56, 56)
    ctx.stroke()
    ctx.move_to(32, 66)
    ctx.line_to(74, 66)
    ctx.stroke()

def _draw_settings(ctx: cairo.Context) -> None:
    _setup_stroke(ctx)
    ctx.arc(50, 50, 16, 0, 2 * 3.14159)
    ctx.stroke()
    import math
    for i in range(8):
        angle = i * (math.pi / 4)
        ctx.save()
        ctx.translate(50, 50)
        ctx.rotate(angle)
        ctx.move_to(0, -16)
        ctx.line_to(0, -26)
        ctx.stroke()
        ctx.restore()


