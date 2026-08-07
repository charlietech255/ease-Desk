"""Charlie File Manager main window.

Implements navigation, icon view, file operations, context menu, keyboard
shortcuts, history (back/forward) and the status bar.
"""

from __future__ import annotations

import html
import os
from html import escape

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from file_manager.core import fs, types  # noqa: E402
from file_manager.viewer import ImageViewerWindow, TextViewerWindow  # noqa: E402
from shared.utilities import animate  # noqa: E402


def _mk(tooltip: str) -> Gtk.Button:
    btn = Gtk.Button.new_with_label(tooltip)
    btn.set_tooltip_text(tooltip)
    return btn


class FileManagerWindow(Gtk.Window):
    def __init__(self, start_path: str):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_title("ease-Desk File Manager")
        self.set_default_size(920, 580)
        self.set_position(Gtk.WindowPosition.CENTER)

        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        header.set_title("ease-Desk File Manager")
        header.set_subtitle("VPS File Browser")
        self.set_titlebar(header)

        self.history: list[str] = []
        self.history_index: int = -1
        self.clipboard: tuple[str, list[str]] | None = None  # (mode, paths)
        self.current_dir: str = os.path.realpath(start_path)

        self._build_ui()
        self._build_menu()

        self.connect("delete-event", self._on_delete_event)
        self.connect("key-press-event", self._on_key_press)
        self.view.connect("item-activated", self._on_item_activated)
        self.view.connect("button-press-event", self._on_view_button_press)
        self.path_entry.connect("activate", self._on_path_activate)

        self._navigate(self.current_dir, record=False)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.pack_start(self._build_toolbar(), False, False, 0)
        root.pack_start(self._build_actions(), False, False, 0)

        self.model = Gtk.ListStore(str, str, str, str)  # markup, name, path, desc
        self.view = Gtk.IconView.new_with_model(self.model)
        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", 3)  # END
        self.view.pack_start(renderer, True)
        self.view.add_attribute(renderer, "markup", 0)
        self.view.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.view.set_item_width(150)
        self.view.set_spacing(12)
        self.view.set_column_spacing(20)
        self.view.set_margin(14)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.view)
        root.pack_start(scrolled, True, True, 0)

        self.status_label = Gtk.Label(label="")
        self.status_label.set_xalign(0)
        self.status_label.get_style_context().add_class("statusbar")
        root.pack_start(self.status_label, False, False, 0)

        self.add(root)

    def _build_toolbar(self) -> Gtk.Widget:
        bar = Gtk.Toolbar()
        bar.set_style(Gtk.ToolbarStyle.TEXT)

        self.back_btn = _mk("← Back")
        self.forward_btn = _mk("→ Forward")
        self.up_btn = _mk("↑ Up")
        self.home_btn = _mk("~ Home")
        self.root_btn = _mk("/ Root")

        for btn in (self.back_btn, self.forward_btn, self.up_btn, self.home_btn, self.root_btn):
            item = Gtk.ToolItem()
            item.add(btn)
            bar.insert(item, -1)
            bar.insert(Gtk.SeparatorToolItem(), -1)

        self.back_btn.connect("clicked", lambda *_: self._history_move(-1))
        self.forward_btn.connect("clicked", lambda *_: self._history_move(1))
        self.up_btn.connect("clicked", lambda *_: self._go_up())
        self.home_btn.connect("clicked", lambda *_: self._navigate(os.path.expanduser("~")))
        self.root_btn.connect("clicked", lambda *_: self._navigate("/"))

        self.path_entry = Gtk.Entry()
        self.path_entry.set_hexpand(True)
        self.path_entry.set_placeholder_text("Path…")
        path_item = Gtk.ToolItem()
        path_item.set_expand(True)
        path_item.add(self.path_entry)
        bar.insert(path_item, -1)

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
        bar.get_style_context().add_class("action-bar")
        bar.set_margin_start(0)
        bar.set_margin_end(0)
        bar.set_margin_bottom(0)
        for label, callback in actions:
            btn = _mk(label)
            btn.get_style_context().add_class("action-btn")
            btn.connect("clicked", lambda *_, cb=callback: cb())
            bar.pack_start(btn, False, False, 0)
        return bar

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
            ("Properties", self._properties_selected),
        ]:
            if label is None:
                self.menu.append(Gtk.SeparatorMenuItem())
            else:
                item = Gtk.MenuItem.new_with_label(label)
                item.connect("activate", lambda *_, cb=callback: cb())
                self.menu.append(item)
        self.menu.show_all()

    # ------------------------------------------------------------ selection
    def _selected_paths(self) -> list[str]:
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

    # -------------------------------------------------------------- actions
    def _navigate(self, path: str, record: bool = True) -> None:
        real = os.path.realpath(path)
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
        parent = os.path.dirname(self.current_dir)
        if parent and parent != self.current_dir:
            self._navigate(parent)

    def _reload(self) -> None:
        try:
            entries = fs.list_dir(self.current_dir)
        except fs.FileOpError as exc:
            self._error(str(exc))
            entries = []
        self.model.clear()
        for entry in entries:
            cat, desc, icon = types.categorize(entry.name, entry.is_dir, entry.is_link)
            markup = (
                f"<span font='26'>{icon}</span>\n"
                f"<span font='11' foreground='#e2e8f0'>{escape(entry.name)}</span>"
            )
            self.model.append([markup, entry.name, entry.path, desc])
        self.path_entry.set_text(self.current_dir)
        self.set_title(f"File Manager — {self.current_dir}")
        self._update_status()
        self.back_btn.set_sensitive(self.history_index > 0)
        self.forward_btn.set_sensitive(self.history_index < len(self.history) - 1)

    def _update_status(self) -> None:
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
        if not self.clipboard:
            self._toast("Clipboard is empty")
            return
        mode, sources = self.clipboard
        errors = []
        done = 0
        for src in sources:
            if os.path.dirname(os.path.realpath(src)) == self.current_dir and mode == "move":
                continue  # already here
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

    # --------------------------------------------------------------- events
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
        if key == Gdk.KEY_Return:
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
        self.menu.popup_at_pointer(event) if event else self.menu.popup_at_pointer(None)

    def _on_path_activate(self, entry) -> None:
        path = entry.get_text().strip()
        if path:
            self._navigate(path)

    # --------------------------------------------------------------- helpers
    def _toast(self, message: str) -> None:
        self.status_label.set_text(message)
        GLib.timeout_add(2500, lambda: self._update_status())

    def _prompt(self, title: str, label: str, default: str = "") -> str | None:
        dialog = Gtk.Dialog(title=title, transient_for=self, modal=True)
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
        dialog = Gtk.Dialog(title=title, transient_for=self, modal=True)
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
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
        )
        dialog.set_title("File Manager")
        dialog.set_markup(f"<b>Operation failed</b>\n\n{escape(message)}")
        dialog.show_all()
        dialog.run()
        dialog.destroy()
