# CLAUDE.md — Immergas-Modbus Codebase Guide

This file provides AI assistants with the context needed to understand, navigate,
and contribute to the Immergas-Modbus ESPHome custom component.

---

## Project Overview

This repository implements a **custom ESPHome component** that integrates Immergas
heating systems (boilers, heat pumps) via **Modbus RTU** over RS-485. It exposes
2,000+ registers as native ESPHome entities (sensors, numbers, switches, selects,
binary sensors, climate) that surface in Home Assistant.

The register metadata is extracted from the proprietary Dominus configuration files
and stored in `immergas_registers.json`. A code generator then produces a C++ header
(`immergas_pdus.h`) that embeds a static PDU map consumed at runtime.

---

## Repository Layout

```
Immergas-Modbus/
├── components/immergas_modbus/       # ESPHome custom component (Python + C++)
│   ├── __init__.py                   # Controller schema & registration
│   ├── immergas_modbus.cpp/.h        # Core Modbus RTU controller
│   ├── immergas_pdus.h               # AUTO-GENERATED – do not edit by hand
│   ├── im_device.cpp/.h              # Base entity class
│   ├── im_client.h                   # UART/RS-485 wrapper
│   ├── im_number.h                   # Writable numeric entity
│   ├── im_switch.h                   # Boolean control entity
│   ├── im_select.h                   # Multi-option entity
│   ├── im_binary_sensor.h            # Read-only boolean entity
│   ├── im_climate.h                  # Climate entity (stub)
│   ├── immergas/                     # Immergas-specific Python helpers
│   │   ├── auto_entities.py          # JSON → entity-type classifier
│   │   ├── const.py                  # Shared constants
│   │   └── labels_*.py               # Multi-language label mappings (16 langs)
│   ├── sensor/                       # ESPHome sensor platform
│   ├── number/                       # ESPHome number platform
│   ├── switch/                       # ESPHome switch platform
│   ├── select/                       # ESPHome select platform
│   ├── climate/                      # ESPHome climate platform
│   └── binary_sensor/                # ESPHome binary_sensor platform
├── tools/
│   ├── generate_pdus_header.py       # JSON → immergas_pdus.h code generator
│   ├── lookup_register.py            # Debug utility: decode PDU values
│   └── modbus_loopback.cpp           # Standalone C++ test (CRC, framing)
├── extract_registers.py              # Dominus JSON → immergas_registers.json
├── extract_registers.js              # JS alternative extractor
├── immergas_registers.json           # Master PDU registry (77 KB, 2000+ entries)
├── immergas-custom-component.yaml    # Example ESPHome config (M5Stack Atom)
├── immergas-magis-combo-bms.yaml     # Example config (Magis Combo V2 heat pump)
├── docker-compose.yml                # Dev orchestration (ESPHome, tools, loopback)
├── README.md                         # Quick-start guide
├── DOCS/DEVELOPER.md                 # Architecture notes & improvement roadmap
└── DOCS/ESPHOME_DOCKER.md            # Docker flashing instructions
```

---

## Architecture

### Data Flow

```
Dominus JSON files          (external, sibling ../dominus/ directory)
        │
        ▼
extract_registers.py        → immergas_registers.json + labels_*.py
        │
        ▼
generate_pdus_header.py     → immergas_pdus.h  (static C++ PDU array)
        │
        ▼
ImmergasModbus (C++)        polls RS-485 bus every 30 s
        │
        ▼
IM_Device subclasses        parse raw values → ESPHome entity states
        │
        ▼
Home Assistant              receives sensor/switch/number updates
```

### Modbus RTU Protocol

- **Read**: Function `0x03` — Read Holding Registers (up to 125 registers)
- **Write**: Function `0x10` — Write Multiple Registers
- **CRC**: CRC-16 with polynomial `0xA001` (LSB-first)
- **Timeouts**: 300 ms for reads, 500 ms for writes
- **Batching**: Contiguous registers are grouped into single requests to minimize bus traffic

### PDU Data Types

| Enum | Meaning |
|------|---------|
| `IM_PDU_U16` | Unsigned 16-bit integer |
| `IM_PDU_S16` | Signed 16-bit integer |
| `IM_PDU_U32` | Unsigned 32-bit (2 registers) |
| `IM_PDU_S32` | Signed 32-bit (2 registers) |
| `IM_PDU_FLOAT32` | IEEE 754 float (2 registers) |
| `IM_PDU_TEMP` | Temperature (scaled integer) |
| `IM_PDU_LB_FLAG8` | Low-byte bit flags |

### Entity Type Mapping

`auto_entities.py` classifies PDUs from `immergas_registers.json` at import time:

- **sensor** — read-only numeric values
- **number** — writable numeric values (have `commands` in JSON)
- **switch** — boolean on/off (two-option select)
- **select** — multi-option choice
- **binary_sensor** — read-only boolean flag
- **climate** — temperature setpoint control (stub)

---

## Development Workflow

### Typical Change Scenarios

#### 1. Add or update registers (from Dominus files)
```bash
# Requires sibling ../dominus/ directory with Dominus CFG/LBL JSON files
docker compose run tools python extract_registers.py
docker compose run tools python tools/generate_pdus_header.py
```
Then commit both `immergas_registers.json` and `immergas_pdus.h`.

#### 2. Run C++ loopback test
```bash
docker compose run loopback
```
Verifies CRC calculation, frame structure, and register parsing without hardware.

#### 3. Start ESPHome dashboard
```bash
docker compose up esphome
# → http://localhost:6052
```

#### 4. Flash firmware (see DOCS/ESPHOME_DOCKER.md for full instructions)
```bash
# Via USB
docker compose run --device=/dev/ttyUSB0 esphome \
  esphome run immergas-custom-component.yaml

# Via OTA (after first flash)
docker compose run esphome \
  esphome run immergas-custom-component.yaml --device=<ip>
```

#### 5. Lookup / debug a PDU
```bash
docker compose run tools python tools/lookup_register.py --pdu <PDU_ID> --value <raw>
```

---

## Key Conventions

### CRITICAL: Never Edit `immergas_pdus.h` Directly
This file is **auto-generated** by `tools/generate_pdus_header.py` from
`immergas_registers.json`. The CI pipeline verifies they are in sync. If you
need to change a PDU definition, update the JSON and re-run the generator.

### C++ Style
- **Standard**: C++17
- **Naming**: `snake_case` for variables/functions, `PascalCase` for classes
- **Entity classes** (`IM_Number`, `IM_Switch`, etc.) inherit from both an
  `IM_Device` base and the corresponding ESPHome platform class
- Write operations call `controller_->write_pdu_by_value(pdu_, float_value)`;
  never write to UART directly from entity classes

### Python Style
- **Linting**: `flake8` (enforced in CI)
- **Import pattern**: Platform `__init__.py` files import from `auto_entities.py`
  to get entity lists; they do not hardcode PDU IDs
- **Label files** (`labels_*.py`) are auto-generated — do not edit them manually

### YAML Configuration
- Secrets must go in `secrets.yaml` (git-ignored) — never hardcode credentials
- UART defaults: 9600 baud, GPIO19 TX, GPIO22 RX (M5Stack Atom S3)
- Device addresses use dotted format matching Modbus slave IDs (e.g., `"20.00.00"`)

### `immergas_registers.json` Schema
```json
{
  "pdus": [
    {
      "pdu": 12345,
      "views": [
        {
          "item": "PARAM_NAME",
          "return_type": "u16",
          "decimal": 1,
          "labels": { "en": "English Label" }
        }
      ],
      "commands": [...],
      "messages": [{ "action": "read" }, { "action": "write" }]
    }
  ]
}
```
- `views` → reading metadata (type, scale from decimal, labels)
- `commands` → writing metadata (makes PDU writable)
- `messages.action` → `"read"` / `"write"` / `"read/write"`

---

## CI/CD Pipeline (`.github/workflows/ci.yml`)

| Step | What it checks |
|------|----------------|
| JSON validation | All PDU entries have required fields |
| Header sync | `immergas_pdus.h` matches what `generate_pdus_header.py` would produce |
| C++ build & loopback | Compiles and runs `modbus_loopback.cpp` with GCC/C++17 |
| Python lint | `flake8` on all `.py` files in `tools/` and root |

**All CI steps must pass before merging.**

---

## Environment & Configuration

### Required `secrets.yaml` (git-ignored)
```yaml
wifi_ssid: "your_network"
wifi_password: "your_password"
api_encryption_key: "base64_32_byte_key"
ota_password: "your_ota_password"
```

### Key ESPHome Config Options
| Option | Default | Notes |
|--------|---------|-------|
| `baud_rate` | 9600 | Modbus RTU standard for Immergas |
| `update_interval` | 30s | Polling frequency |
| `language` | `en` | One of: en, it, fr, de, es (and 11 more) |
| `debug` | false | Verbose UART logging |
| `flow_control_pin` | — | Optional GPIO for RS-485 direction control |

### Multi-language Support
16 languages are supported via `labels_*.py` modules:
`en`, `it`, `de`, `fr`, `es`, `pt`, `nl`, `pl`, `hu`, `cs`, `sk`, `sl`, `bg`, `el`, `ro`, `ru`

---

## Common Pitfalls

1. **Editing `immergas_pdus.h` by hand** — CI will fail the header-sync check.
   Always regenerate via `generate_pdus_header.py`.

2. **Committing `secrets.yaml`** — It's in `.gitignore` for a reason. Never commit
   Wi-Fi credentials or API keys.

3. **Forgetting `../dominus/`** — `extract_registers.py` requires Dominus CFG/LBL
   files in a sibling directory. They are not included in this repo.

4. **Wrong device address format** — Addresses must match Modbus slave IDs in
   dotted notation (`"20.00.00"`), not plain integers.

5. **Polling interval too low** — The RS-485 bus can be slow. Values below 15s
   may cause timeouts. Default 30s is recommended.

---

## File Ownership & Editability

| File / Pattern | Status | Notes |
|----------------|--------|-------|
| `immergas_pdus.h` | AUTO-GENERATED | Regenerate via `generate_pdus_header.py` |
| `labels_*.py` | AUTO-GENERATED | Regenerate via `extract_registers.py` |
| `immergas_registers.json` | AUTO-GENERATED | Regenerate via `extract_registers.py` |
| `README_AUTOGEN.md` | AUTO-GENERATED | Placeholder for sensor docs |
| `im_*.h`, `immergas_modbus.*` | Hand-authored C++ | Edit freely |
| `components/**/__init__.py` | Hand-authored Python | Edit freely |
| `tools/generate_pdus_header.py` | Hand-authored Python | Edit freely |
| `tools/lookup_register.py` | Hand-authored Python | Edit freely |
| `*.yaml` | Hand-authored config | Edit freely |
