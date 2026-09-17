#!/usr/bin/env bash
# HyperBox Uninstaller Script

set -e

echo "HyperBox sistemden kaldırılıyor..."

# Remove desktop entry
rm -f "$HOME/.local/share/applications/hyperbox.desktop"

# Remove desktop shortcuts
rm -f "$HOME/Desktop/HyperBox.desktop" "$HOME/Masaüstü/HyperBox.desktop"

# Remove icons
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/hyperbox.svg"
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/hyperbox.png"

# Remove bin symlink
rm -f "$HOME/.local/bin/hyperbox"

# Update caches
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "HyperBox kısayolları ve ikonları başarıyla kaldırıldı."
echo "(Not: Sanal makineleriniz ve diskleriniz ~/.local/share/hyperbox altında korunmuştur.)"
