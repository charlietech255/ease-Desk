"""Server system information for Charlie Desktop.

Lightweight, dependency-free probes (no external commands).  Every probe has a
graceful fallback so the desktop still works in minimal containers.
"""

from __future__ import annotations

import os
import re
import shutil
import socket


def hostname() -> str:
    return socket.gethostname() or "unknown"


def os_name() -> str:
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    value = line.split("=", 1)[1].strip().strip('"')
                    return value
    except OSError:
        pass
    return "Linux"


def cpu_count() -> int:
    if hasattr(os, "cpu_count") and os.cpu_count():
        return os.cpu_count()
    try:
        return sum(1 for _ in open("/proc/cpuinfo", encoding="utf-8", errors="replace")
                   if _.startswith("processor"))
    except OSError:
        return 1


def _kb_from_proc(pattern: str) -> int:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                m = re.match(pattern + r":\s+(\d+) kB", line)
                if m:
                    return int(m.group(1)) * 1024
    except OSError:
        pass
    return 0


def memory() -> tuple[int, int]:
    """Return (used_bytes, total_bytes) for physical memory."""
    total = _kb_from_proc("MemTotal")
    available = _kb_from_proc("MemAvailable")
    if not total:
        return (0, 0)
    used = max(0, total - available)
    return (used, total)


def disk(path: str = "/") -> tuple[int, int]:
    """Return (used_bytes, total_bytes) for the filesystem at `path`."""
    try:
        usage = shutil.disk_usage(path)
        return (usage.used, usage.total)
    except OSError:
        return (0, 0)


def partitions() -> list[dict]:
    """Return a list of storage partitions/disks with usage information."""
    results: list[dict] = []
    seen_mounts: set[str] = set()

    # Always ensure root filesystem is present
    try:
        u = shutil.disk_usage("/")
        results.append({
            "id": "root",
            "mount": "/",
            "device": "/dev/root",
            "fstype": "ext4",
            "name": "Local Disk (/)",
            "icon": "🗄️",
            "total": u.total,
            "used": u.used,
            "free": u.free,
            "percent": (u.used / u.total) if u.total > 0 else 0.0,
            "free_str": human_size(u.free),
            "total_str": human_size(u.total),
            "used_str": human_size(u.used),
        })
        seen_mounts.add("/")
    except OSError:
        pass

    # Probe /proc/mounts for real filesystems
    valid_fstypes = {
        "ext4", "ext3", "ext2", "xfs", "btrfs", "vfat", "fat", "fat32",
        "ntfs", "fuseblk", "exfat", "zfs", "f2fs", "cifs", "nfs", "nfs4",
    }
    ignore_prefixes = ("/proc", "/sys", "/dev", "/run/docker", "/var/lib/docker/overlay2")

    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 3:
                    dev, mount, fstype = parts[0], parts[1], parts[2]
                    if mount in seen_mounts:
                        continue
                    if any(mount.startswith(p) for p in ignore_prefixes):
                        continue
                    if fstype in valid_fstypes or dev.startswith("/dev/"):
                        if os.path.exists(mount):
                            try:
                                u = shutil.disk_usage(mount)
                                if u.total > 0:
                                    name = (
                                        "Home Storage (/home)" if mount == "/home"
                                        else f"Drive ({mount})"
                                    )
                                    results.append({
                                        "id": mount,
                                        "mount": mount,
                                        "device": dev,
                                        "fstype": fstype,
                                        "name": name,
                                        "icon": "🗄️",
                                        "total": u.total,
                                        "used": u.used,
                                        "free": u.free,
                                        "percent": (u.used / u.total) if u.total > 0 else 0.0,
                                        "free_str": human_size(u.free),
                                        "total_str": human_size(u.total),
                                        "used_str": human_size(u.used),
                                    })
                                    seen_mounts.add(mount)
                            except OSError:
                                pass
    except OSError:
        pass

    # Ensure /home is present if it exists
    if "/home" not in seen_mounts and os.path.exists("/home"):
        try:
            u = shutil.disk_usage("/home")
            if u.total > 0:
                results.append({
                    "id": "home",
                    "mount": "/home",
                    "device": "User Storage",
                    "fstype": "ext4",
                    "name": "Home Storage (/home)",
                    "icon": "📁",
                    "total": u.total,
                    "used": u.used,
                    "free": u.free,
                    "percent": (u.used / u.total) if u.total > 0 else 0.0,
                    "free_str": human_size(u.free),
                    "total_str": human_size(u.total),
                    "used_str": human_size(u.used),
                })
                seen_mounts.add("/home")
        except OSError:
            pass

    return results


def quick_folders() -> list[dict]:
    """Return common quick-access system and user folders."""
    candidates = [
        {"name": "Home", "icon": "🏠", "path": os.path.expanduser("~"), "desc": "Personal folder"},
        {"name": "Desktop", "icon": "🖥️", "path": os.path.expanduser("~/Desktop"), "desc": "Desktop files"},
        {"name": "Documents", "icon": "📄", "path": os.path.expanduser("~/Documents"), "desc": "Documents"},
        {"name": "Downloads", "icon": "📥", "path": os.path.expanduser("~/Downloads"), "desc": "Downloads"},
        {"name": "Web Root", "icon": "🌐", "path": "/var/www", "desc": "Web server (/var/www)"},
        {"name": "Config", "icon": "⚙️", "path": "/etc", "desc": "System configuration (/etc)"},
        {"name": "Logs", "icon": "📋", "path": "/var/log", "desc": "System logs (/var/log)"},
        {"name": "Root (FS)", "icon": "🗄️", "path": "/", "desc": "Root filesystem (/)"},
    ]
    return [c for c in candidates if os.path.exists(os.path.expanduser(c["path"]))]


def human_size(num: float) -> str:
    if num <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} PB"


def summary() -> dict:
    """A compact dict used by the desktop shell VPS info panel."""
    used, total = memory()
    dused, dtotal = disk("/")
    return {
        "hostname": hostname(),
        "os": os_name(),
        "cpu": cpu_count(),
        "mem_used": human_size(used),
        "mem_total": human_size(total),
        "disk_used": human_size(dused),
        "disk_total": human_size(dtotal),
    }
