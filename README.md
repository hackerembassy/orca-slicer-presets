# Orca Slicer Presets

OrcaSlicer presets for **Anette Hackem** — FDM 3D printer at [Hacker Embassy](https://hackem/cc/).

## Printer

- **Name**: Anette Hackem
- **Type**: FDM (Fused Deposition Modeling)
- **Firmware**: Klipper
- **Slicer**: [OrcaSlicer](https://github.com/SoftFever/OrcaSlicer)

## Nozzle Sizes

Machine presets are available for 9 nozzle diameters:

- 0.15 mm
- 0.2 mm
- 0.25 mm
- 0.3 mm
- 0.4 mm (default)
- 0.5 mm
- 0.6 mm
- 0.8 mm
- 1.0 mm

## Filament Presets

| Material | Variants |
| --- | --- |
| PLA | All PLA |
| PETG | Base PETG, Black PETG, White PETG |
| ABS | Black ABS, White ABS, Color ABS |
| TPU | Black TPU |

Each filament preset is available for all nozzle sizes.

## Process Presets

Process presets define print quality profiles (layer height, speed, etc.) for each nozzle size. Only validated nozzle sizes are included in this repository.

### Validation Status

| Nozzle | PLA | PETG | ABS | TPU | Standard |
| --- | --- | --- | --- | --- | --- |
| 0.15 mm (Detail) | pending | pending | pending | — | — |
| 0.2 mm (Detail) | pending | pending | pending | — | — |
| 0.25 mm (Detail) | pending | pending | pending | — | — |
| 0.3 mm (Standard) | pending | pending | pending | — | — |
| **0.4 mm** | **validated** | **validated** | **validated** | **validated** | **validated** |
| 0.5 mm (Standard) | pending | pending | pending | — | — |
| 0.6 mm (Speed) | pending | pending | pending | pending | — |
| 0.8 mm (Speed) | pending | pending | pending | pending | — |
| 1.0 mm (Speed) | pending | pending | pending | — | — |

Process presets for non-validated nozzle sizes exist locally but are not yet uploaded. To add a new nozzle size, update `.gitignore` to include the corresponding files.

## Repository Structure

```text
machine/            # Printer/nozzle definitions
  base/             # Base machine preset
filament/           # Filament temperature/flow profiles
  base/             # Per-nozzle filament presets
process/            # Print quality profiles (layer height, speed, etc.)
  base/             # Base process presets per nozzle
```

## Installation

1. Clone this repository
2. Copy the preset directories into your OrcaSlicer user profile:

   ```bash
   cp --recursive machine/ filament/ process/ ~/.config/OrcaSlicer/user/default/
   ```

3. Restart OrcaSlicer — presets will appear in the UI

## License

These presets are shared for the Hacker Embassy community. Use and modify freely.
