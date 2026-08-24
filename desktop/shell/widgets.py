import datetime
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, Gdk, GLib
from shared.utilities import sysinfo

class ClockWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        
        self.time_lbl = Gtk.Label()
        self.time_lbl.set_halign(Gtk.Align.CENTER)
        self.date_lbl = Gtk.Label()
        self.date_lbl.set_halign(Gtk.Align.CENTER)
        
        # Style
        css = b"""
            .widget-time {
                color: rgba(255, 255, 255, 0.9);
                font-size: 72px;
                font-weight: 800;
                font-family: "Inter", "Ubuntu", sans-serif;
                text-shadow: 0 4px 12px rgba(0,0,0,0.5);
            }
            .widget-date {
                color: rgba(255, 255, 255, 0.7);
                font-size: 20px;
                font-weight: 500;
                font-family: "Inter", "Ubuntu", sans-serif;
                text-shadow: 0 2px 8px rgba(0,0,0,0.5);
                margin-top: -10px;
            }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        self.time_lbl.get_style_context().add_class("widget-time")
        self.date_lbl.get_style_context().add_class("widget-date")
        
        self.pack_start(self.time_lbl, False, False, 0)
        self.pack_start(self.date_lbl, False, False, 0)
        
        self._update_time()
        GLib.timeout_add_seconds(1, self._update_time)

    def _update_time(self):
        now = datetime.datetime.now()
        self.time_lbl.set_text(now.strftime("%H:%M"))
        self.date_lbl.set_text(now.strftime("%A, %B %d"))
        return True


class VitalsWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_halign(Gtk.Align.END)
        self.set_valign(Gtk.Align.END)
        self.set_margin_end(24)
        self.set_margin_bottom(24)
        
        self.lbl = Gtk.Label()
        self.lbl.set_xalign(1)
        
        css = b"""
            .widget-vitals {
                background-color: rgba(20, 20, 24, 0.4);
                color: rgba(255, 255, 255, 0.6);
                font-size: 11px;
                font-weight: 600;
                font-family: "JetBrains Mono", "Fira Code", monospace;
                padding: 6px 12px;
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
        self.lbl.get_style_context().add_class("widget-vitals")
        self.pack_start(self.lbl, False, False, 0)
        
        self._update_vitals()
        GLib.timeout_add_seconds(3, self._update_vitals)

    def _update_vitals(self):
        info = sysinfo.summary()
        cpu = info.get("cpu_percent", 0.0)
        ram = info.get("mem_percent", 0.0)
        self.lbl.set_markup(f"CPU: {cpu:04.1f}% | RAM: {ram:04.1f}%")
        return True


class WidgetEngine(Gtk.Window):
    """A transparent layer sitting right above the desktop background to host widgets."""
    
    def __init__(self, parent_window):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.set_transient_for(parent_window)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
        self.set_app_paintable(True)
        
        # Transparent background for the widget layer itself
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and self.is_composited():
            self.set_visual(visual)
        
        self.override_background_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(0, 0, 0, 0)
        )
        
        # Make the window cover the entire screen
        self.set_default_size(screen.get_width(), screen.get_height())
        self.move(0, 0)
        
        # Layout container
        overlay = Gtk.Overlay()
        self.add(overlay)
        
        # Add Clock (Center)
        self.clock = ClockWidget()
        overlay.add_overlay(self.clock)
        
        # Add Vitals (Bottom Right)
        self.vitals = VitalsWidget()
        overlay.add_overlay(self.vitals)
        
        self.show_all()
