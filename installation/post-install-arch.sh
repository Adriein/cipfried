#!/usr/bin/env bash
# =============================================================================
# Tibia post installer (Arch Linux)
# Author: aclaret
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[POST-INSTALLER]${NC} $*" ; }
warn() { echo -e "${YELLOW}[POST-INSTALLER] WARN:${NC} $*" ; }
error() { echo -e "${RED}[POST-INSTALLER] ERROR:${NC} $*" >&2 ; }

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ----------------------------------------------------------------------
# 1. Install minimap
# ----------------------------------------------------------------------
log "Installing minimap from tibiamaps.io..."
if [[ -f "$SCRIPT_DIR/maps.sh" ]]; then
    bash "$SCRIPT_DIR/maps.sh" --no-markers
    log "Minimap with no markers installed"
else
    warn "maps.sh not found next to post-install-arch.sh – skipping minimap"
    warn "Download it separately: https://tibiamaps.io"
fi

# ----------------------------------------------------------------------
# 2. Install fonts
# ----------------------------------------------------------------------
log "Installing fonts..."
if [[ -f "$SCRIPT_DIR/fonts-arch.sh" ]]; then
    bash "$SCRIPT_DIR/fonts-arch.sh"
    log "Fonts installed"
else
    warn "fonts-arch.sh not found next to post-install-arch.sh – skipping fonts"
fi

exit 0
