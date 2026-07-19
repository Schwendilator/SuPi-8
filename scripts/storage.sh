#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Plase run as root (sudo)." >&2
    exit 1
fi

PART_DATA="/dev/mmcblk0p3"
MOUNTPOINT="/mnt/recordings"

echo "Starting storage setup"

if blkid "$PART_DATA" | grep -q "exfat"; then
    echo "Partition $PART_DATA with exFAT found."
else
    echo "Error: No exFAT partition at $PART_DATA."
    echo "See README.md — resize root to 8 GB and create exFAT partition before first boot."
    exit 1
fi

mkdir -p "$MOUNTPOINT"
chmod 777 "$MOUNTPOINT"

UUID=$(blkid -o value -s UUID "$PART_DATA")

grep -q "configfs" /etc/fstab || echo "configfs /sys/kernel/config configfs defaults 0 0" >> /etc/fstab

if ! grep -q "$UUID" /etc/fstab; then
    echo "UUID=$UUID $MOUNTPOINT exfat defaults,nofail,noatime,umask=0000 0 0" >> /etc/fstab
fi

systemctl daemon-reload
mount -a

echo "Storage setup done"
