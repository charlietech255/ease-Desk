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
