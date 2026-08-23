try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    try:
        ok, _ = Gtk.init_check()
        if not ok:
            Gtk.init()
    except Exception:
        try:
            Gtk.init()
        except Exception:
            pass
except Exception:
    pass
