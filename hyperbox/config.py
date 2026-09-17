"""
HyperBox Configuration and Constants
"""
import os
import shutil

APP_NAME = "HyperBox"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Linux için Hızlı ve Modern KVM/QEMU Sanal Makine Yöneticisi"

BASE_CONFIG_DIR = os.path.expanduser("~/.config/hyperbox")
BASE_DATA_DIR = os.path.expanduser("~/.local/share/hyperbox")
VMS_DIR = os.path.join(BASE_DATA_DIR, "vms")
SNAPSHOTS_DIR = os.path.join(BASE_DATA_DIR, "snapshots")

for d in [BASE_CONFIG_DIR, BASE_DATA_DIR, VMS_DIR, SNAPSHOTS_DIR]:
    os.makedirs(d, exist_ok=True)

# Dynamic QEMU and KVM detection functions
def get_qemu_bin():
    return shutil.which("qemu-system-x86_64")

def get_qemu_img_bin():
    return shutil.which("qemu-img")

def check_kvm():
    return os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK)

# PEP 562 Module-level dynamic attribute access
def __getattr__(name):
    if name == "QEMU_BIN":
        return get_qemu_bin()
    elif name == "QEMU_IMG_BIN":
        return get_qemu_img_bin()
    elif name == "HAS_KVM":
        return check_kvm()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

KVM_DEVICE = "/dev/kvm"

# Common OS Presets
OS_TEMPLATES = {
    "linux_ubuntu": {
        "family": "Linux",
        "name": "Ubuntu (64-bit)",
        "icon": "distributor-logo-ubuntu",
        "default_ram": 2048,
        "default_cpus": 2,
        "default_disk_gb": 25,
        "video": "virtio",
    },
    "linux_arch": {
        "family": "Linux",
        "name": "Arch Linux (64-bit)",
        "icon": "distributor-logo-archlinux",
        "default_ram": 2048,
        "default_cpus": 2,
        "default_disk_gb": 20,
        "video": "virtio",
    },
    "linux_debian": {
        "family": "Linux",
        "name": "Debian (64-bit)",
        "icon": "distributor-logo-debian",
        "default_ram": 2048,
        "default_cpus": 2,
        "default_disk_gb": 20,
        "video": "virtio",
    },
    "linux_fedora": {
        "family": "Linux",
        "name": "Fedora (64-bit)",
        "icon": "distributor-logo-fedora",
        "default_ram": 2048,
        "default_cpus": 2,
        "default_disk_gb": 25,
        "video": "virtio",
    },
    "linux_generic": {
        "family": "Linux",
        "name": "Diğer Linux (64-bit)",
        "icon": "system-run",
        "default_ram": 2048,
        "default_cpus": 2,
        "default_disk_gb": 20,
        "video": "virtio",
    },
    "windows_11": {
        "family": "Windows",
        "name": "Windows 11 (64-bit)",
        "icon": "applications-other",
        "default_ram": 4096,
        "default_cpus": 4,
        "default_disk_gb": 64,
        "video": "qxl",
    },
    "windows_10": {
        "family": "Windows",
        "name": "Windows 10 (64-bit)",
        "icon": "applications-other",
        "default_ram": 4096,
        "default_cpus": 2,
        "default_disk_gb": 50,
        "video": "qxl",
    },
    "other": {
        "family": "Diğer",
        "name": "Diğer / Bilinmeyen",
        "icon": "computer",
        "default_ram": 1024,
        "default_cpus": 1,
        "default_disk_gb": 10,
        "video": "std",
    }
}
