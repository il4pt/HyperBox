"""
Data models for HyperBox Virtual Machines
"""
import os
import json
import uuid
from typing import List, Dict, Optional
from hyperbox.config import VMS_DIR, OS_TEMPLATES, check_kvm


class VirtualDisk:
    def __init__(self, path: str, size_gb: int = 20, disk_format: str = "qcow2"):
        self.path = path
        self.size_gb = size_gb
        self.disk_format = disk_format

    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "size_gb": self.size_gb,
            "disk_format": self.disk_format
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'VirtualDisk':
        return cls(
            path=data.get("path", ""),
            size_gb=data.get("size_gb", 20),
            disk_format=data.get("disk_format", "qcow2")
        )


class NetworkConfig:
    def __init__(self, mode: str = "user", port_forwards: Optional[List[Dict[str, int]]] = None):
        self.mode = mode
        self.port_forwards = port_forwards or []

    def to_dict(self) -> Dict:
        return {
            "mode": self.mode,
            "port_forwards": self.port_forwards
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'NetworkConfig':
        return cls(
            mode=data.get("mode", "user"),
            port_forwards=data.get("port_forwards", [])
        )


class VirtualMachine:
    def __init__(
        self,
        name: str,
        os_type: str = "linux_ubuntu",
        ram_mb: int = 2048,
        cpus: int = 2,
        vm_id: Optional[str] = None,
        disks: Optional[List[VirtualDisk]] = None,
        iso_path: str = "",
        video_model: str = "virtio",
        enable_kvm: bool = True,
        boot_order: str = "cdrom,c",
        network: Optional[NetworkConfig] = None
    ):
        self.id = vm_id or str(uuid.uuid4())[:8]
        self.name = name
        self.os_type = os_type
        self.ram_mb = int(ram_mb)
        self.cpus = int(cpus)
        self.disks = disks or []
        self.iso_path = iso_path
        self.video_model = video_model
        self.enable_kvm = bool(enable_kvm and check_kvm())
        self.boot_order = boot_order
        self.network = network or NetworkConfig()

        # Runtime states (not serialized)
        self.status = "stopped"
        self.pid: Optional[int] = None
        self.qmp_socket = ""
        self.spice_port = 0

    @property
    def vm_dir(self) -> str:
        d = os.path.join(VMS_DIR, self.id)
        os.makedirs(d, exist_ok=True)
        return d

    @property
    def config_path(self) -> str:
        return os.path.join(self.vm_dir, "vm.json")

    @property
    def os_info(self) -> Dict:
        return OS_TEMPLATES.get(self.os_type, OS_TEMPLATES["other"])

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "os_type": self.os_type,
            "ram_mb": self.ram_mb,
            "cpus": self.cpus,
            "disks": [d.to_dict() for d in self.disks],
            "iso_path": self.iso_path,
            "video_model": self.video_model,
            "enable_kvm": bool(self.enable_kvm),
            "boot_order": self.boot_order,
            "network": self.network.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'VirtualMachine':
        disks = [VirtualDisk.from_dict(d) for d in data.get("disks", [])]
        net = NetworkConfig.from_dict(data.get("network", {}))
        return cls(
            name=data.get("name", "VM"),
            os_type=data.get("os_type", "linux_ubuntu"),
            ram_mb=data.get("ram_mb", 2048),
            cpus=data.get("cpus", 2),
            vm_id=data.get("id"),
            disks=disks,
            iso_path=data.get("iso_path", ""),
            video_model=data.get("video_model", "virtio"),
            enable_kvm=bool(data.get("enable_kvm", True)),
            boot_order=data.get("boot_order", "cdrom,c"),
            network=net
        )

    def save(self):
        tmp_path = self.config_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, self.config_path)

    @classmethod
    def load(cls, config_path: str) -> Optional['VirtualMachine']:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            print(f"Error loading VM from {config_path}: {e}")
            return None
