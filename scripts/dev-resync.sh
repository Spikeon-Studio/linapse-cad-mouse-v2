#!/bin/bash
# Keep a local dev checkout's *installed* copies in sync with the repo.
#
# install.sh copies service/ into ~/.local/bin and renders the configurator's
# systemd unit + desktop launcher from templates (filling in the absolute repo
# path). None of that re-runs on `git pull` — so a checkout can silently drift
# from what's actually running. That drift has caused two real bugs on dev
# machines: a home-directory rename left stale absolute paths in the installed
# systemd unit and desktop file, and ~/.local/bin/linapse-service sat months
# behind the repo, still running code with a fixed phantom-gamepad bug.
#
# This script is idempotent and safe to re-run any time: it only touches files
# that actually differ, and only restarts a service if its files changed.
# Run manually with `scripts/dev-resync.sh`, or install the git hook below to
# run it automatically after every pull/checkout on this machine:
#
#   git config core.hooksPath .githooks
#
# See "Local dev hooks" in service/README.md.
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_BIN="$HOME/.local/bin"
SYSTEMD_USER="$HOME/.config/systemd/user"
DESKTOP_DIR="$HOME/.local/share/applications"

changed=0

info() { echo "  $*"; }

sync_file() {
    # sync_file <src> <dst>
    if [ ! -f "$2" ] || ! cmp -s "$1" "$2"; then
        mkdir -p "$(dirname "$2")"
        cp -f "$1" "$2"
        changed=1
        info "updated: $2"
    fi
}

sync_dir() {
    # sync_dir <src dir> <dst dir>
    if [ ! -d "$2" ] || ! diff -rq --exclude=__pycache__ "$1" "$2" >/dev/null 2>&1; then
        rsync -a --delete --exclude '__pycache__' "$1/" "$2/"
        changed=1
        info "updated: $2/"
    fi
}

# ── linapse-service ──────────────────────────────────────────────────────────
if [ -f "$USER_BIN/linapse-service" ]; then
    echo "==> Resyncing installed linapse-service"
    svc_changed=0
    before=$changed
    sync_file "$REPO_DIR/service/linapse-service" "$USER_BIN/linapse-service"
    chmod +x "$USER_BIN/linapse-service"
    sync_dir  "$REPO_DIR/service/linapse" "$USER_BIN/linapse"
    sync_dir  "$REPO_DIR/service/spacenav_ws" "$USER_BIN/spacenav_ws"
    sync_file "$REPO_DIR/service/linapse-ws-proxy" "$USER_BIN/linapse-ws-proxy"
    chmod +x "$USER_BIN/linapse-ws-proxy" 2>/dev/null || true
    [ "$changed" != "$before" ] && svc_changed=1

    if [ "$svc_changed" = "1" ] && systemctl --user is-active --quiet linapse-service 2>/dev/null; then
        info "restarting linapse-service..."
        systemctl --user restart linapse-service
    fi
else
    echo "==> linapse-service not installed here; skipping (run service/install.sh first)"
fi

# ── configurator systemd unit (path/port baked in at install time) ─────────
if [ -f "$SYSTEMD_USER/linapse-configurator.service" ]; then
    PORT=$(grep -oP '(?<=http\.server )[0-9]+' "$SYSTEMD_USER/linapse-configurator.service" 2>/dev/null | head -1)
    PORT="${PORT:-7890}"
    tmp="$(mktemp)"
    sed -e "s|__CONFIGURATOR_DIR__|$REPO_DIR/configurator|g" -e "s|__PORT__|$PORT|g" \
        "$REPO_DIR/service/systemd/linapse-configurator.service" > "$tmp"
    if ! cmp -s "$tmp" "$SYSTEMD_USER/linapse-configurator.service"; then
        cp -f "$tmp" "$SYSTEMD_USER/linapse-configurator.service"
        changed=1
        info "updated: $SYSTEMD_USER/linapse-configurator.service"
        systemctl --user daemon-reload
        systemctl --user restart linapse-configurator 2>/dev/null || true
    fi
    rm -f "$tmp"
fi

# ── configurator desktop launcher (repo path baked in at install time) ─────
if [ -f "$DESKTOP_DIR/linapse-configurator.desktop" ]; then
    tmp="$(mktemp)"
    sed -e "s|__REPO_DIR__|$REPO_DIR|g" \
        "$REPO_DIR/service/systemd/linapse-configurator.desktop" > "$tmp"
    if ! cmp -s "$tmp" "$DESKTOP_DIR/linapse-configurator.desktop"; then
        cp -f "$tmp" "$DESKTOP_DIR/linapse-configurator.desktop"
        chmod +x "$DESKTOP_DIR/linapse-configurator.desktop"
        changed=1
        info "updated: $DESKTOP_DIR/linapse-configurator.desktop"
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi
    rm -f "$tmp"
fi

[ "$changed" = "0" ] && echo "==> Already up to date."
exit 0
