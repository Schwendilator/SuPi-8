#!/bin/bash
set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Plase run as root (sudo)." >&2
    exit 1
fi

DISK="/dev/mmcblk0"
PART_ROOT="${DISK}p2"
PART_DATA="${DISK}p3"
MOUNTPOINT="/mnt/recordings"

echo "Starting storage setup"


if blkid "$PART_DATA" | grep -q "exfat"; then
    echo "Partition $PART_DATA with exFAT already exists. Nothing to do."
    mkdir -p "$MOUNTPOINT"
    mount -a
    echo "Storage setup skipped (already done)."
    exit 0
fi


DISK_SIZE_BYTES=$(blockdev --getsize64 "$DISK")
MIN_SIZE_BYTES=$((10 * 1024 * 1024 * 1024)) # 10 GB in Bytes

if [ "$DISK_SIZE_BYTES" -lt "$MIN_SIZE_BYTES" ]; then
    echo "Error: SD card is too small ($(($(($DISK_SIZE_BYTES / 1024)) / 1024)) MB)."
    echo "Minimum 10 GB required to create 8 GB Root + exFAT."
    exit 1
fi

CURRENT_ROOT_END=$(parted -s "$DISK" unit MB print | grep "^ 2" | awk '{print $3}' | tr -d 'MB' | cut -d. -f1)

if [ "$CURRENT_ROOT_END" -gt 8192 ]; then
    echo "Error: Root partition is already larger than 8.5 GB ($CURRENT_ROOT_END MB)."
    echo "Automatic expansion was probably not disabled in cmdline.txt."
    exit 1
fi


echo "Yes" | parted ---pretend-input-tty "$DISK" resizepart 2 8192MB

parted -s "$DISK" mkpart primary "" 8192MB 100%

partprobe "$DISK"
sleep 2

resize2fs "$PART_ROOT"

mkfs.exfat -n "RECORDINGS" "$PART_DATA"

mkdir -p "$MOUNTPOINT"
UUID=$(blkid -o value -s UUID "$PART_DATA")



grep -q "configfs" /etc/fstab || echo "configfs /sys/kernel/config configfs defaults 0 0" >> /etc/fstab

if ! grep -q "$UUID" /etc/fstab; then
    echo "UUID=$UUID $MOUNTPOINT exfat defaults,nofail,noatime,umask=0000 0 0" >> /etc/fstab
fi

systemctl daemon-reload
mount -a

echo "Storage setup done"
