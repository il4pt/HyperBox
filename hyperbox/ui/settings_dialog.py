"""
Virtual Machine Settings Dialog (VirtualBox Style)
"""
import os
import psutil
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from hyperbox.models import VirtualMachine
from hyperbox.config import OS_TEMPLATES, HAS_KVM
from hyperbox.qemu_runner import QemuRunner


class SettingsDialog(Gtk.Dialog):
    def __init__(self, vm: VirtualMachine, parent=None, on_saved_callback=None):
        super().__init__(
            title=f"{vm.name} - Ayarlar",
            transient_for=parent,
            flags=0
        )
        self.vm = vm
        self.on_saved_callback = on_saved_callback
        self.is_running = QemuRunner.is_running(vm)

        self.set_default_size(700, 500)
        self.set_border_width(10)

        total_ram = int(psutil.virtual_memory().total / (1024 * 1024))
        self.max_ram = min(total_ram, 32768)
        self.total_cpus = os.cpu_count() or 4

        self.init_ui()

    def init_ui(self):
        content = self.get_content_area()

        # Split pane: Categories on left, stack pages on right
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.pack_start(hbox, True, True, 0)

        # Left Category Sidebar
        sidebar_frame = Gtk.Frame()
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self.listbox.connect("row-selected", self.on_category_selected)

        categories = [
            ("preferences-system", "Genel"),
            ("system-run", "Sistem"),
            ("video-display", "Ekran"),
            ("drive-harddisk", "Depolama"),
            ("network-wired", "Ağ")
        ]

        for icon_name, label in categories:
            row = Gtk.ListBoxRow()
            r_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            r_box.set_border_width(8)
            img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DND)
            lbl = Gtk.Label(label=label, xalign=0)
            r_box.pack_start(img, False, False, 0)
            r_box.pack_start(lbl, True, True, 0)
            row.add(r_box)
            self.listbox.add(row)

        sidebar_frame.add(self.listbox)
        sidebar_frame.set_size_request(160, -1)
        hbox.pack_start(sidebar_frame, False, False, 0)

        # Right Stack
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        hbox.pack_start(self.stack, True, True, 0)

        self.build_general_page()
        self.build_system_page()
        self.build_display_page()
        self.build_storage_page()
        self.build_network_page()

        # Select first category
        first_row = self.listbox.get_row_at_index(0)
        if first_row:
            self.listbox.select_row(first_row)

        # Dialog buttons
        self.add_button("İptal", Gtk.ResponseType.CANCEL)
        save_btn = self.add_button("Tamam", Gtk.ResponseType.OK)
        save_btn.get_style_context().add_class("suggested-action")

        self.connect("response", self.on_response)
        self.show_all()

    def on_category_selected(self, listbox, row):
        if not row:
            return
        idx = row.get_index()
        names = ["general", "system", "display", "storage", "network"]
        if idx < len(names):
            self.stack.set_visible_child_name(names[idx])

    def build_general_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        page.set_border_width(10)

        grid = Gtk.Grid()
        grid.set_column_spacing(15)
        grid.set_row_spacing(12)

        grid.attach(Gtk.Label(label="Sanal Makine Adı:", xalign=0), 0, 0, 1, 1)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text(self.vm.name)
        grid.attach(self.name_entry, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="İşletim Sistemi Türü:", xalign=0), 0, 1, 1, 1)
        self.os_combo = Gtk.ComboBoxText()
        for key, tpl in OS_TEMPLATES.items():
            self.os_combo.append(key, f"{tpl['family']} - {tpl['name']}")
        self.os_combo.set_active_id(self.vm.os_type)
        grid.attach(self.os_combo, 1, 1, 1, 1)

        page.pack_start(grid, False, False, 0)
        self.stack.add_named(page, "general")

    def build_system_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        page.set_border_width(10)

        if self.is_running:
            warn = Gtk.Label()
            warn.set_markup("<span color='#e67e22'>⚠ Makine çalışırken bellek ve işlemci ayarları değiştirilemez.</span>")
            page.pack_start(warn, False, False, 0)

        grid = Gtk.Grid()
        grid.set_column_spacing(15)
        grid.set_row_spacing(15)

        # RAM
        grid.attach(Gtk.Label(label="Ana Bellek (RAM):", xalign=0), 0, 0, 1, 1)
        ram_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.ram_adj = Gtk.Adjustment(value=self.vm.ram_mb, lower=512, upper=self.max_ram, step_increment=256, page_increment=1024)
        self.ram_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.ram_adj)
        self.ram_scale.set_hexpand(True)
        self.ram_scale.set_digits(0)
        self.ram_scale.set_sensitive(not self.is_running)
        self.ram_spin = Gtk.SpinButton(adjustment=self.ram_adj)
        self.ram_spin.set_sensitive(not self.is_running)
        ram_box.pack_start(self.ram_scale, True, True, 0)
        ram_box.pack_start(self.ram_spin, False, False, 0)
        ram_box.pack_start(Gtk.Label(label="MB"), False, False, 0)
        grid.attach(ram_box, 1, 0, 1, 1)

        # CPU
        grid.attach(Gtk.Label(label="İşlemci Çekirdekleri:", xalign=0), 0, 1, 1, 1)
        cpu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.cpu_adj = Gtk.Adjustment(value=self.vm.cpus, lower=1, upper=self.total_cpus, step_increment=1, page_increment=1)
        self.cpu_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.cpu_adj)
        self.cpu_scale.set_hexpand(True)
        self.cpu_scale.set_digits(0)
        self.cpu_scale.set_sensitive(not self.is_running)
        self.cpu_spin = Gtk.SpinButton(adjustment=self.cpu_adj)
        self.cpu_spin.set_sensitive(not self.is_running)
        cpu_box.pack_start(self.cpu_scale, True, True, 0)
        cpu_box.pack_start(self.cpu_spin, False, False, 0)
        cpu_box.pack_start(Gtk.Label(label="vCPU"), False, False, 0)
        grid.attach(cpu_box, 1, 1, 1, 1)

        # Boot Order
        grid.attach(Gtk.Label(label="Önyükleme Sırası:", xalign=0), 0, 2, 1, 1)
        self.boot_combo = Gtk.ComboBoxText()
        self.boot_combo.append("cdrom,c", "Önce CD/DVD-ROM, sonra Sabit Disk")
        self.boot_combo.append("c,cdrom", "Önce Sabit Disk, sonra CD/DVD-ROM")
        self.boot_combo.set_active_id(self.vm.boot_order)
        grid.attach(self.boot_combo, 1, 2, 1, 1)

        # KVM
        grid.attach(Gtk.Label(label="Donanım Sanallaştırma:", xalign=0), 0, 3, 1, 1)
        self.kvm_check = Gtk.CheckButton(label="KVM Hızlandırmasını Etkinleştir (Önerilen)")
        self.kvm_check.set_active(self.vm.enable_kvm and HAS_KVM)
        self.kvm_check.set_sensitive(HAS_KVM)
        grid.attach(self.kvm_check, 1, 3, 1, 1)

        page.pack_start(grid, False, False, 0)
        self.stack.add_named(page, "system")

    def build_display_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        page.set_border_width(10)

        grid = Gtk.Grid()
        grid.set_column_spacing(15)
        grid.set_row_spacing(12)

        grid.attach(Gtk.Label(label="Grafik Denetleyicisi:", xalign=0), 0, 0, 1, 1)
        self.video_combo = Gtk.ComboBoxText()
        self.video_combo.append("virtio", "VirtIO GPU (Hızlı & 3D Uyumlu)")
        self.video_combo.append("qxl", "QXL (SPICE İstemcisi İçin İdeal)")
        self.video_combo.append("std", "Standart VGA")
        self.video_combo.set_active_id(self.vm.video_model or "virtio")
        grid.attach(self.video_combo, 1, 0, 1, 1)

        page.pack_start(grid, False, False, 0)
        self.stack.add_named(page, "display")

    def build_storage_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        page.set_border_width(10)

        # CD/DVD Drive
        cd_frame = Gtk.Frame(label="Optik Sürücü (CD/DVD)")
        cd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        cd_box.set_border_width(10)

        self.iso_chooser = Gtk.FileChooserButton(
            title="ISO İmajı Seçin",
            action=Gtk.FileChooserAction.OPEN
        )
        filt = Gtk.FileFilter()
        filt.set_name("ISO İmajları (*.iso)")
        filt.add_pattern("*.iso")
        self.iso_chooser.add_filter(filt)
        if self.vm.iso_path and os.path.exists(self.vm.iso_path):
            self.iso_chooser.set_filename(self.vm.iso_path)

        iso_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        iso_row.pack_start(self.iso_chooser, True, True, 0)

        eject_btn = Gtk.Button(label="Çıkar / Boşalt")
        eject_btn.connect("clicked", lambda b: self.iso_chooser.unselect_all())
        iso_row.pack_start(eject_btn, False, False, 0)

        cd_box.pack_start(iso_row, False, False, 0)
        cd_frame.add(cd_box)
        page.pack_start(cd_frame, False, False, 0)

        # Hard Disks
        hd_frame = Gtk.Frame(label="Sanal Sabit Diskler")
        hd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hd_box.set_border_width(10)

        if self.vm.disks:
            for i, d in enumerate(self.vm.disks):
                d_lbl = Gtk.Label(label=f"Disk {i}: {d.path} ({d.size_gb} GB, {d.disk_format})", xalign=0)
                hd_box.pack_start(d_lbl, False, False, 0)
        else:
            hd_box.pack_start(Gtk.Label(label="Bağlı sabit disk yok.", xalign=0), False, False, 0)

        hd_frame.add(hd_box)
        page.pack_start(hd_frame, False, False, 0)

        self.stack.add_named(page, "storage")

    def build_network_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        page.set_border_width(10)

        grid = Gtk.Grid()
        grid.set_column_spacing(15)
        grid.set_row_spacing(12)

        grid.attach(Gtk.Label(label="Ağ Modu:", xalign=0), 0, 0, 1, 1)
        self.net_combo = Gtk.ComboBoxText()
        self.net_combo.append("user", "NAT (Kullanıcı Modu - İnternet Erişimi)")
        self.net_combo.append("none", "Bağlantı Yok (İzole)")
        self.net_combo.set_active_id(self.vm.network.mode)
        grid.attach(self.net_combo, 1, 0, 1, 1)

        page.pack_start(grid, False, False, 0)
        self.stack.add_named(page, "network")

    def on_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.OK:
            # Save settings
            self.vm.name = self.name_entry.get_text().strip() or self.vm.name
            self.vm.os_type = self.os_combo.get_active_id() or self.vm.os_type

            if not self.is_running:
                self.vm.ram_mb = int(self.ram_adj.get_value())
                self.vm.cpus = int(self.cpu_adj.get_value())

            self.vm.boot_order = self.boot_combo.get_active_id() or "cdrom,c"
            self.vm.enable_kvm = self.kvm_check.get_active()
            self.vm.video_model = self.video_combo.get_active_id() or "virtio"

            # ISO path
            chosen_iso = self.iso_chooser.get_filename() or ""
            self.vm.iso_path = chosen_iso

            # Network
            self.vm.network.mode = self.net_combo.get_active_id() or "user"

            self.vm.save()

            if self.on_saved_callback:
                self.on_saved_callback(self.vm)

        self.destroy()
