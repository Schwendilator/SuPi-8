#!/bin/bash
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
BACKUP_DIRS=""
[ -d "worker" ]    && BACKUP_DIRS="$BACKUP_DIRS worker"
[ -d "templates" ] && BACKUP_DIRS="$BACKUP_DIRS templates"

if [ -n "$BACKUP_DIRS" ]; then
    tar -czf "$APP_HOME/backup-$TIMESTAMP.tar.gz" -C "$APP_HOME" $BACKUP_DIRS
    echo "Backup saved: $APP_HOME/backup-$TIMESTAMP.tar.gz"
fi

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
        tar -xzf "$LATEST" -C "$APP_HOME"
        chown -R supi:supi "$APP_HOME/worker" "$APP_HOME/templates" 2>/dev/null || true
        systemctl restart supi-8.service
        echo "Rolled back to $LATEST"
    else
        echo "No backup found, cannot roll back"
    fi
fi
