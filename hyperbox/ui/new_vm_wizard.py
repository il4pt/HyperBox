"""
New Virtual Machine Wizard with Mandatory ISO Selection (VirtualBox Style)
"""
import os
import psutil
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from hyperbox.config import OS_TEMPLATES
from hyperbox.vm_manager import VMManager


class NewVMWizard(Gtk.Assistant):
    def __init__(self, parent=None, on_created_callback=None):
        super().__init__(title="Yeni Sanal Makine Oluştur - HyperBox")
        self.set_transient_for(parent)
        self.set_default_size(650, 520)
        self.set_border_width(12)
        self.on_created_callback = on_created_callback

        self.total_ram_mb = int(psutil.virtual_memory().total / (1024 * 1024))
        self.total_cpus = os.cpu_count() or 4

        self.init_pages()
        self.connect("cancel", self.on_cancel)
        self.connect("close", self.on_cancel)
        self.connect("apply", self.on_finish)

    def init_pages(self):
        # ---------------- Page 1: Name, OS and Mandatory ISO ----------------
        p1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        p1.set_border_width(12)

        info_lbl = Gtk.Label()
        info_lbl.set_markup("<big><b>Sanal Makine ve Kurulum İmajı (ISO)</b></big>\n"
                            "Sanal makinenin başlatılabilmesi ve işletim sisteminin kurulabilmesi için bir <b>ISO kalıbı seçimi zorunludur</b>.")
        info_lbl.set_line_wrap(True)
        info_lbl.set_xalign(0)
        p1.pack_start(info_lbl, False, False, 0)

        grid1 = Gtk.Grid()
        grid1.set_column_spacing(15)
        grid1.set_row_spacing(14)

        # 1. VM Name
        grid1.attach(Gtk.Label(label="<b>Sanal Makine Adı:</b>", use_markup=True, xalign=0), 0, 0, 1, 1)
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text("Yeni Sanal Makine")
        self.name_entry.connect("changed", self.validate_p1)
        grid1.attach(self.name_entry, 1, 0, 1, 1)

        # 2. ISO Image (ZORUNLU)
        grid1.attach(Gtk.Label(label="<b>Kurulum ISO Dosyası:</b>\n<small><span color='#e74c3c'>(Zorunlu)</span></small>", use_markup=True, xalign=0), 0, 1, 1, 1)
        
        iso_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.iso_chooser = Gtk.FileChooserButton(
            title="Kurulum ISO Dosyası Seçin (Zorunlu)",
            action=Gtk.FileChooserAction.OPEN
        )
        filt = Gtk.FileFilter()
        filt.set_name("ISO İmajları (*.iso, *.img)")
        filt.add_pattern("*.iso")
        filt.add_pattern("*.img")
        self.iso_chooser.add_filter(filt)
        self.iso_chooser.connect("file-set", self.on_iso_selected)
        iso_box.pack_start(self.iso_chooser, False, False, 0)

        self.iso_hint_lbl = Gtk.Label(use_markup=True, xalign=0)
        self.iso_hint_lbl.set_markup("<span color='#e74c3c'>⚠ İlerlemek için lütfen bir .iso dosyası seçin.</span>")
        iso_box.pack_start(self.iso_hint_lbl, False, False, 0)

        grid1.attach(iso_box, 1, 1, 1, 1)

        # 3. OS Preset Combo
        grid1.attach(Gtk.Label(label="<b>İşletim Sistemi Türü:</b>", use_markup=True, xalign=0), 0, 2, 1, 1)
        self.os_combo = Gtk.ComboBoxText()
        for key, tpl in OS_TEMPLATES.items():
            self.os_combo.append(key, f"{tpl['family']} - {tpl['name']}")
        self.os_combo.set_active_id("linux_ubuntu")
        self.os_combo.connect("changed", self.on_os_changed)
        grid1.attach(self.os_combo, 1, 2, 1, 1)

        p1.pack_start(grid1, False, False, 0)
        self.append_page(p1)
        self.set_page_title(p1, "Temel Bilgiler & ISO")
        self.set_page_type(p1, Gtk.AssistantPageType.CONTENT)
        # Initially not complete because ISO is not selected yet
        self.set_page_complete(p1, False)

        # ---------------- Page 2: Hardware (RAM & CPU) ----------------
        p2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        p2.set_border_width(12)

        p2_info = Gtk.Label()
        p2_info.set_markup("<b>Donanım Kaynakları</b>\n"
                           "Sanal makineye atanacak ana bellek (RAM) ve işlemci çekirdeği miktarını belirleyin.")
        p2_info.set_xalign(0)
        p2.pack_start(p2_info, False, False, 0)

        grid2 = Gtk.Grid()
        grid2.set_column_spacing(15)
        grid2.set_row_spacing(15)

        # RAM
        grid2.attach(Gtk.Label(label="Ana Bellek (RAM):", xalign=0), 0, 0, 1, 1)
        ram_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        max_ram = min(self.total_ram_mb, 32768)
        self.ram_adj = Gtk.Adjustment(value=2048, lower=512, upper=max_ram, step_increment=256, page_increment=1024)
        self.ram_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.ram_adj)
        self.ram_scale.set_hexpand(True)
        self.ram_scale.set_digits(0)
        self.ram_spin = Gtk.SpinButton(adjustment=self.ram_adj)
        ram_box.pack_start(self.ram_scale, True, True, 0)
        ram_box.pack_start(self.ram_spin, False, False, 0)
        ram_box.pack_start(Gtk.Label(label="MB"), False, False, 0)
        grid2.attach(ram_box, 1, 0, 1, 1)

        # CPU
        grid2.attach(Gtk.Label(label="İşlemci (vCPU):", xalign=0), 0, 1, 1, 1)
        cpu_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.cpu_adj = Gtk.Adjustment(value=2, lower=1, upper=self.total_cpus, step_increment=1, page_increment=1)
        self.cpu_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.cpu_adj)
        self.cpu_scale.set_hexpand(True)
        self.cpu_scale.set_digits(0)
        self.cpu_spin = Gtk.SpinButton(adjustment=self.cpu_adj)
        cpu_box.pack_start(self.cpu_scale, True, True, 0)
        cpu_box.pack_start(self.cpu_spin, False, False, 0)
        cpu_box.pack_start(Gtk.Label(label="Çekirdek"), False, False, 0)
        grid2.attach(cpu_box, 1, 1, 1, 1)

        p2.pack_start(grid2, False, False, 0)
        self.append_page(p2)
        self.set_page_title(p2, "Donanım")
        self.set_page_type(p2, Gtk.AssistantPageType.CONTENT)
        self.set_page_complete(p2, True)

        # ---------------- Page 3: Virtual Disk ----------------
        p3 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        p3.set_border_width(12)

        p3_info = Gtk.Label()
        p3_info.set_markup("<b>Sanal Sabit Disk</b>\n"
                           "Sanal makinenin işletim sistemi ve verileri için yeni bir sanal sabit disk oluşturulacak. "
                           "Disk dinamik genişleyen (QCOW2) formatta saklanacaktır.")
        p3_info.set_xalign(0)
        p3.pack_start(p3_info, False, False, 0)

        grid3 = Gtk.Grid()
        grid3.set_column_spacing(15)
        grid3.set_row_spacing(15)

        grid3.attach(Gtk.Label(label="Disk Boyutu:", xalign=0), 0, 0, 1, 1)
        disk_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.disk_adj = Gtk.Adjustment(value=25, lower=5, upper=500, step_increment=5, page_increment=20)
        self.disk_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=self.disk_adj)
        self.disk_scale.set_hexpand(True)
        self.disk_scale.set_digits(0)
        self.disk_spin = Gtk.SpinButton(adjustment=self.disk_adj)
        disk_box.pack_start(self.disk_scale, True, True, 0)
        disk_box.pack_start(self.disk_spin, False, False, 0)
        disk_box.pack_start(Gtk.Label(label="GB"), False, False, 0)
        grid3.attach(disk_box, 1, 0, 1, 1)

        p3.pack_start(grid3, False, False, 0)
        self.append_page(p3)
        self.set_page_title(p3, "Depolama")
        self.set_page_type(p3, Gtk.AssistantPageType.CONFIRM)
        self.set_page_complete(p3, True)

    def on_iso_selected(self, chooser):
        iso_file = chooser.get_filename()
        if iso_file and os.path.isfile(iso_file):
            filename_lower = os.path.basename(iso_file).lower()
            # Auto-detect OS preset
            if "ubuntu" in filename_lower:
                self.os_combo.set_active_id("linux_ubuntu")
            elif "arch" in filename_lower:
                self.os_combo.set_active_id("linux_arch")
            elif "debian" in filename_lower:
                self.os_combo.set_active_id("linux_debian")
            elif "fedora" in filename_lower:
                self.os_combo.set_active_id("linux_fedora")
            elif "win11" in filename_lower or "windows 11" in filename_lower:
                self.os_combo.set_active_id("windows_11")
            elif "win10" in filename_lower or "windows 10" in filename_lower:
                self.os_combo.set_active_id("windows_10")

            # Update default VM name if user hasn't typed custom name
            if self.name_entry.get_text() in ["Yeni Sanal Makine", ""]:
                base = os.path.splitext(os.path.basename(iso_file))[0]
                self.name_entry.set_text(base.replace("-", " ").capitalize())

        self.validate_p1(None)

    def on_os_changed(self, combo):
        os_id = combo.get_active_id()
        if os_id in OS_TEMPLATES:
            tpl = OS_TEMPLATES[os_id]
            self.ram_adj.set_value(tpl["default_ram"])
            self.cpu_adj.set_value(tpl["default_cpus"])
            self.disk_adj.set_value(tpl["default_disk_gb"])

    def validate_p1(self, widget):
        name_valid = bool(self.name_entry.get_text().strip())
        iso_path = self.iso_chooser.get_filename()
        iso_valid = bool(iso_path and os.path.isfile(iso_path))

        if not iso_valid:
            self.iso_hint_lbl.set_markup("<span color='#e74c3c'>⚠ İlerlemek için lütfen geçerli bir .iso dosyası seçin.</span>")
        else:
            self.iso_hint_lbl.set_markup(f"<span color='#2ecc71'>✔ ISO Seçildi: {os.path.basename(iso_path)}</span>")

        is_complete = name_valid and iso_valid
        p1 = self.get_nth_page(0)
        self.set_page_complete(p1, is_complete)

    def on_cancel(self, assistant):
        self.destroy()

    def on_finish(self, assistant):
        name = self.name_entry.get_text().strip() or "Sanal Makine"
        os_type = self.os_combo.get_active_id() or "linux_generic"
        ram_mb = int(self.ram_adj.get_value())
        cpus = int(self.cpu_adj.get_value())
        disk_gb = int(self.disk_adj.get_value())
        iso_path = self.iso_chooser.get_filename() or ""

        if not iso_path or not os.path.isfile(iso_path):
            err = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="ISO İmajı Seçilmedi"
            )
            err.format_secondary_text("Sanal makinenin kurulabilmesi için geçerli bir ISO dosyası seçilmesi zorunludur.")
            err.run()
            err.destroy()
            return

        mgr = VMManager.get_instance()
        vm = mgr.create_vm(
            name=name,
            os_type=os_type,
            ram_mb=ram_mb,
            cpus=cpus,
            disk_size_gb=disk_gb,
            iso_path=iso_path
        )

        if self.on_created_callback:
            self.on_created_callback(vm)

        self.destroy()
