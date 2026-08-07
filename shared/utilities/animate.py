"""Minimal, low-CPU GTK animation helpers.

All animations are short opacity/time-scaled fades driven by GLib.timeout
callbacks.  They are cheap enough for VPS-class hardware and never run longer
than a fraction of a second.
"""

from __future__ import annotations

from gi.repository import Gdk, GLib

_TICK_MS = 15
_EASE = 0.5  # ease-out exponent, cheap to compute


def _is_composited() -> bool:
    try:
        screen = Gdk.Screen.get_default()
        return screen is not None and screen.is_composited()
    except Exception:
        return False


def _step(widget, start, end, steps, on_done, state):
    state["n"] += 1
    t = min(1.0, state["n"] / steps)
    eased = 1 - (1 - t) ** 2  # ease-out quad
    value = start + (end - start) * eased
    try:
        widget.set_opacity(value)
    except Exception:
        pass
    if t >= 1.0:
        if on_done:
            on_done()
        return False
    return True


def fade_in(widget, duration_ms=220, on_done=None):
    """Fade a widget in from transparent to fully opaque."""
    if not _is_composited():
        widget.show()
        if on_done:
            on_done()
        return
    steps = max(2, int(duration_ms / _TICK_MS))
    widget.set_opacity(0.0)
    widget.show()
    GLib.timeout_add(_TICK_MS, _step, widget, 0.0, 1.0, steps, on_done, {"n": 0})


def fade_out(widget, duration_ms=200, on_done=None):
    """Fade a widget out; `on_done` is called when fully transparent."""
    if not _is_composited():
        if on_done:
            on_done()
        return
    steps = max(2, int(duration_ms / _TICK_MS))
    GLib.timeout_add(_TICK_MS, _step, widget, 1.0, 0.0, steps, on_done, {"n": 0})


def pulse(widget, property_getter, property_setter, start, peak, base, duration_ms=220):
    """Animate a scalar widget property up to `peak` and back to `base`.

    Used for the desktop icon hover effect (font size / padding).
    """
    state = {"n": 0}

    def tick():
        state["n"] += 1
        total = int(duration_ms / _TICK_MS)
        mid = total // 2
        n = state["n"]
        if n <= mid:
            t = n / mid
            v = start + (peak - start) * (1 - (1 - t) ** 2)
        else:
            t = (n - mid) / mid
            v = peak - (peak - base) * (1 - (1 - t) ** 2)
        property_setter(v)
        if n >= total:
            return False
        return True

    GLib.timeout_add(_TICK_MS, tick)
