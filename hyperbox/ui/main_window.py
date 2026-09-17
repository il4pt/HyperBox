"""
HyperBox Main Window (VirtualBox-style Interface)
"""
import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib
from hyperbox.config import APP_NAME, APP_VERSION, APP_DESCRIPTION, QEMU_BIN, HAS_KVM
from hyperbox.models import VirtualMachine
from hyperbox.vm_manager import VMManager
from hyperbox.qemu_runner import QemuRunner
from hyperbox.ui.new_vm_wizard import NewVMWizard
from hyperbox.ui.settings_dialog import SettingsDialog
from hyperbox.ui.console_window import VMConsoleWindow
from hyperbox.ui.dependency_dialog import DependencyDialog
from hyperbox.distro import LinuxDistro



class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title=f"{APP_NAME} - Sanal Makine Yöneticisi")
        self.set_default_size(1050, 680)
        self.set_position(Gtk.WindowPosition.CENTER)

        self.mgr = VMManager.get_instance()
        self.active_consoles = {}  # vm_id -> VMConsoleWindow
        self.selected_vm_id = None

        self.init_ui()
        self.load_vm_list()

        # Polling timer for live VM states
        self.timer_id = GLib.timeout_add_seconds(2, self.on_timer_tick)
        self.connect("delete-event", self.on_delete_event)
        self.connect("destroy", self.on_window_destroy)


    def init_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(vbox)

        # ---------------- VirtualBox Style Toolbar ----------------
        toolbar = Gtk.Toolbar()
        toolbar.set_style(Gtk.ToolbarStyle.BOTH)
        toolbar.get_style_context().add_class("primary-toolbar")

        # 1. New (Yeni)
        self.btn_new = Gtk.ToolButton.new_from_stock(Gtk.STOCK_NEW)
        self.btn_new.set_label("Yeni")
        self.btn_new.set_tooltip_text("Yeni bir sanal makine sihirbazı başlatın")
        self.btn_new.connect("clicked", self.on_new_vm)
        toolbar.insert(self.btn_new, -1)

        # 2. Settings (Ayarlar)
        self.btn_settings = Gtk.ToolButton.new_from_stock(Gtk.STOCK_PREFERENCES)
        self.btn_settings.set_label("Ayarlar")
        self.btn_settings.set_tooltip_text("Seçili sanal makinenin donanım ve sistem ayarlarını düzenleyin")
        self.btn_settings.connect("clicked", self.on_settings)
        toolbar.insert(self.btn_settings, -1)

        toolbar.insert(Gtk.SeparatorToolItem(), -1)

        # 3. Start (Başlat)
        self.btn_start = Gtk.ToolButton.new_from_stock(Gtk.STOCK_MEDIA_PLAY)
        self.btn_start.set_label("Başlat")
        self.btn_start.set_tooltip_text("Seçili sanal makineyi başlatın")
        self.btn_start.connect("clicked", self.on_start_vm)
        toolbar.insert(self.btn_start, -1)

        # 4. Pause (Duraklat)
        self.btn_pause = Gtk.ToolButton.new_from_stock(Gtk.STOCK_MEDIA_PAUSE)
        self.btn_pause.set_label("Duraklat")
        self.btn_pause.set_tooltip_text("Çalışan makineyi duraklatın veya devam ettirin")
        self.btn_pause.connect("clicked", self.on_pause_vm)
        toolbar.insert(self.btn_pause, -1)

        # 5. Stop (Kapat)
        self.btn_stop = Gtk.ToolButton.new_from_stock(Gtk.STOCK_MEDIA_STOP)
        self.btn_stop.set_label("Kapat")
        self.btn_stop.set_tooltip_text("Sanal makineyi güvenle kapatın (ACPI)")
        self.btn_stop.connect("clicked", self.on_stop_vm)
        toolbar.insert(self.btn_stop, -1)

        # 6. Console (Ekran Konsolu)
        self.btn_console = Gtk.ToolButton.new_from_stock(Gtk.STOCK_FULLSCREEN)
        self.btn_console.set_label("Konsol")
        self.btn_console.set_tooltip_text("Sanal makinenin canlı ekran konsolunu açın")
        self.btn_console.connect("clicked", self.on_open_console)
        toolbar.insert(self.btn_console, -1)

        toolbar.insert(Gtk.SeparatorToolItem(), -1)

        # 7. Delete (Sil)
        self.btn_delete = Gtk.ToolButton.new_from_stock(Gtk.STOCK_DELETE)
        self.btn_delete.set_label("Sil")
        self.btn_delete.set_tooltip_text("Seçili sanal makineyi ve disklerini silin")
        self.btn_delete.connect("clicked", self.on_delete_vm)
        toolbar.insert(self.btn_delete, -1)

        # 8. Dependency Check (QEMU / KVM Durumu)
        sep_flex = Gtk.SeparatorToolItem()
        sep_flex.set_draw(False)
        sep_flex.set_expand(True)
        toolbar.insert(sep_flex, -1)

        self.btn_dep = Gtk.ToolButton.new_from_stock(Gtk.STOCK_INFO)
        self.btn_dep.set_label("KVM/QEMU")
        self.btn_dep.set_tooltip_text("Sistem sanallaştırma motoru ve sürücü durumunu görüntüleyin")
        self.btn_dep.connect("clicked", lambda b: DependencyDialog(self).run())
        toolbar.insert(self.btn_dep, -1)

        vbox.pack_start(toolbar, False, False, 0)

        # ---------------- Main Split View ----------------
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(320)
        vbox.pack_start(paned, True, True, 0)

        # Left Pane: Search + VM List
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left_box.set_border_width(8)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Makinelerde ara...")
        self.search_entry.connect("search-changed", self.on_search_changed)
        left_box.pack_start(self.search_entry, False, False, 0)

        scrolled_list = Gtk.ScrolledWindow()
        scrolled_list.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.vm_listbox = Gtk.ListBox()
        self.vm_listbox.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self.vm_listbox.connect("row-selected", self.on_vm_selected)
        scrolled_list.add(self.vm_listbox)
        left_box.pack_start(scrolled_list, True, True, 0)

        paned.pack1(left_box, False, False)

        # Right Pane: Details, Logs, and Preview
        self.right_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.build_right_pane()
        paned.pack2(self.right_container, True, False)

        # ---------------- Bottom Statusbar ----------------
        self.statusbar = Gtk.Statusbar()
        self.status_ctx = self.statusbar.get_context_id("main")
        distro_name = LinuxDistro.get_info().get("name", "Linux")
        kvm_msg = "KVM Donanım Hızlandırma: Aktif ✔" if HAS_KVM else "KVM Donanım Hızlandırma: Devre Dışı ✖"
        self.statusbar.push(self.status_ctx, f"{APP_NAME} v{APP_VERSION} | {distro_name} | {kvm_msg}")
        vbox.pack_start(self.statusbar, False, False, 0)

        self.update_toolbar_state()

    def build_right_pane(self):
        # Header Card for Selected VM
        self.header_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        self.header_card.set_border_width(12)
        self.header_card.get_style_context().add_class("view")

        self.vm_big_icon = Gtk.Image.new_from_icon_name("computer", Gtk.IconSize.DIALOG)
        self.header_card.pack_start(self.vm_big_icon, False, False, 0)

        meta_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.vm_title_lbl = Gtk.Label(xalign=0)
        self.vm_title_lbl.set_markup("<big><b>Bir Sanal Makine Seçin</b></big>")
        self.vm_status_lbl = Gtk.Label(xalign=0)
        self.vm_status_lbl.set_markup("<span color='#7f8c8d'>Durum: Seçim yapılmadı</span>")
        meta_box.pack_start(self.vm_title_lbl, False, False, 0)
        meta_box.pack_start(self.vm_status_lbl, False, False, 0)
        self.header_card.pack_start(meta_box, True, True, 0)

        self.right_container.pack_start(self.header_card, False, False, 0)

        # Tabs: Details, Console Preview, Logs
        self.notebook = Gtk.Notebook()

        # Tab 1: Details
        self.details_scrolled = Gtk.ScrolledWindow()
        self.details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.details_box.set_border_width(15)
        self.details_scrolled.add(self.details_box)
        self.notebook.append_page(self.details_scrolled, Gtk.Label(label="Ayrıntılar"))

        # Tab 2: Logs
        logs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        logs_box.set_border_width(10)
        logs_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        refresh_logs_btn = Gtk.Button(label="Logları Yenile")
        refresh_logs_btn.connect("clicked", lambda b: self.refresh_logs())
        logs_toolbar.pack_start(refresh_logs_btn, False, False, 0)
        logs_box.pack_start(logs_toolbar, False, False, 0)

        scrolled_log = Gtk.ScrolledWindow()
        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        scrolled_log.add(self.log_view)
        logs_box.pack_start(scrolled_log, True, True, 0)

        self.notebook.append_page(logs_box, Gtk.Label(label="Günlükler (Logs)"))

        self.right_container.pack_start(self.notebook, True, True, 0)

    def load_vm_list(self):
        # Clear existing rows
        for child in self.vm_listbox.get_children():
            self.vm_listbox.remove(child)

        vms = self.mgr.list_vms()
        search_term = self.search_entry.get_text().strip().lower()

        for vm in vms:
            if search_term and search_term not in vm.name.lower():
                continue

            row = Gtk.ListBoxRow()
            row.vm_id = vm.id

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            hbox.set_border_width(10)

            # Icon
            icon_name = vm.os_info.get("icon", "computer")
            img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DND)
            hbox.pack_start(img, False, False, 0)

            # Text
            tbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            name_lbl = Gtk.Label(label=f"<b>{vm.name}</b>", use_markup=True, xalign=0)

            status_text = self.get_status_markup(vm.status)
            sub_lbl = Gtk.Label(label=f"{status_text} • {vm.ram_mb} MB • {vm.cpus} vCPU", use_markup=True, xalign=0)

            tbox.pack_start(name_lbl, False, False, 0)
            tbox.pack_start(sub_lbl, False, False, 0)
            hbox.pack_start(tbox, True, True, 0)

            row.add(hbox)
            self.vm_listbox.add(row)

        self.vm_listbox.show_all()

        # Select first or restore selected
        children = self.vm_listbox.get_children()
        if children:
            target_row = children[0]
            if self.selected_vm_id:
                for r in children:
                    if getattr(r, "vm_id", None) == self.selected_vm_id:
                        target_row = r
                        break
            self.vm_listbox.select_row(target_row)
        else:
            self.selected_vm_id = None
            self.show_empty_details()
            self.update_toolbar_state()

    def get_status_markup(self, status: str) -> str:
        if status == "running":
            return "<span color='#2ecc71'>● Çalışıyor</span>"
        elif status == "paused":
            return "<span color='#f39c12'>● Duraklatıldı</span>"
        else:
            return "<span color='#95a5a6'>○ Güç Kapalı</span>"

    def on_vm_selected(self, listbox, row):
        if not row:
            return
        self.selected_vm_id = getattr(row, "vm_id", None)
        self.update_vm_details()
        self.update_toolbar_state()

    def update_vm_details(self):
        vm = self.mgr.get_vm(self.selected_vm_id) if self.selected_vm_id else None
        if not vm:
            self.show_empty_details()
            return

        # Header
        self.vm_big_icon.set_from_icon_name(vm.os_info.get("icon", "computer"), Gtk.IconSize.DIALOG)
        self.vm_title_lbl.set_markup(f"<big><b>{vm.name}</b></big>")
        status_markup = self.get_status_markup(vm.status)
        pid_info = f" (PID: {vm.pid})" if vm.pid else ""
        self.vm_status_lbl.set_markup(f"<b>Durum:</b> {status_markup}{pid_info} | <b>İşletim Sistemi:</b> {vm.os_info['name']}")

        # Clear Details Box
        for c in self.details_box.get_children():
            self.details_box.remove(c)

        # Group 1: Genel & Sistem
        g1 = self.create_card_group("Sistem Bilgileri", [
            ("İşlemci (vCPU):", f"{vm.cpus} Çekirdek"),
            ("Ana Bellek (RAM):", f"{vm.ram_mb} MB ({round(vm.ram_mb / 1024, 1)} GB)"),
            ("Donanım Hızlandırma:", "KVM Destekli (Etkin)" if vm.enable_kvm else "Yazılımsal Emülasyon"),
            ("Önyükleme Sırası:", "CD/DVD-ROM, Sabit Disk" if "cdrom" in vm.boot_order else "Sabit Disk, CD/DVD-ROM")
        ])
        self.details_box.pack_start(g1, False, False, 0)

        # Group 2: Ekran & Grafik
        g2 = self.create_card_group("Ekran ve Grafik", [
            ("Video Denetleyicisi:", vm.video_model.upper()),
            ("Grafik Sunucusu:", "SPICE Canlı Ekran Konsolu"),
            ("SPICE Portu:", str(vm.spice_port) if vm.spice_port else "Bağlı Değil")
        ])
        self.details_box.pack_start(g2, False, False, 0)

        # Group 3: Depolama
        storage_rows = []
        for i, d in enumerate(vm.disks):
            storage_rows.append((f"Sabit Disk {i}:", f"{d.path} ({d.size_gb} GB, {d.disk_format})"))
        iso_name = os.path.basename(vm.iso_path) if vm.iso_path else "Boş / Takılı Değil"
        storage_rows.append(("Optik Sürücü (CD/DVD):", iso_name))
        g3 = self.create_card_group("Depolama Aygıtları", storage_rows)
        self.details_box.pack_start(g3, False, False, 0)

        # Group 4: Ağ
        g4 = self.create_card_group("Ağ", [
            ("Bağdaştırıcı 1:", "Kullanıcı Modu NAT (İnternet Aktif)" if vm.network.mode == "user" else "Devre Dışı")
        ])
        self.details_box.pack_start(g4, False, False, 0)

        self.details_box.show_all()
        self.refresh_logs()

    def create_card_group(self, title: str, items: list) -> Gtk.Frame:
        frame = Gtk.Frame(label=f" {title} ")
        box = Gtk.Grid()
        box.set_border_width(10)
        box.set_column_spacing(20)
        box.set_row_spacing(6)

        for row_idx, (k, v) in enumerate(items):
            k_lbl = Gtk.Label(label=f"<b>{k}</b>", use_markup=True, xalign=0)
            v_lbl = Gtk.Label(label=v, xalign=0)
            box.attach(k_lbl, 0, row_idx, 1, 1)
            box.attach(v_lbl, 1, row_idx, 1, 1)

        frame.add(box)
        return frame

    def show_empty_details(self):
        self.vm_big_icon.set_from_icon_name("computer", Gtk.IconSize.DIALOG)
        self.vm_title_lbl.set_markup("<big><b>HyperBox Sanal Makine Yöneticisi</b></big>")
        self.vm_status_lbl.set_markup("<span color='#7f8c8d'>Başlamak için 'Yeni' düğmesi ile sanal makine oluşturun.</span>")

        for c in self.details_box.get_children():
            self.details_box.remove(c)

        welcome_lbl = Gtk.Label()
        welcome_lbl.set_markup(
            "\n\n<b>Hoş Geldiniz!</b>\n\n"
            "VirtualBox kolaylığında KVM donanım hızlandırmalı sanal makineler oluşturabilirsiniz.\n"
            "Yukarıdaki <b>[Yeni]</b> butonuna tıklayarak ISO dosyanızla hemen bir sanal makine başlatabilirsiniz."
        )
        welcome_lbl.set_justify(Gtk.Justification.CENTER)
        self.details_box.pack_start(welcome_lbl, True, True, 0)
        self.details_box.show_all()

    def refresh_logs(self):
        vm = self.mgr.get_vm(self.selected_vm_id) if self.selected_vm_id else None
        if not vm:
            self.log_view.get_buffer().set_text("")
            return

        log_path = os.path.join(vm.vm_dir, "qemu.log")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-150:]  # Last 150 lines
                    self.log_view.get_buffer().set_text("".join(lines))
            except Exception:
                pass
        else:
            self.log_view.get_buffer().set_text("Bu makine için henüz kayıt (log) oluşmadı.")

    def update_toolbar_state(self):
        vm = self.mgr.get_vm(self.selected_vm_id) if self.selected_vm_id else None
        has_vm = vm is not None

        self.btn_settings.set_sensitive(has_vm)
        self.btn_delete.set_sensitive(has_vm)

        if not has_vm:
            self.btn_start.set_sensitive(False)
            self.btn_pause.set_sensitive(False)
            self.btn_stop.set_sensitive(False)
            self.btn_console.set_sensitive(False)
            return

        is_running = vm.status == "running"
        is_paused = vm.status == "paused"

        self.btn_start.set_sensitive(not is_running and not is_paused)
        self.btn_pause.set_sensitive(is_running or is_paused)
        self.btn_pause.set_label("Devam Et" if is_paused else "Duraklat")
        self.btn_stop.set_sensitive(is_running or is_paused)
        self.btn_console.set_sensitive(is_running or is_paused)

    def on_timer_tick(self):
        self.mgr.refresh_states()
        self.update_toolbar_state()
        # Refresh current row status label
        for row in self.vm_listbox.get_children():
            vm_id = getattr(row, "vm_id", None)
            vm = self.mgr.get_vm(vm_id)
            if vm:
                # Update status in list row
                hbox = row.get_child()
                if hbox:
                    tbox = hbox.get_children()[1]
                    sub_lbl = tbox.get_children()[1]
                    status_text = self.get_status_markup(vm.status)
                    sub_lbl.set_markup(f"{status_text} • {vm.ram_mb} MB • {vm.cpus} vCPU")

        if self.selected_vm_id:
            vm = self.mgr.get_vm(self.selected_vm_id)
            if vm:
                status_markup = self.get_status_markup(vm.status)
                pid_info = f" (PID: {vm.pid})" if vm.pid else ""
                self.vm_status_lbl.set_markup(f"<b>Durum:</b> {status_markup}{pid_info} | <b>İşletim Sistemi:</b> {vm.os_info['name']}")

        return True

    # ---------------- Action Handlers ----------------
    def on_new_vm(self, btn):
        wizard = NewVMWizard(self, on_created_callback=self.on_vm_created)
        wizard.show_all()

    def on_vm_created(self, vm: VirtualMachine):
        self.load_vm_list()
        self.selected_vm_id = vm.id
        self.update_vm_details()

    def on_settings(self, btn):
        vm = self.mgr.get_vm(self.selected_vm_id) if self.selected_vm_id else None
        if not vm:
            return
        dialog = SettingsDialog(vm, self, on_saved_callback=self.on_vm_settings_saved)
        dialog.run()

    def on_vm_settings_saved(self, vm: VirtualMachine):
        self.load_vm_list()
        self.update_vm_details()

    def on_start_vm(self, btn):
        vm = self.mgr.get_vm(self.selected_vm_id) if self.selected_vm_id else None
        if not vm:
            return

        if not QemuRunner.is_qemu_available():
            dialog = DependencyDialog(self)
            dialog.run()
            dialog.destroy()
            return

        # Mandatory ISO check
        if not vm.iso_path or not os.path.exists(vm.iso_path):
            file_dlg = Gtk.FileChooserDialog(
                title=f"'{vm.name}' İçin Kurulum ISO Seçin (Zorunlu)",
                parent=self,
                action=Gtk.FileChooserAction.OPEN
            )
            file_dlg.add_button("İptal", Gtk.ResponseType.CANCEL)
            sel_btn = file_dlg.add_button("ISO'yu Bağla ve Başlat", Gtk.ResponseType.OK)
            sel_btn.get_style_context().add_class("suggested-action")

            filt = Gtk.FileFilter()
            filt.set_name("ISO İmajları (*.iso, *.img)")
            filt.add_pattern("*.iso")
            filt.add_pattern("*.img")
            file_dlg.add_filter(filt)

            resp = file_dlg.run()
            chosen_iso = file_dlg.get_filename()
            file_dlg.destroy()

            if resp == Gtk.ResponseType.OK and chosen_iso and os.path.isfile(chosen_iso):
                vm.iso_path = chosen_iso
                vm.save()
                self.update_vm_details()
            else:
                warn_dlg = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.OK,
                    text="Başlatma İptal Edildi"
                )
                warn_dlg.format_secondary_text("Sanal makinenin başlatılabilmesi için geçerli bir ISO kalıbı seçilmesi zorunludur.")
                warn_dlg.run()
                warn_dlg.destroy()
                return

        success, msg = QemuRunner.start_vm(vm, use_spice=True)
        if not success:
            err_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.OK,
                text="Sanal Makine Başlatılamadı"
            )
            err_dialog.format_secondary_text(msg)
            err_dialog.run()
            err_dialog.destroy()
        else:
            self.update_toolbar_state()
            self.on_open_console(None)

    def on_pause_vm(self, btn):
        vm = self.mgr.get_vm(self.selected_vm_id) if self.selected_vm_id else None
        if not vm:
            return
        if vm.status == "running":
            QemuRunner.pause_vm(vm)
        elif vm.status == "paused":
            QemuRunner.resume_vm(vm)
        self.update_toolbar_state()

    def on_stop_vm(self, btn):
        vm = self.mgr.get_vm(self.selected_vm_id) if self.selected_vm_id else None
        if not vm:
            return

        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text=f"'{vm.name}' sanal makinesini kapatmak istiyor musunuz?"
        )
        dialog.add_button("İptal", Gtk.ResponseType.CANCEL)
        dialog.add_button("Zorla Kapat (Güç Kes)", Gtk.ResponseType.REJECT)
        acpi_btn = dialog.add_button("Kapat (ACPI)", Gtk.ResponseType.ACCEPT)
        acpi_btn.get_style_context().add_class("suggested-action")

        resp = dialog.run()
        dialog.destroy()

        if resp == Gtk.ResponseType.ACCEPT:
            QemuRunner.acpi_shutdown(vm)
        elif resp == Gtk.ResponseType.REJECT:
            QemuRunner.force_stop(vm)
            if vm.id in self.active_consoles:
                self.active_consoles[vm.id].destroy()
                del self.active_consoles[vm.id]

        self.update_toolbar_state()

    def on_delete_vm(self, btn):
        vm = self.mgr.get_vm(self.selected_vm_id) if self.selected_vm_id else None
        if not vm:
            return

        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=f"'{vm.name}' sanal makinesini silmek istediğinize emin misiniz?"
        )
        dialog.format_secondary_text("Bu işlem sanal makinenin tüm sabit disk dosyalarını kalıcı olarak silecektir.")
        resp = dialog.run()
        dialog.destroy()

        if resp == Gtk.ResponseType.OK:
            self.mgr.delete_vm(vm.id, delete_disks=True)
            self.selected_vm_id = None
            self.load_vm_list()

    def on_open_console(self, btn):
        vm = self.mgr.get_vm(self.selected_vm_id) if self.selected_vm_id else None
        if not vm or vm.status not in ["running", "paused"]:
            return

        if vm.id in self.active_consoles:
            self.active_consoles[vm.id].present()
        else:
            win = VMConsoleWindow(vm, self)
            self.active_consoles[vm.id] = win
            win.connect("destroy", lambda w: self.active_consoles.pop(vm.id, None))
            win.show_all()

    def on_search_changed(self, entry):
        self.load_vm_list()

    def on_delete_event(self, widget, event):
        running_vms = [vm for vm in self.mgr.list_vms() if vm.status in ["running", "paused"]]
        if running_vms:
            names = ", ".join([v.name for v in running_vms])
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.NONE,
                text="Çalışan Sanal Makineler Var"
            )
            dialog.format_secondary_text(
                f"Şu anda çalışan sanal makine(ler) bulunuyor: {names}\n"
                "Çıkmadan önce ne yapmak istersiniz?"
            )
            dialog.add_button("İptal", Gtk.ResponseType.CANCEL)
            dialog.add_button("Arka Planda Bırak", Gtk.ResponseType.NO)
            acpi_btn = dialog.add_button("Makineleri Kapat (ACPI)", Gtk.ResponseType.YES)
            acpi_btn.get_style_context().add_class("suggested-action")

            resp = dialog.run()
            dialog.destroy()

            if resp == Gtk.ResponseType.CANCEL:
                return True
            elif resp == Gtk.ResponseType.YES:
                for vm in running_vms:
                    QemuRunner.acpi_shutdown(vm)

        return False

    def on_window_destroy(self, widget):
        if self.timer_id:
            GLib.source_remove(self.timer_id)
        if Gtk.main_level() > 0:
            Gtk.main_quit()


