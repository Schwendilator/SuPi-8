#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Plase run as root (sudo)." >&2
    exit 1
fi

REPO_DIR="${1:-$(pwd)}"


cp "$REPO_DIR/scripts/"*.sh /usr/local/bin/
chmod +x /usr/local/bin/*.sh

cp "$REPO_DIR/services/"*.service /etc/systemd/system/
cp "$REPO_DIR/services/"*.path /etc/systemd/system/ 2>/dev/null || true

systemctl daemon-reload

systemctl enable supi-8.service
systemctl enable supi-8-storage.service
systemctl enable supi-8-login.service
# systemctl enable usb-watchdog.service -> currently quite buggy