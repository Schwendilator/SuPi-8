#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
set -e

TARBALL="$1"
APP_HOME="/opt/supi"
SYSTEMD_DIR="/etc/systemd/system"
LOCAL_BIN="/usr/local/bin"
TIMESTAMP=$(date +%y-%m-%d_%H-%M-%S)
TMPDIR=$(mktemp -d /tmp/supi-update-XXXXXX)

trap "rm -rf $TMPDIR" EXIT

if [ -z "$TARBALL" ] || [ ! -f "$TARBALL" ]; then
    echo "Usage: $0 <tarball>" >&2
    exit 1
fi

tar -xzf "$TARBALL" -C "$TMPDIR"

# Top-level directory prefix
cd "$TMPDIR"
if [ "$(ls -1 | wc -l)" -eq 1 ] && [ -d "$(ls -1)" ]; then
    cd "$(ls -1)"
fi

if [ ! -f "worker/supi-8.py" ]; then
    echo "ERROR: Archive must contain worker/supi-8.py" >&2
    exit 1
fi

# Backup
BACKUP_STAGE=$(mktemp -d /tmp/supi-backup-XXXXXX)
HAVE_BACKUP=0

if [ -d "$APP_HOME/worker" ]; then
    cp -r "$APP_HOME/worker" "$BACKUP_STAGE/worker"
    HAVE_BACKUP=1
fi
if [ -d "$APP_HOME/templates" ]; then
    cp -r "$APP_HOME/templates" "$BACKUP_STAGE/templates"
    HAVE_BACKUP=1
fi

mkdir -p "$BACKUP_STAGE/scripts"
shopt -s nullglob
for f in "$LOCAL_BIN"/*.sh; do
    cp "$f" "$BACKUP_STAGE/scripts/"
    HAVE_BACKUP=1
done

mkdir -p "$BACKUP_STAGE/services"
for f in "$SYSTEMD_DIR"/supi8*.service "$SYSTEMD_DIR"/usb-watchdog.service; do
    cp "$f" "$BACKUP_STAGE/services/"
    HAVE_BACKUP=1
done
shopt -u nullglob

if [ "$HAVE_BACKUP" -eq 1 ]; then
    tar -czf "$APP_HOME/backup-$TIMESTAMP.tar.gz" -C "$BACKUP_STAGE" .
    echo "Backup saved: $APP_HOME/backup-$TIMESTAMP.tar.gz"
fi
rm -rf "$BACKUP_STAGE"

# Install
if [ -d "worker" ]; then
    cp -r worker "$APP_HOME/"
fi
if [ -d "templates" ]; then
    cp -r templates "$APP_HOME/"
fi
chown -R supi:supi "$APP_HOME/worker" "$APP_HOME/templates" 2>/dev/null || true

if [ -d "services" ]; then
    cp services/*.service "$SYSTEMD_DIR/" 2>/dev/null || true
    systemctl daemon-reload
    echo "Services updated, daemon reloaded"
fi

if [ -d "scripts" ]; then
    cp scripts/*.sh "$LOCAL_BIN/" 2>/dev/null || true
    chmod +x "$LOCAL_BIN/"*.sh 2>/dev/null || true
    echo "Scripts updated"
fi

# Restart
sleep 1
systemctl restart supi-8.service

# Auto-rollback: if service fails within 10 seconds, restore backup
sleep 10
if ! systemctl is-active --quiet supi-8.service; then
    echo "Service failed to start, rolling back..."
    LATEST=$(ls -1t "$APP_HOME"/backup-*.tar.gz 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        ROLLBACK_STAGE=$(mktemp -d /tmp/supi-rollback-XXXXXX)
        tar -xzf "$LATEST" -C "$ROLLBACK_STAGE"

        [ -d "$ROLLBACK_STAGE/worker" ] && cp -r "$ROLLBACK_STAGE/worker" "$APP_HOME/"
        [ -d "$ROLLBACK_STAGE/templates" ] && cp -r "$ROLLBACK_STAGE/templates" "$APP_HOME/"
        chown -R supi:supi "$APP_HOME/worker" "$APP_HOME/templates" 2>/dev/null || true

        if [ -d "$ROLLBACK_STAGE/scripts" ]; then
            cp "$ROLLBACK_STAGE/scripts/"* "$LOCAL_BIN/" 2>/dev/null || true
            chmod +x "$LOCAL_BIN/"*.sh 2>/dev/null || true
        fi
        if [ -d "$ROLLBACK_STAGE/services" ]; then
            cp "$ROLLBACK_STAGE/services/"* "$SYSTEMD_DIR/" 2>/dev/null || true
            systemctl daemon-reload
        fi
        rm -rf "$ROLLBACK_STAGE"

        systemctl restart supi-8.service
        echo "Rolled back to $LATEST"
    else
        echo "No backup found, cannot roll back"
    fi
fi