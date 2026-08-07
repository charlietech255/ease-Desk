"""File-type recognition for Charlie File Manager.

Maps a filename to a category, a friendly description and an emoji glyph used
as the icon in the icon view.  Unsupported files degrade gracefully to basic
metadata ('other').
"""

from __future__ import annotations

ICONS = {
    "folder": "📁",
    "text": "📄",
    "image": "🖼️",
    "archive": "📦",
    "php": "🐘",
    "javascript": "📜",
    "html": "🌐",
    "css": "🎨",
    "json": "📋",
    "config": "⚙️",
    "script": "⚙️",
    "database": "🗄️",
    "pdf": "📕",
    "audio": "🎵",
    "video": "🎬",
    "link": "🔗",
    "other": "📄",
}

# extension -> (category, description)
_EXT_MAP = {
    # text
    "txt": ("text", "Text document"),
    "md": ("text", "Markdown document"),
    "markdown": ("text", "Markdown document"),
    "log": ("text", "Log file"),
    "csv": ("text", "CSV data"),
    "doc": ("text", "Word document"),
    "docx": ("text", "Word document"),
    # images
    "png": ("image", "PNG image"),
    "jpg": ("image", "JPEG image"),
    "jpeg": ("image", "JPEG image"),
    "gif": ("image", "GIF image"),
    "svg": ("image", "SVG image"),
    "webp": ("image", "WebP image"),
    "ico": ("image", "Icon image"),
    "bmp": ("image", "Bitmap image"),
    # archives
    "zip": ("archive", "ZIP archive"),
    "tar": ("archive", "TAR archive"),
    "gz": ("archive", "Gzip archive"),
    "tgz": ("archive", "Gzip archive"),
    "bz2": ("archive", "Bzip2 archive"),
    "xz": ("archive", "XZ archive"),
    "7z": ("archive", "7-Zip archive"),
    "rar": ("archive", "RAR archive"),
    # web / server
    "php": ("php", "PHP source"),
    "js": ("javascript", "JavaScript source"),
    "mjs": ("javascript", "JavaScript source"),
    "ts": ("javascript", "TypeScript source"),
    "html": ("html", "HTML document"),
    "htm": ("html", "HTML document"),
    "css": ("css", "CSS stylesheet"),
    "scss": ("css", "SCSS stylesheet"),
    "json": ("json", "JSON data"),
    "xml": ("json", "XML document"),
    # config
    "conf": ("config", "Configuration file"),
    "cfg": ("config", "Configuration file"),
    "ini": ("config", "INI configuration"),
    "yaml": ("config", "YAML configuration"),
    "yml": ("config", "YAML configuration"),
    "toml": ("config", "TOML configuration"),
    "env": ("config", "Environment file"),
    "service": ("config", "systemd unit file"),
    "list": ("config", "Package list"),
    "sources": ("config", "Sources list"),
    # scripts
    "sh": ("script", "Shell script"),
    "bash": ("script", "Bash script"),
    "py": ("script", "Python script"),
    "pl": ("script", "Perl script"),
    "rb": ("script", "Ruby script"),
    "go": ("script", "Go source"),
    # database
    "sql": ("database", "SQL file"),
    "db": ("database", "Database file"),
    "sqlite": ("database", "SQLite database"),
    "sqlite3": ("database", "SQLite database"),
    # documents / media
    "pdf": ("pdf", "PDF document"),
    "mp3": ("audio", "MP3 audio"),
    "wav": ("audio", "WAV audio"),
    "ogg": ("audio", "Ogg audio"),
    "flac": ("audio", "FLAC audio"),
    "mp4": ("video", "MP4 video"),
    "mkv": ("video", "Matroska video"),
    "webm": ("video", "WebM video"),
    "mov": ("video", "QuickTime video"),
    "avi": ("video", "AVI video"),
}


def categorize(name: str, is_dir: bool, is_link: bool = False):
    """Return (category, description, icon)."""
    if is_link:
        return "link", "Symbolic link", ICONS["link"]
    if is_dir:
        return "folder", "Folder", ICONS["folder"]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    category, description = _EXT_MAP.get(ext, ("other", f".{ext} file" if ext else "File"))
    return category, description, ICONS[category]
