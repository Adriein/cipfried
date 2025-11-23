#!/usr/bin/env bash
# =============================================================================
# Tibia 64-bit Linux Installer
# Author: aclaret
# Purpose: Install official Tibia client cleanly and safely on modern Ubuntu
# Tested on: Ubuntu 24.04
# =============================================================================

set -euo pipefail               # Strict mode: exit on error, undefined var, pipe fail
IFS=$'\n\t'                     # Safer word splitting
readonly SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="/var/log/tibia-installer.log"

# Colors for pretty output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $*${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR] $*${NC}" >&2 | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[WARN] $*${NC}" | tee -a "$LOG_FILE"
}

die() {
    error "$1"
    exit "${2:-1}"
}

# ----------------------------------------------------------------------
# Root check
# ----------------------------------------------------------------------
if [[ "${EUID}" -ne 0 ]]; then
    clear
    echo "======================================================================"
    echo "          Tibia Linux Installer (by Aclaret)"
    echo "======================================================================"
    echo "This script requires root privileges (to install system-wide)."
    echo "Please run with sudo or as root."
    echo "======================================================================"
    read -n 1 -s -r -p "Press any key to exit..."
    echo
    exit 1
fi

log "Starting Tibia installation as root"

# ----------------------------------------------------------------------
# Configuration (easy to tweak)
# ----------------------------------------------------------------------
readonly INSTALL_DIR="/opt/Tibia"
readonly DESKTOP_FILE="/usr/share/applications/Tibia.desktop"
readonly DOWNLOAD_URL="https://static.tibia.com/download/tibia.x64.tar.gz"
readonly TEMP_DIR="$(mktemp -d -t tibia-install-XXXXXXXXXX)"

cleanup() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
        log "Cleaned up temporary directory: $TEMP_DIR"
    fi
}
trap cleanup EXIT

log "Using temporary directory: $TEMP_DIR"

# ----------------------------------------------------------------------
# 1. Download & extract Tibia
# ----------------------------------------------------------------------
log "Downloading Tibia client from official source..."
if ! wget --quiet --show-progress --tries=3 --timeout=30 -O "$TEMP_DIR/tibia.x64.tar.gz" "$DOWNLOAD_URL"; then
    die "Failed to download Tibia package. Check your internet connection or the URL."
fi

log "Extracting archive..."
tar -xzf "$TEMP_DIR/tibia.x64.tar.gz" -C "$TEMP_DIR" || die "Failed to extract archive"

# The official tarball extracts to a folder called "Tibia"
if [[ ! -d "$TEMP_DIR/Tibia" ]]; then
    die "Expected 'Tibia' directory not found after extraction!"
fi

# ----------------------------------------------------------------------
# 2. Install to /opt/Tibia (idempotent)
# ----------------------------------------------------------------------
if [[ -d "$INSTALL_DIR" ]]; then
    warn "Existing installation found at $INSTALL_DIR – removing old version"
    rm -rf "$INSTALL_DIR"
fi

log "Installing Tibia to $INSTALL_DIR"
mv "$TEMP_DIR/Tibia" "$INSTALL_DIR"

chmod +x "$INSTALL_DIR/Tibia"

# ----------------------------------------------------------------------
# 3. Install modern dependencies
# ----------------------------------------------------------------------
log "Installing/updating required libraries..."
apt_update_needed=0
if ! dpkg -l | grep -q libpcre2-16-0; then
    apt_update_needed=1
fi

if [[ $apt_update_needed -eq 1 ]]; then
    apt-get update -y
fi

apt-get install -y libpcre2-16-0 libglib2.0-0 libgtk-3-0 libx11-xcb1 libxcb-xinerama0 libxcb-xfixes0 libxcb-shape0 libxcb-randr0 libxcb-render-util0 libevent-2.1-7

# Some older Tibia versions still look for the old lib name → symlink
if [[ ! -e /usr/lib/x86_64-linux-gnu/libpcre.so.3 ]] && [[ -e /usr/lib/x86_64-linux-gnu/libpcre2-16.so.0 ]]; then
    ln -sf /usr/lib/x86_64-linux-gnu/libpcre2-16.so.0 /usr/lib/x86_64-linux-gnu/libpcre.so.3
    log "Created compatibility symlink for libpcre"
fi

# ----------------------------------------------------------------------
# 4. Create .desktop entry (proper quoting, valid icon path)
# ----------------------------------------------------------------------
log "Creating desktop entry..."
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Tibia
Comment=Official Tibia MMORPG Client (Linux)
Icon=$INSTALL_DIR/tibia.ico
Exec="$INSTALL_DIR/Tibia"
Categories=Game;RolePlaying;
Terminal=false
StartupWMClass=Tibia
Path=$INSTALL_DIR
EOF

chmod 644 "$DESKTOP_FILE"
log "Desktop entry created at $DESKTOP_FILE"

# ----------------------------------------------------------------------
# 5. Final success message
# ----------------------------------------------------------------------
clear
echo -e "${NC}Tibia has been successfully installed!${GREEN}"
echo "   • Launch from your applications menu or run: $INSTALL_DIR/Tibia"
echo "   • For botting VMs: you can now safely run multiple clients with --no-sandbox if needed"
echo "   • Log file: $LOG_FILE"
echo -e "${NC}"

# ----------------------------------------------------------------------
# Optional: self-delete (comment if you want to keep the installer)
# ----------------------------------------------------------------------
# read -n 1 -s -r -p "Press Y to delete this installer script, any other key to keep it: "
# if [[ $REPLY =~ ^[Yy]$ ]]; then
#     rm -f "${SCRIPT_DIR}/${SCRIPT_NAME}"
#     log "Installer script deleted by user request"
# fi