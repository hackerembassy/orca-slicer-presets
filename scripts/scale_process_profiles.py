#!/usr/bin/env python3
"""
Regenerate all non-0.4 process profiles using validated volumetric-flow caps.

Source of truth:
  - Speeds / accels : validated 0.4 nozzle process values (V04 dict below).
  - Flow cap        : filament_max_volumetric_speed from the 0.4 nozzle filament
                      profiles for each printer+material (min across all variants).

Speed scaling (ratio-preserving):
  eff_mvf  = max(filament_mvf, max_flow_at_0.4)
  scale    = min(1.0, eff_mvf / max_flow_at_target_nozzle) * detail_factor
  speed_N  = ref_speed_0.4 * scale

  All sections share a single scale derived from whichever section would
  exceed eff_mvf first at the target nozzle geometry. This preserves the
  outer-wall:inner-wall:infill speed ratios from the 0.4 profile.

Acceleration scaling:
  Same global scale factor applied to all absolute accelerations.
  Percentage-based accelerations (e.g. "100%") pass through unchanged.
  TPU: speeds and accelerations floored at validated 0.4 values.

Detail factor (nozzle <= 0.25 mm):
  scale * 0.5 — halves speeds, accelerations, and MVF ceiling relative
  to the throughput-limited value. An explicit filament_max_volumetric_speed
  cap is written to the process file so OrcaSlicer enforces it.

Layer heights set to 50% of nozzle. Line widths scale proportionally.
Support distances scale with layer height using the same ratio as 0.4.
"""

import json, os, glob

BASE   = "/Users/edie/Library/Application Support/OrcaSlicer/user/default"
PROC   = os.path.join(BASE, "process")
FILB   = os.path.join(BASE, "filament", "base")
FILR   = os.path.join(BASE, "filament")

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def layer_h(nz):
    """50 % of nozzle, rounded to 2 decimals."""
    return round(nz * 0.5, 2)

def std_width(nz, ratio=1.12):
    return round(nz * ratio, 4)

def sup_width(nz, ratio=1.05):
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
        ow_acc=600,  iw_acc=800,  inf_acc=800,  isol_acc=1100, top_acc=600,
        def_acc=800,  il_acc=500,  br_acc=500,  travel_acc=1500,
    ),
    ("anette", "PETG"): dict(
        ow=90, iw=125, inf=125, top=50, sup=90, sup_i=90, il=30, ili=50, isol=150, br=40, gap=50,
        wid=0.45, sup_wid=0.42,
        sup_top_ratio=1.5, sup_bot_ratio=1.5,
        sup_xy=0.8, lw_pct=1.125,
        ow_acc=2000, iw_acc=3000, inf_acc=4000, isol_acc=2500, top_acc=1000,
        def_acc=2500, il_acc=1000, br_acc=1000, travel_acc=2000,
    ),
    ("anette", "PLA"):  dict(
        ow=50, iw=70, inf=90, top=50, sup=80, sup_i=60, il=25, ili=25, isol=80, br=25, gap=50,
        wid=0.45, sup_wid=0.42,
        sup_top_ratio=1.0, sup_bot_ratio=1.0,
        sup_xy=0.6, lw_pct=1.12,
        ow_acc=600,  iw_acc=800,  inf_acc=800,  isol_acc=1100, top_acc=600,
        def_acc=800,  il_acc=500,  br_acc=500,  travel_acc=1500,
    ),
    ("anette", "TPU"):  dict(
        ow=15, iw=20, inf=25, top=15, sup=20, sup_i=15, il=10, ili=10, isol=20, br=25, gap=30,
        wid=0.48, sup_wid=0.48,
        sup_top_ratio=1.25, sup_bot_ratio=1.25,
        sup_xy=0.8, lw_pct=1.2,
        # percentage-based accel fields pass through unchanged; absolute ones floored at 0.4
        ow_acc=300,    iw_acc=400,    inf_acc="100%", isol_acc="100%", top_acc=300,
        def_acc=400,   il_acc=200,    br_acc=300,     travel_acc=600,
    ),
    # ---- Shaytan K2 ----
    ("k2", "ABS"):  dict(
        ow=180, iw=250, inf=265, top=95, sup=190, sup_i=190, il=95, ili=125, isol=265, br=25, gap=275,
        wid=0.45, sup_wid=0.42,
        sup_top_ratio=1.5, sup_bot_ratio=1.5,
        sup_xy=0.8, lw_pct=1.12,
        ow_acc=5000, iw_acc=7000, inf_acc=9000, isol_acc=9000, top_acc=4000,
        def_acc=9000, il_acc=4000, br_acc=2750, travel_acc=6500,
    ),
    # K2 PETG uses 100% LW and explicit 0.42 infill width
    ("k2", "PETG"): dict(
        ow=160, iw=180, inf=240, top=140, sup=120, sup_i=100, il=130, ili=140, isol=210, br=25, gap=200,
        wid=0.40, sup_wid=0.42,
        inf_wid=0.42,
        sup_top_ratio=1.5, sup_bot_ratio=1.5,
        sup_xy=0.8, lw_pct=1.0,
        ow_acc=7000, iw_acc=8000, inf_acc=10000, isol_acc=1000, top_acc=5000,
        def_acc=8000, il_acc=5000, br_acc=2750, travel_acc=7000,
    ),
    ("k2", "PLA"):  dict(
        ow=200, iw=250, inf=260, top=180, sup=125, sup_i=150, il=150, ili=160, isol=275, br=25, gap=250,
        wid=0.45, sup_wid=0.42,
        sup_top_ratio=0.75, sup_bot_ratio=1.0,
        sup_xy=0.6, lw_pct=1.125,
        ow_acc=8000, iw_acc=8000, inf_acc=12500, isol_acc=12500, top_acc=6000,
        def_acc=12500, il_acc=6000, br_acc=3500, travel_acc=7500,
    ),
    ("k2", "TPU"):  dict(
        ow=15, iw=20, inf=25, top=15, sup=20, sup_i=15, il=10, ili=10, isol=20, br=25, gap=30,
        wid=0.48, sup_wid=0.48,
        sup_top_ratio=1.25, sup_bot_ratio=1.25,
        sup_xy=0.8, lw_pct=1.2,
        ow_acc=300,    iw_acc=400,    inf_acc="100%", isol_acc="100%", top_acc=300,
        def_acc=400,   il_acc=200,    br_acc=300,     travel_acc=600,
    ),
}
# fmt: on

REF_LAYER = 0.20   # validated layer height for all 0.4 profiles

# ---------------------------------------------------------------------------
# Read validated MVF from 0.4 filament profiles (min across all variants)
# ---------------------------------------------------------------------------
def get_validated_mvf(printer, material):
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


def build_updates(printer, material, nozzle, detail_factor=1.0):
    """Return a dict of JSON key→value updates for the target process file."""
    ref     = V04[(printer, material)]
    raw_mvf = get_validated_mvf(printer, material)

    lh        = layer_h(nozzle)
    rw        = ref["wid"]
    wid       = std_width(nozzle, ref["lw_pct"])
    sw        = sup_width(nozzle, ref["sup_wid"] / 0.4)
    inf_ref_w = ref.get("inf_wid", rw)
    inf_w     = round(nozzle * (inf_ref_w / 0.4), 4)

    is_tpu = material == "TPU"

    # -- Ratio-preserving global scale --
    # Effective MVF: higher of filament rating and what the 0.4 process actually pushes
    best_0_4_flow = max(
        ref["ow"]   * REF_LAYER * rw,
        ref["iw"]   * REF_LAYER * rw,
        ref["inf"]  * REF_LAYER * inf_ref_w,
        ref["isol"] * REF_LAYER * inf_ref_w,
        ref["top"]  * REF_LAYER * rw,
        ref["gap"]  * REF_LAYER * rw,
    )
    eff_mvf = max(raw_mvf, best_0_4_flow)

    # Max flow any section would produce at target nozzle geometry, at 0.4 reference speeds
    max_tgt_flow = max(
        ref["ow"]    * lh * wid,
        ref["iw"]    * lh * wid,
        ref["inf"]   * lh * inf_w,
        ref["isol"]  * lh * inf_w,
        ref["top"]   * lh * wid,
        ref["il"]    * lh * wid,
        ref["ili"]   * lh * wid,
        ref["gap"]   * lh * wid,
        ref["sup"]   * lh * sw,
        ref["sup_i"] * lh * sw,
    )

    # Single scale applied to all sections: preserves ratios, caps at eff_mvf.
    # detail_factor adds an extra reduction for fine nozzle profiles.
    scale = min(1.0, eff_mvf / max_tgt_flow) * detail_factor

    def sp(ref_spd):
        return max(1, round(ref_spd * scale))

    def sa(ref_acc):
        """Scale absolute acceleration; pass percentage strings through unchanged."""
        if isinstance(ref_acc, str):
            return ref_acc
        return max(100, round(ref_acc * scale))

    # Speed floors
    br_floor  = 10
    il_floor  = ref["il"]  if is_tpu else (10 if printer == "anette" else 40)
    ili_floor = ref["ili"] if is_tpu else (10 if printer == "anette" else 40)
    gen_floor = ref["ow"]  if is_tpu else 1

    ow_spd   = max(gen_floor, sp(ref["ow"]))
    iw_spd   = max(gen_floor, sp(ref["iw"]))
    inf_spd  = max(gen_floor, sp(ref["inf"]))
    top_spd  = max(gen_floor, sp(ref["top"]))
    sup_spd  = max(gen_floor, sp(ref["sup"]))
    supi_spd = max(gen_floor, sp(ref["sup_i"]))
    isol_spd = max(gen_floor, sp(ref["isol"]))
    br_spd   = max(br_floor,  sp(ref["br"]))
    gap_spd  = max(gen_floor, sp(ref["gap"]))
    il_spd   = max(il_floor,  sp(ref["il"]))
    ili_spd  = max(ili_floor, sp(ref["ili"]))

    # Accelerations: scale for non-TPU; TPU uses 0.4 values unchanged
    ow_acc     = ref["ow_acc"]     if is_tpu else sa(ref["ow_acc"])
    iw_acc     = ref["iw_acc"]     if is_tpu else sa(ref["iw_acc"])
    inf_acc    = ref["inf_acc"]    if is_tpu else sa(ref["inf_acc"])
    isol_acc   = ref["isol_acc"]   if is_tpu else sa(ref["isol_acc"])
    top_acc    = ref["top_acc"]    if is_tpu else sa(ref["top_acc"])
    def_acc    = ref["def_acc"]    if is_tpu else sa(ref["def_acc"])
    il_acc     = ref["il_acc"]     if is_tpu else sa(ref["il_acc"])
    br_acc     = ref["br_acc"]     if is_tpu else sa(ref["br_acc"])
    travel_acc = ref["travel_acc"] if is_tpu else sa(ref["travel_acc"])

    sup_top_z  = round(lh * ref["sup_top_ratio"], 2)
    sup_bot_z  = round(lh * ref["sup_bot_ratio"], 2)
    lw_pct_str = f"{round(ref['lw_pct'] * 100)}%"

    updates = {
        "layer_height":                       str(lh),
        "initial_layer_print_height":         str(lh),
        "line_width":                         lw_pct_str,
        "outer_wall_line_width":              str(wid),
        "inner_wall_line_width":              str(wid),
        "sparse_infill_line_width":           str(inf_w),
        "top_surface_line_width":             str(wid),
        "support_line_width":                 str(sw),
        "outer_wall_speed":                   str(ow_spd),
        "inner_wall_speed":                   str(iw_spd),
        "sparse_infill_speed":                str(inf_spd),
        "top_surface_speed":                  str(top_spd),
        "support_speed":                      str(sup_spd),
        "support_interface_speed":            str(supi_spd),
        "initial_layer_speed":                str(il_spd),
        "initial_layer_infill_speed":         str(ili_spd),
        "internal_solid_infill_speed":        str(isol_spd),
        "bridge_speed":                       str(br_spd),
        "gap_infill_speed":                   str(gap_spd),
        "support_top_z_distance":             str(sup_top_z),
        "support_bottom_z_distance":          str(sup_bot_z),
        "support_object_xy_distance":         str(ref["sup_xy"]),
        "outer_wall_acceleration":            str(ow_acc),
        "inner_wall_acceleration":            str(iw_acc),
        "sparse_infill_acceleration":         str(inf_acc),
        "internal_solid_infill_acceleration": str(isol_acc),
        "top_surface_acceleration":           str(top_acc),
        "default_acceleration":               str(def_acc),
        "initial_layer_acceleration":         str(il_acc),
        "bridge_acceleration":                str(br_acc),
        "travel_acceleration":                str(travel_acc),
    }

    # K2 PETG: wall widths stay "0" (resolved from global line_width %)
    if printer == "k2" and material == "PETG":
        updates["outer_wall_line_width"] = "0"
        updates["inner_wall_line_width"] = "0"
        updates["top_surface_line_width"] = "0"
        updates["line_width"] = "100%"

    # Detail profiles: explicit MVF cap enforced by OrcaSlicer
    if detail_factor < 1.0:
        updates["filament_max_volumetric_speed"] = [str(round(eff_mvf * detail_factor, 1))]

    return updates


def process_target(printer, material, nozzle, filename, name, printer_preset):
    path = os.path.join(PROC, filename)
    if not os.path.exists(path):
        print(f"  SKIP (file not found): {filename}")
        return

    with open(path) as f:
        data = json.load(f)

    detail_factor = 0.5 if nozzle <= 0.25 else 1.0
    updates = build_updates(printer, material, nozzle, detail_factor=detail_factor)
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
        f"{'ow':>5} {'iw':>5} {'inf':>5} {'top':>5} {'il':>5} "
        f"{'ow_a':>6} {'iw_a':>6} {'inf_a':>7}"
    )
    print(header)
    print("-" * len(header))
    for (printer, material, nozzle, filename, name, _) in TARGETS:
        raw_mvf       = get_validated_mvf(printer, material)
        detail_factor = 0.5 if nozzle <= 0.25 else 1.0
        u             = build_updates(printer, material, nozzle, detail_factor=detail_factor)
        lh            = layer_h(nozzle)
        flag          = " [detail]" if detail_factor < 1.0 else ""
        print(
            f"  {filename:<44} {nozzle:>4.2f} {lh:>5.2f} {raw_mvf:>5.1f} "
            f"{u['outer_wall_speed']:>5} {u['inner_wall_speed']:>5} "
            f"{u['sparse_infill_speed']:>5} {u['top_surface_speed']:>5} "
            f"{u['initial_layer_speed']:>5} "
            f"{u['outer_wall_acceleration']:>6} {u['inner_wall_acceleration']:>6} "
            f"{u['sparse_infill_acceleration']:>7}{flag}"
        )


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv

    print("\n=== Ratio-preserving volumetric-flow speed + acceleration scaling ===\n")
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
