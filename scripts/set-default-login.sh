#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root (sudo)." >&2
    exit 1
fi

STAMP="/boot/firmware/supi8-login-done"
USERNAME="pi"
PASSWORD="Classic!"

if [ -f "$STAMP" ]; then
    echo "Default login already set, skipping."
    exit 0
fi

if ! id "$USERNAME" &>/dev/null; then
    useradd -m -s /bin/bash "$USERNAME"
    usermod -aG sudo,video,render,gpio,spi,i2c,netdev "$USERNAME" 2>/dev/null || true
fi

echo "${USERNAME}:${PASSWORD}" | chpasswd

touch "$STAMP"
echo "SuPi-8: default login set (${USERNAME} / ${PASSWORD})"
