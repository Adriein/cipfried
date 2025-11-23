#!/usr/bin/env bash
# =============================================================================
# Tibia post installer
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

# ----------------------------------------------------------------------
# 1. Install minimap
# ----------------------------------------------------------------------
log "Installing minimap from tibiamaps.io..."
if [[ -f "./maps.sh" ]]; then
    bash "./maps.sh" --no-markers
    log "Minimap with no markers installed"
else
    warn "maps.sh not found in current directory – skipping minimap"
    warn "Download it separately: https://tibiamaps.io"
fi

# ----------------------------------------------------------------------
# 2. Install fonts
# ----------------------------------------------------------------------
log "Installing fonts..."
if [[ -f "./fonts.sh" ]]; then
    bash "./fonts.sh"
    log "Fonts installed"
else
    warn "fonts.sh not found in current directory – skipping fonts"
fi

exit 0