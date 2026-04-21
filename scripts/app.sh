#!/bin/bash

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Plase run as root (sudo)." >&2
    exit 1
fi

APP_USER="supi"
APP_HOME="/opt/supi"
REPO_DIR="${1:-$(pwd)}"

if ! id -u "$APP_USER" >/dev/null 2>&1; then
    useradd -r -m -d "$APP_HOME" -s /usr/sbin/nologin "$APP_USER"
fi

if id -u "$APP_USER" >/dev/null 2>&1; then
    usermod -a -G video,render "$APP_USER"
fi

install -d -o "$APP_USER" -g "$APP_USER" "$APP_HOME"

test -f "$REPO_DIR/worker/supi-8-recorder.py" || {
    echo "ERROR: supi-8-recorder.py not found in $REPO_DIR/worker"
    exit 1
}

cp -r "$REPO_DIR/worker" "$APP_HOME/"
cp -r "$REPO_DIR/templates" "$APP_HOME/"
chown -R "$APP_USER:$APP_USER" "$APP_HOME"
chmod +x "$APP_HOME/worker/supi-8-recorder.py"