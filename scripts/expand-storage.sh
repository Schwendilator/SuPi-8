#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root (sudo)." >&2
    exit 1
fi

STAMP="/boot/firmware/supi-8-storage-done"
DEVICE="/dev/mmcblk0"
PART_NUM="3"
PART_DEV="${DEVICE}p${PART_NUM}"
MOUNTPOINT="/mnt/recordings"
LABEL="RECORDINGS"

if [ -f "$STAMP" ]; then
    echo "Storage already expanded, skipping."
    exit 0
fi

if [ ! -b "$PART_DEV" ]; then
    echo "Error: $PART_DEV not found, nothing to expand." >&2
    exit 1
fi

echo "SuPi-8: expanding data partition to fill the SD card"

umount "$MOUNTPOINT" 2>/dev/null || true
umount "$PART_DEV" 2>/dev/null || true

parted -s "$DEVICE" resizepart "$PART_NUM" 100%
partprobe "$DEVICE"
udevadm settle

mkfs.exfat -F -n "$LABEL" "$PART_DEV"

mkdir -p "$MOUNTPOINT"
chmod 777 "$MOUNTPOINT"

UUID=$(blkid -o value -s UUID "$PART_DEV")

sed -i "\|[[:space:]]$MOUNTPOINT[[:space:]]|d" /etc/fstab
grep -q "configfs" /etc/fstab || echo "configfs /sys/kernel/config configfs defaults 0 0" >> /etc/fstab
echo "UUID=$UUID $MOUNTPOINT exfat defaults,nofail,noatime,umask=0000 0 0" >> /etc/fstab

systemctl daemon-reload
mount -a

touch "$STAMP"
echo "SuPi-8: storage expanded and mounted at $MOUNTPOINT"