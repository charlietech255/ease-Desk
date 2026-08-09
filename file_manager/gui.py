"""ease-Desk This PC & File Manager main window.

Implements Windows "This PC" partition & storage overview, plus full file explorer
with icon view, drag-and-drop file organization, sorting, context menus,
keyboard shortcuts, navigation history and system status.
"""

from __future__ import annotations

import html
import os
import subprocess
import sys
import urllib.parse
from html import escape

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

from file_manager.core import fs, types  # noqa: E402
from file_manager.viewer import ImageViewerWindow, TextViewerWindow  # noqa: E402
from shared.utilities import animate, sysinfo, wallpaper  # noqa: E402
from shared.utilities.icons import get_icon_pixbuf  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DRAG_TARGET_URI = 0
DRAG_TARGET_TEXT = 1
THIS_PC_URI = "thispc://"


def _mk(tooltip: str) -> Gtk.Button:
    btn = Gtk.Button.new_with_label(tooltip)
    btn.set_tooltip_text(tooltip)
    btn.get_style_context().add_class("tool-btn")
    return btn


class FileManagerWindow(Gtk.Window):
    def __init__(self, start_path: str = THIS_PC_URI):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("This PC — ease-Desk")
        self.set_default_size(960, 620)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(False)  # Let Openbox handle close button
        self.header.set_title("This PC")
        self.header.set_subtitle("Devices and drives")

        self.history: list[str] = []
        self.history_index: int = -1
        self.clipboard: tuple[str, list[str]] | None = None  # (mode, paths)
        self.current_dir: str = THIS_PC_URI
        self.sort_field: str = "name"
        self.sort_reverse: bool = False

        self._build_ui()
        self._build_menu()
        self._setup_dnd()

        self.connect("delete-event", self._on_delete_event)
        self.connect("key-press-event", self._on_key_press)
        self.view.connect("item-activated", self._on_item_activated)
        self.view.connect("button-press-event", self._on_view_button_press)
        self.path_entry.connect("activate", self._on_path_activate)

        # Start navigation
        init_target = start_path if start_path else THIS_PC_URI
        self._navigate(init_target, record=False)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.pack_start(self.header, False, False, 0)
        root.pack_start(self._build_toolbar(), False, False, 0)

        # Action bar (visible in folder view)
        self.action_bar = self._build_actions()
        root.pack_start(self.action_bar, False, False, 0)

        # Main Stack: page 1 = This PC overview, page 2 = File Explorer
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(180)

        # ---- PAGE 1: THIS PC (Drives & Partitions Overview) ----
        self.thispc_container = self._build_thispc_view()
        self.stack.add_named(self.thispc_container, "thispc")

        # ---- PAGE 2: FOLDER EXPLORER (IconView) ----
        self.explorer_container = self._build_explorer_view()
        self.stack.add_named(self.explorer_container, "explorer")

        root.pack_start(self.stack, True, True, 0)

        # Bottom status bar
        self.status_label = Gtk.Label(label="")
        self.status_label.set_xalign(0)
        self.status_label.get_style_context().add_class("statusbar")
        root.pack_start(self.status_label, False, False, 0)

        self.add(root)

    def _build_toolbar(self) -> Gtk.Widget:
        bar = Gtk.Toolbar()
        bar.set_style(Gtk.ToolbarStyle.TEXT)
        bar.get_style_context().add_class("toolbar")

        self.back_btn = _mk("← Back")
        self.forward_btn = _mk("→ Forward")
        self.up_btn = _mk("↑ Up")
        self.thispc_btn = _mk("This PC")
        self.home_btn = _mk("~ Home")

        for btn in (self.back_btn, self.forward_btn, self.up_btn, self.thispc_btn, self.home_btn):
            item = Gtk.ToolItem()
            item.add(btn)
            bar.insert(item, -1)
            bar.insert(Gtk.SeparatorToolItem(), -1)

        self.back_btn.connect("clicked", lambda *_: self._history_move(-1))
        self.forward_btn.connect("clicked", lambda *_: self._history_move(1))
        self.up_btn.connect("clicked", lambda *_: self._go_up())
        self.thispc_btn.connect("clicked", lambda *_: self._navigate(THIS_PC_URI))
        self.home_btn.connect("clicked", lambda *_: self._navigate(os.path.expanduser("~")))

        self.path_entry = Gtk.Entry()
        self.path_entry.set_hexpand(True)
        self.path_entry.set_placeholder_text("Enter path or 'thispc'…")
        path_item = Gtk.ToolItem()
        path_item.set_expand(True)
        path_item.add(self.path_entry)
        bar.insert(path_item, -1)

        self.sort_btn = _mk("⇃⇂ Arrange")
        item_sort = Gtk.ToolItem()
        item_sort.add(self.sort_btn)
        bar.insert(item_sort, -1)
        self.sort_btn.connect("clicked", lambda *_: self._popup_sort_menu())

        self.refresh_btn = _mk("⟳ Refresh")
        item = Gtk.ToolItem()
        item.add(self.refresh_btn)
        bar.insert(item, -1)
        self.refresh_btn.connect("clicked", lambda *_: self._reload())

        self.menu_btn = _mk("☰")
        item = Gtk.ToolItem()
        item.add(self.menu_btn)
        bar.insert(item, -1)
        self.menu_btn.connect("clicked", lambda *_: self._popup_menu(None))

        return bar

    def _build_actions(self) -> Gtk.Widget:
        actions = [
            ("Open", self._open_selected),
            ("New Folder", self._new_folder),
            ("Rename", self._rename_selected),
            ("Delete", self._delete_selected),
            ("Copy", self._copy_selected),
            ("Cut", self._cut_selected),
            ("Paste", self._paste),
            ("Properties", self._properties_selected),
        ]
        bar = Gtk.Box(spacing=6)
        bar.set_no_show_all(True)
        bar.get_style_context().add_class("action-bar")
        for label, callback in actions:
            btn = _mk(label)
            btn.get_style_context().add_class("action-btn")
            btn.connect("clicked", lambda *_, cb=callback: cb())
            bar.pack_start(btn, False, False, 0)
        return bar

    # ---------------------------------------------------- THIS PC VIEW
    def _build_thispc_view(self) -> Gtk.Widget:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        vbox.get_style_context().add_class("thispc-container")

        # System Banner
        self.banner_label = Gtk.Label()
        self.banner_label.get_style_context().add_class("thispc-banner")
        self.banner_label.set_xalign(0)
        vbox.pack_start(self.banner_label, False, False, 0)

        # Section 1: Devices and drives
        drives_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_drives = Gtk.Label(label="Devices and drives")
        lbl_drives.get_style_context().add_class("thispc-sec-title")
        lbl_drives.set_xalign(0)
        drives_header.pack_start(lbl_drives, False, False, 0)
        drives_header.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), True, True, 0)
        vbox.pack_start(drives_header, False, False, 0)

        self.drives_flow = Gtk.FlowBox()
        self.drives_flow.set_valign(Gtk.Align.START)
        self.drives_flow.set_max_children_per_line(3)
        self.drives_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.drives_flow.set_row_spacing(10)
        self.drives_flow.set_column_spacing(12)
        vbox.pack_start(self.drives_flow, False, False, 0)

        # Section 2: Quick Folders
        folders_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_folders = Gtk.Label(label="Quick Folders")
        lbl_folders.get_style_context().add_class("thispc-sec-title")
        lbl_folders.set_xalign(0)
        folders_header.pack_start(lbl_folders, False, False, 0)
        folders_header.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), True, True, 0)
        vbox.pack_start(folders_header, False, False, 0)

        self.folders_flow = Gtk.FlowBox()
        self.folders_flow.set_valign(Gtk.Align.START)
        self.folders_flow.set_max_children_per_line(4)
        self.folders_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.folders_flow.set_row_spacing(10)
        self.folders_flow.set_column_spacing(12)
        vbox.pack_start(self.folders_flow, False, False, 0)

        scrolled.add(vbox)
        return scrolled

    def _render_thispc_content(self) -> None:
        # 1. Update Banner
        s = sysinfo.summary()
        self.banner_label.set_markup(
            f"<span font='13' weight='bold' foreground='#7aa2f7'>Host: {escape(s['hostname'])}</span>   "
            f"<span font='11' foreground='#94a3b8'>•  OS: {escape(s['os'])}  •  CPU: {s['cpu']} cores  "
            f"•  RAM: {s['mem_used']} / {s['mem_total']}  •  Root Disk: {s['disk_used']} / {s['disk_total']}</span>"
        )

        # 2. Render Devices and Drives
        for child in self.drives_flow.get_children():
            self.drives_flow.remove(child)

        parts = sysinfo.partitions()
        for p in parts:
            card = self._make_drive_card(p)
            self.drives_flow.add(card)

        # 3. Render Quick Folders
        for child in self.folders_flow.get_children():
            self.folders_flow.remove(child)

        qf = sysinfo.quick_folders()
        for f in qf:
            fcard = self._make_folder_card(f)
            self.folders_flow.add(fcard)

        self.thispc_container.show_all()

    def _make_drive_card(self, p: dict) -> Gtk.Widget:
        """Create a Windows 'This PC' style storage partition card."""
        event_box = Gtk.EventBox()
        event_box.set_visible_window(False)

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        card.get_style_context().add_class("drive-card")
        card.set_size_request(270, 76)

        # Large Drive Icon
        img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf("drive", size=38))
        card.pack_start(img, False, False, 0)

        # Info Box
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        info.set_valign(Gtk.Align.CENTER)

        name_lbl = Gtk.Label(label=p.get("name", "Local Disk"))
        name_lbl.get_style_context().add_class("drive-title")
        name_lbl.set_xalign(0)
        info.pack_start(name_lbl, False, False, 0)

        # Progress bar
        pbar = Gtk.ProgressBar()
        pct = p.get("percent", 0.0)
        pbar.set_fraction(max(0.0, min(1.0, pct)))
        if pct >= 0.95:
            pbar.get_style_context().add_class("drive-crit")
        elif pct >= 0.85:
            pbar.get_style_context().add_class("drive-warn")
        info.pack_start(pbar, False, False, 2)

        # Space label
        space_txt = f"{p.get('free_str', '')} free of {p.get('total_str', '')}"
        space_lbl = Gtk.Label(label=space_txt)
        space_lbl.get_style_context().add_class("drive-sub")
        space_lbl.set_xalign(0)
        info.pack_start(space_lbl, False, False, 0)

        meta_txt = f"{p.get('fstype', 'ext4')} • {p.get('device', '')}"
        meta_lbl = Gtk.Label(label=meta_txt)
        meta_lbl.get_style_context().add_class("drive-meta")
        meta_lbl.set_xalign(0)
        info.pack_start(meta_lbl, False, False, 0)

        card.pack_start(info, True, True, 0)
        event_box.add(card)

        # Events
        mount = p.get("mount", "/")
        event_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        event_box.connect(
            "button-press-event",
            lambda w, ev, m=mount, part=p: self._on_drive_press(w, ev, m, part),
        )
        return event_box

    def _make_folder_card(self, f: dict) -> Gtk.Widget:
        """Create a quick access folder card."""
        event_box = Gtk.EventBox()
        event_box.set_visible_window(False)

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        card.get_style_context().add_class("folder-card")
        card.set_size_request(175, 48)

        icon_key = f.get("icon_key", "folder")
        img = Gtk.Image.new_from_pixbuf(get_icon_pixbuf(icon_key, size=28))
        card.pack_start(img, False, False, 0)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_valign(Gtk.Align.CENTER)

        name_lbl = Gtk.Label(label=f.get("name", "Folder"))
        name_lbl.get_style_context().add_class("drive-title")
        name_lbl.set_xalign(0)
        info.pack_start(name_lbl, False, False, 0)

        path_lbl = Gtk.Label(label=f.get("path", ""))
        path_lbl.get_style_context().add_class("drive-meta")
        path_lbl.set_xalign(0)
        info.pack_start(path_lbl, False, False, 0)

        card.pack_start(info, True, True, 0)
        event_box.add(card)

        target = os.path.expanduser(f.get("path", "~"))
        event_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        event_box.connect(
            "button-press-event",
            lambda w, ev, t=target: self._on_folder_press(w, ev, t),
        )
        return event_box

    def _on_drive_press(self, widget: Gtk.Widget, event: Gdk.EventButton, mount: str, part: dict) -> bool:
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self._navigate(mount)
            return True
        if event.button == 3:
            self._show_drive_menu(event, mount, part)
            return True
        return False

    def _on_folder_press(self, widget: Gtk.Widget, event: Gdk.EventButton, path: str) -> bool:
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self._navigate(path)
            return True
        if event.button == 1:
            # Single click also navigates for quick folders
            self._navigate(path)
            return True
        return False

    def _show_drive_menu(self, event: Gdk.EventButton, mount: str, part: dict) -> None:
        menu = Gtk.Menu()

        op = Gtk.MenuItem.new_with_label(f"Open '{part.get('name', 'Drive')}'")
        op.connect("activate", lambda *_: self._navigate(mount))
        menu.append(op)

        menu.append(Gtk.SeparatorMenuItem())

        prop = Gtk.MenuItem.new_with_label("Properties…")
        prop.connect("activate", lambda *_: self._drive_properties(part))
        menu.append(prop)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _drive_properties(self, p: dict) -> None:
        rows = [
            ("Drive Name", p.get("name", "")),
            ("Mount Point", p.get("mount", "")),
            ("Device", p.get("device", "")),
            ("Filesystem Type", p.get("fstype", "")),
            ("Used Space", f"{p.get('used_str', '')} ({p.get('percent', 0)*100:.1f}%)"),
            ("Free Space", p.get("free_str", "")),
            ("Total Capacity", p.get("total_str", "")),
        ]
        self._info_table(f"Properties — {p.get('name')}", rows)

    # ---------------------------------------------------- EXPLORER VIEW
    def _build_explorer_view(self) -> Gtk.Widget:
        # Model columns: pixbuf (0), name (1), path (2), desc (3), is_dir (4), size (5), mtime (6)
        self.model = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str, str, bool, int, float)
        self.view = Gtk.IconView.new_with_model(self.model)
        self.view.set_pixbuf_column(0)
        self.view.set_text_column(1)
        self.view.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.view.set_item_width(108)
        self.view.set_spacing(6)
        self.view.set_column_spacing(12)
        self.view.set_row_spacing(12)
        self.view.set_margin(12)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.view)
        return scrolled

    def _build_menu(self) -> None:
        self.menu = Gtk.Menu()
        for label, callback in [
            ("Open", self._open_selected),
            ("New Folder", self._new_folder),
            ("Rename", self._rename_selected),
            ("Delete", self._delete_selected),
            (None, None),
            ("Copy", self._copy_selected),
            ("Cut", self._cut_selected),
            ("Paste", self._paste),
            (None, None),
            ("Arrange / Sort By…", self._popup_sort_menu),
            ("Properties", self._properties_selected),
        ]:
            if label is None:
                self.menu.append(Gtk.SeparatorMenuItem())
            else:
                item = Gtk.MenuItem.new_with_label(label)
                item.connect("activate", lambda *_, cb=callback: cb())
                self.menu.append(item)
        self.menu.show_all()

    # ------------------------------------------------------------ DND
    def _setup_dnd(self) -> None:
        targets = [
            Gtk.TargetEntry.new("text/uri-list", 0, DRAG_TARGET_URI),
            Gtk.TargetEntry.new("text/plain", 0, DRAG_TARGET_TEXT),
        ]
        self.view.enable_model_drag_source(
            Gdk.ModifierType.BUTTON1_MASK,
            targets,
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE,
        )
        self.view.enable_model_drag_dest(
            targets,
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE,
        )
        self.view.connect("drag-data-get", self._on_drag_data_get)
        self.view.connect("drag-data-received", self._on_drag_data_received)

    def _on_drag_data_get(
        self,
        widget: Gtk.Widget,
        context: Gdk.DragContext,
        selection_data: Gtk.SelectionData,
        info: int,
        time: int,
    ) -> None:
        paths = self._selected_paths()
        if not paths:
            return
        if info == DRAG_TARGET_URI:
            uris = [f"file://{urllib.parse.quote(p)}" for p in paths]
            selection_data.set_uris(uris)
        else:
            selection_data.set_text("\n".join(paths), -1)

    def _on_drag_data_received(
        self,
        widget: Gtk.Widget,
        context: Gdk.DragContext,
        x: int,
        y: int,
        selection_data: Gtk.SelectionData,
        info: int,
        time: int,
    ) -> None:
        if self.current_dir == THIS_PC_URI:
            context.finish(False, False, time)
            return

        dest_dir = self.current_dir
        path_at = self.view.get_path_at_pos(x, y)
        if path_at is not None:
            it = self.model.get_iter(path_at)
            if it is not None:
                item_path = self.model.get_value(it, 2)
                is_dir = self.model.get_value(it, 4)
                if is_dir:
                    dest_dir = item_path

        sources = []
        if info == DRAG_TARGET_URI:
            uris = selection_data.get_uris() or []
            for u in uris:
                parsed = urllib.parse.urlparse(u)
                if parsed.scheme == "file":
                    p = urllib.parse.unquote(parsed.path)
                    if os.path.exists(p):
                        sources.append(p)
        else:
            text = selection_data.get_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if line and os.path.exists(line):
                    sources.append(line)

        if not sources:
            context.finish(False, False, time)
            return

        action = context.get_selected_action()
        is_move = action == Gdk.DragAction.MOVE
        errors = []
        done = 0

        for src in sources:
            if os.path.dirname(os.path.realpath(src)) == dest_dir and is_move:
                continue
            src_name = os.path.basename(src)
            dest_target = os.path.join(dest_dir, src_name)

            overwrite = False
            if os.path.exists(dest_target):
                choice = self._confirm_replace(src_name)
                if choice == "cancel":
                    continue
                overwrite = choice == "replace"

            try:
                if is_move:
                    fs.move_or_replace(src, dest_dir, overwrite=overwrite)
                else:
                    fs.copy_or_replace(src, dest_dir, overwrite=overwrite)
                done += 1
            except fs.FileOpError as exc:
                errors.append(str(exc))

        if errors:
            self._error("\n".join(errors))
        if done:
            self._toast(f"{'Moved' if is_move else 'Copied'} {done} item{'s' if done > 1 else ''}")
        self._reload()
        context.finish(True, is_move, time)

    def _confirm_replace(self, filename: str) -> str:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
        )
        dialog.set_title("File Exists")
        dialog.set_markup(
            f"<b>Replace existing file?</b>\n\n"
            f"A file or folder named '<b>{escape(filename)}</b>' already exists in the destination folder."
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Keep Both (Rename)", Gtk.ResponseType.NO)
        dialog.add_button("Replace", Gtk.ResponseType.YES)
        dialog.set_default_response(Gtk.ResponseType.NO)
        dialog.show_all()
        res = dialog.run()
        dialog.destroy()
        if res == Gtk.ResponseType.YES:
            return "replace"
        if res == Gtk.ResponseType.NO:
            return "rename"
        return "cancel"

    # ------------------------------------------------------------ ARRANGE / SORT
    def _popup_sort_menu(self) -> None:
        if self.current_dir == THIS_PC_URI:
            return
        menu = Gtk.Menu()

        def set_sort(field: str, reverse: bool = False) -> None:
            self.sort_field = field
            self.sort_reverse = reverse
            self._reload()

        sort_options = [
            ("Name (A → Z)", "name", False),
            ("Name (Z → A)", "name", True),
            ("Size (Smallest first)", "size", False),
            ("Size (Largest first)", "size", True),
            ("Date Modified (Newest first)", "mtime", True),
            ("Date Modified (Oldest first)", "mtime", False),
            ("File Type / Category", "type", False),
        ]

        for label, field, rev in sort_options:
            item = Gtk.MenuItem.new_with_label(label)
            item.connect("activate", lambda *_, f=field, r=rev: set_sort(f, r))
            menu.append(item)

        menu.show_all()
        menu.popup_at_pointer(None)

    # ------------------------------------------------------------ SELECTION
    def _selected_paths(self) -> list[str]:
        if self.current_dir == THIS_PC_URI:
            return []
        items = self.view.get_selected_items()
        paths = []
        for tree_path in items:
            it = self.model.get_iter(tree_path)
            if it is not None:
                paths.append(self.model.get_value(it, 2))
        return paths

    def _first_selected(self) -> str | None:
        items = self._selected_paths()
        return items[0] if items else None

    # -------------------------------------------------------------- ACTIONS
    def _navigate(self, path: str, record: bool = True) -> None:
        target = path.strip()
        if target.lower() in ("thispc", "thispc://", "pc", "pc://", "mycomputer", "computer://", "this pc"):
            real = THIS_PC_URI
        else:
            real = os.path.realpath(os.path.expanduser(target))
            if not os.path.isdir(real):
                self._error(f"Not a directory:\n{real}")
                return

        if record:
            self.history = self.history[: self.history_index + 1]
            if not self.history or self.history[-1] != real:
                self.history.append(real)
                self.history_index = len(self.history) - 1
        else:
            if not self.history or self.history[-1] != real:
                self.history.append(real)
                self.history_index = len(self.history) - 1

        self.current_dir = real
        self._reload()

    def _history_move(self, delta: int) -> None:
        index = self.history_index + delta
        if 0 <= index < len(self.history):
            self.history_index = index
            self.current_dir = self.history[index]
            self._reload()

    def _go_up(self) -> None:
        if self.current_dir == THIS_PC_URI:
            return
        parent = os.path.dirname(self.current_dir)
        if parent == self.current_dir or self.current_dir == "/":
            self._navigate(THIS_PC_URI)
        elif parent:
            self._navigate(parent)

    def _reload(self) -> None:
        self.back_btn.set_sensitive(self.history_index > 0)
        self.forward_btn.set_sensitive(self.history_index < len(self.history) - 1)

        # MODE 1: THIS PC OVERVIEW
        if self.current_dir == THIS_PC_URI:
            self.thispc_container.show()
            self.explorer_container.hide()
            self.stack.set_visible_child_name("thispc")
            self.action_bar.hide()
            self.sort_btn.set_sensitive(False)
            self.path_entry.set_text("This PC")
            self.header.set_title("This PC")
            self.header.set_subtitle("Devices and drives")
            self.set_title("This PC — ease-Desk")
            self._render_thispc_content()
            parts_count = len(sysinfo.partitions())
            self.status_label.set_text(f"{parts_count} Drives / Partitions available  •  Windows This PC Mode")
            return

        # MODE 2: FOLDER EXPLORER
        self.thispc_container.hide()
        self.explorer_container.show()
        self.stack.set_visible_child_name("explorer")
        self.action_bar.show()
        self.sort_btn.set_sensitive(True)

        try:
            entries = fs.list_dir(self.current_dir)
        except fs.FileOpError as exc:
            self._error(str(exc))
            entries = []

        if self.sort_field == "size":
            entries.sort(key=lambda e: (not e.is_dir, e.size), reverse=self.sort_reverse)
        elif self.sort_field == "mtime":
            entries.sort(key=lambda e: (not e.is_dir, e.mtime), reverse=self.sort_reverse)
        elif self.sort_field == "type":
            entries.sort(key=lambda e: (not e.is_dir, types.categorize(e.name, e.is_dir)[0]), reverse=self.sort_reverse)
        else:  # name
            entries.sort(key=lambda e: (not e.is_dir, e.name.lower()), reverse=self.sort_reverse)

        self.model.clear()
        for entry in entries:
            cat, desc, _ = types.categorize(entry.name, entry.is_dir, entry.is_link)
            pixbuf = get_icon_pixbuf(cat, size=48)
            self.model.append([pixbuf, entry.name, entry.path, desc, entry.is_dir, entry.size, entry.mtime])

        self.path_entry.set_text(self.current_dir)
        self.header.set_title(os.path.basename(self.current_dir) or "/")
        self.header.set_subtitle(self.current_dir)
        self.set_title(f"File Manager — {self.current_dir}")
        self._update_status()

    def _update_status(self) -> None:
        if self.current_dir == THIS_PC_URI:
            return
        count = len(self.model)
        selected = len(self.view.get_selected_items())
        text = f"{count} item{'s' if count != 1 else ''}"
        if count == 0:
            text = "Empty folder"
        if selected:
            text += f" — {selected} selected"
        self.status_label.set_text(text)

    def _open_selected(self) -> None:
        selected = self._selected_paths()
        if not selected:
            return
        self._open_path(selected[0])

    def _open_path(self, path: str) -> None:
        if os.path.isdir(path):
            self._navigate(path)
            return
        try:
            cat, desc, _icon = types.categorize(os.path.basename(path), False)
            if cat == "image" or fs.is_text_like(path):
                try:
                    ImageViewerWindow(path).show_all()
                    return
                except fs.FileOpError:
                    pass
            if fs.is_text_like(path):
                try:
                    TextViewerWindow(path).show_all()
                    return
                except fs.FileOpError as exc:
                    self._error(str(exc))
                    return
            self._properties(path)
        except fs.FileOpError as exc:
            self._error(str(exc))

    def _on_item_activated(self, view, tree_path) -> None:
        it = self.model.get_iter(tree_path)
        if it is None:
            return
        path = self.model.get_value(it, 2)
        self._open_path(path)

    def _new_folder(self) -> None:
        if self.current_dir == THIS_PC_URI:
            return
        name = self._prompt("New Folder", "Folder name:", "New Folder")
        if not name:
            return
        try:
            fs.make_directory(self.current_dir, name)
            self._reload()
        except fs.FileOpError as exc:
            self._error(str(exc))

    def _rename_selected(self) -> None:
        current = self._first_selected()
        if not current:
            return
        name = self._prompt("Rename", "New name:", os.path.basename(current))
        if not name:
            return
        try:
            fs.rename(current, name)
            self._reload()
        except fs.FileOpError as exc:
            self._error(str(exc))

    def _delete_selected(self) -> None:
        selected = self._selected_paths()
        if not selected:
            return
        names = "\n".join("• " + os.path.basename(p) for p in selected[:8])
        if len(selected) > 8:
            names += f"\n…and {len(selected) - 8} more"
        plural = "item" if len(selected) == 1 else "items"
        if not self._confirm(
            f"Delete {len(selected)} {plural}?",
            f"{names}\n\nThis cannot be undone.",
            "Delete",
        ):
            return
        errors = []
        for path in selected:
            try:
                fs.delete(path)
            except fs.FileOpError as exc:
                errors.append(str(exc))
        if errors:
            self._error("\n".join(errors))
        self._reload()

    def _copy_selected(self) -> None:
        selected = self._selected_paths()
        if selected:
            self.clipboard = ("copy", selected)
            self._toast(f"Copied {len(selected)} item{'s' if len(selected) > 1 else ''}")

    def _cut_selected(self) -> None:
        selected = self._selected_paths()
        if selected:
            self.clipboard = ("move", selected)
            self._toast(f"Cut {len(selected)} item{'s' if len(selected) > 1 else ''}")

    def _paste(self) -> None:
        if self.current_dir == THIS_PC_URI:
            return
        if not self.clipboard:
            self._toast("Clipboard is empty")
            return
        mode, sources = self.clipboard
        errors = []
        done = 0
        for src in sources:
            if os.path.dirname(os.path.realpath(src)) == self.current_dir and mode == "move":
                continue
            try:
                if mode == "copy":
                    fs.copy(src, self.current_dir)
                else:
                    fs.move(src, self.current_dir)
                done += 1
            except fs.FileOpError as exc:
                errors.append(str(exc))
        if errors:
            self._error("\n".join(errors))
        if mode == "move":
            self.clipboard = None
        if done:
            self._toast(f"{'Moved' if mode == 'move' else 'Copied'} {done} item{'s' if done > 1 else ''}")
        self._reload()

    def _properties_selected(self) -> None:
        current = self._first_selected()
        if current:
            self._properties(current)

    def _properties(self, path: str) -> None:
        try:
            props = fs.properties(path)
        except fs.FileOpError as exc:
            self._error(str(exc))
            return
        cat, desc, _icon = types.categorize(os.path.basename(path), os.path.isdir(path))
        rows = [
            ("Name", props["name"]),
            ("Type", f"{props['type']} — {desc}"),
            ("Path", props["path"]),
            ("Size", props["size"]),
            ("Permissions", f"{props['permissions']} ({props['mode']})"),
            ("Owner", f"{props['owner']} : {props['group']}"),
            ("Modified", props["modified"]),
        ]
        if props["is_link"]:
            rows.append(("Link target", props["link_target"] or ""))
        self._info_table("Properties", rows)

    def _set_as_wallpaper(self) -> None:
        target = self._first_selected()
        if not target or not os.path.isfile(target):
            return
        if not wallpaper.is_image_file(target):
            self._toast("Selected file is not a supported image format.")
            return

        try:
            wallpaper.set_wallpaper(target, mode="fill")
            self._toast(f"Desktop wallpaper set to '{os.path.basename(target)}'")
        except Exception as exc:
            self._error(f"Failed to set wallpaper:\n{exc}")

    # --------------------------------------------------------------- EVENTS
    def _on_delete_event(self, window, event) -> bool:
        animate.fade_out(self, duration_ms=180, on_done=self.destroy)
        return True

    def _on_key_press(self, window, event) -> bool:
        key = event.keyval
        state = event.state
        ctrl = state & Gdk.ModifierType.CONTROL_MASK

        if ctrl and key == Gdk.KEY_l:
            self.path_entry.grab_focus()
            self.path_entry.select_region(0, -1)
            return True
        if ctrl and key == Gdk.KEY_r:
            self._reload()
            return True
        if ctrl and key == Gdk.KEY_c:
            self._copy_selected()
            return True
        if ctrl and key == Gdk.KEY_x:
            self._cut_selected()
            return True
        if ctrl and key == Gdk.KEY_v:
            self._paste()
            return True
        if key == Gdk.KEY_Delete:
            self._delete_selected()
            return True
        if key == Gdk.KEY_F2:
            self._rename_selected()
            return True
        if key == Gdk.KEY_BackSpace:
            self._go_up()
            return True
        if key == Gdk.KEY_Return and self.current_dir != THIS_PC_URI:
            self._open_selected()
            return True
        return False

    def _on_view_button_press(self, view, event) -> bool:
        if event.button == 3:
            try:
                path_at = view.get_path_at_pos(int(event.x), int(event.y))
            except TypeError:
                path_at = None
            if path_at is not None:
                view.select_path(path_at)
                self._update_status()
            self._popup_menu(event)
            return True
        return False

    def _popup_menu(self, event) -> None:
        if self.current_dir == THIS_PC_URI:
            return

        # Dynamically build menu based on selection
        selected_file = self._first_selected()
        selected_paths = self._selected_paths()
        is_image = bool(
            selected_file
            and os.path.isfile(selected_file)
            and wallpaper.is_image_file(selected_file)
        )
        is_arch = bool(
            selected_file
            and os.path.isfile(selected_file)
            and fs.is_archive(selected_file)
        )

        menu = Gtk.Menu()
        menu_items = [
            ("Open", self._open_selected),
        ]
        if is_image:
            menu_items.append(("Set as Desktop Wallpaper", self._set_as_wallpaper))

        if is_arch:
            menu_items.extend([
                ("Extract Here", self._extract_selected_here),
                ("Extract to Subfolder…", self._extract_selected_to_folder),
            ])

        if selected_paths:
            menu_items.extend([
                ("Compress to .ZIP", self._compress_selected_zip),
                ("Compress to .TAR.GZ", self._compress_selected_tar),
            ])

        menu_items.extend([
            (None, None),
            ("Open Terminal Here", self._open_terminal_here),
            (None, None),
            ("New Folder", self._new_folder),
            ("Rename", self._rename_selected),
            ("Delete", self._delete_selected),
            (None, None),
            ("Copy", self._copy_selected),
            ("Cut", self._cut_selected),
            ("Paste", self._paste),
            (None, None),
            ("Arrange / Sort By…", self._popup_sort_menu),
            ("Properties", self._properties_selected),
        ])

        for label, callback in menu_items:
            if label is None:
                menu.append(Gtk.SeparatorMenuItem())
            else:
                item = Gtk.MenuItem.new_with_label(label)
                item.connect("activate", lambda *_, cb=callback: cb())
                menu.append(item)

        menu.show_all()
        menu.popup_at_pointer(event) if event else menu.popup_at_pointer(None)

    def _extract_selected_here(self) -> None:
        selected = self._first_selected()
        if not selected or not fs.is_archive(selected):
            return
        dest_dir = self.current_dir
        try:
            fs.extract_archive(selected, dest_dir)
            self._toast(f"Extracted '{os.path.basename(selected)}'")
            self._reload()
        except (fs.FileOpError, fs.SecurityError) as exc:
            self._error(str(exc))

    def _extract_selected_to_folder(self) -> None:
        selected = self._first_selected()
        if not selected or not fs.is_archive(selected):
            return
        base = os.path.basename(selected)
        folder_name = base
        for ext in fs.ARCHIVE_EXTENSIONS:
            if folder_name.lower().endswith(ext):
                folder_name = folder_name[:-len(ext)]
                break
        dest_dir = os.path.join(self.current_dir, folder_name or "extracted")
        try:
            fs.extract_archive(selected, dest_dir)
            self._toast(f"Extracted to '{os.path.basename(dest_dir)}'")
            self._reload()
        except (fs.FileOpError, fs.SecurityError) as exc:
            self._error(str(exc))

    def _compress_selected_zip(self) -> None:
        selected = self._selected_paths()
        if not selected:
            return
        if len(selected) == 1:
            base = os.path.basename(selected[0].rstrip(os.sep)) or "archive"
            default_name = f"{base}.zip"
        else:
            default_name = "Archive.zip"

        output_path = os.path.join(self.current_dir, default_name)
        counter = 1
        while os.path.exists(output_path):
            name_part, _ = os.path.splitext(default_name)
            output_path = os.path.join(self.current_dir, f"{name_part}_{counter}.zip")
            counter += 1

        try:
            fs.compress_archive(selected, output_path)
            self._toast(f"Created '{os.path.basename(output_path)}'")
            self._reload()
        except fs.FileOpError as exc:
            self._error(str(exc))

    def _compress_selected_tar(self) -> None:
        selected = self._selected_paths()
        if not selected:
            return
        if len(selected) == 1:
            base = os.path.basename(selected[0].rstrip(os.sep)) or "archive"
            default_name = f"{base}.tar.gz"
        else:
            default_name = "Archive.tar.gz"

        output_path = os.path.join(self.current_dir, default_name)
        counter = 1
        while os.path.exists(output_path):
            output_path = os.path.join(self.current_dir, f"Archive_{counter}.tar.gz")
            counter += 1

        try:
            fs.compress_archive(selected, output_path)
            self._toast(f"Created '{os.path.basename(output_path)}'")
            self._reload()
        except fs.FileOpError as exc:
            self._error(str(exc))

    def _open_terminal_here(self) -> None:
        target_dir = self.current_dir
        if not os.path.isdir(target_dir):
            target_dir = os.path.expanduser("~")
        cmd = [sys.executable, "-m", "desktop.terminal.app", target_dir]
        try:
            subprocess.Popen(
                cmd,
                cwd=ROOT,
                env=dict(os.environ, PYTHONPATH=ROOT + os.pathsep + os.environ.get("PYTHONPATH", "")),
            )
        except OSError:
            pass

    def _on_path_activate(self, entry) -> None:
        path = entry.get_text().strip()
        if path:
            self._navigate(path)

    # --------------------------------------------------------------- HELPERS
    def _toast(self, message: str) -> None:
        self.status_label.set_text(message)
        GLib.timeout_add(2500, lambda: self._update_status())

    def _prompt(self, title: str, label: str, default: str = "") -> str | None:
        dialog = Gtk.Dialog(title=title, transient_for=self, modal=True, destroy_with_parent=True)
        dialog.set_default_size(360, -1)
        content = dialog.get_content_area()
        content.set_margin_start(14)
        content.set_margin_end(14)
        content.set_margin_top(14)
        content.set_margin_bottom(6)
        content.pack_start(Gtk.Label(label=label, xalign=0), False, False, 4)
        entry = Gtk.Entry()
        entry.set_text(default)
        entry.set_activates_default(True)
        content.pack_start(entry, False, False, 4)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("OK", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        dialog.show_all()
        response = dialog.run()
        value = entry.get_text().strip() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        return value

    def _confirm(self, title: str, body: str, confirm_label: str) -> bool:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            destroy_with_parent=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.NONE,
        )
        dialog.set_title(title)
        dialog.set_markup(f"<b>{html.escape(title)}</b>\n\n{escape(body)}")
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        confirm = dialog.add_button(confirm_label, Gtk.ResponseType.OK)
        confirm.get_style_context().add_class("destructive-action")
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        dialog.show_all()
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK

    def _info_table(self, title: str, rows: list[tuple[str, str]]) -> None:
        dialog = Gtk.Dialog(title=title, transient_for=self, modal=True, destroy_with_parent=True)
        dialog.set_default_size(480, -1)
        content = dialog.get_content_area()
        grid = Gtk.Grid()
        grid.set_column_spacing(16)
        grid.set_row_spacing(8)
        grid.set_margin_start(16)
        grid.set_margin_end(16)
        grid.set_margin_top(16)
        grid.set_margin_bottom(16)
        for i, (key, value) in enumerate(rows):
            key_label = Gtk.Label(label=key, xalign=0)
            key_label.get_style_context().add_class("dim-label")
            value_label = Gtk.Label(label=value, xalign=0, selectable=True)
            value_label.set_line_wrap(True)
            grid.attach(key_label, 0, i, 1, 1)
            grid.attach(value_label, 1, i, 1, 1)
        content.pack_start(grid, False, False, 0)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _error(self, message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            destroy_with_parent=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
        )
        dialog.set_title("ease-Desk")
        dialog.set_markup(f"<b>Operation failed</b>\n\n{escape(message)}")
        dialog.show_all()
        dialog.run()
        dialog.destroy()
