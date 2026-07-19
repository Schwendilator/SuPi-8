#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-only

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Plase run as root (sudo)." >&2
    exit 1
fi


DEVICE="/dev/mmcblk0p3"

apt update
DEBIAN_FRONTEND=noninteractive apt upgrade -y
DEBIAN_FRONTEND=noninteractive apt install -y iptables-persistent dnsmasq ffmpeg python3 python3-pip python3-flask python3-opencv exfatprogs
DEBIAN_FRONTEND=noninteractive apt install -y python3-picamera2 --no-install-recommends 
DEBIAN_FRONTEND=noninteractive pip3 install rpi-ws281x --break-system-packages --root-user-action=ignore

raspi-config nonint do_spi 0
sed -i 's/$/ spidev.bufsiz=32768/' /boot/firmware/cmdline.txt
echo "dtoverlay=dwc2,dr_mode=peripheral" >> /boot/firmware/config.txt
echo "core_freq=250" >> /boot/firmware/config.txt
echo "core_freq_min=250" >> /boot/firmware/config.txt
echo "blacklist snd_bcm2835" > /etc/modprobe.d/snd-blacklist.conf


echo "dtoverlay=disable-bt" >> /boot/firmware/config.txt
systemctl disable hciuart 2>/dev/null || true
systemctl disable bluetooth 2>/dev/null || true

echo "hdmi_blanking=2" >> /boot/firmware/config.txt