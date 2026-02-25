Immergas-Modbus
===============

ESPHome custom component that reads Immergas device registers over Modbus RTU (UART / RS-485).
Exposes PDUs as sensors, numbers, switches, selects and climate entities.

Project goals
-------------
- Centralize PDU/register metadata in `immergas_registers.json`.
- Generate a C++ header from that mapping to drive decoding/reads at runtime.
- Implement a simple Modbus RTU client (CRC, read/write) and safe wiring for entity writes.

Prerequisites
-------------
- [Docker](https://docs.docker.com/get-docker/) and Docker Compose v2
- The Dominus JSON files (`CFG-WFC01_IM_MBUS.json`, `LBL-WFC01_IM_MBUS.json`) placed in a
  `dominus/` folder **next to** (sibling of) this repository — only needed to re-extract registers

Quick start with Docker Compose
--------------------------------

### 1. Create `secrets.yaml`

Copy your Wi-Fi credentials into a file at the repository root (it is git-ignored):

```yaml
# secrets.yaml
wifi_ssid: "YourNetworkName"
wifi_password: "YourPassword"
api_encryption_key: "your-32-byte-base64-key"
ota_password: "your-ota-password"
```

### 2. Start the ESPHome dashboard

```bash
docker compose up esphome
```

Browse to **http://localhost:6052** to compile, flash and monitor via the UI.

### 3. Compile or flash from the command line

```bash
# Validate config only
docker compose run --rm esphome config example.yaml

# Compile firmware
docker compose run --rm esphome compile example.yaml

# Flash via USB (replace /dev/ttyUSB0 with your port)
docker compose run --rm --device /dev/ttyUSB0 esphome \
  run example.yaml --device /dev/ttyUSB0

# Flash via OTA
docker compose run --rm esphome run example.yaml --device 192.168.1.XX

# Stream live logs
docker compose run --rm esphome logs example.yaml --device 192.168.1.XX
```

### 4. Run the Python tools

```bash
# Re-extract registers from Dominus CFG/LBL files
docker compose run --rm tools python extract_registers.py

# Regenerate the C++ header from immergas_registers.json
docker compose run --rm tools python tools/generate_pdus_header.py

# Inspect all PDUs (summary / sanity check)
docker compose run --rm tools python tools/lookup_register.py

# Decode a live register reading
docker compose run --rm tools python tools/lookup_register.py --pdu 2100 --value 10
docker compose run --rm tools python tools/lookup_register.py --pdu 3016 --value 550
docker compose run --rm tools python tools/lookup_register.py --pdu 2001 --value 5

# Change label language (default: en)
docker compose run --rm tools python tools/lookup_register.py --pdu 2100 --value 10 --lang de
```

### 5. Run the Modbus loopback test (C++)

Compiles `tools/modbus_loopback.cpp` and runs the Modbus RTU frame validator without hardware:

```bash
docker compose run --rm loopback
```

Developer workflow (without Docker)
-------------------------------------

```bash
# 1. Extract registers
python extract_registers.py

# 2. Generate C++ header
python tools/generate_pdus_header.py

# 3. Inspect / test register output
python tools/lookup_register.py
python tools/lookup_register.py --pdu 2100 --value 10

# 4. Build and run C++ loopback test
g++ -std=c++17 tools/modbus_loopback.cpp -o tools/modbus_loopback
./tools/modbus_loopback

# 5. Compile / flash ESPHome
esphome compile example.yaml
esphome run example.yaml
```

Quick-reference table
----------------------

| Goal | Command |
|---|---|
| ESPHome dashboard | `docker compose up esphome` |
| Validate config | `docker compose run --rm esphome config example.yaml` |
| Compile firmware | `docker compose run --rm esphome compile example.yaml` |
| Flash via USB | `docker compose run --rm --device /dev/ttyUSBX esphome run example.yaml --device /dev/ttyUSBX` |
| Flash via OTA | `docker compose run --rm esphome run example.yaml --device <IP>` |
| Live logs | `docker compose run --rm esphome logs example.yaml --device <IP>` |
| Extract registers | `docker compose run --rm tools python extract_registers.py` |
| Generate header | `docker compose run --rm tools python tools/generate_pdus_header.py` |
| Inspect registers | `docker compose run --rm tools python tools/lookup_register.py` |
| Decode a value | `docker compose run --rm tools python tools/lookup_register.py --pdu <N> --value <V>` |
| Loopback test | `docker compose run --rm loopback` |

See `DOCS/DEVELOPER.md` for detailed developer notes, assumptions, and where to change behaviour.
