#!/usr/bin/env bash
# HyperBox Universal Linux Installer
# Installs HyperBox desktop entry, icons, and system commands for the current user.

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "===================================================="
echo "          HyperBox Universal Linux Installer        "
echo "===================================================="

# 1. Set permissions
echo "[1/5] İzinler ayarlanıyor..."
chmod +x "$DIR/main.py" "$DIR/launch.sh"

# 2. Install icons to XDG directories
echo "[2/5] Uygulama ikonları kuruluyor..."
ICON_DIR_SCALABLE="$HOME/.local/share/icons/hicolor/scalable/apps"
ICON_DIR_256="$HOME/.local/share/icons/hicolor/256x256/apps"
mkdir -p "$ICON_DIR_SCALABLE" "$ICON_DIR_256"

if [ -f "$DIR/assets/hyperbox.svg" ]; then
    cp "$DIR/assets/hyperbox.svg" "$ICON_DIR_SCALABLE/hyperbox.svg"
fi
if [ -f "$DIR/assets/hyperbox.png" ]; then
    cp "$DIR/assets/hyperbox.png" "$ICON_DIR_256/hyperbox.png"
fi

# 3. Install CLI launcher symlink in ~/.local/bin
echo "[3/5] Komut satırı kısayolu (~/.local/bin/hyperbox) oluşturuluyor..."
mkdir -p "$HOME/.local/bin"
ln -sf "$DIR/launch.sh" "$HOME/.local/bin/hyperbox"

# 4. Install Desktop Entry in ~/.local/share/applications
echo "[4/5] Sistem uygulama menüsü (.desktop) girdisi oluşturuluyor..."
APP_DIR="$HOME/.local/share/applications"
mkdir -p "$APP_DIR"

cat > "$APP_DIR/hyperbox.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=HyperBox
GenericName=Sanal Makine Yöneticisi
Comment=Linux için Hızlı ve Modern KVM/QEMU Sanal Makine Yöneticisi (VirtualBox Benzeri)
Exec=$DIR/launch.sh %U
Path=$DIR
Icon=hyperbox
Terminal=false
Categories=System;Emulator;Virtualization;Utility;
StartupNotify=true
StartupWMClass=HyperBox
Keywords=virtualbox;vm;qemu;kvm;virtual;machine;
EOF

chmod +x "$APP_DIR/hyperbox.desktop"

# 5. Create Desktop shortcut on user's Desktop folder
echo "[5/5] Masaüstü kısayolu oluşturuluyor..."
DESKTOP_DIRS=("$HOME/Desktop" "$HOME/Masaüstü")
for d in "${DESKTOP_DIRS[@]}"; do
    if [ -d "$d" ]; then
        cp "$APP_DIR/hyperbox.desktop" "$d/HyperBox.desktop"
        chmod +x "$d/HyperBox.desktop"
        gio set "$d/HyperBox.desktop" metadata::trusted true 2>/dev/null || true
        echo "  -> Masaüstü kısayolu oluşturuldu: $d/HyperBox.desktop"
    fi
done

# Update system icon and desktop caches if possible
update-desktop-database "$APP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "===================================================="
echo "  Kurulum Başarıyla Tamamlandı! ✔"
echo "  - Menüden veya masaüstünden 'HyperBox' ile açabilirsiniz."
echo "  - Terminalden çalıştırmak için: hyperbox"
echo "===================================================="
