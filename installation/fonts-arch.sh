#!/usr/bin/env bash
# =============================================================================
# Tibia fonts installer (Arch Linux)
# Author: aclaret
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[FONTS]${NC} $*" ; }
warn() { echo -e "${YELLOW}[FONTS] WARN:${NC} $*" ; }
error() { echo -e "${RED}[FONTS] ERROR:${NC} $*" >&2 ; }

# AUR helpers refuse to run as root. Re-exec as the invoking user if possible,
# since fonts and the Tibia config live in that user's home.
if [[ "${EUID}" -eq 0 ]]; then
    if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
        warn "Running as root – re-executing as $SUDO_USER"
        exec sudo -u "$SUDO_USER" -H bash "${BASH_SOURCE[0]}" "$@"
    fi
    error "Run this script as your normal user, not as root."
    exit 1
fi

if ! TIBIA_DIR="$(find_tibia_dir)"; then
    error "Tibia client not found! Install it first with tibia-arch.sh"
    exit 1
fi

log "Using Tibia data directory: $TIBIA_DIR"

# ----------------------------------------------------------------------
# 1. Install Microsoft Core Fonts (AUR)
# ----------------------------------------------------------------------
log "Installing Microsoft Core Fonts (Tahoma, Arial, Verdana...) for correct text rendering..."

AUR_HELPER=""
for helper in yay paru; do
    if command -v "$helper" >/dev/null 2>&1; then
        AUR_HELPER="$helper"
        break
    fi
done

if [[ -z "$AUR_HELPER" ]]; then
    error "No AUR helper found (yay or paru)."
    error "Install one, then run: yay -S ttf-mscorefonts-installer"
    exit 1
fi

log "Using $AUR_HELPER to install ttf-mscorefonts-installer..."
if ! "$AUR_HELPER" -S --needed --noconfirm ttf-mscorefonts-installer; then
    error "Failed to install ttf-mscorefonts-installer via $AUR_HELPER."
    error "Try manually: $AUR_HELPER -S ttf-mscorefonts-installer"
    exit 1
fi

# Final step: Update font cache (critical!)
log "Updating font cache..."
fc-cache -f >/dev/null 2>&1 || log "fc-cache failed (non-fatal) - fonts should still work"

# Force Tibia to re-read fonts on next launch
CONFIG_FILE="$TIBIA_DIR/config.ini"
if [[ -f "$CONFIG_FILE" ]]; then
    sed -i 's/FontName=.*/FontName=Tahoma/' "$CONFIG_FILE" 2>/dev/null || true
    sed -i 's/UseCustomFont=.*/UseCustomFont=true/' "$CONFIG_FILE" 2>/dev/null || true
fi

log "Microsoft fonts installed and activated"

exit 0
