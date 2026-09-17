"""
Universal Linux Dependency Check and Installation Dialog
"""
import os
import shutil
import subprocess
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from hyperbox.config import get_qemu_bin, get_qemu_img_bin, check_kvm
from hyperbox.distro import LinuxDistro


class DependencyDialog(Gtk.Dialog):
    def __init__(self, parent=None):
        super().__init__(
            title="Sistem Sanallaştırma Durumu (QEMU / KVM)",
            transient_for=parent,
            flags=0
        )
        self.set_default_size(640, 460)
        self.set_border_width(14)

        self.distro_info = LinuxDistro.get_info()
        self.pm_name, self.cmd_str = LinuxDistro.get_package_manager()
        if not self.cmd_str:
            self.cmd_str = "sudo pacman -S qemu-desktop qemu-img || sudo apt install qemu-system-x86 qemu-utils || sudo dnf install qemu-kvm qemu-img"

        box = self.get_content_area()
        box.set_spacing(12)

        # Header info with detected Distro
        header_lbl = Gtk.Label()
        header_lbl.set_markup(
            f"<big><b>Sistem Sanallaştırma Bileşenleri</b></big>\n"
            f"<b>Tespit Edilen Dağıtım:</b> {self.distro_info['name']} (Paket Yöneticisi: <i>{self.pm_name or 'Bilinmiyor'}</i>)\n"
            f"HyperBox, Linux çekirdeğinin yerel KVM donanım hızlandırma yeteneğini ve QEMU motorunu kullanır."
        )
        header_lbl.set_line_wrap(True)
        header_lbl.set_xalign(0)
        box.pack_start(header_lbl, False, False, 0)

        # Status Table/Grid
        self.grid = Gtk.Grid()
        self.grid.set_column_spacing(15)
        self.grid.set_row_spacing(10)
        self.grid.set_margin_top(6)
        self.grid.set_margin_bottom(6)

        # 1. KVM Status
        self.grid.attach(Gtk.Label(label="<b>KVM Donanım Hızlandırma:</b>", use_markup=True, xalign=0), 0, 0, 1, 1)
        self.kvm_status = Gtk.Label(use_markup=True, xalign=0)
        self.grid.attach(self.kvm_status, 1, 0, 1, 1)

        # 2. QEMU Binary
        self.grid.attach(Gtk.Label(label="<b>QEMU Sanallaştırıcı:</b>", use_markup=True, xalign=0), 0, 1, 1, 1)
        self.qemu_status = Gtk.Label(use_markup=True, xalign=0)
        self.grid.attach(self.qemu_status, 1, 1, 1, 1)

        # 3. qemu-img
        self.grid.attach(Gtk.Label(label="<b>Disk Yöneticisi (qemu-img):</b>", use_markup=True, xalign=0), 0, 2, 1, 1)
        self.img_status = Gtk.Label(use_markup=True, xalign=0)
        self.grid.attach(self.img_status, 1, 2, 1, 1)

        box.pack_start(self.grid, False, False, 0)

        # Refresh button row
        refresh_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.refresh_btn = Gtk.Button(label="🔄 Durumu Yeniden Kontrol Et")
        self.refresh_btn.connect("clicked", lambda b: self.update_statuses())
        refresh_box.pack_start(self.refresh_btn, False, False, 0)
        box.pack_start(refresh_box, False, False, 0)

        # Instruction Card
        card = Gtk.Frame(label=f" {self.distro_info['name']} İçin Kurulum Çözümü ")
        card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card_box.set_border_width(12)

        info_text = Gtk.Label()
        info_text.set_markup(
            f"<b>{self.distro_info['name']}</b> için hazırlanan kurulum komutunu aşağıdan kopyalayabilir veya doğrudan terminalde başlatabilirsiniz:"
        )
        info_text.set_line_wrap(True)
        info_text.set_xalign(0)
        card_box.pack_start(info_text, False, False, 0)

        cmd_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        cmd_entry = Gtk.Entry()
        cmd_entry.set_text(self.cmd_str)
        cmd_entry.set_editable(False)
        cmd_entry.set_hexpand(True)
        cmd_box.pack_start(cmd_entry, True, True, 0)

        copy_btn = Gtk.Button(label="Kopyala")
        copy_btn.connect("clicked", self.on_copy_clicked)
        cmd_box.pack_start(copy_btn, False, False, 0)

        card_box.pack_start(cmd_box, False, False, 0)

        # Action buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        terminal_btn = Gtk.Button(label="🚀 Terminalde Kurulumu Başlat")
        terminal_btn.get_style_context().add_class("suggested-action")
        terminal_btn.connect("clicked", self.on_install_in_terminal)
        action_box.pack_start(terminal_btn, False, False, 0)

        card_box.pack_start(action_box, False, False, 0)
        card.add(card_box)
        box.pack_start(card, False, False, 0)

        # Bottom buttons
        self.add_button("Kapat", Gtk.ResponseType.CLOSE)

        self.update_statuses()
        self.show_all()

    def update_statuses(self):
        # 1. KVM
        if check_kvm():
            self.kvm_status.set_markup("<span color='#2ecc71'>✔ Aktif ve Kullanılabilir (/dev/kvm)</span>")
        else:
            self.kvm_status.set_markup("<span color='#e74c3c'>✖ Devre dışı veya izin yok</span>")

        # 2. QEMU
        qemu_bin = get_qemu_bin()
        if qemu_bin and os.path.exists(qemu_bin):
            self.qemu_status.set_markup(f"<span color='#2ecc71'>✔ Kurulu ({qemu_bin})</span>")
        else:
            self.qemu_status.set_markup("<span color='#e67e22'>⚠ Yüklü Değil (qemu-system-x86_64)</span>")

        # 3. qemu-img
        img_bin = get_qemu_img_bin()
        if img_bin and os.path.exists(img_bin):
            self.img_status.set_markup(f"<span color='#2ecc71'>✔ Kurulu ({img_bin})</span>")
        else:
            self.img_status.set_markup("<span color='#e67e22'>⚠ Yüklü Değil (qemu-img)</span>")

    def on_copy_clicked(self, button):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self.cmd_str, -1)
        button.set_label("Kopyalandı! ✔")

    def on_install_in_terminal(self, button):
        term = LinuxDistro.get_preferred_terminal()
        if not term:
            return

        cmd = (
            f"echo '=== HyperBox: {self.distro_info['name']} Sanallaştırma Kurulumu ==='; "
            "echo 'Lütfen sudo şifrenizi girin:'; "
            f"{self.cmd_str}; "
            "echo ''; "
            "echo 'Kurulum tamamlandı! Pencereyi kapatabilirsiniz (Enter).'; "
            "read"
        )

        try:
            term_name = os.path.basename(term)
            if term_name in ["konsole", "alacritty"]:
                subprocess.Popen([term, "--noclose", "-e", "bash", "-c", cmd])
            elif term_name in ["gnome-terminal", "xfce4-terminal", "tilix"]:
                subprocess.Popen([term, "--", "bash", "-c", cmd])
            else:
                subprocess.Popen([term, "-e", f"bash -c \"{cmd}\""])
        except Exception as e:
            print(f"Error launching terminal: {e}")
