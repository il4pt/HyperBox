"""
Virtual Machine Live Console Window (Embedded SPICE Display & Full Input Controls)
"""
import os
import shutil
import subprocess
import gi
gi.require_version('Gtk', '3.0')
try:
    gi.require_version('SpiceClientGLib', '2.0')
    gi.require_version('SpiceClientGtk', '3.0')
    from gi.repository import SpiceClientGLib, SpiceClientGtk
    HAS_SPICE = True
except Exception as e:
    print(f"SPICE GTK library import error: {e}")
    HAS_SPICE = False

from gi.repository import Gtk, Gdk, GLib
from hyperbox.models import VirtualMachine
from hyperbox.qemu_runner import QemuRunner


class VMConsoleWindow(Gtk.Window):
    def __init__(self, vm: VirtualMachine, parent=None):
        super().__init__(title=f"{vm.name} - HyperBox Ekran Konsolu")
        self.vm = vm
        self.set_default_size(1024, 768)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.is_fullscreen = False
        self.spice_session = None
        self.spice_display = None

        self.init_ui()
        self.connect("destroy", self.on_window_close)
        self.connect("key-press-event", self.on_key_press)

        # Refresh loop to detect if VM exits
        self.timer_id = GLib.timeout_add_seconds(1, self.check_vm_status)

        # Ensure display has focus once window is mapped
        GLib.idle_add(self.focus_display)

    def init_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(vbox)

        # ---------------- Toolbar ----------------
        self.toolbar = Gtk.Toolbar()
        self.toolbar.set_style(Gtk.ToolbarStyle.BOTH)
        self.toolbar.get_style_context().add_class("primary-toolbar")
        self.toolbar.set_can_focus(False)

        # 1. Pause / Resume
        self.pause_btn = Gtk.ToolButton.new_from_stock(Gtk.STOCK_MEDIA_PAUSE)
        self.pause_btn.set_label("Duraklat")
        self.pause_btn.connect("clicked", self.toggle_pause)
        self.toolbar.insert(self.pause_btn, -1)

        # 2. Reset
        reset_btn = Gtk.ToolButton.new_from_stock(Gtk.STOCK_REFRESH)
        reset_btn.set_label("Yeniden Başlat")
        reset_btn.connect("clicked", self.on_reset)
        self.toolbar.insert(reset_btn, -1)

        # 3. ACPI Shutdown
        acpi_btn = Gtk.ToolButton.new_from_stock(Gtk.STOCK_QUIT)
        acpi_btn.set_label("Kapat (ACPI)")
        acpi_btn.connect("clicked", self.on_acpi_shutdown)
        self.toolbar.insert(acpi_btn, -1)

        # 4. Force Stop
        stop_btn = Gtk.ToolButton.new_from_stock(Gtk.STOCK_STOP)
        stop_btn.set_label("Güç Kes")
        stop_btn.connect("clicked", self.on_force_stop)
        self.toolbar.insert(stop_btn, -1)

        self.toolbar.insert(Gtk.SeparatorToolItem(), -1)

        # 5. Quick Key helpers (for Boot menus & GRUB)
        enter_btn = Gtk.ToolButton.new_from_stock(Gtk.STOCK_APPLY)
        enter_btn.set_label("Enter Gönder")
        enter_btn.set_tooltip_text("Sanal makineye doğrudan Enter tuşu sinyali gönderir (Boot menüsü seçimi için)")
        enter_btn.connect("clicked", self.send_enter)
        self.toolbar.insert(enter_btn, -1)

        down_btn = Gtk.ToolButton.new_from_stock(Gtk.STOCK_GO_DOWN)
        down_btn.set_label("Aşağı Ok")
        down_btn.set_tooltip_text("Boot menüsünde alt satıra geçmek için Aşağı Ok sinyali gönderir")
        down_btn.connect("clicked", self.send_down)
        self.toolbar.insert(down_btn, -1)

        # 6. Send Ctrl+Alt+Del
        cad_btn = Gtk.ToolButton.new_from_stock(Gtk.STOCK_EXECUTE)
        cad_btn.set_label("Ctrl+Alt+Del")
        cad_btn.connect("clicked", self.send_ctrl_alt_del)
        self.toolbar.insert(cad_btn, -1)

        # 7. Fullscreen
        self.fs_btn = Gtk.ToolButton.new_from_stock(Gtk.STOCK_FULLSCREEN)
        self.fs_btn.set_label("Tam Ekran")
        self.fs_btn.connect("clicked", self.toggle_fullscreen)
        self.toolbar.insert(self.fs_btn, -1)

        # 8. External Viewer button (remote-viewer)
        if shutil.which("remote-viewer"):
            ext_btn = Gtk.ToolButton.new_from_stock(Gtk.STOCK_FIND_AND_REPLACE)
            ext_btn.set_label("Ayrı Pencere")
            ext_btn.set_tooltip_text("Görüntüyü virt-viewer (remote-viewer) harici penceresinde açar")
            ext_btn.connect("clicked", self.open_external_viewer)
            self.toolbar.insert(ext_btn, -1)

        # Disable focus stealing on all toolbar items
        for item in self.toolbar.get_children():
            item.set_can_focus(False)
            child = item.get_child()
            if child:
                child.set_can_focus(False)

        vbox.pack_start(self.toolbar, False, False, 0)

        # ---------------- Display Area ----------------
        self.display_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.display_container.set_can_focus(False)
        vbox.pack_start(self.display_container, True, True, 0)

        if HAS_SPICE and self.vm.spice_port > 0:
            self.setup_spice_display()
        else:
            self.setup_fallback_display()

        # ---------------- Statusbar ----------------
        self.statusbar = Gtk.Statusbar()
        self.status_ctx = self.statusbar.get_context_id("vm_status")
        kvm_text = "KVM: Aktif ✔" if self.vm.enable_kvm else "KVM: Pasif"
        self.statusbar.push(self.status_ctx, f"Durum: Çalışıyor | RAM: {self.vm.ram_mb} MB | vCPU: {self.vm.cpus} | {kvm_text} | Etkileşim için ekrana tıklayın")
        vbox.pack_start(self.statusbar, False, False, 0)

        self.show_all()

    def setup_spice_display(self):
        try:
            self.spice_session = SpiceClientGLib.Session()
            self.spice_session.set_property("host", "127.0.0.1")
            self.spice_session.set_property("port", str(self.vm.spice_port))

            self.spice_display = SpiceClientGtk.Display.new(self.spice_session, 0)
            self.spice_display.set_property("scaling", True)
            self.spice_display.set_can_focus(True)
            self.spice_display.set_focus_on_click(True)

            # Auto grab focus on mouse enter / click
            self.spice_display.connect("button-press-event", self.on_display_clicked)
            self.spice_display.connect("enter-notify-event", self.on_display_hover)
            self.spice_display.connect("map", lambda w: GLib.idle_add(w.grab_focus))

            # Channel listener
            def on_channel_new(sess, channel):
                ch_name = type(channel).__name__
                if "Display" in ch_name:
                    GLib.idle_add(lambda: self.statusbar.push(self.status_ctx, "Görüntü ve Girişler: Hazır ✔ (Klavye/Fare aktif)"))

            self.spice_session.connect_after("channel-new", on_channel_new)

            self.display_container.pack_start(self.spice_display, True, True, 0)
            self.spice_display.show()
            self.spice_session.connect()
        except Exception as e:
            print(f"Failed to connect SPICE widget: {e}")
            self.setup_fallback_display()

    def on_display_clicked(self, widget, event):
        widget.grab_focus()
        self.set_focus(widget)
        return False  # Propagate event to SPICE

    def on_display_hover(self, widget, event):
        if not widget.is_focus():
            widget.grab_focus()
            self.set_focus(widget)
        return False

    def focus_display(self):
        if self.spice_display:
            self.spice_display.grab_focus()
            self.set_focus(self.spice_display)
        return False

    def open_external_viewer(self, btn=None):
        if self.vm.spice_port > 0:
            uri = f"spice://127.0.0.1:{self.vm.spice_port}"
            subprocess.Popen(["remote-viewer", uri], start_new_session=True)

    def setup_fallback_display(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("computer", Gtk.IconSize.DIALOG)
        box.pack_start(icon, False, False, 0)

        lbl = Gtk.Label()
        lbl.set_markup(f"<big><b>{self.vm.name} Çalışıyor</b></big>\n\n"
                       f"Görüntüyü harici pencerede açmak için yukarıdaki <b>'Ayrı Pencere'</b> butonunu kullanabilirsiniz.")
        lbl.set_justify(Gtk.Justification.CENTER)
        box.pack_start(lbl, False, False, 0)

        self.display_container.pack_start(box, True, True, 0)

    def toggle_pause(self, btn):
        if self.vm.status == "running":
            if QemuRunner.pause_vm(self.vm):
                self.pause_btn.set_label("Devam Et")
                self.statusbar.push(self.status_ctx, "Durum: Duraklatıldı ⏸")
        elif self.vm.status == "paused":
            if QemuRunner.resume_vm(self.vm):
                self.pause_btn.set_label("Duraklat")
                self.statusbar.push(self.status_ctx, "Durum: Çalışıyor 🟢")

    def on_reset(self, btn):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"'{self.vm.name}' sanal makinesini yeniden başlatmak istiyor musunuz?"
        )
        dialog.format_secondary_text("Kaydedilmemiş veriler kaybolabilir.")
        resp = dialog.run()
        dialog.destroy()
        if resp == Gtk.ResponseType.YES:
            QemuRunner.reset_vm(self.vm)

    def on_acpi_shutdown(self, btn):
        QemuRunner.acpi_shutdown(self.vm)
        self.statusbar.push(self.status_ctx, "Kapatma sinyali (ACPI) gönderildi...")

    def on_force_stop(self, btn):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"'{self.vm.name}' sanal makinesinin gücünü zorla kesmek istiyor musunuz?"
        )
        dialog.format_secondary_text("Bu işlem sanal bilgisayarın fişini çekmek gibidir.")
        resp = dialog.run()
        dialog.destroy()
        if resp == Gtk.ResponseType.OK:
            QemuRunner.force_stop(self.vm)
            self.destroy()

    def send_enter(self, btn):
        cmd = {
            "execute": "send-key",
            "arguments": {
                "keys": [
                    {"type": "qcode", "data": "ret"}
                ]
            }
        }
        QemuRunner.send_qmp_command(self.vm.qmp_socket, cmd)
        self.statusbar.push(self.status_ctx, "Enter tuşu gönderildi ✔")
        self.focus_display()

    def send_down(self, btn):
        cmd = {
            "execute": "send-key",
            "arguments": {
                "keys": [
                    {"type": "qcode", "data": "down"}
                ]
            }
        }
        QemuRunner.send_qmp_command(self.vm.qmp_socket, cmd)
        self.statusbar.push(self.status_ctx, "Aşağı Ok tuşu gönderildi ✔")
        self.focus_display()

    def send_ctrl_alt_del(self, btn):
        cmd = {
            "execute": "send-key",
            "arguments": {
                "keys": [
                    {"type": "qcode", "data": "ctrl"},
                    {"type": "qcode", "data": "alt"},
                    {"type": "qcode", "data": "delete"}
                ]
            }
        }
        QemuRunner.send_qmp_command(self.vm.qmp_socket, cmd)
        self.statusbar.push(self.status_ctx, "Ctrl+Alt+Del sinyali sanal makineye iletildi.")
        self.focus_display()

    def toggle_fullscreen(self, btn):
        if not self.is_fullscreen:
            self.fullscreen()
            self.is_fullscreen = True
            self.fs_btn.set_label("Pencereye Dön")
        else:
            self.unfullscreen()
            self.is_fullscreen = False
            self.fs_btn.set_label("Tam Ekran")
        self.focus_display()

    def on_key_press(self, widget, event):
        if event.keyval in (Gdk.KEY_F11,):
            self.toggle_fullscreen(None)
            return True

        # If display is mapped but not currently focused, focus and forward
        if self.spice_display:
            if not self.spice_display.is_focus():
                self.spice_display.grab_focus()
                self.set_focus(self.spice_display)
        return False

    def check_vm_status(self):
        if not QemuRunner.is_running(self.vm):
            self.statusbar.push(self.status_ctx, "Sanal makine kapandı.")
            return False
        return True

    def on_window_close(self, widget):
        if self.timer_id:
            GLib.source_remove(self.timer_id)
        if self.spice_session:
            try:
                self.spice_session.disconnect()
            except Exception:
                pass
