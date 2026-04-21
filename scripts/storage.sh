#!/bin/bash
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root (sudo)." >&2
    exit 1
fi

DEVICE="/dev/mmcblk0p3"
MOUNTPOINT="/mnt/recordings"

echo "== Storage Setup =="

grep -q configfs /etc/fstab || \
echo "configfs /sys/kernel/config configfs defaults 0 0" >> /etc/fstab

mount -a


if [ ! -b "$DEVICE" ]; then
    echo "Error: $DEVICE doesn't exist!"
    exit 1
fi

if ! blkid "$DEVICE" >/dev/null 2>&1; then
    echo "Formatting $DEVICE as exFAT..."
    mkfs.exfat "$DEVICE"
else
    echo "Filesystem already exists"
fi

mkdir -p "$MOUNTPOINT"

UUID=$(blkid -o value -s UUID "$DEVICE")

if [ -z "$UUID" ]; then
    echo "Error: UUID could not be determined!"
    exit 1
fi

grep -q "$UUID" /etc/fstab || \
echo "UUID=$UUID $MOUNTPOINT exfat defaults,nofail,noatime,umask=0000 0 0" >> /etc/fstab


systemctl daemon-reload
mount -a || true