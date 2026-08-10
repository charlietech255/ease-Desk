"""ease-Desk Media Player — Main GTK3 Window.

Backend priority:
  1. GStreamer (gi.repository.Gst)  – supports all formats, embedded video
  2. subprocess mpv / vlc / ffplay  – fallback, opens in own window

Audio output routes through PulseAudio which KasmVNC streams to the browser.
"""

from __future__ import annotations

import math
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GLib", "2.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, GObject, Gtk, Pango

# ── GStreamer optional import ──────────────────────────────────────────────
_GST_OK = False
try:
    gi.require_version("Gst", "1.0")
    gi.require_version("GstVideo", "1.0")
    from gi.repository import Gst, GstVideo  # type: ignore[attr-defined]

    Gst.init(None)
    _GST_OK = True
except Exception:
    pass

# ── Supported formats ──────────────────────────────────────────────────────
AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".opus", ".wav", ".m4a", ".aac", ".wma", ".aiff"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".ts", ".m4v", ".wmv"}
ALL_MEDIA_EXTS = AUDIO_EXTS | VIDEO_EXTS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSS_PATH = os.path.join(os.path.dirname(__file__), "theme.css")


def _fmt_time(seconds: float) -> str:
    """Format seconds to mm:ss or hh:mm:ss."""
    if seconds < 0 or math.isnan(seconds):
        return "0:00"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def _is_media(path: str) -> bool:
    return Path(path).suffix.lower() in ALL_MEDIA_EXTS


def _is_video(path: str) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTS


# ══════════════════════════════════════════════════════════════════════════════
#  GStreamer backend
# ══════════════════════════════════════════════════════════════════════════════
class GstPlayer:
    """Thin GStreamer playbin wrapper."""

    def __init__(self) -> None:
        self._pipe = Gst.ElementFactory.make("playbin", "playbin")
        if self._pipe is None:
            raise RuntimeError("Could not create GStreamer playbin element")

        # Try embedded GtkSink for video
        self._video_widget: Gtk.Widget | None = None
        sink = Gst.ElementFactory.make("gtksink", "gtksink")
        if sink:
            self._pipe.set_property("video-sink", sink)
            self._video_widget = sink.props.widget  # type: ignore[union-attr]

        # Bus for EOS / error messages
        bus = self._pipe.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

        self._on_eos: Any = None
        self._on_error: Any = None
        self._on_tag: Any = None

    # ── Properties ────────────────────────────────────────────────────────
    @property
    def video_widget(self) -> Gtk.Widget | None:
        return self._video_widget

    def set_uri(self, uri: str) -> None:
        self._pipe.set_state(Gst.State.NULL)
        self._pipe.set_property("uri", uri)

    def play(self) -> None:
        self._pipe.set_state(Gst.State.PLAYING)

    def pause(self) -> None:
        self._pipe.set_state(Gst.State.PAUSED)

    def stop(self) -> None:
        self._pipe.set_state(Gst.State.NULL)

    def seek(self, position: float) -> None:
        """Seek to position in seconds."""
        ns = int(position * Gst.SECOND)
        self._pipe.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, ns)

    def get_position(self) -> float:
        ok, pos = self._pipe.query_position(Gst.Format.TIME)
        return pos / Gst.SECOND if ok else 0.0

    def get_duration(self) -> float:
        ok, dur = self._pipe.query_duration(Gst.Format.TIME)
        return dur / Gst.SECOND if ok else 0.0

    def set_volume(self, volume: float) -> None:
        """Volume 0.0–1.0."""
        self._pipe.set_property("volume", max(0.0, min(1.0, volume)))

    def is_playing(self) -> bool:
        _, state, _ = self._pipe.get_state(0)
        return state == Gst.State.PLAYING

    def destroy(self) -> None:
        self._pipe.set_state(Gst.State.NULL)

    # ── Internal ──────────────────────────────────────────────────────────
    def _on_bus_message(self, _bus: Any, msg: Any) -> None:
        t = msg.type
        if t == Gst.MessageType.EOS:
            if self._on_eos:
                GLib.idle_add(self._on_eos)
        elif t == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            if self._on_error:
                GLib.idle_add(self._on_error, str(err))
        elif t == Gst.MessageType.TAG:
            tags = msg.parse_tag()
            if self._on_tag:
                GLib.idle_add(self._on_tag, tags)


# ══════════════════════════════════════════════════════════════════════════════
#  Subprocess fallback backend  (mpv / vlc / ffplay)
# ══════════════════════════════════════════════════════════════════════════════
class SubprocessPlayer:
    """Launches mpv/vlc/ffplay as a child process (no embedded video)."""

    CANDIDATES = ["mpv", "vlc", "ffplay", "mplayer"]

    def __init__(self) -> None:
        self._cmd = None
        for c in self.CANDIDATES:
            if subprocess.run(["which", c], capture_output=True).returncode == 0:
                self._cmd = c
                break
        self._proc: subprocess.Popen | None = None
        self.video_widget = None
        self._on_eos: Any = None

    def set_uri(self, uri: str) -> None:
        self.stop()
        path = uri.replace("file://", "") if uri.startswith("file://") else uri
        if self._cmd == "mpv":
            args = [self._cmd, "--no-video", path]
        elif self._cmd == "vlc":
            args = [self._cmd, "--intf", "dummy", path]
        else:
            args = [self._cmd, path] if self._cmd else ["false"]
        self._args = args

    def play(self) -> None:
        if not self._proc or self._proc.poll() is not None:
            self._proc = subprocess.Popen(
                self._args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            threading.Thread(target=self._wait_eos, daemon=True).start()

    def pause(self) -> None:
        pass  # subprocess control is limited

    def stop(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def seek(self, _pos: float) -> None:
        pass

    def get_position(self) -> float:
        return 0.0

    def get_duration(self) -> float:
        return 0.0

    def set_volume(self, _v: float) -> None:
        pass

    def is_playing(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def destroy(self) -> None:
        self.stop()

    def _wait_eos(self) -> None:
        if self._proc:
            self._proc.wait()
            if self._on_eos:
                GLib.idle_add(self._on_eos)


# ══════════════════════════════════════════════════════════════════════════════
#  Animated Equalizer Widget
# ══════════════════════════════════════════════════════════════════════════════
class EqualizerWidget(Gtk.DrawingArea):
    NUM_BARS = 14

    def __init__(self) -> None:
        super().__init__()
        self._bars = [random.uniform(0.1, 0.5) for _ in range(self.NUM_BARS)]
        self._targets = [random.uniform(0.1, 0.9) for _ in range(self.NUM_BARS)]
        self._playing = False
        self._tick_id: int | None = None
        self.set_size_request(120, 60)
        self.connect("draw", self._on_draw)

    def set_playing(self, playing: bool) -> None:
        self._playing = playing
        if playing and self._tick_id is None:
            self._tick_id = GLib.timeout_add(80, self._tick)
        elif not playing and self._tick_id is not None:
            GLib.source_remove(self._tick_id)
            self._tick_id = None
            self.queue_draw()

    def _tick(self) -> bool:
        if not self._playing:
            self._tick_id = None
            return False
        for i in range(self.NUM_BARS):
            self._bars[i] += (self._targets[i] - self._bars[i]) * 0.35
            if abs(self._bars[i] - self._targets[i]) < 0.02:
                self._targets[i] = random.uniform(0.05, 0.95)
        self.queue_draw()
        return True

    def _on_draw(self, _w: Gtk.Widget, cr: Any) -> None:
        alloc = self.get_allocation()
        w, h = alloc.width, alloc.height
        bar_w = max(3, (w - (self.NUM_BARS - 1) * 2) // self.NUM_BARS)
        for i, lvl in enumerate(self._bars):
            bh = int(h * (lvl if self._playing else 0.05))
            x = i * (bar_w + 2)
            y = h - bh
            # Gradient: blue → cyan
            t = i / max(1, self.NUM_BARS - 1)
            r = 0.412 + (0.455 - 0.412) * t
            g = 0.443 + (0.784 - 0.443) * t
            b = 0.980 + (0.925 - 0.980) * t
            alpha = 0.9 if self._playing else 0.3
            cr.set_source_rgba(r, g, b, alpha)
            cr.rectangle(x, y, bar_w, bh)
            cr.fill()


# ══════════════════════════════════════════════════════════════════════════════
#  Playlist Row
# ══════════════════════════════════════════════════════════════════════════════
class PlaylistRow(Gtk.ListBoxRow):
    def __init__(self, filepath: str) -> None:
        super().__init__()
        self.filepath = filepath
        self.duration_str = "–:––"
        self.get_style_context().add_class("mp-playlist-item")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(8)
        box.set_margin_end(8)

        # Icon
        is_vid = _is_video(filepath)
        icon_lbl = Gtk.Label(label="🎬" if is_vid else "🎵")
        icon_lbl.set_margin_end(2)
        box.pack_start(icon_lbl, False, False, 0)

        # Name + duration
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        name = Path(filepath).stem
        self.name_label = Gtk.Label(label=name)
        self.name_label.set_xalign(0)
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_label.get_style_context().add_class("mp-track-name")
        self.dur_label = Gtk.Label(label="–:––")
        self.dur_label.set_xalign(0)
        self.dur_label.get_style_context().add_class("mp-track-duration")
        info_box.pack_start(self.name_label, False, False, 0)
        info_box.pack_start(self.dur_label, False, False, 0)
        box.pack_start(info_box, True, True, 0)

        self.add(box)

    def set_playing(self, playing: bool) -> None:
        ctx = self.name_label.get_style_context()
        if playing:
            ctx.add_class("playing")
        else:
            ctx.remove_class("playing")
        ctx2 = self.get_style_context()
        if playing:
            ctx2.add_class("playing")
        else:
            ctx2.remove_class("playing")

    def set_duration(self, seconds: float) -> None:
        self.duration_str = _fmt_time(seconds)
        self.dur_label.set_text(self.duration_str)


# ══════════════════════════════════════════════════════════════════════════════
#  Main Media Player Window
# ══════════════════════════════════════════════════════════════════════════════
class MediaPlayerWindow(Gtk.Window):
    def __init__(self, files: list[str] | None = None) -> None:
        super().__init__(title="ease-Desk Media Player")
        self.set_default_size(900, 560)
        self.set_resizable(True)

        # Window decoration
        self.get_style_context().add_class("media-player")
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("Media Player")
        self.set_titlebar(header)

        # Load CSS
        provider = Gtk.CssProvider()
        if os.path.exists(CSS_PATH):
            provider.load_from_path(CSS_PATH)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # State
        self._playlist: list[str] = []
        self._current_idx: int = -1
        self._seeking = False
        self._duration: float = 0.0
        self._tags: dict[str, str] = {}
        self._shuffle = False
        self._repeat = False

        # Backend
        self._player = self._make_player()
        self._player._on_eos = self._on_track_end  # type: ignore[assignment]

        # Build UI
        self._build_ui()

        # Polling timer (position updates)
        GLib.timeout_add(300, self._poll_position)

        # Load initial files
        if files:
            self._add_files(files)

        self.connect("destroy", self._on_destroy)

        # Keyboard shortcuts
        self.connect("key-press-event", self._on_key)

    # ── Backend factory ────────────────────────────────────────────────────
    def _make_player(self) -> GstPlayer | SubprocessPlayer:
        if _GST_OK:
            try:
                return GstPlayer()
            except Exception:
                pass
        return SubprocessPlayer()

    # ── UI Construction ────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(root)

        # ── Left Sidebar (Playlist) ────────────────────────────────────────
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar.get_style_context().add_class("mp-sidebar")
        sidebar.set_size_request(230, -1)

        sidebar_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        sidebar_header.get_style_context().add_class("mp-sidebar-header")
        sidebar_header.set_margin_start(14)
        sidebar_header.set_margin_end(8)
        sidebar_header.set_margin_top(10)
        sidebar_header.set_margin_bottom(10)
        pl_label = Gtk.Label(label="PLAYLIST")
        pl_label.set_xalign(0)
        sidebar_header.pack_start(pl_label, True, True, 0)

        # Add files button
        add_btn = Gtk.Button(label="＋ Add")
        add_btn.get_style_context().add_class("mp-add-btn")
        add_btn.connect("clicked", self._on_add_files)
        sidebar_header.pack_end(add_btn, False, False, 0)
        sidebar.pack_start(sidebar_header, False, False, 0)

        # Playlist listbox
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect("row-activated", self._on_row_activated)
        scroll.add(self._listbox)
        sidebar.pack_start(scroll, True, True, 0)

        # Clear playlist button
        clear_btn = Gtk.Button(label="Clear Playlist")
        clear_btn.get_style_context().add_class("mp-add-btn")
        clear_btn.set_margin_top(4)
        clear_btn.set_margin_bottom(8)
        clear_btn.connect("clicked", self._on_clear_playlist)
        sidebar.pack_end(clear_btn, False, False, 0)

        root.pack_start(sidebar, False, False, 0)

        # ── Right Pane ─────────────────────────────────────────────────────
        right_pane = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.pack_start(right_pane, True, True, 0)

        # Canvas / Video / Art area
        self._canvas_stack = Gtk.Stack()
        self._canvas_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._canvas_stack.set_transition_duration(200)

        # ── Audio art page ─────────────────────────────────────────────────
        audio_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        audio_page.set_halign(Gtk.Align.CENTER)
        audio_page.set_valign(Gtk.Align.CENTER)
        audio_page.get_style_context().add_class("mp-art-overlay")

        self._art_icon = Gtk.Label(label="🎵")
        self._art_icon.get_style_context().add_class("mp-art-icon")
        audio_page.pack_start(self._art_icon, False, False, 0)

        self._art_pixbuf_widget = Gtk.Image()
        self._art_pixbuf_widget.set_size_request(160, 160)
        self._art_pixbuf_widget.set_no_show_all(True)
        audio_page.pack_start(self._art_pixbuf_widget, False, False, 0)

        self._audio_title = Gtk.Label(label="No track loaded")
        self._audio_title.get_style_context().add_class("mp-audio-title")
        self._audio_title.set_ellipsize(Pango.EllipsizeMode.END)
        self._audio_title.set_max_width_chars(30)
        audio_page.pack_start(self._audio_title, False, False, 0)

        self._audio_artist = Gtk.Label(label="")
        self._audio_artist.get_style_context().add_class("mp-audio-artist")
        audio_page.pack_start(self._audio_artist, False, False, 0)

        # Equalizer bars
        self._eq = EqualizerWidget()
        audio_page.pack_start(self._eq, False, False, 8)

        self._canvas_stack.add_named(audio_page, "audio")

        # ── Video page ─────────────────────────────────────────────────────
        if isinstance(self._player, GstPlayer) and self._player.video_widget:
            vid_widget = self._player.video_widget
            self._canvas_stack.add_named(vid_widget, "video")
        else:
            no_vid = Gtk.Label(label="No video output\n(install gstreamer1.0-plugins-good)")
            no_vid.set_halign(Gtk.Align.CENTER)
            no_vid.set_valign(Gtk.Align.CENTER)
            self._canvas_stack.add_named(no_vid, "video")

        self._canvas_stack.set_visible_child_name("audio")
        right_pane.pack_start(self._canvas_stack, True, True, 0)

        # ── Controls ───────────────────────────────────────────────────────
        controls = self._build_controls()
        right_pane.pack_end(controls, False, False, 0)

    def _build_controls(self) -> Gtk.Box:
        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        wrapper.get_style_context().add_class("mp-controls")

        # ── Seek bar row ───────────────────────────────────────────────────
        seek_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        seek_row.set_margin_bottom(6)

        self._time_label = Gtk.Label(label="0:00")
        self._time_label.get_style_context().add_class("mp-time-label")
        self._time_label.set_xalign(0)
        seek_row.pack_start(self._time_label, False, False, 0)

        self._seek_adj = Gtk.Adjustment(value=0, lower=0, upper=100, step_increment=1, page_increment=10)
        self._seek_bar = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self._seek_adj)
        self._seek_bar.set_draw_value(False)
        self._seek_bar.set_hexpand(True)
        self._seek_bar.get_style_context().add_class("mp-seek")
        self._seek_bar.connect("button-press-event", lambda *_: setattr(self, "_seeking", True))
        self._seek_bar.connect("button-release-event", self._on_seek_released)
        seek_row.pack_start(self._seek_bar, True, True, 0)

        self._dur_label = Gtk.Label(label="0:00")
        self._dur_label.get_style_context().add_class("mp-time-label")
        self._dur_label.set_xalign(1)
        seek_row.pack_end(self._dur_label, False, False, 0)

        wrapper.pack_start(seek_row, False, False, 0)

        # ── Buttons row ────────────────────────────────────────────────────
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_row.set_halign(Gtk.Align.CENTER)
        btn_row.set_margin_top(4)

        def ctrl_btn(label: str, primary: bool = False) -> Gtk.Button:
            b = Gtk.Button(label=label)
            b.get_style_context().add_class("mp-ctrl-btn")
            if primary:
                b.get_style_context().add_class("primary")
            return b

        self._shuf_btn = ctrl_btn("⇀")
        self._shuf_btn.set_tooltip_text("Shuffle")
        self._shuf_btn.connect("clicked", self._on_shuffle_toggle)
        btn_row.pack_start(self._shuf_btn, False, False, 0)

        prev_btn = ctrl_btn("⏮")
        prev_btn.set_tooltip_text("Previous")
        prev_btn.connect("clicked", self._on_prev)
        btn_row.pack_start(prev_btn, False, False, 0)

        self._play_btn = ctrl_btn("▶", primary=True)
        self._play_btn.set_tooltip_text("Play / Pause")
        self._play_btn.connect("clicked", self._on_play_pause)
        btn_row.pack_start(self._play_btn, False, False, 0)

        next_btn = ctrl_btn("⏭")
        next_btn.set_tooltip_text("Next")
        next_btn.connect("clicked", self._on_next)
        btn_row.pack_start(next_btn, False, False, 0)

        self._rep_btn = ctrl_btn("↺")
        self._rep_btn.set_tooltip_text("Repeat")
        self._rep_btn.connect("clicked", self._on_repeat_toggle)
        btn_row.pack_start(self._rep_btn, False, False, 0)

        # Volume
        vol_sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        vol_sep.set_margin_start(12)
        vol_sep.set_margin_end(8)
        btn_row.pack_start(vol_sep, False, False, 0)

        vol_icon = Gtk.Label(label="🔊")
        vol_icon.get_style_context().add_class("mp-vol-icon")
        btn_row.pack_start(vol_icon, False, False, 0)

        self._vol_adj = Gtk.Adjustment(value=80, lower=0, upper=100, step_increment=5, page_increment=10)
        vol_bar = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self._vol_adj)
        vol_bar.set_draw_value(False)
        vol_bar.set_size_request(90, -1)
        vol_bar.get_style_context().add_class("mp-volume")
        vol_bar.connect("value-changed", self._on_volume_changed)
        btn_row.pack_start(vol_bar, False, False, 0)

        wrapper.pack_start(btn_row, False, False, 0)

        # Set initial volume
        self._player.set_volume(0.8)

        return wrapper

    # ── File handling ──────────────────────────────────────────────────────
    def _add_files(self, paths: list[str]) -> None:
        for p in paths:
            resolved = os.path.abspath(p)
            if os.path.isdir(resolved):
                for fname in sorted(os.listdir(resolved)):
                    full = os.path.join(resolved, fname)
                    if _is_media(full):
                        self._add_single(full)
            elif os.path.isfile(resolved) and _is_media(resolved):
                self._add_single(resolved)

        # Auto-play first track if nothing playing
        if self._current_idx < 0 and self._playlist:
            self._play_index(0)

    def _add_single(self, path: str) -> None:
        if path in self._playlist:
            return
        self._playlist.append(path)
        row = PlaylistRow(path)
        self._listbox.add(row)
        self._listbox.show_all()

    def _on_add_files(self, _btn: Gtk.Button) -> None:
        dialog = Gtk.FileChooserDialog(
            title="Add Media Files",
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog.add_button(Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        dialog.set_select_multiple(True)

        f_all = Gtk.FileFilter()
        f_all.set_name("All Media Files")
        for ext in sorted(ALL_MEDIA_EXTS):
            f_all.add_pattern(f"*{ext}")
            f_all.add_pattern(f"*{ext.upper()}")
        dialog.add_filter(f_all)

        f_audio = Gtk.FileFilter()
        f_audio.set_name("Audio Files")
        for ext in sorted(AUDIO_EXTS):
            f_audio.add_pattern(f"*{ext}")
        dialog.add_filter(f_audio)

        f_video = Gtk.FileFilter()
        f_video.set_name("Video Files")
        for ext in sorted(VIDEO_EXTS):
            f_video.add_pattern(f"*{ext}")
        dialog.add_filter(f_video)

        dialog.set_current_folder(os.path.expanduser("~"))

        if dialog.run() == Gtk.ResponseType.OK:
            self._add_files(dialog.get_filenames())
        dialog.destroy()

    def _on_clear_playlist(self, _btn: Gtk.Button) -> None:
        self._player.stop()
        self._playlist.clear()
        self._current_idx = -1
        for row in self._listbox.get_children():
            self._listbox.remove(row)
        self._play_btn.set_label("▶")
        self._audio_title.set_text("No track loaded")
        self._audio_artist.set_text("")
        self._eq.set_playing(False)

    # ── Playback ───────────────────────────────────────────────────────────
    def _play_index(self, idx: int) -> None:
        if not self._playlist or idx < 0 or idx >= len(self._playlist):
            return
        self._current_idx = idx
        path = self._playlist[idx]
        uri = Path(path).as_uri()

        # Highlight row
        for i, row in enumerate(self._listbox.get_children()):
            if isinstance(row, PlaylistRow):
                row.set_playing(i == idx)

        self._player.set_uri(uri)
        self._player.play()
        self._play_btn.set_label("⏸")

        name = Path(path).stem
        self._audio_title.set_text(name)
        self._audio_artist.set_text("")
        self._tags = {}

        # Switch canvas
        is_vid = _is_video(path)
        self._canvas_stack.set_visible_child_name("video" if is_vid else "audio")
        self._art_icon.set_visible(not is_vid)
        self._eq.set_playing(not is_vid)

    def _on_play_pause(self, _btn: Gtk.Button) -> None:
        if not self._playlist:
            self._on_add_files(_btn)
            return
        if self._current_idx < 0:
            self._play_index(0)
            return
        if self._player.is_playing():
            self._player.pause()
            self._play_btn.set_label("▶")
            self._eq.set_playing(False)
        else:
            self._player.play()
            self._play_btn.set_label("⏸")
            is_vid = _is_video(self._playlist[self._current_idx]) if self._playlist else False
            self._eq.set_playing(not is_vid)

    def _on_prev(self, _btn: Gtk.Button) -> None:
        if not self._playlist:
            return
        idx = self._current_idx - 1
        if idx < 0:
            idx = len(self._playlist) - 1
        self._play_index(idx)

    def _on_next(self, _btn: Gtk.Button) -> None:
        if not self._playlist:
            return
        if self._shuffle:
            idx = random.randint(0, len(self._playlist) - 1)
        else:
            idx = self._current_idx + 1
            if idx >= len(self._playlist):
                idx = 0
        self._play_index(idx)

    def _on_track_end(self) -> None:
        if self._repeat:
            self._play_index(self._current_idx)
        else:
            self._on_next(None)

    def _on_shuffle_toggle(self, btn: Gtk.Button) -> None:
        self._shuffle = not self._shuffle
        btn.set_label("⇄" if self._shuffle else "⇀")

    def _on_repeat_toggle(self, btn: Gtk.Button) -> None:
        self._repeat = not self._repeat
        btn.set_label("↻" if self._repeat else "↺")

    def _on_row_activated(self, _lb: Gtk.ListBox, row: PlaylistRow) -> None:
        idx = row.get_index()
        self._play_index(idx)

    # ── Seek & Volume ──────────────────────────────────────────────────────
    def _on_seek_released(self, _scale: Gtk.Scale, _event: Any) -> None:
        self._seeking = False
        pos = self._seek_adj.get_value()
        if self._duration > 0:
            self._player.seek(pos / 100.0 * self._duration)

    def _on_volume_changed(self, scale: Gtk.Scale) -> None:
        self._player.set_volume(scale.get_value() / 100.0)

    # ── Position polling ───────────────────────────────────────────────────
    def _poll_position(self) -> bool:
        pos = self._player.get_position()
        dur = self._player.get_duration()
        if dur > 0:
            self._duration = dur
            if not self._seeking:
                frac = pos / dur * 100.0
                self._seek_adj.set_value(frac)
            self._time_label.set_text(_fmt_time(pos))
            self._dur_label.set_text(_fmt_time(dur))
            # Update row duration
            rows = self._listbox.get_children()
            if 0 <= self._current_idx < len(rows):
                row = rows[self._current_idx]
                if isinstance(row, PlaylistRow) and row.duration_str == "–:––":
                    row.set_duration(dur)
        return True  # keep polling

    # ── Keyboard shortcuts ─────────────────────────────────────────────────
    def _on_key(self, _win: Gtk.Window, event: Gdk.EventKey) -> bool:
        key = event.keyval
        if key == Gdk.KEY_space:
            self._on_play_pause(self._play_btn)
            return True
        if key == Gdk.KEY_Right:
            self._player.seek(self._player.get_position() + 5)
            return True
        if key == Gdk.KEY_Left:
            self._player.seek(max(0, self._player.get_position() - 5))
            return True
        if key == Gdk.KEY_n:
            self._on_next(None)
            return True
        if key == Gdk.KEY_p:
            self._on_prev(None)
            return True
        return False

    def _on_destroy(self, _win: Gtk.Window) -> None:
        self._player.destroy()
