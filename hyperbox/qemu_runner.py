"""
QEMU Process and QMP Management
"""
import os
import sys
import socket
import json
import time
import subprocess
from typing import Tuple, Optional, Dict
from hyperbox.config import get_qemu_bin, check_kvm
from hyperbox.models import VirtualMachine
from hyperbox.storage import StorageManager
from hyperbox.distro import LinuxDistro




def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class QemuRunner:
    @staticmethod
    def is_qemu_available() -> bool:
        qemu_bin = get_qemu_bin()
        return qemu_bin is not None and os.path.exists(qemu_bin)

    @classmethod
    def send_qmp_command(cls, socket_path: str, command: dict, timeout: float = 2.0) -> Optional[dict]:
        """
        Sends a QMP JSON command over unix domain socket.
        """
        if not os.path.exists(socket_path):
            return None

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(timeout)
                client.connect(socket_path)

                # QMP Greeting handshake
                client.recv(2048)
                # Enable capabilities
                client.sendall(json.dumps({"execute": "qmp_capabilities"}).encode() + b"\n")
                client.recv(2048)

                # Send actual command
                client.sendall(json.dumps(command).encode() + b"\n")
                resp_data = b""
                while True:
                    chunk = client.recv(2048)
                    if not chunk:
                        break
                    resp_data += chunk
                    if b"\n" in chunk:
                        break

                for line in resp_data.decode(errors="ignore").splitlines():
                    try:
                        res = json.loads(line)
                        if "return" in res or "error" in res:
                            return res
                    except Exception:
                        continue
        except Exception as e:
            print(f"QMP communication error: {e}")
        return None

    @classmethod
    def start_vm(cls, vm: VirtualMachine, use_spice: bool = True) -> Tuple[bool, str]:
        qemu_bin = get_qemu_bin()
        if not qemu_bin or not os.path.exists(qemu_bin):
            return False, "QEMU çalıştırılabilir dosyası (qemu-system-x86_64) sistemde bulunamadı. Lütfen 'sudo pacman -S --needed qemu-desktop qemu-img' ile kurulumu tamamlayın."

        if cls.is_running(vm):
            return True, "Sanal makine zaten çalışıyor."

        qmp_sock = os.path.join(vm.vm_dir, "qmp.sock")
        if os.path.exists(qmp_sock):
            try:
                os.remove(qmp_sock)
            except Exception:
                pass

        spice_port = find_free_port() if use_spice else 0
        vm.spice_port = spice_port
        vm.qmp_socket = qmp_sock

        cmd = [
            qemu_bin,
            "-name", vm.name,
            "-m", f"{vm.ram_mb}M",
            "-smp", str(vm.cpus),
        ]

        # KVM hardware acceleration
        if vm.enable_kvm and check_kvm():
            cmd.extend(["-enable-kvm", "-cpu", "host"])
        else:
            cmd.extend(["-cpu", "max"])

        # Storage Disks (with auto-repair for missing/invalid images)
        for i, disk in enumerate(vm.disks):
            if os.path.exists(disk.path):
                if disk.disk_format == "qcow2":
                    try:
                        with open(disk.path, "rb") as df:
                            magic = df.read(4)
                        if magic != b"QFI\xfb":
                            print(f"Bozuk/ham disk tespit edildi, qcow2 olarak yeniden oluşturuluyor: {disk.path}")
                            StorageManager.create_disk(disk.path, disk.size_gb, "qcow2")
                    except Exception:
                        pass
                cmd.extend([
                    "-drive", f"file={disk.path},format={disk.disk_format},if=virtio,index={i}"
                ])
            else:
                StorageManager.create_disk(disk.path, disk.size_gb, disk.disk_format)
                cmd.extend([
                    "-drive", f"file={disk.path},format={disk.disk_format},if=virtio,index={i}"
                ])

        # CD-ROM / ISO
        if vm.iso_path and os.path.exists(vm.iso_path):
            cmd.extend(["-cdrom", vm.iso_path])
            if "cdrom" in vm.boot_order:
                cmd.extend(["-boot", "order=d,menu=on"])
            else:
                cmd.extend(["-boot", "order=c,menu=on"])
        else:
            cmd.extend(["-boot", "order=c,menu=on"])

        # Video
        video = vm.video_model or "virtio"
        if video == "virtio":
            cmd.extend(["-vga", "virtio"])
        elif video == "qxl":
            cmd.extend(["-vga", "qxl"])
        else:
            cmd.extend(["-vga", "std"])

        # Display and SPICE
        if use_spice and spice_port > 0:
            cmd.extend([
                "-spice", f"port={spice_port},disable-ticketing=on",
                "-device", "virtio-serial-pci",
                "-chardev", "spicevmc,id=vdagent,name=vdagent",
                "-device", "virtserialport,chardev=vdagent,name=com.redhat.spice.0"
            ])
        else:
            cmd.extend(["-display", "gtk,zoom-to-fit=on"])

        # Input Devices (Absolute USB Tablet + USB Keyboard for full interaction)
        cmd.extend([
            "-usb",
            "-device", "usb-tablet",
            "-device", "usb-kbd"
        ])

        # Audio Support (Auto-detect Host Audio Backend: pipewire, pulseaudio, alsa)
        audio_drv = LinuxDistro.detect_audio_driver()
        audio_args = [
            "-audiodev", f"{audio_drv},id=snd0",
            "-device", "intel-hda",
            "-device", "hda-duplex,audiodev=snd0"
        ]
        cmd.extend(audio_args)

        # Network
        net_mode = vm.network.mode
        if net_mode == "user":
            fwd_opts = []
            for fwd in vm.network.port_forwards:
                hp = fwd.get("host", 0)
                gp = fwd.get("guest", 0)
                if hp and gp:
                    fwd_opts.append(f"hostfwd=tcp::{hp}-:{gp}")
            fwd_str = ("," + ",".join(fwd_opts)) if fwd_opts else ""
            cmd.extend([
                "-netdev", f"user,id=net0{fwd_str}",
                "-device", "virtio-net-pci,netdev=net0"
            ])
        elif net_mode == "none":
            cmd.extend(["-nic", "none"])

        # QMP socket for live control
        cmd.extend(["-qmp", f"unix:{qmp_sock},server,nowait"])

        # Run process detached
        try:
            log_path = os.path.join(vm.vm_dir, "qemu.log")
            log_file = open(log_path, "w")
            proc = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
            vm.pid = proc.pid
            vm.status = "running"

            # Wait briefly to ensure QEMU didn't crash on startup
            time.sleep(0.5)
            if proc.poll() is not None:
                log_file.close()
                with open(log_path, "r") as f:
                    err = f.read()

                # If audio driver failed on minimal QEMU, retry without audio
                if "audio" in err.lower() or "snd0" in err:
                    print("Audio backend not supported by QEMU installation; retrying without audio...")
                    cmd_no_audio = [c for c in cmd if c not in audio_args]
                    log_file = open(log_path, "w")
                    proc = subprocess.Popen(
                        cmd_no_audio,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        start_new_session=True
                    )
                    vm.pid = proc.pid
                    vm.status = "running"
                    time.sleep(0.5)
                    if proc.poll() is None:
                        return True, "Sanal makine başlatıldı (ses devre dışı bırakıldı)."

                vm.status = "stopped"
                vm.pid = None
                return False, f"QEMU başlatılamadı:\n{err}"

            return True, "Sanal makine başarıyla başlatıldı."
        except Exception as e:
            vm.status = "stopped"
            vm.pid = None
            return False, str(e)

    @classmethod
    def is_running(cls, vm: VirtualMachine) -> bool:
        if not vm.pid:
            return False
        try:
            os.kill(vm.pid, 0)
            return True
        except (ProcessLookupError, OSError):
            vm.status = "stopped"
            vm.pid = None
            return False

    @classmethod
    def pause_vm(cls, vm: VirtualMachine) -> bool:
        if not cls.is_running(vm):
            return False
        res = cls.send_qmp_command(vm.qmp_socket, {"execute": "stop"})
        if res and "return" in res:
            vm.status = "paused"
            return True
        return False

    @classmethod
    def resume_vm(cls, vm: VirtualMachine) -> bool:
        if not cls.is_running(vm):
            return False
        res = cls.send_qmp_command(vm.qmp_socket, {"execute": "cont"})
        if res and "return" in res:
            vm.status = "running"
            return True
        return False

    @classmethod
    def reset_vm(cls, vm: VirtualMachine) -> bool:
        if not cls.is_running(vm):
            return False
        res = cls.send_qmp_command(vm.qmp_socket, {"execute": "system_reset"})
        return res is not None and "return" in res

    @classmethod
    def acpi_shutdown(cls, vm: VirtualMachine) -> bool:
        if not cls.is_running(vm):
            return False
        res = cls.send_qmp_command(vm.qmp_socket, {"execute": "system_powerdown"})
        return res is not None and "return" in res

    @classmethod
    def force_stop(cls, vm: VirtualMachine) -> bool:
        if not cls.is_running(vm):
            return True
        cls.send_qmp_command(vm.qmp_socket, {"execute": "quit"})
        time.sleep(0.3)
        if not cls.is_running(vm):
            vm.status = "stopped"
            vm.pid = None
            return True
        try:
            os.kill(vm.pid, 15)
            time.sleep(0.5)
            if cls.is_running(vm):
                os.kill(vm.pid, 9)
        except Exception:
            pass
        vm.status = "stopped"
        vm.pid = None
        return True
