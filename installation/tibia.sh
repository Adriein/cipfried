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
readonly INSTALL_DIR="${XDG_DATA_HOME:-"${HOME}/.local/share"}"
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
chmod +x "$INSTALL_DIR/start-tibia-launcher.sh"

# ----------------------------------------------------------------------
# 3. Install modern dependencies (no more libssl1.0-dev!)
# ----------------------------------------------------------------------
log "Installing/updating required libraries..."
apt_update_needed=0
if ! dpkg -l | grep -q libpcre2-16-0; then
    apt_update_needed=1
fi

if [[ $apt_update_needed -eq 1 ]]; then
    apt-get update -y
fi

apt-get install -y libpcre2-16-0 libglib2.0-0 libgtk-3-0 libx11-xcb1 libxcb-xinerama0 libxcb-xfixes0 libxcb-shape0 libxcb-randr0 libxcb-render-util0

# Some older Tibia versions still look for the old lib name → symlink
if [[ ! -e /usr/lib/x86_64-linux-gnu/libpcre.so.3 ]] && [[ -e /usr/lib/x86_64-linux-gnu/libpcre2-16.so.0 ]]; then
    ln -sf /usr/lib/x86_64-linux-gnu/libpcre2-16.so.0 /usr/lib/x86_64-linux-gnu/libpcre.so.3
    log "Created compatibility symlink for libpcre"
fi

# ----------------------------------------------------------------------
# 3.5 Install Microsoft Core Fonts (TTF) - CRISP TEXT = BETTER PIXEL BOT ACCURACY
# ----------------------------------------------------------------------
log "Installing Microsoft Core Fonts (Tahoma, Arial, Verdana...) for correct text rendering..."

# Method 1: Official package (Ubuntu/Debian/Mint)
if command -v apt-get >/dev/null; then
    # Accept Microsoft EULA automatically
    echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true | debconf-set-selections

    # Create temporary dir for font installer (it downloads to /tmp sometimes)
    export TMPDIR="$TEMP_DIR"

    if apt-get install -y ttf-mscorefonts-installer; then
        log "Microsoft Core Fonts installed successfully via package"
    else
        warn "Package installer failed. Falling back to direct download method..."

        # Method 2: Fallback - Direct download of latest font pack (works 100% even on fresh minimal installs)
        log "Downloading and installing Microsoft fonts manually"
        wget -q -O "$TEMP_DIR/mscorefonts.tar.gz" \
            https://github.com/peterbrittain/asciimatics/raw/master/ttf-mscorefonts.tar.gz || \
            wget -q -O "$TEMP_DIR/mscorefonts.tar.gz" \
            https://web.archive.org/web/2024/https://downloads.sourceforge.net/project/mscorefonts2/fonts/mscorefonts-latest.tar.gz

        tar -xzf "$TEMP_DIR/mscorefonts.tar.gz" -C "$TEMP_DIR"

        mkdir -p /usr/share/fonts/truetype/msttcorefonts
        find "$TEMP_DIR" -name "*.ttf" -exec cp {} /usr/share/fonts/truetype/msttcorefonts/ \; 2>/dev/null || true
        find "$TEMP_DIR" -name "*.TTF" -exec cp {} /usr/share/fonts/truetype/msttcorefonts/ \; 2>/dev/null || true

        log "Copied $(find /usr/share/fonts/truetype/msttcorefonts -name "*.ttf" -o -name "*.TTF" | wc -l) Microsoft fonts"
    fi

# Final step: Update font cache (critical!)
log "Updating font cache..."
fc-cache -f -v >/dev/null 2>&1 || log "fc-cache failed (non-fatal) - fonts should still work"

# Force Tibia to re-read fonts on next launch
if [[ -f "$INSTALL_DIR/packages/Tibia/config.ini" ]]; then
    sed -i 's/FontName=.*/FontName=Tahoma/' "$INSTALL_DIR/packages/Tibia/config.ini" 2>/dev/null || true
    sed -i 's/UseCustomFont=.*/UseCustomFont=true/' "$INSTALL_DIR/packages/Tibia/config.ini" 2>/dev/null || true
fi

log "Microsoft fonts installed and activated"

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
Icon=$INSTALL_DIR/packages/Tibia/tibia.png
Exec="$INSTALL_DIR/start-tibia-launcher.sh"
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
echo "   • Launch from your applications menu or run: $INSTALL_DIR/start-tibia-launcher.sh"
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

# ----------------------------------------------------------------------
# 6. Install minimap (essential for cavebot, pathfinding, targeting)
# ----------------------------------------------------------------------
log "Installing minimap from tibiamaps.io..."
if [[ -f "./maps.sh" ]]; then
    bash "./maps.sh" --no-markers > /dev/null 2>&1
    log "Minimap with no markers installed"
elif command -v maps.sh >/dev/null; then
    maps.sh --grid-poi-markers
else
    warn "maps.sh not found in current directory – skipping minimap"
    warn "Download it separately: https://tibiamaps.io"
fi

exit 0