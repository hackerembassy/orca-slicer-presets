#!/usr/bin/env python3
"""
Regenerate all non-0.4 process profiles using validated volumetric-flow caps.

Source of truth:
  - Speeds     : validated 0.4 nozzle process values (V04 dict below).
  - Flow cap   : filament_max_volumetric_speed from the 0.4 nozzle filament
                 profiles for each printer+material (min across all variants).

Formula: speed_N = min(speed_0.4, mvf_0.4 / (layer_N * width_N))

This gives "as fast as the printer can move, limited by what the hotend
can push". For large nozzles the flow cap is the binding constraint; for
small nozzles the motion speed is the binding constraint.

TPU speeds are floored at the validated 0.4 values since TPU is
material-property-driven, not motion-limited.

Layer heights set to 50 % of nozzle. Line widths scale proportionally
at the same nozzle-to-width ratio as the validated 0.4 profile.
Support distances scale with layer height using the same ratio as 0.4.
"""

import json, os, glob, math, copy

BASE   = "/Users/edie/Library/Application Support/OrcaSlicer/user/default"
PROC   = os.path.join(BASE, "process")
FILB   = os.path.join(BASE, "filament", "base")
FILR   = os.path.join(BASE, "filament")   # root (non-base variants)

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
# Validated 0.4 source data
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
# Read validated MVF from 0.4 filament profiles (min across all variants)
# ---------------------------------------------------------------------------
def get_validated_mvf(printer, material):
    """
    Read minimum filament_max_volumetric_speed from all 0.4 nozzle filament
    profiles for this printer+material (base and root dirs, skip missing).
    """
    tag = "Shaytan K2" if printer == "k2" else "anette hackem"
    vals = []
    for search_dir in [FILB, FILR]:
        pattern = os.path.join(search_dir, f"*{material}* @{tag} 0.4 nozzle.json")
        for path in glob.glob(pattern):
            with open(path) as f:
                d = json.load(f)
            raw = d.get("filament_max_volumetric_speed", [None])
            if isinstance(raw, list):
                raw = raw[0] if raw else None
            if raw and str(raw) not in ("?", "nil", ""):
                vals.append(float(raw))
    if not vals:
        raise KeyError(f"No filament MVF found for ({printer}, {material})")
    return min(vals)

# ---------------------------------------------------------------------------
# Speed calculation
# ---------------------------------------------------------------------------
def scale_speed(ref_speed, ref_layer, ref_width, tgt_layer, tgt_width, filament_mvf, floor=1):
    """
    effective_mvf = max(ref_speed * ref_layer * ref_width, filament_mvf)
    target_speed  = min(ref_speed, effective_mvf / (tgt_layer * tgt_width))

    Never cap below what the validated 0.4 process already achieves.
    Filament MVF serves as a higher-flow ceiling where the rating exceeds
    the validated process (e.g. larger nozzle allows more flow).
    """
    process_flow  = ref_speed * ref_layer * ref_width
    effective_mvf = max(process_flow, filament_mvf)
    cap           = effective_mvf / (tgt_layer * tgt_width)
    return max(floor, round(min(ref_speed, cap)))

# ---------------------------------------------------------------------------
# Target files
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
    mvf = get_validated_mvf(printer, material)

    lh  = layer_h(nozzle)
    rw  = ref["wid"]          # reference wall width at 0.4 nozzle
    wid = std_width(nozzle, ref["lw_pct"])
    sw  = sup_width(nozzle, ref["sup_wid"] / 0.4)

    # Infill width at target nozzle
    inf_ref_w = ref.get("inf_wid", rw)
    inf_w = round(nozzle * (inf_ref_w / 0.4), 4)

    def sp(ref_spd, w=None):
        return scale_speed(ref_spd, REF_LAYER, rw, lh, w or wid, mvf)

    def sp_inf(ref_spd):
        return scale_speed(ref_spd, REF_LAYER, inf_ref_w, lh, inf_w, mvf)

    def sp_sup(ref_spd):
        return scale_speed(ref_spd, REF_LAYER, ref["sup_wid"], lh, sw, mvf)

    # TPU: floor at validated 0.4 speeds (material-property-driven limit)
    is_tpu   = material == "TPU"
    br_floor = 10
    il_floor = ref["il"]  if is_tpu else (10 if printer == "anette" else 40)
    ili_floor = ref["ili"] if is_tpu else (10 if printer == "anette" else 40)
    gen_floor = ref["ow"] if is_tpu else 1

    ow_spd   = max(gen_floor, sp(ref["ow"]))
    iw_spd   = max(gen_floor, sp(ref["iw"]))
    inf_spd  = max(gen_floor, sp_inf(ref["inf"]))
    top_spd  = max(gen_floor, sp(ref["top"]))
    sup_spd  = max(gen_floor, sp_sup(ref["sup"]))
    supi_spd = max(gen_floor, sp_sup(ref["sup_i"]))
    isol_spd = max(gen_floor, sp_inf(ref["isol"]))
    br_spd   = max(br_floor,  sp(ref["br"]))
    gap_spd  = max(gen_floor, sp(ref["gap"]))
    il_spd   = max(il_floor,  sp(ref["il"]))
    ili_spd  = max(ili_floor, sp(ref["ili"]))

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

    data["name"] = name
    data["print_settings_id"] = name
    data["compatible_printers"] = [printer_preset]

    with open(path, "w") as f:
        json.dump(data, f, indent="\t", ensure_ascii=False)
        f.write("\n")

    print(f"  updated: {filename}")


# ---------------------------------------------------------------------------
# Dry-run table
# ---------------------------------------------------------------------------
def print_table():
    header = (
        f"{'file':<46} {'nz':>4} {'lh':>5} {'mvf':>5} "
        f"{'ow':>5} {'iw':>5} {'inf':>5} {'top':>5} {'il':>5} {'cap@nz':>8}"
    )
    print(header)
    print("-" * len(header))
    for (printer, material, nozzle, filename, name, _) in TARGETS:
        ref  = V04[(printer, material)]
        mvf  = get_validated_mvf(printer, material)
        lh   = layer_h(nozzle)
        wid  = std_width(nozzle, ref["lw_pct"])
        ow   = scale_speed(ref["ow"],  REF_LAYER, ref["wid"], lh, wid, mvf)
        iw   = scale_speed(ref["iw"],  REF_LAYER, ref["wid"], lh, wid, mvf)
        sw   = sup_width(nozzle, ref["sup_wid"] / 0.4)
        inf_ref_w = ref.get("inf_wid", ref["wid"])
        inf_w = round(nozzle * (inf_ref_w / 0.4), 4)
        inf  = scale_speed(ref["inf"], REF_LAYER, inf_ref_w, lh, inf_w, mvf)
        top  = scale_speed(ref["top"], REF_LAYER, ref["wid"], lh, wid, mvf)
        il_f = ref["il"] if material == "TPU" else (10 if printer == "anette" else 40)
        il   = max(il_f, scale_speed(ref["il"], REF_LAYER, ref["wid"], lh, wid, mvf))
        eff  = max(ref["iw"] * REF_LAYER * ref["wid"], mvf)
        cap  = round(eff / (lh * wid))
        print(
            f"  {filename:<44} {nozzle:>4.2f} {lh:>5.2f} {mvf:>5.1f} "
            f"{ow:>5} {iw:>5} {inf:>5} {top:>5} {il:>5}  cap={cap}"
        )


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv

    print("\n=== Volumetric-flow speed scaling ===")
    print("Formula: speed = min(speed_0.4, mvf_0.4_filament / (layer * width))\n")
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
