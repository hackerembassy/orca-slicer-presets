# Orca Slicer Presets

OrcaSlicer presets for **two FDM printers** at [Hacker Embassy](https://hackem.cc/):
**Anette Hackem** and **Shaytan** (Creality K2 Pro).

---

## Printers

### Anette Hackem

| Field | Value |
| --- | --- |
| **Name** | Anette Hackem |
| **Type** | FDM — i3 cartesian |
| **Build volume** | 220 × 220 × 170 mm |
| **Firmware** | Klipper |

#### Nozzle sizes

| Preset name | Nozzle | Profile tier |
| --- | --- | --- |
| anette hackem 0.15 nozzle | 0.15 mm | Detail |
| anette hackem 0.25 nozzle | 0.25 mm | Detail |
| anette hackem 0.3 nozzle | 0.3 mm | Standard |
| anette hackem 0.4 nozzle | **0.4 mm** | Standard — default |
| anette hackem 0.4 nozzle skip-mesh | **0.4 mm** | Standard — skips bed mesh (for ABS) |
| anette hackem 0.6 nozzle | 0.6 mm | Speed |
| anette hackem 0.6 nozzle skip-mesh | 0.6 mm | Speed — skips bed mesh |
| anette hackem 0.8 nozzle | 0.8 mm | Speed |
| anette hackem 1.0 nozzle | 1.0 mm | Speed |

> **Note:** 0.2 mm and 0.5 mm nozzles are MK8 format and are not compatible with this printer.

---

### Shaytan (Creality K2 Pro)

| Field | Value |
| --- | --- |
| **Name** | Shaytan |
| **Model** | Creality K2 Pro |
| **Type** | FDM — CoreXY |
| **Build volume** | 260 × 260 × 260 mm |
| **Firmware** | Klipper |

#### Nozzle sizes

| Preset name | Nozzle | Profile tier |
| --- | --- | --- |
| Shaytan K2 @ 0.2 | 0.2 mm | Detail |
| Shaytan K2 @ 0.4 | **0.4 mm** | Standard — default |
| Shaytan K2 @ 0.6 | 0.6 mm | Speed |
| Shaytan K2 @ 0.8 | 0.8 mm | Speed |
| Shaytan K2 @ 1.0 | 1.0 mm | Speed |

---

## Filament Presets

Filament presets are shared across both printers for nozzle sizes they have in common.

| Material | Variants |
| --- | --- |
| PLA | All PLA hot |
| PETG | Base PETG hot, Black PETG hot, White PETG hot |
| ABS | Black ABS hot, White ABS hot, Color ABS hot |
| TPU | Black TPU hot |
| SBS | Color SBS hot |

Each preset is available for every nozzle size where a matching process profile exists.

---

## Process Presets

Process presets define print quality profiles (layer height, speeds, supports, etc.) for each printer and nozzle size.

### Anette Hackem — Validation Status

| Nozzle | PLA | PETG | ABS | TPU | Standard |
| --- | --- | --- | --- | --- | --- |
| 0.15 mm (Detail) | **validated** | pending | pending | — | — |
| 0.25 mm (Detail) | pending | pending | pending | — | — |
| 0.3 mm (Standard) | **validated** | **validated** | pending | — | — |
| **0.4 mm** | **validated** | **validated** | **validated** | **validated** | **validated** |
| 0.6 mm (Speed) | **validated** | **validated** | **validated** | pending | — |
| 0.8 mm (Speed) | pending | pending | pending | pending | — |
| 1.0 mm (Speed) | pending | pending | pending | — | — |

### Shaytan K2 — Validation Status

All K2 process presets are **baseline** — structural parameters (layer heights, support distances, wall counts) are derived from Anette's validated profiles. Print speeds have not yet been tuned for the K2 and will need manual adjustment after test prints.

| Nozzle | PLA | PETG | ABS | TPU | SBS | Standard |
| --- | --- | --- | --- | --- | --- | --- |
| 0.2 mm (Detail) | baseline | baseline | baseline | — | — | — |
| **0.4 mm** | baseline | baseline | baseline | baseline | baseline | baseline |
| 0.6 mm (Speed) | baseline | baseline | baseline | baseline | — | — |
| 0.8 mm (Speed) | baseline | baseline | baseline | baseline | — | — |
| 1.0 mm (Speed) | baseline | baseline | baseline | — | — | — |

---

## Repository Structure

```text
machine/            # Printer and nozzle definitions
  base/             # Shared base configs (anette hackem, Creality K2)
filament/           # Filament temperature and flow profiles
  base/             # Per-nozzle-size filament presets
process/            # Print quality profiles (layer height, speed, etc.)
  base/             # Base process presets per nozzle
```

---

## Installation

Clone this repository, then copy the preset directories into your OrcaSlicer user profile. The path differs by operating system.

### macOS

```bash
cp -r machine/ filament/ process/ \
  ~/Library/Application\ Support/OrcaSlicer/user/default/
```

### Linux

```bash
cp --recursive machine/ filament/ process/ \
  ~/.config/OrcaSlicer/user/default/
```

### Windows (PowerShell)

```powershell
$dest = "$env:APPDATA\OrcaSlicer\user\default"
Copy-Item -Recurse machine, filament, process -Destination $dest
```

> **Windows path in Explorer:** `%APPDATA%\OrcaSlicer\user\default\`

After copying, restart OrcaSlicer — presets will appear in the printer, process, and filament dropdowns.

---

## Troubleshooting

> Troubleshooting notes below are specific to **Anette Hackem**.

### SKIP\_MESH for ABS prints

When printing ABS, the BL-Touch probe may fail on a heated bed. The `SKIP_MESH` parameter tells the `START_PRINT` macro to skip bed mesh probing and use a previously saved mesh instead.

Use the **anette hackem 0.4 nozzle skip-mesh** (or 0.6 skip-mesh) printer preset — the modified start G-code passes `SKIP_MESH=1` automatically.

**Important:** `SKIP_MESH=1` must be on the **same line** as `START_PRINT`, passed as a macro argument. Putting it on a separate line causes a Klipper error.

**Correct** (same line as START\_PRINT):

```text
START_PRINT FIRST_LAYER_EXT_TEMP=... FIRST_LAYER_BED_TEMP=... SKIP_MESH=1
```

**Incorrect** (separate line — causes Klipper error):

```text
START_PRINT FIRST_LAYER_EXT_TEMP=... FIRST_LAYER_BED_TEMP=...
SKIP_MESH=1
```

Only use `SKIP_MESH=1` when a saved bed mesh already exists for the target bed temperature. Without a saved mesh the print starts with no leveling compensation.

---

## License

These presets are shared for the Hacker Embassy community. Use and modify freely.
