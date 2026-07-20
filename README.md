# SuPi-8

A Raspberry Pi Zero 2W tucked inside a Super 8 cartridge — turns any Super 8 camera with a removable film gate into a digital film camera. Wi-Fi hotspot, web UI, motion-triggered recording.
The sensor sits at the film gate position where the film would normally run. A 3D-printed cartridge body (CAD files included — work in progress) holds everything.

## Hardware

**Electronics**

- **Raspberry Pi Zero 2W**
- **Camera Module 3** (lens removed)
- **Arducam B0439** 200 mm sensor extension cable
- **2× WS2812b LED modules**
- **18650 Li-ion battery**, with U-shaped solder tabs
- **JST connector + socket**
- **MH-CD42**
- **USB-C socket**
- SD card ≥ 16 GB
- Super 8 Camera with removed Film Gate

**Mechanical / fasteners**

- 1× compression spring, 1 × 6 × 20 mm (DIN 2095)
- 1× M3 threaded rod, 70 mm
- 1× M3 nut
- 2x M3 washer (DIN 125)
- 1× M3 knurled nut, high form (DIN 466)
- 3× M2.5×4 threaded inserts
- 1× M3×6 threaded insert
- 4× M2×3 threaded inserts
- 4× M2×6 screws (DIN 912)
- 1× M2.5×6 screw (DIN 912)
- 2× M2.5×12 screws (DIN 7991)

**Tools / consumables**

- Soldering iron + a bit of wire
- Thin enameled copper wire (magnet wire)
- Sharp thin blade (scalpel or razor blade)
- Insulation tape
- A 3D-Printer and a bit of filament
- Glue

## Preparation

Before assembly, the lens has to be removed from the Camera Module 3 so the bare sensor sits flush at the film gate.

1. Gently warm the lens holder (e.g. with a hot air gun on low, or a hairdryer) — this softens the adhesive holding the lens assembly to the sensor board.
2. While warm, carefully work a sharp, thin blade (scalpel or razor blade) under the edge of the lens holder and slowly pry it loose. Go slowly and reheat if it resists — the sensor underneath is fragile and easily scratched or cracked.
3. Once removed, keep the sensor covered/protected until it's mounted in the cartridge to avoid dust on the die.

## Assembly

### 1. Print the case

Print the cartridge housing — ideally in a filament with some heat resistance (e.g. ABS/ASA/PETG), since it sits close to a working camera.

### 2. Wire the electronics

Easiest done on the bench before anything goes into the case:

1. Solder a JST cable to the battery.
2. Solder a matching JST socket to the MH-CD42, along with wires for VIN (5V in) and OUT + GND (5V out).
3. Solder the VIN wires to the USB-C socket (this is the charging input).
4. Solder the OUT and GND wires to the Pi's 5V/GND header pins (physical pin 4 = 5V, pin 6 = GND) — this powers the Pi directly through the GPIO header instead of its own USB port.
5. Solder wires for the LEDs to 5V (physical pin 2) and GND, plus a data wire to GPIO10 (physical pin 19).
6. Chain the two LED modules together. Thin enameled copper wire (magnet wire) is recommended here.
7. Solder the wires from step 5 onto the first LED module.
8. Glue both LED modules into the lid and cover the solder joints with insulation tape.

### 3. Prepare the housing

Press in the threaded inserts: 4× M2 for the Camera Module 3 board, 3× M2.5 for the Pi, and 1× M3 into the sensor holder.

### 4. Build the sensor/focus assembly

1. Screw the M3 threaded rod into the sensor holder and lock it with a M3 nut and a washer, then slide the spring onto the rod.
2. **Carefully** glue the bare sensor onto the sensor holder and connect it with the Arducam extension cable.
3. Connect the ribbon cable and the Arducam B0439 extension cable to the Camera Module 3 board.
4. Screw the Camera Module board down with the 4× M2×6 screws, with the Arducam connector facing down.

### 5. Final assembly

1. Put the washer through the slot, slide the sensor holder (with rod and spring) into the housing and lock it in place with the knurled nut.
2. Glue the USB-C socket into position.
3. Glue the MH-CD42 charging board into position.
4. Glue the battery into position.
5. Fold the Raspberry Pi camera cable so it fits inside the housing and connect it to the Pi.
6. Screw the Pi down with the single M2.5 (DIN 912) screw in the center mounting hole.
7. Plug the battery's JST connector into the MH-CD42.
8. Close the lid and screw it shut.

## Quick Start

### Option A: Flash the pre-built image (recommended)

The easiest way to get started — no manual partitioning, no dependency installs.

1. Download the latest `supi8-*.img.xz` from the [Releases](../../releases) page.
2. Flash it to an SD card (≥ 16 GB) with [Raspberry Pi Imager](https://www.raspberrypi.com/software/), [balenaEtcher](https://etcher.balena.io/), or `dd`.
3. Insert the card and boot the Pi.

On first boot, SuPi-8 automatically grows and formats the data partition to use all the free space on your card — however big it is — so there's nothing to prepare manually. This takes a few seconds and only happens once; after that it boots straight into the hotspot.

Then jump to [Connect](#connect) below.

### Option B: Build from source

For developers, or if you want to build your own image from scratch.

#### 1. Flash the SD card

Flash **Raspberry Pi OS Lite (64-bit)** to an SD card (≥ 16 GB). **Before booting the Pi for the first time**, resize the root partition to 8 GB and create an exFAT partition for the remaining space. Use [GParted](https://gparted.org/) or any suitable partition editor:

1. Resize the rootfs partition to **8 GB**
2. Create a new **exFAT** partition in the unallocated space (label it `RECORDINGS`)
3. Apply changes and boot the Pi

#### 2. Boot, clone, install

```bash
sudo apt install git
git clone https://github.com/Schwendilator/SuPi-8.git
cd SuPi-8
sudo bash setup.sh
```

Set a hotspot password (or press Enter for `Classic!`). The installer does everything — partitions the SD card, installs dependencies, deploys the app, creates the hotspot. Reboot when prompted.

### Connect

The Pi creates a Wi-Fi hotspot:

- **SSID:** `SuPi-8 <last 4 MAC chars>`
- **Password:** the one you chose (or `Classic!` if you flashed the pre-built image)
- **IP:** `10.42.0.1`

Open `http://10.42.0.1/` in a browser. You'll see the live preview, camera status, controls, and recordings.

It also works as a Wi-Fi client — if you connect it to your home network via the Setup page, it'll prefer that over the hotspot and auto-fallback if the connection drops.

## Recording

The camera fires at 18 fps by default (adjustable in the web UI). Recording starts automatically when the scene is bright enough; it stops when it gets dark. Raw footage is muxed to `.mp4` in the background. Files land on the exFAT data partition — pop the SD card into any computer to grab them.

## Web UI

**Dashboard:** Live preview with optional focus peaking overlay, brightness/gain/temp/focus readouts, controls for FPS, threshold, bitrate, white balance.

**Setup:** Connect to Wi-Fi, upload firmware updates, restore previous versions, factory reset.

Vibe Coded with Claude, because I don't like doning frontends.


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