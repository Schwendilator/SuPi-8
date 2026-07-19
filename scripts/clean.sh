#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root (sudo)." >&2
    exit 1
fi

echo "Cleaning previous SuPi-8 installation..."

# Stop and disable service
systemctl stop supi-8.service 2>/dev/null || true
systemctl disable supi-8.service 2>/dev/null || true
systemctl stop usb-watchdog.service 2>/dev/null || true
systemctl disable usb-watchdog.service 2>/dev/null || true

# Remove app directory
rm -rf /opt/supi

# Remove scripts installed to /usr/local/bin/
rm -f /usr/local/bin/apply-update.sh
rm -f /usr/local/bin/usb-off.sh
rm -f /usr/local/bin/usb-on.sh
rm -f /usr/local/bin/usb-watchdog.sh

# Remove systemd service files
rm -f /etc/systemd/system/supi-8.service
rm -f /etc/systemd/system/usb-watchdog.service

# Remove NetworkManager dispatcher
rm -f /etc/NetworkManager/dispatcher.d/50-supi8-wifi

# Remove sudoers config
rm -f /etc/sudoers.d/supi

# Remove dnsmasq config
rm -f /etc/dnsmasq.conf

# Remove NetworkManager hotspot and client connections
nmcli connection delete supi-8-hotspot 2>/dev/null || true
# Delete all wifi connections (user Wi-Fi networks)
for conn in $(nmcli -t -f NAME,TYPE connection show 2>/dev/null | grep ':wifi$' | cut -d: -f1); do
    nmcli connection delete "$conn" 2>/dev/null || true
done

# Delete supi user and group
if id -u supi >/dev/null 2>&1; then
    userdel -r supi 2>/dev/null || true
fi
if getent group supi >/dev/null 2>&1; then
    groupdel supi 2>/dev/null || true
fi

systemctl daemon-reload

echo "Cleanup done."
