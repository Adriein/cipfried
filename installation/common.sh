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
