#!/usr/bin/env python3
"""
Fork all @anette hackem filament presets into @Shaytan K2 variants.

For each base filament at a nozzle size with a matching Shaytan K2 machine
(0.2, 0.4, 0.6, 0.8, 1.0):
  - Creates a @Shaytan K2 copy with exclusive Shaytan printer/process bindings
  - Strips all Shaytan references from the original (locks it to Anette only)

Also processes root-level derivative filaments and warns about orphans.
"""

import json
import glob
import re
import random
import string
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FILAMENT_BASE = REPO_ROOT / "filament" / "base"
FILAMENT_ROOT = REPO_ROOT / "filament"
PROCESS_DIR = REPO_ROOT / "process"

SHAYTAN_NOZZLE_SIZES = {"0.2", "0.4", "0.6", "0.8", "1.0"}


def new_filament_id():
    prefix = random.choice(string.ascii_uppercase)
    suffix = "".join(random.choices("0123456789abcdef", k=7))
    return prefix + suffix


def build_shaytan_process_map():
    """Build dict: nozzle_size -> [process_names] for all Shaytan K2 processes."""
    process_map = {}
    for f in sorted(PROCESS_DIR.glob("*.json")):
        with open(f) as fp:
            d = json.load(fp)
        for printer in d.get("compatible_printers", []):
            m = re.match(r"Shaytan K2 @ (\d+\.\d+)", printer)
            if m:
                nozzle = m.group(1)
                process_map.setdefault(nozzle, []).append(d.get("name", ""))
    return process_map


def get_compatible_prints(nozzle_size, filament_type, process_map):
    """Return list of compatible Shaytan process names for a filament.
    Returns [] for derivative files that don't define filament_type."""
    if not filament_type or nozzle_size not in process_map:
        return []
    mat = filament_type.upper()
    result = []
    for name in process_map[nozzle_size]:
        if mat in name.upper() or "STANDARD" in name.upper():
            result.append(name)
    return result


def make_info_content():
    ts = int(time.time())
    return f"sync_info = create\nuser_id = \nsetting_id = \nbase_id = \nupdated_time = {ts}\n"


def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent="\t", sort_keys=True, ensure_ascii=False)
        f.write("\n")


def process_filament_file(json_path, process_map):
    """
    Create a Shaytan copy and strip Shaytan refs from the original.
    Returns True if a Shaytan copy was created.
    """
    with open(json_path) as f:
        data = json.load(f)

    filename = json_path.name
    m = re.search(r"(\d+\.\d+) nozzle", filename)
    if not m:
        print(f"  SKIP (no nozzle size): {filename}")
        return False
    nozzle_size = m.group(1)

    if nozzle_size not in SHAYTAN_NOZZLE_SIZES:
        # Clean any stray Shaytan refs from this Anette-only size
        orig_cp = data.get("compatible_printers", [])
        clean_cp = [x for x in orig_cp if "Shaytan" not in x]
        if clean_cp != orig_cp:
            data["compatible_printers"] = clean_cp
            data["compatible_prints"] = [
                x for x in data.get("compatible_prints", []) if "Shaytan" not in x
            ]
            write_json(json_path, data)
            print(f"  CLEANED (no Shaytan machine for {nozzle_size}): {filename}")
        return False

    # --- Build the Shaytan copy ---
    shaytan_data = dict(data)

    shaytan_name = data.get("name", "").replace("@anette hackem", "@Shaytan K2")
    shaytan_data["name"] = shaytan_name
    shaytan_data["filament_settings_id"] = [shaytan_name]
    shaytan_data["filament_id"] = new_filament_id()
    shaytan_data["compatible_printers"] = [f"Shaytan K2 @ {nozzle_size}"]

    filament_type_raw = data.get("filament_type", [""])
    filament_type = filament_type_raw[0] if isinstance(filament_type_raw, list) else filament_type_raw
    shaytan_data["compatible_prints"] = get_compatible_prints(nozzle_size, filament_type, process_map)

    # Fix inherits if it points to an Anette filament
    inherits = data.get("inherits", "")
    if inherits and "@anette hackem" in inherits:
        shaytan_data["inherits"] = inherits.replace("@anette hackem", "@Shaytan K2")

    # Write copy + .info
    shaytan_filename = filename.replace("@anette hackem", "@Shaytan K2")
    shaytan_path = json_path.parent / shaytan_filename
    write_json(shaytan_path, shaytan_data)
    shaytan_path.with_suffix(".info").write_text(make_info_content())
    print(f"  CREATED: {shaytan_filename}")

    # --- Update original: strip all Shaytan refs ---
    data["compatible_printers"] = [
        x for x in data.get("compatible_printers", [])
        if "Shaytan" not in x and "Creality K2" not in x
    ]
    data["compatible_prints"] = [
        x for x in data.get("compatible_prints", []) if "Shaytan" not in x
    ]
    write_json(json_path, data)
    print(f"  UPDATED: {filename}")

    return True


def main():
    random.seed()

    print("=== Phase A: Shaytan process map ===")
    process_map = build_shaytan_process_map()
    for nozzle, names in sorted(process_map.items()):
        print(f"  {nozzle}: {names}")

    print("\n=== Phase B: filament/base/ ===")
    base_files = sorted(FILAMENT_BASE.glob("*@anette hackem*.json"))
    created = sum(process_filament_file(f, process_map) for f in base_files)
    print(f"\n  {created} Shaytan copies created from {len(base_files)} Anette base files")

    print("\n=== Phase C: filament/ root ===")
    root_files = sorted(FILAMENT_ROOT.glob("*@anette hackem*.json"))
    root_created = sum(process_filament_file(f, process_map) for f in root_files)
    print(f"\n  {root_created} Shaytan copies created from {len(root_files)} Anette root files")

    print("\n=== Phase D: Orphan check ===")
    orphan = FILAMENT_ROOT / "Generic PETG @System - Copy.json"
    if orphan.exists():
        with open(orphan) as f:
            d = json.load(f)
        print(f"  WARNING: {orphan.name}")
        print(f"    compatible_printers: {d.get('compatible_printers', [])}")
        print(f"    inherits: {d.get('inherits', '')}")
        print("    Action needed: rename to 'Base PETG hot @Shaytan K2 0.4 nozzle' or delete if superseded")

    print("\nDone.")


if __name__ == "__main__":
    main()
