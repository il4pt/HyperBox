"""
Linux Distribution & Package Manager Detection
Supports Arch, Debian/Ubuntu, Fedora/RHEL, openSUSE, Void, Alpine, etc.
"""
import os
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple


class LinuxDistro:
    @staticmethod
    def get_info() -> Dict[str, str]:
        """
        Parses /etc/os-release to detect Linux distribution.
        """
        info = {
            "id": "unknown",
            "name": "Linux",
            "version": "",
            "id_like": "",
            "family": "unknown"
        }

        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        v = v.strip("\"'")
                        if k == "ID":
                            info["id"] = v.lower()
                        elif k == "NAME":
                            info["name"] = v
                        elif k == "VERSION_ID":
                            info["version"] = v
                        elif k == "ID_LIKE":
                            info["id_like"] = v.lower()

        # Determine family
        id_str = info["id"]
        id_like = info["id_like"]

        if id_str in ["arch", "cachyos", "manjaro", "endeavouros", "artix", "garuda"] or "arch" in id_like:
            info["family"] = "arch"
        elif id_str in ["ubuntu", "debian", "linuxmint", "pop", "kali", "elementary", "zorin"] or "debian" in id_like or "ubuntu" in id_like:
            info["family"] = "debian"
        elif id_str in ["fedora", "rhel", "centos", "almalinux", "rocky", "nobara"] or "fedora" in id_like or "rhel" in id_like:
            info["family"] = "fedora"
        elif id_str in ["opensuse", "opensuse-tumbleweed", "opensuse-leap", "sles"] or "suse" in id_like:
            info["family"] = "suse"
        elif id_str == "void":
            info["family"] = "void"
        elif id_str == "alpine":
            info["family"] = "alpine"

        return info

    @classmethod
    def get_package_manager(cls) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (package_manager_name, install_command)
        """
        info = cls.get_info()
        family = info["family"]

        if family == "arch" or shutil.which("pacman"):
            # If CachyOS with broken mirror, strip dead mirror first
            prefix = "sudo sed -i '/bali0531/d' /etc/pacman.d/cachyos-mirrorlist 2>/dev/null; " if info["id"] == "cachyos" else ""
            return "pacman", f"{prefix}sudo pacman -S --needed --noconfirm qemu-desktop qemu-img virt-viewer"

        elif family == "debian" or shutil.which("apt-get"):
            return "apt", "sudo apt-get update && sudo apt-get install -y qemu-system-x86 qemu-utils virt-viewer python3-gi gir1.2-spiceclientgtk-3.0 gir1.2-gtk-3.0"

        elif family == "fedora" or shutil.which("dnf"):
            return "dnf", "sudo dnf install -y qemu-kvm qemu-img virt-viewer python3-gobject spice-gtk3"

        elif family == "suse" or shutil.which("zypper"):
            return "zypper", "sudo zypper install -y qemu-x86 qemu-tools virt-viewer python3-gobject typelib-SpiceClientGtk"

        elif family == "void" or shutil.which("xbps-install"):
            return "xbps", "sudo xbps-install -Sy qemu qemu-tools virt-viewer python3-gobject spice-gtk"

        elif family == "alpine" or shutil.which("apk"):
            return "apk", "sudo apk add qemu-system-x86_64 qemu-img virt-viewer py3-gobject3"

        return None, None

    @staticmethod
    def detect_audio_driver() -> str:
        """
        Detects available host audio daemon: pipewire, pa (pulseaudio), or alsa.
        """
        # Check PipeWire
        if shutil.which("pipewire") or shutil.which("pw-cli"):
            try:
                res = subprocess.run(["pgrep", "-x", "pipewire"], capture_output=True)
                if res.returncode == 0:
                    return "pipewire"
            except Exception:
                pass

        # Check PulseAudio
        if shutil.which("pulseaudio"):
            try:
                res = subprocess.run(["pgrep", "-x", "pulseaudio"], capture_output=True)
                if res.returncode == 0:
                    return "pa"
            except Exception:
                pass

        # Fallback ALSA
        return "alsa"

    @staticmethod
    def get_preferred_terminal() -> Optional[str]:
        """
        Finds the available terminal emulator on host.
        """
        terminals = [
            "konsole",
            "gnome-terminal",
            "xfce4-terminal",
            "alacritty",
            "kitty",
            "foot",
            "tilix",
            "terminator",
            "xterm"
        ]
        for t in terminals:
            p = shutil.which(t)
            if p:
                return p
        return None
