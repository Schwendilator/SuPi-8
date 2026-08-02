#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only

set -e
 
if [ "$(id -u)" -ne 0 ]; then
    echo "Please run as root (sudo)." >&2
    exit 1
fi
 
STAMP="/boot/firmware/supi-8-storage-done"
DEVICE="/dev/mmcblk0"
ROOT_PART="2"
ROOT_DEV="${DEVICE}p${ROOT_PART}"
DATA_PART="3"
DATA_DEV="${DEVICE}p${DATA_PART}"
MOUNTPOINT="/mnt/recordings"
LABEL="Recordings"
ROOT_TARGET_SECTORS=$((8 * 1024 * 1024 * 1024 / 512))   # 8 GB in 512-byte sectors
 
if [ -f "$STAMP" ]; then
    echo "Storage already expanded, skipping."
    exit 0
fi
 
if [ ! -b "$ROOT_DEV" ] || [ ! -b "$DATA_DEV" ]; then
    echo "Error: expected partitions not found." >&2
    exit 1
fi
 
echo "SuPi-8: preparing storage..."
umount "$MOUNTPOINT" 2>/dev/null || true
umount "$DATA_DEV" 2>/dev/null || true
 
parted -s "$DEVICE" rm "$DATA_PART"
partprobe "$DEVICE"
udevadm settle
 
echo "SuPi-8: growing root partition to 8 GB..."
ROOT_START=$(parted -ms "$DEVICE" unit s print | awk -F: -v p="$ROOT_PART" '$1==p {gsub("s","",$2); print $2}')
ROOT_END=$((ROOT_START + ROOT_TARGET_SECTORS - 1))
DISK_SECTORS=$(blockdev --getsz "$DEVICE")
 
if [ "$ROOT_END" -ge "$((DISK_SECTORS - 1))" ]; then
    echo "Error: card too small to grow root to 8 GB and still have room for data storage." >&2
    exit 1
fi
 
parted -s "$DEVICE" resizepart "$ROOT_PART" "${ROOT_END}s"
partprobe "$DEVICE"
udevadm settle
resize2fs "$ROOT_DEV"
 
echo "SuPi-8: creating data partition with the rest of the card..."
parted -s "$DEVICE" mkpart primary "$((ROOT_END + 1))s" 100%
partprobe "$DEVICE"
udevadm settle
mkfs.exfat -n "$LABEL" "$DATA_DEV"
 
mkdir -p "$MOUNTPOINT"
chmod 777 "$MOUNTPOINT"
 
sed -i "\|[[:space:]]$MOUNTPOINT[[:space:]]|d" /etc/fstab
grep -q "configfs" /etc/fstab || echo "configfs /sys/kernel/config configfs defaults 0 0" >> /etc/fstab
echo "LABEL=$LABEL $MOUNTPOINT exfat defaults,nofail,noatime,umask=0000 0 0" >> /etc/fstab
 
systemctl daemon-reload
mount -a
 
touch "$STAMP"
echo "SuPi-8: root grown to 8 GB, data partition mounted at $MOUNTPOINT"