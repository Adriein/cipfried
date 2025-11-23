#!/usr/bin/env bash
# =============================================================================
# Tibia Minimap Downloader
# Author: aclaret
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[MAPS]${NC} $*" ; }
warn() { echo -e "${YELLOW}[MAPS] WARN:${NC} $*" ; }
error() { echo -e "${RED}[MAPS] ERROR:${NC} $*" >&2 ; }

# ----------------------------------------------------------------------
# Auto-detect Tibia data directory (supports /opt and user-local installs)
# ----------------------------------------------------------------------
find_tibia_dir() {
    # 1. Official /opt install (our bot farm standard)
    if [[ -d "/opt/Tibia/packages/Tibia" ]]; then
        echo "/opt/Tibia/packages/Tibia"
        return 0
    fi

    # 2. User-local install (XDG standard)
    local xdg="${XDG_DATA_HOME:-"${HOME}/.local/share"}/CipSoft GmbH/Tibia/packages/Tibia"
    if [[ -d "$xdg" ]]; then
        echo "$xdg"
        return 0
    fi

    # 3. Fallback: search common locations
    local candidates=(
        "$HOME/.local/share/CipSoft GmbH/Tibia/packages/Tibia"
        "$HOME/Tibia/packages/Tibia"
        "/usr/local/Tibia/packages/Tibia"
    )
    for dir in "${candidates[@]}"; do
        [[ -d "$dir" ]] && echo "$dir" && return 0
    done

    error "Tibia client not found! Install it first with install-tibia.sh"
    exit 1
}

TIBIA_DIR="$(find_tibia_dir)"
log "Using Tibia data directory: $TIBIA_DIR"

mkdir -p "$TIBIA_DIR"

# ----------------------------------------------------------------------
# Map selection
# ----------------------------------------------------------------------

case "${1}" in
	--grid)
		URL='https://tibiamaps.io/downloads/minimap-with-grid-overlay-and-markers';
		NAME="grid + markers";
		;;
	--grid-no-markers)
		URL='https://tibiamaps.io/downloads/minimap-with-grid-overlay-without-markers';
		NAME="grid only";
		;;
	--no-markers)
		URL='https://tibiamaps.io/downloads/minimap-without-markers';
		NAME="clean";
		;;
	--grid-poi-markers)
		URL='https://tibiamaps.io/downloads/minimap-with-grid-overlay-and-poi-markers';
		NAME="grid + POI";
		;;
	*)
		URL='https://tibiamaps.io/downloads/minimap-with-markers';
		NAME="default (markers)";
		;;
esac;

log "Downloading minimap: $NAME…"

ZIP_FILE="$(mktemp -t tibia-maps-XXXXXX.zip)"
trap 'rm -f "$ZIP_FILE"' EXIT

if ! curl --fail --silent --show-error --location --progress-bar "$URL" -o "$ZIP_FILE"; then
    error "Download failed. Check internet or tibiamaps.io status."
    exit 1
fi

log "Extracting $(du -h "$ZIP_FILE" | cut -f1) to $TIBIA_DIR…"
unzip -o -q "$ZIP_FILE" -d "$TIBIA_DIR" || {
    error "Failed to extract ZIP. Corrupted download?"
    exit 1
}

log "Minimap installed successfully! ($NAME)"
exit 0