#!/bin/bash

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Plase run as root (sudo)." >&2
    exit 1
fi


DEVICE="/dev/mmcblk0p3"

apt update
DEBIAN_FRONTEND=noninteractive apt upgrade -y
DEBIAN_FRONTEND=noninteractive apt install -y python3 iptables-persistent dnsmasq exfatprogs ffmpeg python3-flask python3-opencv
DEBIAN_FRONTEND=noninteractive apt install -y python3-picamera2 --no-install-recommends 


if ! grep -q "dtoverlay=dwc2,dr_mode=peripheral" /boot/firmware/config.txt; then
    echo "dtoverlay=dwc2,dr_mode=peripheral" >> /boot/firmware/config.txt
fi
