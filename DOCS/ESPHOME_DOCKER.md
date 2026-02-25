# Flashing `example.yaml` with ESPHome on Docker

This guide explains how to compile and flash `example.yaml` to an ESP32 using
the official ESPHome Docker image — no local Python installation required.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed and running
- An ESP32 board connected via USB **or** already on your network (for OTA)
- The repository cloned locally

---

## 1. Create `secrets.yaml`

`example.yaml` references Wi-Fi credentials through ESPHome's secrets mechanism.
Create a `secrets.yaml` file in the **repository root** (next to `example.yaml`):

```yaml
wifi_ssid: "YourNetworkName"
wifi_password: "YourPassword"
```

> `secrets.yaml` is listed in `.gitignore` — it will not be committed.

---

## 2. Pull the ESPHome image

```bash
docker pull ghcr.io/esphome/esphome
```

All commands below mount the repository root into the container as `/config`:

```bash
# Run from the repository root
cd /path/to/Immergas-Modbus
```

---

## 3. Validate the configuration

Check the config for errors without compiling:

```bash
docker run --rm \
  -v "${PWD}:/config" \
  ghcr.io/esphome/esphome \
  config example.yaml
```

---

## 4. Compile only

Build the firmware binary without flashing:

```bash
docker run --rm \
  -v "${PWD}:/config" \
  ghcr.io/esphome/esphome \
  compile example.yaml
```

The compiled binary is written to `.esphome/build/immergas_hp/.pioenvs/immergas_hp/firmware.bin`.

---

## 5. Flash via USB (first-time)

Find the serial port your ESP32 is on:

```bash
# Linux
ls /dev/ttyUSB* /dev/ttyACM*

# macOS
ls /dev/cu.usbserial-* /dev/cu.SLAB_*
```

Pass the device into the container and run:

```bash
docker run --rm \
  -v "${PWD}:/config" \
  --device /dev/ttyUSB0 \
  ghcr.io/esphome/esphome \
  run example.yaml --device /dev/ttyUSB0
```

Replace `/dev/ttyUSB0` with your actual port.

> **Linux permission error?** Add your user to the `dialout` group:
> `sudo usermod -aG dialout $USER` (re-login required).

---

## 6. Update via OTA (subsequent flashes)

Once the device is on your network, skip the `--device` flag — ESPHome will
discover or prompt for the device address:

```bash
docker run --rm \
  -v "${PWD}:/config" \
  ghcr.io/esphome/esphome \
  run example.yaml
```

To target a specific IP address directly:

```bash
docker run --rm \
  -v "${PWD}:/config" \
  ghcr.io/esphome/esphome \
  run example.yaml --device 192.168.1.XX
```

---

## 7. Monitor serial logs

Stream live logs from a USB-connected device:

```bash
docker run --rm \
  -v "${PWD}:/config" \
  --device /dev/ttyUSB0 \
  ghcr.io/esphome/esphome \
  logs example.yaml --device /dev/ttyUSB0
```

Or stream logs over the network:

```bash
docker run --rm \
  -v "${PWD}:/config" \
  ghcr.io/esphome/esphome \
  logs example.yaml --device 192.168.1.XX
```

---

## 8. Using docker-compose (dashboard + persistent container)

A `docker-compose.yml` is provided in the repository root. It starts the
ESPHome dashboard on **http://localhost:6052** and keeps it running so you can
manage the device through the web UI.

```bash
# Start the dashboard (detached)
docker compose up -d

# Open http://localhost:6052 in your browser, then click "immergas_hp" to
# compile, flash, and view logs from the UI.

# Stop the dashboard
docker compose down
```

### One-shot commands via docker compose run

You can also use `docker compose run` to run single commands without starting
the long-running dashboard service:

```bash
# Validate
docker compose run --rm esphome config example.yaml

# Compile
docker compose run --rm esphome compile example.yaml

# Flash via OTA
docker compose run --rm esphome run example.yaml --device 192.168.1.XX

# Stream logs
docker compose run --rm esphome logs example.yaml --device 192.168.1.XX
```

### USB flashing with docker-compose

Uncomment the `devices` block in `docker-compose.yml` and set the correct port:

```yaml
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
```

Then flash with:

```bash
docker compose run --rm esphome run example.yaml --device /dev/ttyUSB0
```

---

## Quick-reference

| Goal | Command |
|---|---|
| Validate config | `docker run --rm -v "${PWD}:/config" ghcr.io/esphome/esphome config example.yaml` |
| Compile only | `docker run --rm -v "${PWD}:/config" ghcr.io/esphome/esphome compile example.yaml` |
| Flash via USB | add `--device /dev/ttyUSB0` and `run … --device /dev/ttyUSB0` |
| Flash via OTA | `run example.yaml --device <IP>` |
| Live logs (USB) | `logs example.yaml --device /dev/ttyUSB0` |
| Live logs (OTA) | `logs example.yaml --device <IP>` |
| Start dashboard | `docker compose up -d` → http://localhost:6052 |
| One-shot compile | `docker compose run --rm esphome compile example.yaml` |
