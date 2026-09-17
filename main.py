#!/usr/bin/env python3
"""
HyperBox - VirtualBox Alternative for Linux (KVM/QEMU)
"""
import sys
import os

# Ensure package path is included
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
from hyperbox.ui.main_window import MainWindow
from hyperbox.config import APP_NAME


def main():
    # Set application name and icon if available
    GLib.set_application_name(APP_NAME)
    icon_path = os.path.join(SCRIPT_DIR, "assets", "hyperbox.png")
    if os.path.exists(icon_path):
        try:
            Gtk.Window.set_default_icon_from_file(icon_path)
        except Exception:
            pass

    win = MainWindow()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
