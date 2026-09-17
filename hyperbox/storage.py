"""
Virtual Disk Storage Management
"""
import os
import subprocess
from typing import Tuple
from hyperbox.config import get_qemu_img_bin


class StorageManager:
    @staticmethod
    def create_disk(path: str, size_gb: int, disk_format: str = "qcow2") -> Tuple[bool, str]:
        """
        Creates a virtual hard disk image.
        Supports qcow2 and raw. If qemu-img is available, uses it.
        Otherwise falls back to sparse file creation for raw format.
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            qemu_img = get_qemu_img_bin()

            if qemu_img and os.path.exists(qemu_img):
                cmd = [qemu_img, "create", "-f", disk_format, path, f"{size_gb}G"]
                res = subprocess.run(cmd, capture_output=True, text=True)
                if res.returncode == 0:
                    return True, "Disk başarıyla oluşturuldu."
                else:
                    return False, f"qemu-img hatası: {res.stderr}"
            else:
                # Fallback: create sparse raw file
                size_bytes = size_gb * 1024 * 1024 * 1024
                with open(path, "wb") as f:
                    f.truncate(size_bytes)
                return True, "Disk ham (sparse) biçimde oluşturuldu."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_disk_info(path: str) -> dict:
        """
        Retrieves disk format and actual/virtual size.
        """
        if not os.path.exists(path):
            return {"exists": False, "size_gb": 0, "actual_mb": 0}

        actual_size = os.path.getsize(path) / (1024 * 1024)
        info = {
            "exists": True,
            "actual_mb": round(actual_size, 2),
            "format": "qcow2" if path.endswith(".qcow2") else "raw"
        }

        qemu_img = get_qemu_img_bin()
        if qemu_img and os.path.exists(qemu_img):
            try:
                res = subprocess.run([qemu_img, "info", path], capture_output=True, text=True)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if "virtual size:" in line:
                            info["virtual_size_str"] = line.split("virtual size:")[1].strip()
                        elif "file format:" in line:
                            info["format"] = line.split("file format:")[1].strip()
            except Exception:
                pass

        return info

    @staticmethod
    def delete_disk(path: str) -> bool:
        try:
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception as e:
            print(f"Error deleting disk {path}: {e}")
            return False
