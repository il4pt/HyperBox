"""
Central VM Manager
"""
import os
import shutil
from typing import List, Optional, Dict
from hyperbox.config import VMS_DIR
from hyperbox.models import VirtualMachine, VirtualDisk
from hyperbox.storage import StorageManager
from hyperbox.qemu_runner import QemuRunner


class VMManager:
    _instance = None

    def __init__(self):
        self.vms: Dict[str, VirtualMachine] = {}
        self.load_all()

    @classmethod
    def get_instance(cls) -> 'VMManager':
        if cls._instance is None:
            cls._instance = VMManager()
        return cls._instance

    def load_all(self):
        self.vms.clear()
        if not os.path.exists(VMS_DIR):
            return

        for item in os.listdir(VMS_DIR):
            vm_dir = os.path.join(VMS_DIR, item)
            config_file = os.path.join(vm_dir, "vm.json")
            if os.path.exists(config_file):
                vm = VirtualMachine.load(config_file)
                if vm:
                    self.vms[vm.id] = vm

    def get_vm(self, vm_id: str) -> Optional[VirtualMachine]:
        return self.vms.get(vm_id)

    def list_vms(self) -> List[VirtualMachine]:
        return list(self.vms.values())

    def create_vm(
        self,
        name: str,
        os_type: str,
        ram_mb: int,
        cpus: int,
        disk_size_gb: int,
        iso_path: str = ""
    ) -> VirtualMachine:
        vm = VirtualMachine(
            name=name,
            os_type=os_type,
            ram_mb=ram_mb,
            cpus=cpus,
            iso_path=iso_path
        )
        # Create virtual disk
        disk_path = os.path.join(vm.vm_dir, "disk0.qcow2")
        StorageManager.create_disk(disk_path, disk_size_gb, "qcow2")

        vm.disks.append(VirtualDisk(path=disk_path, size_gb=disk_size_gb, disk_format="qcow2"))
        vm.save()
        self.vms[vm.id] = vm
        return vm

    def delete_vm(self, vm_id: str, delete_disks: bool = True) -> bool:
        vm = self.get_vm(vm_id)
        if not vm:
            return False

        if QemuRunner.is_running(vm):
            QemuRunner.force_stop(vm)

        if delete_disks and os.path.exists(vm.vm_dir):
            try:
                shutil.rmtree(vm.vm_dir)
            except Exception as e:
                print(f"Error removing vm directory: {e}")

        if vm_id in self.vms:
            del self.vms[vm_id]

        return True

    def refresh_states(self):
        for vm in self.vms.values():
            if vm.pid:
                if not QemuRunner.is_running(vm):
                    vm.status = "stopped"
                    vm.pid = None
