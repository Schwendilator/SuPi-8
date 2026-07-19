# SuPi-8

A Raspberry Pi Zero 2W tucked inside a Super 8 cartridge — turns any Super 8 camera with a removable film gate into a digital film camera. Wi-Fi hotspot, web UI, motion-triggered recording.

## Hardware

- **Raspberry Pi Zero 2W**
- **Camera Module 3** (lens removed, sensor exposed)
- **2× WS2812b LEDs** on GPIO 10
- SD card ≥ 16 GB
- Super 8 Camera with removed Film Gate

The sensor sits at the film gate position where the film would normally run. A 3D-printed cartridge body (CAD files included — work in progress) holds everything.

## Quick Start

### 1. Flash the SD card

Flash **Raspberry Pi OS Lite (64-bit)** to an SD card (≥ 16 GB). **Before booting the Pi for the first time**, resize the root partition to 8 GB and create an exFAT partition for the remaining space. Use [GParted](https://gparted.org/) or any suitable partition editor:

1. Resize the rootfs partition to **8 GB**
2. Create a new **exFAT** partition in the unallocated space (label it `RECORDINGS`)
3. Apply changes and boot the Pi

### 2. Boot, clone, install

```bash
sudo apt install git
git clone https://github.com/your-org/SuPi-8.git
cd SuPi-8
sudo bash setup.sh
```

Set a hotspot password (or press Enter for `Classic!`). The installer does everything — partitions the SD card, installs dependencies, deploys the app, creates the hotspot. Reboot when prompted.

### 3. Connect

The Pi creates a Wi-Fi hotspot:

- **SSID:** `SuPi-8 <last 4 MAC chars>`
- **Password:** the one you chose
- **IP:** `10.42.0.1`

Open `http://10.42.0.1/` in a browser. You'll see the live preview, camera status, controls, and recordings.

It also works as a Wi-Fi client — if you connect it to your home network via the Setup page, it'll prefer that over the hotspot and auto-fallback if the connection drops.

## Recording

The camera fires at 18 fps by default (adjustable in the web UI). Recording starts automatically when the scene is bright enough; it stops when it gets dark. Raw footage is muxed to `.mp4` in the background. Files land on the exFAT data partition — pop the SD card into any computer to grab them.

## Web UI

**Dashboard** (`/`): Live preview with optional focus peaking overlay, brightness/gain/temp/focus readouts, controls for FPS, threshold, bitrate, white balance.

**Setup** (`/setup`): Connect to Wi-Fi, upload firmware updates, restore previous versions, factory reset.

## Updating

Package your changes into a `.tar.gz` and upload it via the Setup page:

```bash
tar -czf update.tar.gz worker/ templates/
```

The device backs up the current version, deploys yours, and restarts. If the new code crashes, it automatically rolls back. Manual restore is also available from the Setup page.

## The CAD Files

The `CAD/` and `KiCad/` directories contain the cartridge design — not finished yet, but the dimensions are correct for a Pi Zero 2W + Camera Module 3 (lens removed).

## License

**Software** (worker/, templates/, scripts/, services/) — [GNU General Public License v3.0](LICENSE)

**Hardware** (CAD/, KiCad/) — [CERN Open Hardware Licence Version 2 - Strongly Reciprocal](LICENSE_HARDWARE)
