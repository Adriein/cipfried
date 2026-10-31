#!/usr/bin/env bash

find_tibia_dir() {
    local data_home="${XDG_DATA_HOME:-$HOME/.local/share}"
    local candidates=(
        "$data_home/CipSoft GmbH/Tibia/packages/Tibia"
        "/opt/Tibia"
    )
    local candidate

    for candidate in "${candidates[@]}"; do
        if [[ -d "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}

find_tibia_tarball() {
    local explicit="${1:-}"
    local search_dirs=()
    local dir candidate

    if [[ -n "${TIBIA_TARBALL:-}" && -f "${TIBIA_TARBALL}" ]]; then
        echo "$TIBIA_TARBALL"
        return 0
    fi

    if [[ -n "$explicit" && -f "$explicit" ]]; then
        echo "$explicit"
        return 0
    fi

    if [[ -n "${XDG_DOWNLOAD_DIR:-}" && -d "${XDG_DOWNLOAD_DIR}" ]]; then
        search_dirs+=("$XDG_DOWNLOAD_DIR")
    fi

    if command -v xdg-user-dir >/dev/null 2>&1; then
        dir="$(xdg-user-dir DOWNLOAD 2>/dev/null || true)"
        if [[ -n "$dir" && -d "$dir" ]]; then
            search_dirs+=("$dir")
        fi
    fi

    if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
        dir="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
        if [[ -n "$dir" && -d "$dir/Downloads" ]]; then
            search_dirs+=("$dir/Downloads")
        fi
    fi

    if [[ -d "$HOME/Downloads" ]]; then
        search_dirs+=("$HOME/Downloads")
    fi

    for dir in /home/*/Downloads; do
        if [[ -d "$dir" ]]; then
            search_dirs+=("$dir")
        fi
    done

    for dir in "${search_dirs[@]}"; do
        candidate="$dir/tibia.x64.tar.gz"
        if [[ -f "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done

    for dir in "${search_dirs[@]}"; do
        candidate="$(find "$dir" -maxdepth 1 -type f -iname 'tibia*.tar.gz' -print -quit 2>/dev/null || true)"
        if [[ -n "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}

verify_sha256() {
    local file="$1"
    local expected="${2:-}"

    if [[ -z "$expected" ]]; then
        return 0
    fi

    if ! echo "$expected  $file" | sha256sum --check --status -; then
        echo "SHA-256 checksum verification failed for $file" >&2
        return 1
    fi
}
