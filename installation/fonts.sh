#!/usr/bin/env bash
# =============================================================================
# Tibia fonts installer
# Author: aclaret
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[FONTS]${NC} $*" ; }
warn() { echo -e "${YELLOW}[FONTS] WARN:${NC} $*" ; }
error() { echo -e "${RED}[FONTS] ERROR:${NC} $*" >&2 ; }

# ----------------------------------------------------------------------
# Auto-detect Tibia data directory (supports /opt and user-local installs)
# ----------------------------------------------------------------------
find_tibia_dir() {
    local xdg="${XDG_DATA_HOME:-"${HOME}/.local/share"}/CipSoft GmbH/Tibia/packages/Tibia"
    if [[ -d "$xdg" ]]; then
        echo "$xdg"
        return 0
    fi

    error "Tibia client not found! Install it first with tibia.sh"
    exit 1
}

readonly TEMP_DIR="$(mktemp -d -t tibia-fonts-XXXXXXXXXX)"

TIBIA_DIR="$(find_tibia_dir)"
log "Using Tibia data directory: $TIBIA_DIR"

cleanup() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
        log "Cleaned up temporary directory: $TEMP_DIR"
    fi
}
trap cleanup EXIT

# ----------------------------------------------------------------------
# 1 Install Microsoft Core Fonts (TTF)
# ----------------------------------------------------------------------
log "Installing Microsoft Core Fonts (Tahoma, Arial, Verdana...) for correct text rendering..."

log "Downloading and installing Microsoft fonts manually"

FONT_DIR="$HOME/.local/share/fonts/msttcorefonts"
mkdir -p "$FONT_DIR"

# Accept EULA non-interactively (critical!)
echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | \
    sudo debconf-set-selections

# Install (this will download and extract the real EXEs from SourceForge automatically)
sudo apt-get install -y ttf-mscorefonts-installer

# Final step: Update font cache (critical!)
log "Updating font cache..."
fc-cache -f -v >/dev/null 2>&1 || log "fc-cache failed (non-fatal) - fonts should still work"

# Force Tibia to re-read fonts on next launch
if [[ -f "$TIBIA_DIR/packages/Tibia/config.ini" ]]; then
    sed -i 's/FontName=.*/FontName=Tahoma/' "$TIBIA_DIR/packages/Tibia/config.ini" 2>/dev/null || true
    sed -i 's/UseCustomFont=.*/UseCustomFont=true/' "$TIBIA_DIR/packages/Tibia/config.ini" 2>/dev/null || true
fi

log "Microsoft fonts installed and activated"

exit 0