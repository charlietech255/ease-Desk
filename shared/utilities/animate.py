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
    """Instant show to avoid VPS CPU lag."""
    widget.set_opacity(1.0)
    widget.show()
    if on_done:
        on_done()

def fade_out(widget, duration_ms=200, on_done=None):
    """Instant hide to avoid VPS CPU lag."""
    widget.set_opacity(0.0)
    widget.hide()
    if on_done:
        on_done()


def pulse(widget, property_getter, property_setter, start, peak, base, duration_ms=220):
    """No-op pulse to save CPU."""
    property_setter(base)
