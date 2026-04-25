#!/bin/bash

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "Plase run as root (sudo)." >&2
    exit 1
fi


DEVICE="/dev/mmcblk0p3"

apt update
DEBIAN_FRONTEND=noninteractive apt upgrade -y
DEBIAN_FRONTEND=noninteractive apt install -y iptables-persistent dnsmasq exfatprogs ffmpeg python3 python3-pip python3-flask python3-opencv
DEBIAN_FRONTEND=noninteractive apt install -y python3-picamera2 --no-install-recommends 
DEBIAN_FRONTEND=noninteractive pip3 install rpi-ws281x --break-system-packages

raspi-config nonint do_spi 0
sed -i 's/$/ spidev.bufsiz=32768/' /boot/firmware/cmdline.txt
echo "dtoverlay=dwc2,dr_mode=peripheral" >> /boot/firmware/config.txt
echo "core_freq=250" >> /boot/firmware/config.txt
echo "core_freq_min=250" >> /boot/firmware/config.txt
echo "blacklist snd_bcm2835" > /etc/modprobe.d/snd-blacklist.conf