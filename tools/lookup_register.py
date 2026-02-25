#!/usr/bin/env python3
"""
Lookup / sanity-check tool for extracted Immergas Modbus registers.

Usage
-----
# Print a summary of all PDUs extracted from immergas_registers.json
  python tools/lookup_register.py

# Decode a live register reading
  python tools/lookup_register.py --pdu 2000 --value 3
  python tools/lookup_register.py --pdu 2001 --value 5
  python tools/lookup_register.py --pdu 2100 --value 10   # fault code lookup
  python tools/lookup_register.py --pdu 3000 --value 215  # temperature (×0.1)

Run from the Immergas-Modbus directory.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "immergas_registers.json"
LABELS_DIR = ROOT / "components" / "immergas_modbus" / "immergas"


# ---------------------------------------------------------------------------
# Label loading
# ---------------------------------------------------------------------------

def load_labels(lang: str = "en") -> dict:
    """Import a generated labels_<lang>.py module and return the mapping dict."""
    mod_path = LABELS_DIR / f"labels_{lang}.py"
    if not mod_path.exists():
        return {}
    ns: dict = {}
    exec(mod_path.read_text(encoding="utf8"), ns)  # noqa: S102
    return ns.get("immergas_labels", {})


# ---------------------------------------------------------------------------
# View decoding helpers
# ---------------------------------------------------------------------------

def _low_byte(raw: int) -> int:
    return raw & 0xFF


def _high_byte(raw: int) -> int:
    return (raw >> 8) & 0xFF


def _bit(byte_val: int, bit_index: int) -> int:
    return (byte_val >> bit_index) & 1


def decode_view(view: dict, raw: int) -> str:
    """Decode a single view entry against a raw u16 Modbus register value."""
    ret = view.get("return")
    check = view.get("check")
    item = view.get("item", "?")

    # ---- flag8 / bit check (used for boolean items) ----------------------
    if check:
        data = check.get("data", [])
        match_vals = check.get("match", [])
        if len(data) == 3 and data[1] == "flag8":
            byte_sel, bit_idx = data[0], int(data[2])
            byte_val = _low_byte(raw) if byte_sel == "LB" else _high_byte(raw)
            actual = str(_bit(byte_val, bit_idx))
            hit = actual in match_vals
            result = view.get("value", ["1"])[0] if hit else view.get("else-value", ["0"])[0]
            return f"{item}: {result}  (bit {bit_idx} of {'LB' if byte_sel == 'LB' else 'HB'} = {actual})"

    # ---- explicit return type ---------------------------------------------
    if ret:
        if isinstance(ret, list):
            t0 = ret[0]

            if t0 == "u16":
                return f"{item}: {raw}  (u16)"

            if t0 == "s16":
                signed = raw if raw < 0x8000 else raw - 0x10000
                return f"{item}: {signed}  (s16)"

            if t0 == "u8":
                return f"{item}: {raw & 0xFF}  (u8)"

            if t0 == "temp":
                dec = view.get("decimal", 1)
                scale = 10 ** (-int(dec))
                return f"{item}: {raw * scale:.{int(dec)}f} °C  (temp, ×{scale})"

            if t0 == "LB" and len(ret) == 3 and ret[1] == "flag8":
                bit_idx = int(ret[2])
                byte_val = _low_byte(raw)
                return f"{item}: bit {bit_idx} of LB = {_bit(byte_val, bit_idx)}"

            if t0 == "HB" and len(ret) == 3 and ret[1] == "flag8":
                bit_idx = int(ret[2])
                byte_val = _high_byte(raw)
                return f"{item}: bit {bit_idx} of HB = {_bit(byte_val, bit_idx)}"

    # ---- fallback: show raw -----------------------------------------------
    return f"{item}: {raw}  (raw u16)"


# ---------------------------------------------------------------------------
# Fault-code label lookup
# ---------------------------------------------------------------------------

FAULT_CODE_ITEMS = {"mb-functional-log", "mb-anomaly", "mb-error", "mb-fault"}


def maybe_fault_label(pdu_entry: dict, raw: int, labels: dict) -> str | None:
    """
    If this PDU looks like a fault-code register, return the label text.
    Returns None if not applicable.
    """
    for v in pdu_entry.get("views", []):
        item = v.get("item", "")
        ret = v.get("return", [])
        if item in FAULT_CODE_ITEMS or (
            "log" in item and isinstance(ret, list) and ret and ret[0] == "u16"
        ):
            label = labels.get(raw) or labels.get("default")
            if label:
                return (
                    f"  Fault code {raw}: {label['text1']}\n"
                    f"    Detail : {label['text2']}\n"
                    f"    Action : {label['action']}"
                )
    return None


# ---------------------------------------------------------------------------
# Summary / sanity check
# ---------------------------------------------------------------------------

def cmd_summary(data: dict) -> None:
    pdus = data.get("pdus", [])
    writable = [p for p in pdus if any(m.get("action") == "write" for m in p.get("messages", []))]
    read_only = [p for p in pdus if not any(m.get("action") == "write" for m in p.get("messages", []))]
    empty = [p for p in pdus if not p.get("views") and not p.get("commands")]

    print(f"Generated : {data.get('generated_at', 'unknown')}")
    print(f"Total PDUs: {len(pdus)}")
    print(f"  Writable : {len(writable)}")
    print(f"  Read-only: {len(read_only)}")
    print(f"  Empty    : {len(empty)}  (no views/commands — PDU exists in CFG but has no decoded fields)")
    print()

    # Return-type distribution
    type_counts: dict[str, int] = {}
    for p in pdus:
        for v in p.get("views", []):
            ret = v.get("return")
            check = v.get("check")
            if check and len(check.get("data", [])) >= 2 and check["data"][1] == "flag8":
                t = "flag8"
            elif isinstance(ret, list) and ret:
                t = ret[0]
            else:
                t = "unknown"
            type_counts[t] = type_counts.get(t, 0) + 1

    print("View return-type distribution:")
    for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:<12} {n}")
    print()

    # PDU address range
    addrs = [p["pdu"] for p in pdus]
    print(f"PDU address range: {min(addrs)} – {max(addrs)}")
    print()

    # Show a short table of all PDUs
    print(f"{'PDU':>6}  {'R/W':<4}  {'Views':>5}  Items")
    print("-" * 60)
    for p in sorted(pdus, key=lambda x: x["pdu"]):
        rw = "RW" if any(m.get("action") == "write" for m in p.get("messages", [])) else "R"
        items = ", ".join(
            v.get("item", "?") for v in p.get("views", [])
        ) or "(no views)"
        print(f"{p['pdu']:>6}  {rw:<4}  {len(p.get('views', [])):>5}  {items}")


# ---------------------------------------------------------------------------
# Decode a single PDU + raw value
# ---------------------------------------------------------------------------

def cmd_decode(data: dict, pdu_addr: int, raw: int, lang: str) -> None:
    pdus = {p["pdu"]: p for p in data.get("pdus", [])}
    if pdu_addr not in pdus:
        print(f"PDU {pdu_addr} not found in registry.", file=sys.stderr)
        sys.exit(1)

    entry = pdus[pdu_addr]
    labels = load_labels(lang)

    print(f"PDU {pdu_addr}  raw=0x{raw:04X} ({raw})")
    print(f"  Writable: {any(m.get('action') == 'write' for m in entry.get('messages', []))}")
    print()

    views = entry.get("views", [])
    if not views:
        print("  (no view definitions — cannot decode further)")
    else:
        print("  Decoded views:")
        for v in views:
            print(f"    {decode_view(v, raw)}")

    # Fault code overlay
    fault_text = maybe_fault_label(entry, raw, labels)
    if fault_text:
        print()
        print("  Fault label lookup:")
        print(fault_text)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect / decode Immergas Modbus registers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--pdu", type=int, help="PDU (register) address to decode")
    parser.add_argument("--value", type=lambda x: int(x, 0), help="Raw u16 value (decimal or 0x hex)")
    parser.add_argument("--lang", default="en", help="Label language, e.g. en / de / nl (default: en)")
    args = parser.parse_args()

    if not JSON_PATH.exists():
        print(f"Registry not found: {JSON_PATH}", file=sys.stderr)
        print("Run extract_registers.py first.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(JSON_PATH.read_text(encoding="utf8"))

    if args.pdu is not None and args.value is not None:
        cmd_decode(data, args.pdu, args.value, args.lang)
    elif args.pdu is not None or args.value is not None:
        parser.error("Provide both --pdu and --value together, or neither for a summary.")
    else:
        cmd_summary(data)


if __name__ == "__main__":
    main()
