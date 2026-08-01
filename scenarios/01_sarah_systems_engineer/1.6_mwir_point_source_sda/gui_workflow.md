# 1.6 MWIR Point-Source SDA — GUI Workflow

How to build and inspect this point-source scenario in the RADIANT GUI.

## Open

`File → Open` → `inputs/1.6_mwir_point_source_sda.yaml`. The chain evaluates
warning-free; the Performance stage shows SNR ≈ 25.8 and detection range ≈ 1522 km.

## Define the target by intensity (not radiance × area)

Go to the **Source** stage → **Scene & regime** tab and confirm
`Scene type (declared) = point_source`. Selecting `point_source` regates the
Source radiometry inputs:

- The **Target — point source** tab's intensity inputs become **editable**:
  - `Emitter temperature (blackbody I)` = 290 K
  - `Emitting area (blackbody I)` = 8 m²
  - `Emitter emissivity (blackbody I)` = 0.85
  - `Band-integrated intensity [W/sr]` — leave at 0 (blackbody mode is in use; this
    is the alternative scalar input)
- The **Target — thermal** tab's surface-radiance rows
  (`Target temperature`, `Target emissivity`) are **disabled/badged** — they are
  not the point-source input (a point source is defined by radiant intensity `I(λ)`,
  not a surface radiance × area).

Each edit is one `sensor.set` and re-evaluates; the Performance metrics move.

## Geometry & the Schematic

The **Geometry → Schematic** tab draws the sensor→target line of sight. The target
is a point (no shape); its projected-area pill is absent because the target is
defined by intensity, not area. The slant range is derived from
altitude + off-nadir zenith (Gap 98 C — the point-source signal now uses the
derived range; `geometry.target_range_m` need not be set explicitly, though this
config sets it for reproducibility).

## Read the results

**Performance** stage: SNR, and `detection_range_m` (the range at which SNR falls
to `performance.detection_snr_threshold = 6`). Sweeping the emitting area (or
emissivity, or the band intensity) moves the signal **linearly** — the
point-source camera equation `S ∝ I / R²`.

## GUI requirements exercised

- Regime-gated Source radiometry inputs (`regime:point_source` / `regime:extended`
  / `regime:sub_pixel` schema tags): the correct target-definition inputs light up
  for the declared scene type.
- Point-source intensity inputs surfaced (Gap 98 D) — no hand-authored CSV needed.
- Point-source detection-range metric with a derived slant range (Gap 98 C).
