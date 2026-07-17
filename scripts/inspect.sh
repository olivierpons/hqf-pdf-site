#!/usr/bin/env bash
# Run PyCharm's offline code inspector against the versioned project profile and
# write its XML report under .inspection/. The inspector locks the project's
# caches, so this refuses to start while a PyCharm window holds the project
# open: the two would clash and the run would be unreliable.
#
# Usage:  scripts/inspect.sh [output_dir]
# The IDE launcher is found through $PYCHARM_INSPECT, then a launcher on PATH,
# then the usual JetBrains Toolbox / standalone / snap locations.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
profile="$repo_root/.idea/inspectionProfiles/Project_Default.xml"
out_dir="${1:-$repo_root/.inspection}"

if pgrep -f 'PyCharm[0-9]{4}' >/dev/null 2>&1; then
    echo "PyCharm is open. Close it before running an offline inspection." >&2
    exit 1
fi

if [ ! -f "$profile" ]; then
    echo "Inspection profile not found: $profile" >&2
    exit 1
fi

find_inspector() {
    if [ -n "${PYCHARM_INSPECT:-}" ] && [ -x "$PYCHARM_INSPECT" ]; then
        printf '%s\n' "$PYCHARM_INSPECT"
        return 0
    fi
    launcher="$(command -v pycharm || command -v charm || true)"
    if [ -n "$launcher" ]; then
        candidate="$(dirname "$(readlink -f "$launcher")")/inspect.sh"
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    fi
    for candidate in \
        "$HOME/pycharm/bin/inspect.sh" \
        "$HOME"/.local/share/JetBrains/Toolbox/apps/pycharm*/bin/inspect.sh \
        /opt/pycharm*/bin/inspect.sh \
        /snap/pycharm-professional/current/bin/inspect.sh \
        /snap/pycharm-community/current/bin/inspect.sh; do
        if [ -x "$candidate" ]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

inspector="$(find_inspector)" || {
    echo "PyCharm inspector not found. Set PYCHARM_INSPECT to its inspect.sh." >&2
    exit 1
}

rm -rf "$out_dir"
mkdir -p "$out_dir"
"$inspector" "$repo_root" "$profile" "$out_dir" -v2
echo "Inspection report written to $out_dir"
