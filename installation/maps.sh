#!/usr/bin/env bash
# =============================================================================
# Tibia Minimap Downloader
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

log() { echo -e "${GREEN}[MAPS]${NC} $*" ; }
warn() { echo -e "${YELLOW}[MAPS] WARN:${NC} $*" ; }
error() { echo -e "${RED}[MAPS] ERROR:${NC} $*" >&2 ; }

if ! TIBIA_DIR="$(find_tibia_dir)"; then
    error "Tibia client not found! Install it first with tibia.sh"
    exit 1
fi

log "Using Tibia data directory: $TIBIA_DIR"

mkdir -p "$TIBIA_DIR"

# ----------------------------------------------------------------------
# Map selection
# ----------------------------------------------------------------------

case "${1:-}" in
	--grid)
		URL='https://tibiamaps.io/downloads/minimap-with-grid-overlay-and-markers'
		NAME="grid + markers"
		;;
	--grid-no-markers)
		URL='https://tibiamaps.io/downloads/minimap-with-grid-overlay-without-markers'
		NAME="grid only"
		;;
	--no-markers)
		URL='https://tibiamaps.io/downloads/minimap-without-markers'
		NAME="clean"
		;;
	--grid-poi-markers)
		URL='https://tibiamaps.io/downloads/minimap-with-grid-overlay-and-poi-markers'
		NAME="grid + POI"
		;;
	*)
		URL='https://tibiamaps.io/downloads/minimap-with-markers'
		NAME="default (markers)"
		;;
esac

log "Downloading minimap: $NAME…"

ZIP_FILE="$(mktemp -t tibia-maps-XXXXXX.zip)"
trap 'rm -f "$ZIP_FILE"' EXIT

if ! curl --fail --silent --show-error --location --progress-bar "$URL" -o "$ZIP_FILE"; then
    error "Download failed. Check internet or tibiamaps.io status."
    exit 1
fi

if [[ -n "${TIBIA_MAPS_SHA256:-}" ]]; then
    log "Verifying download checksum..."
    verify_sha256 "$ZIP_FILE" "$TIBIA_MAPS_SHA256" || {
        error "Checksum verification failed."
        exit 1
    }
fi

log "Extracting $(du -h "$ZIP_FILE" | cut -f1) to $TIBIA_DIR…"
unzip -o -q "$ZIP_FILE" -d "$TIBIA_DIR" || {
    error "Failed to extract ZIP. Corrupted download?"
    exit 1
}

log "Minimap installed successfully! ($NAME)"
exit 0