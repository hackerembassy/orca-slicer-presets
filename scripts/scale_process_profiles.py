#!/usr/bin/env python3
"""
Regenerate all non-0.4 process profiles using volumetric-flow scaling.

Source of truth: validated 0.4 nozzle speed values.
Formula: speed_N = flow_0.4 / (layer_N * width_N)
Cap:     speed_N = min(speed_N, max_vflow_N / (layer_N * width_N))

Rounds all speeds to nearest integer mm/s.
Only touches speed and geometry parameters; leaves structural settings alone.
"""

import json, os, math, copy

BASE  = "/Users/edie/Library/Application Support/OrcaSlicer/user/default"
PROC  = os.path.join(BASE, "process")
FILB  = os.path.join(BASE, "filament", "base")

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def layer_h(nz):
    """50 % of nozzle, rounded to 2 decimals."""
    return round(nz * 0.5, 2)

def std_width(nz, ratio=1.12):
    """Line width for most extrusions."""
    return round(nz * ratio, 4)

def sup_width(nz, ratio=1.05):
    """Support line width (slightly narrower)."""
    return round(nz * ratio, 4)

# ---------------------------------------------------------------------------
# Validated 0.4 source data (outer_wall, inner_wall, sparse_infill,
# top_surface, support, support_iface, initial_layer, initial_infill,
# internal_solid, bridge, gap_infill)
# Widths: outer_wall/inner_wall/top/infill, support
# ---------------------------------------------------------------------------
# fmt: off
V04 = {
    # ---- Anette ----
    ("anette", "ABS"):  dict(
        ow=50, iw=70, inf=90, top=50, sup=80, sup_i=60, il=25, ili=25, isol=80, br=25, gap=50,
        wid=0.45, sup_wid=0.42,
        sup_top_ratio=1.5, sup_bot_ratio=1.5,
        sup_xy=0.8, lw_pct=1.12,
    ),
    ("anette", "PETG"): dict(
        ow=90, iw=125, inf=125, top=50, sup=90, sup_i=90, il=30, ili=50, isol=150, br=40, gap=50,
        wid=0.45, sup_wid=0.42,
        sup_top_ratio=1.5, sup_bot_ratio=1.5,
        sup_xy=0.8, lw_pct=1.125,
    ),
    ("anette", "PLA"):  dict(
        ow=50, iw=70, inf=90, top=50, sup=80, sup_i=60, il=25, ili=25, isol=80, br=25, gap=50,
        wid=0.45, sup_wid=0.42,
        sup_top_ratio=1.0, sup_bot_ratio=1.0,
        sup_xy=0.6, lw_pct=1.12,
    ),
    ("anette", "TPU"):  dict(
        ow=15, iw=20, inf=25, top=15, sup=20, sup_i=15, il=10, ili=10, isol=20, br=25, gap=30,
        wid=0.48, sup_wid=0.48,
        sup_top_ratio=1.25, sup_bot_ratio=1.25,
        sup_xy=0.8, lw_pct=1.2,
    ),
    # ---- Shaytan K2 ----
    ("k2", "ABS"):  dict(
        ow=180, iw=250, inf=265, top=95, sup=190, sup_i=190, il=95, ili=125, isol=265, br=25, gap=275,
        wid=0.45, sup_wid=0.42,
        sup_top_ratio=1.5, sup_bot_ratio=1.5,
        sup_xy=0.8, lw_pct=1.12,
    ),
    # K2 PETG uses 100% LW and explicit 0.42 infill width
    ("k2", "PETG"): dict(
        ow=160, iw=240, inf=260, top=140, sup=130, sup_i=120, il=100, ili=140, isol=250, br=25, gap=200,
        wid=0.40, sup_wid=0.42,   # 100% of nozzle for walls
        inf_wid=0.42,              # explicit infill/support width at 0.4 nozzle
        sup_top_ratio=1.5, sup_bot_ratio=1.5,
        sup_xy=0.8, lw_pct=1.0,
    ),
    ("k2", "PLA"):  dict(
        ow=200, iw=250, inf=260, top=180, sup=125, sup_i=150, il=175, ili=185, isol=275, br=25, gap=275,
        wid=0.45, sup_wid=0.42,
        sup_top_ratio=0.75, sup_bot_ratio=1.0,
        sup_xy=0.6, lw_pct=1.125,
    ),
    ("k2", "TPU"):  dict(
        ow=15, iw=20, inf=25, top=15, sup=20, sup_i=15, il=10, ili=10, isol=20, br=25, gap=30,
        wid=0.48, sup_wid=0.48,
        sup_top_ratio=1.25, sup_bot_ratio=1.25,
        sup_xy=0.8, lw_pct=1.2,
    ),
}
# fmt: on

REF_LAYER = 0.20   # validated layer height for all 0.4 profiles

# ---------------------------------------------------------------------------
# Per-nozzle filament max volumetric speed caps (mm³/s)
# Use most conservative value across all colour variants at each nozzle.
# ---------------------------------------------------------------------------
MAX_VF = {
    ("anette", "ABS",  0.15): 2.5,
    ("anette", "ABS",  0.25): 4.5,
    ("anette", "ABS",  0.3):  6.5,
    ("anette", "ABS",  0.6):  13.5,
    ("anette", "ABS",  0.8):  20.0,
    ("anette", "PETG", 0.15): 2.5,
    ("anette", "PETG", 0.25): 4.5,
    ("anette", "PETG", 0.3):  6.0,
    ("anette", "PETG", 0.6):  13.0,
    ("anette", "PETG", 0.8):  20.0,
    ("anette", "PLA",  0.15): 2.5,
    ("anette", "PLA",  0.25): 5.0,
    ("anette", "PLA",  0.3):  7.0,
    ("anette", "PLA",  0.6):  15.5,
    ("anette", "PLA",  0.8):  22.0,
    ("anette", "TPU",  0.6):  5.0,
    ("anette", "TPU",  0.8):  7.0,
    ("k2",     "ABS",  0.2):  4.5,
    ("k2",     "ABS",  0.6):  13.5,
    ("k2",     "ABS",  0.8):  20.0,
    ("k2",     "PETG", 0.2):  4.5,
    ("k2",     "PETG", 0.6):  13.0,
    ("k2",     "PETG", 0.8):  20.0,
    ("k2",     "PLA",  0.2):  5.0,
    ("k2",     "PLA",  0.6):  15.5,
    ("k2",     "PLA",  0.8):  22.0,
    ("k2",     "TPU",  0.6):  5.0,
    ("k2",     "TPU",  0.8):  7.0,
}

def scale_speed(ref_speed, ref_layer, ref_width, tgt_layer, tgt_width, max_vf):
    """
    Return integer speed (mm/s) that maintains the reference volumetric flow,
    capped by max_vf / (tgt_layer * tgt_width).
    """
    vol = ref_speed * ref_layer * ref_width
    raw = vol / (tgt_layer * tgt_width)
    cap = max_vf / (tgt_layer * tgt_width)
    return max(1, round(min(raw, cap)))

def scale_or_keep(ref_speed, ref_layer, ref_width, tgt_layer, tgt_width, max_vf, keep_min=None):
    s = scale_speed(ref_speed, ref_layer, ref_width, tgt_layer, tgt_width, max_vf)
    if keep_min is not None:
        s = max(s, keep_min)
    return s

# ---------------------------------------------------------------------------
# Target files: (printer_tag, material, nozzle, filename, name_in_json,
#                printer_preset_in_json)
# Only non-0.4 nozzles are processed (0.4 is the validated reference).
# ---------------------------------------------------------------------------
TARGETS = [
    # ---- Anette ----
    # ABS
    ("anette", "ABS",  0.15, "Detail ABS @ 0.15.json",  "Detail ABS @ 0.15",  "anette hackem 0.15 nozzle"),
    ("anette", "ABS",  0.25, "Detail ABS @ 0.25.json",  "Detail ABS @ 0.25",  "anette hackem 0.25 nozzle"),
    ("anette", "ABS",  0.3,  "Standard ABS @ 0.3.json", "Standard ABS @ 0.3", "anette hackem 0.3 nozzle"),
    ("anette", "ABS",  0.6,  "Speed ABS @ 0.6.json",    "Speed ABS @ 0.6",    "anette hackem 0.6 nozzle"),
    ("anette", "ABS",  0.8,  "Speed ABS @ 0.8.json",    "Speed ABS @ 0.8",    "anette hackem 0.8 nozzle"),
    # PETG
    ("anette", "PETG", 0.15, "Detail PETG @ 0.15.json",  "Detail PETG @ 0.15",  "anette hackem 0.15 nozzle"),
    ("anette", "PETG", 0.25, "Detail PETG @ 0.25.json",  "Detail PETG @ 0.25",  "anette hackem 0.25 nozzle"),
    ("anette", "PETG", 0.3,  "Standard PETG @ 0.3.json", "Standard PETG @ 0.3", "anette hackem 0.3 nozzle"),
    ("anette", "PETG", 0.6,  "Speed PETG @ 0.6.json",    "Speed PETG @ 0.6",    "anette hackem 0.6 nozzle"),
    ("anette", "PETG", 0.8,  "Speed PETG @ 0.8.json",    "Speed PETG @ 0.8",    "anette hackem 0.8 nozzle"),
    # PLA
    ("anette", "PLA",  0.15, "Detail PLA @ 0.15.json",  "Detail PLA @ 0.15",  "anette hackem 0.15 nozzle"),
    ("anette", "PLA",  0.25, "Detail PLA @ 0.25.json",  "Detail PLA @ 0.25",  "anette hackem 0.25 nozzle"),
    ("anette", "PLA",  0.3,  "Standard PLA @ 0.3.json", "Standard PLA @ 0.3", "anette hackem 0.3 nozzle"),
    ("anette", "PLA",  0.6,  "Speed PLA @ 0.6.json",    "Speed PLA @ 0.6",    "anette hackem 0.6 nozzle"),
    ("anette", "PLA",  0.8,  "Speed PLA @ 0.8.json",    "Speed PLA @ 0.8",    "anette hackem 0.8 nozzle"),
    # TPU
    ("anette", "TPU",  0.6,  "TPU @ 0.6.json",  "TPU @ 0.6",  "anette hackem 0.6 nozzle"),
    ("anette", "TPU",  0.8,  "TPU @ 0.8.json",  "TPU @ 0.8",  "anette hackem 0.8 nozzle"),
    # ---- Shaytan K2 ----
    # ABS
    ("k2", "ABS",  0.2, "Shaytan K2 Detail ABS @ 0.2.json", "Shaytan K2 Detail ABS @ 0.2", "Shaytan K2 @ 0.2"),
    ("k2", "ABS",  0.6, "Shaytan K2 Speed ABS @ 0.6.json",  "Shaytan K2 Speed ABS @ 0.6",  "Shaytan K2 @ 0.6"),
    ("k2", "ABS",  0.8, "Shaytan K2 Speed ABS @ 0.8.json",  "Shaytan K2 Speed ABS @ 0.8",  "Shaytan K2 @ 0.8"),
    # PETG
    ("k2", "PETG", 0.2, "Shaytan K2 Detail PETG @ 0.2.json", "Shaytan K2 Detail PETG @ 0.2", "Shaytan K2 @ 0.2"),
    ("k2", "PETG", 0.6, "Shaytan K2 Speed PETG @ 0.6.json",  "Shaytan K2 Speed PETG @ 0.6",  "Shaytan K2 @ 0.6"),
    ("k2", "PETG", 0.8, "Shaytan K2 Speed PETG @ 0.8.json",  "Shaytan K2 Speed PETG @ 0.8",  "Shaytan K2 @ 0.8"),
    # PLA
    ("k2", "PLA",  0.2, "Shaytan K2 Detail PLA @ 0.2.json", "Shaytan K2 Detail PLA @ 0.2", "Shaytan K2 @ 0.2"),
    ("k2", "PLA",  0.6, "Shaytan K2 Speed PLA @ 0.6.json",  "Shaytan K2 Speed PLA @ 0.6",  "Shaytan K2 @ 0.6"),
    ("k2", "PLA",  0.8, "Shaytan K2 Speed PLA @ 0.8.json",  "Shaytan K2 Speed PLA @ 0.8",  "Shaytan K2 @ 0.8"),
    # TPU
    ("k2", "TPU",  0.6, "Shaytan K2 TPU @ 0.6.json", "Shaytan K2 TPU @ 0.6", "Shaytan K2 @ 0.6"),
    ("k2", "TPU",  0.8, "Shaytan K2 TPU @ 0.8.json", "Shaytan K2 TPU @ 0.8", "Shaytan K2 @ 0.8"),
]


def build_updates(printer, material, nozzle):
    """Return a dict of JSON key→value updates for the target process file."""
    ref = V04[(printer, material)]
    mvf = MAX_VF.get((printer, material, nozzle), None)
    if mvf is None:
        raise KeyError(f"No max_vflow entry for ({printer}, {material}, {nozzle})")

    lh   = layer_h(nozzle)
    wid  = std_width(nozzle, ref["lw_pct"])
    sw   = sup_width(nozzle, ref["sup_wid"] / 0.4)  # maintain same ratio as 0.4

    # For K2 PETG, infill/support width follows a different ratio
    if "inf_wid" in ref:
        inf_w = round(nozzle * (ref["inf_wid"] / 0.4), 4)
    else:
        inf_w = sw  # same as support width

    rl  = REF_LAYER
    rw  = ref["wid"]       # reference outer/inner wall width at 0.4

    def sp(ref_spd, w=None):
        return scale_speed(ref_spd, rl, rw, lh, w or wid, mvf)

    # Infill uses its own width for flow calculation
    def sp_inf(ref_spd):
        return scale_speed(ref_spd, rl, ref.get("inf_wid", rw), lh, inf_w, mvf)

    # Support uses support line width
    def sp_sup(ref_spd):
        return scale_speed(ref_spd, rl, ref["sup_wid"], lh, sw, mvf)

    # Speed floors: prevent going slower than validated 0.4 for the same material.
    # TPU is already very slow — maintain its 0.4 minimums across all nozzles.
    ow_min  = ref["ow"]  if material == "TPU" else (1 if printer == "anette" else 1)
    br_min  = 10
    il_min  = ref["il"]  if material == "TPU" else (10 if printer == "anette" else 40)
    ili_min = ref["ili"] if material == "TPU" else (10 if printer == "anette" else 40)

    ow_spd   = max(ow_min, sp(ref["ow"]))
    iw_spd   = max(ow_min, sp(ref["iw"]))
    inf_spd  = max(ow_min, sp_inf(ref["inf"]))
    top_spd  = max(ow_min, sp(ref["top"]))
    sup_spd  = max(ow_min, sp_sup(ref["sup"]))
    supi_spd = max(ow_min, sp_sup(ref["sup_i"]))
    isol_spd = max(ow_min, sp_inf(ref["isol"]))
    br_spd   = max(br_min, sp(ref["br"]))
    gap_spd  = max(ow_min, sp(ref["gap"]))
    il_spd   = max(il_min,  sp(ref["il"]))
    ili_spd  = max(ili_min, sp(ref["ili"]))

    # Support distances scale with layer height using same ratio as 0.4
    sup_top_z = round(lh * ref["sup_top_ratio"], 2)
    sup_bot_z = round(lh * ref["sup_bot_ratio"], 2)

    lw_pct_str = f"{round(ref['lw_pct'] * 100)}%"

    updates = {
        "layer_height":                   str(lh),
        "initial_layer_print_height":     str(lh),
        "line_width":                     lw_pct_str,
        "outer_wall_line_width":          str(wid),
        "inner_wall_line_width":          str(wid),
        "sparse_infill_line_width":       str(inf_w),
        "top_surface_line_width":         str(wid),
        "support_line_width":             str(sw),
        "outer_wall_speed":               str(ow_spd),
        "inner_wall_speed":               str(iw_spd),
        "sparse_infill_speed":            str(inf_spd),
        "top_surface_speed":              str(top_spd),
        "support_speed":                  str(sup_spd),
        "support_interface_speed":        str(supi_spd),
        "initial_layer_speed":            str(il_spd),
        "initial_layer_infill_speed":     str(ili_spd),
        "internal_solid_infill_speed":    str(isol_spd),
        "bridge_speed":                   str(br_spd),
        "gap_infill_speed":               str(gap_spd),
        "support_top_z_distance":         str(sup_top_z),
        "support_bottom_z_distance":      str(sup_bot_z),
        "support_object_xy_distance":     str(ref["sup_xy"]),
    }

    # K2 PETG: outer/inner wall widths must stay "0" (resolved from global line_width)
    if printer == "k2" and material == "PETG":
        updates["outer_wall_line_width"] = "0"
        updates["inner_wall_line_width"] = "0"
        updates["top_surface_line_width"] = "0"
        updates["line_width"] = "100%"

    return updates


def process_target(printer, material, nozzle, filename, name, printer_preset):
    path = os.path.join(PROC, filename)
    if not os.path.exists(path):
        print(f"  SKIP (file not found): {filename}")
        return

    with open(path) as f:
        data = json.load(f)

    updates = build_updates(printer, material, nozzle)
    data.update(updates)

    # Ensure name/settings_id/compatible_printers are correct
    data["name"] = name
    data["print_settings_id"] = name
    data["compatible_printers"] = [printer_preset]

    # Remove internal_solid_infill_line_width "0" overrides that were in old files
    # (they can stay if the file had them — leave them)

    with open(path, "w") as f:
        json.dump(data, f, indent="\t", ensure_ascii=False)
        f.write("\n")

    print(f"  updated: {filename}")


# ---------------------------------------------------------------------------
# Print the computed values table before writing (dry-run display)
# ---------------------------------------------------------------------------
def print_table():
    header = f"{'file':<46} {'nz':>4} {'lh':>5} {'ow':>5} {'iw':>5} {'inf':>5} {'top':>5} {'il':>5} {'cap':>8}"
    print(header)
    print("-" * len(header))
    for (printer, material, nozzle, filename, name, _) in TARGETS:
        ref = V04[(printer, material)]
        mvf = MAX_VF.get((printer, material, nozzle), "?")
        lh  = layer_h(nozzle)
        wid = std_width(nozzle, ref["lw_pct"])
        ow  = scale_speed(ref["ow"], REF_LAYER, ref["wid"], lh, wid, mvf) if mvf != "?" else "?"
        iw  = scale_speed(ref["iw"], REF_LAYER, ref["wid"], lh, wid, mvf) if mvf != "?" else "?"
        inf = scale_speed(ref["inf"], REF_LAYER, ref.get("inf_wid", ref["wid"]), lh,
                          round(nozzle * (ref.get("inf_wid", ref["wid"]) / 0.4), 4), mvf) if mvf != "?" else "?"
        top = scale_speed(ref["top"], REF_LAYER, ref["wid"], lh, wid, mvf) if mvf != "?" else "?"
        il  = max(10 if printer=="anette" else 40,
                  scale_speed(ref["il"], REF_LAYER, ref["wid"], lh, wid, mvf)) if mvf != "?" else "?"
        cap_spd = round(mvf / (lh * wid)) if mvf != "?" else "?"
        print(f"  {filename:<44} {nozzle:>4.2f} {lh:>5.2f} {ow:>5} {iw:>5} {inf:>5} {top:>5} {il:>5}  cap={cap_spd}")


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv

    print("\n=== Volumetric-flow speed scaling ===\n")
    print_table()

    if dry:
        print("\n[dry-run] no files written.")
        sys.exit(0)

    print("\n=== Writing files ===\n")
    for args in TARGETS:
        try:
            process_target(*args)
        except Exception as e:
            print(f"  ERROR {args[3]}: {e}")

    print("\nDone.")
