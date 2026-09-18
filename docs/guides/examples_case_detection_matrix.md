# Case Study — A Target Detection Matrix

**Scenario 4.1** · persona: Lisa, detection/targeting analyst · modality: script-led · scenario folder:
`scenarios/04_lisa_analyst/4.1_target_detection_matrix/`

---

## The question

Lisa owes a quarterly program review one slide. The program has a twelve-target
library, three candidate sensors, and four atmospheric conditions it cares about, and
the question the reviewers will ask is always the same: **how far off-nadir can each
sensor detect each target, and which target is the hardest?**

That is $12 \times 4 \times 3 = 144$ evaluations, and each one is itself a search —
detection range is not a metric RADIANT reports, it is the range at which a detection
criterion stops being satisfied, which has to be found. Doing this by hand is not
arithmetic-hard, it is bookkeeping-hard: 144 configurations, each with a different
target temperature, emissivity and area, a different atmosphere, a different sensor,
and a failure in any one of them silently poisoning a briefing chart.

This is the case for a batch runner, and for a script rather than a window. The GUI
would let Lisa examine any one cell beautifully; it would not let her defend all 144.

## The inputs, and why they are what they are

**The target library** arrives as a twelve-row workbook,
`inputs/lisa_target_library.xlsx`, read by `radiant.io.target_library.load_target_library`,
which derives `projected_area_m2` from length × width so that the analyst maintains
dimensions rather than areas:

| Target | $A_{proj}$ [m²] | T [K] | ε [--] | Material |
|---|---:|---:|---:|---|
| MBT tank | 28.4 | 310.0 | 0.90 | painted steel |
| APC | 18.2 | 306.0 | 0.90 | painted steel |
| Cargo truck | 20.0 | 301.0 | 0.92 | painted steel |
| Technical (pickup) | 10.1 | 303.0 | 0.88 | painted steel |
| SAM TEL | 35.6 | 305.0 | 0.90 | painted steel |
| Towed artillery | 26.6 | 296.0 | 0.85 | painted steel |
| Patrol boat | 145.0 | 299.0 | 0.85 | painted steel |
| Fast attack craft | 476.0 | 302.0 | 0.85 | painted steel |
| Transport aircraft | 1600.0 | 295.0 | 0.30 | bare aluminum |
| Fighter aircraft | 150.0 | 297.0 | 0.35 | low-e coating |
| Fuel bladder farm | 600.0 | 298.0 | 0.95 | rubberized fabric |
| Small UAV (parked) | 12.0 | 294.0 | 0.80 | composite |

Note the spread in emissivity, not just in size: the transport aircraft is enormous
(1600 m²) but bare aluminium at ε = 0.30 and *cold* at 295 K, while the fuel bladder
farm is a third its size at ε = 0.95. Those two facts will fight each other later.

**Three sensors**, all at 500 km, all read from YAML:

| | A — MWIR smallsat | B — MWIR flagship | C — LWIR wide |
|---|---|---|---|
| Aperture | 0.18 m | 0.50 m | 0.35 m |
| Focal length | 0.45 m (f/2.5) | 1.50 m (f/3.0) | 0.70 m (f/2.0) |
| Band | 3.6–4.9 µm | 3.6–4.9 µm | 8.0–11.5 µm |
| Pixel pitch | 15 µm | 12 µm | 17 µm |
| **GSD at nadir** | **16.7 m** | **4.0 m** | **12.1 m** |
| Quantum efficiency | 0.72 | 0.78 | 0.65 |
| Dark rate | 5,000 e-/s at 80 K | 2,000 e-/s at 75 K | 200,000 e-/s at 60 K |
| Read noise | 35 e- RMS | 25 e- RMS | 40 e- RMS |
| Integration time | 4 ms | 4 ms | 2 ms |

Sensor C's YAML is deliberately stale — it still carries the old name
`platform.h_sensor` where the current schema says `geometry.sensor_altitude_m`. RADIANT
accepts it through the deprecated-alias mechanism and says so:

```text
  OUTDATED PARAMETER NAME absorbed: sensor C's YAML still says
  'platform.h_sensor' (the superseded name). RADIANT accepted it
  through the deprecated-alias mechanism (1 DeprecationWarning(s) raised) and mapped it to
  geometry.sensor_altitude_m — the config still runs, loudly.
```

That is the intended behavior for an aged config: run, but warn. A config archive
that silently breaks on a schema rename is a config archive nobody keeps.

**Four atmospheres**, each pairing a visibility with the profile that physically goes
with it:

| Condition | Visibility | Standard profile |
|---|---|---|
| `clear` | 50 km | `midlat_summer` |
| `haze` | 10 km | `midlat_summer` |
| `tropical_haze` | 5 km | `tropical` |
| `arctic_clear` | 100 km | `subarctic_winter` |

**The detection criterion** is declared in the script, before any run:

```python
SCNR_THRESHOLD = 5.0       # detection criterion [dimensionless]
CLUTTER_SIGMA = 0.02       # rural scene clutter, fraction of in-pixel background
ALTITUDE_M = 500_000.0     # all three sensors fly the same 500 km orbit
ZENITH_MAX_RAD = math.radians(66.0)   # horizon at 500 km is 68.0° — stay clear
BISECTION_STEPS = 9        # zenith resolution ~0.13° → ~0.5% in range
```

## Why SCNR and not SNR

RADIANT reports `snr` and `contrast_snr`, and this study uses neither. That decision is
the analytic heart of the scenario, so it deserves the space.

Pure noise-limited SNR does not discriminate here. Every one of these sensors holds
SNR above 19 across the entire swath for every target — a 500 km MWIR imager staring at
a warm Earth is photon-rich. A criterion that every cell passes is not a criterion.

Real sub-pixel detection against a terrestrial background is **clutter-limited**: what
defeats you is not the sensor's noise but the scene's own spatial variability, patches
of ground that are as different from their neighbors as your target is. So the script
models rural scene clutter at 2 % of the in-pixel background and forms a
signal-to-clutter-plus-noise ratio:

```python
def scnr_of(result) -> float:
    """|contrast_e| / RSS(all noise terms incl. clutter) — detection SCNR."""
    contrast_e = abs(float(result.stage_outputs["spectral_integration"]["contrast_e"]))
    total = math.sqrt(sum(nt.value_e**2 for nt in result.noise_terms))
    return contrast_e / total if total > 0 else 0.0
```

It is assembled script-side because RADIANT's own `snr` and `contrast_snr` metrics
carry *temporal* noise only; the spatial clutter term is deliberately excluded from
them, and this is recorded as a gap in the scenario's `gaps.md`.

The absolute value is not a convenience. In the sub-pixel regime the chain forms
$\mathrm{contrast}_e = f\!f \cdot (L_{target} \cdot \mathrm{EE_{box}} - L_{bg})$: the
target's compact energy is EE_box-weighted, because its PSF spills into neighbouring
pixels, while the uniform background it **occludes** is not. A deeply sub-pixel target
with a small EE_box is therefore detected largely by the *dip* it punches in the
background, and `contrast_e` goes negative. A single hot pixel and a single occluded
pixel are equally detectable against a scene, so $|\cdot|$ is the physically right
criterion — but it means "detectability" here is distance from the weighted-background
null in either direction, not brightness.

## The scripted path

```bash
PYTHONPATH=src python \
  scenarios/04_lisa_analyst/4.1_target_detection_matrix/scripts/run_detection_matrix.py
```

### Geometry: set one thing, derive the rest

```python
def configure_geometry(sensor: Sensor, zenith_rad: float, area_m2: float) -> None:
    r_slant = slant_range_from_theta_o_m(zenith_rad, ALTITUDE_M, 0.0)
    sensor.set("geometry.path_zenith_rad", zenith_rad)
    footprint_m2 = (_ifov_rad(sensor) * r_slant) ** 2
    sensor.set("geometry.target.projected_area_m2", min(area_m2, footprint_m2))
    sensor.set("source.target.fill_fraction", min(1.0, area_m2 / footprint_m2))
```

Three subtleties are packed into six lines, and each one was a bug before it was a
line of code.

**Only $\theta_o$ is set.** The target-side path zenith is the single geometric input;
the chain derives the slant range from it through its own spherical viewing triangle.
Setting `geometry.target_range_m` *as well* would over-specify the line of sight with a
different (sensor-side) slant and trip RADIANT's consistency check. The script reads the
slant back through the same `slant_range_from_theta_o_m` the chain uses, so the
footprint it computes and the geometry the chain runs cannot diverge.

**`Sensor.get` returns canonical units.** `detector.pixel_pitch_x_um` comes back in
**meters**, despite the `_um` suffix in the name — the suffix records the *input* unit,
not the storage unit. An initial version of this script multiplied by $10^{-6}$ again
and made the pixel footprint $10^{12}$ times too small; the symptom was a printed GSD
of 0.0 m.

**Fill fraction, not projected area, drives sub-pixel weighting.** This is the one that
matters physically. `geometry.target.projected_area_m2` drives the *point-source* path
($A_t/R^2$). In the **sub-pixel** regime the target is weighted by
`source.target.fill_fraction` $= \min(1, A_{target}/(\mathrm{IFOV} \cdot R)^2)$ — the
fraction of the pixel it covers. Off-nadir, the pixel footprint grows as $R^2$, fill
falls, and SCNR falls with it. *That* is the detection-range mechanism this whole matrix
rests on, and a script that sets only the projected area would produce a matrix with no
range dependence at all and no obvious sign that anything was wrong.

### Detection range by bisection

```python
if scnr_at(sensor, ZENITH_MAX_RAD, area_true) >= SCNR_THRESHOLD:
    return {... "detection_range_km": range_max_km, "horizon_limited": 1.0}

lo, hi = 0.0, ZENITH_MAX_RAD  # SCNR(lo) >= threshold > SCNR(hi)
for _ in range(BISECTION_STEPS):
    mid = 0.5 * (lo + hi)
    if scnr_at(sensor, mid, area_true) >= SCNR_THRESHOLD:
        lo = mid
    else:
        hi = mid
detection_range_km = slant_range_from_theta_o_m(0.5 * (lo + hi), ALTITUDE_M, 0.0) / 1000.0
```

Nine bisection steps on the zenith angle, bracketed at nadir and at the 66° practical
swath edge (the true horizon at 500 km is 68.0°). Two early exits keep the cost honest:
a cell that fails at nadir is "not detectable" without any search, and a cell that still
passes at the swath edge is reported as **swath-edge limited** at 1,061 km — the sensor's
access, not the atmosphere, is what ends it there. Nine steps give ~0.13° of zenith
resolution, about 0.5 % in range; that figure matters when reading the tables below.

### The matrix itself

```python
for label, path in SENSOR_FILES.items():
    runner = BatchRunner(
        base_config={},  # unused — the factory loads the YAML
        axes=[("target", TARGET_AXIS), ("atmosphere", ATMOSPHERES)],
        sensor_factory=lambda cfg, p=path: _load_sensor(p),
    )
    results[label] = runner.run(evaluate_cell)
    n_failed = results[label].n_failed
    if n_failed:
        print(f"    {n_failed} cell(s) failed — recorded in the error column")
```

`radiant.api.batch.BatchRunner` takes the Cartesian product of the declared axes,
applies each cell's parameter overrides to a freshly built `Sensor`, and captures
per-cell failures rather than aborting the batch — a failed cell is recorded and
reported, never dropped. `result.pivot("detection_range_km", rows="target",
cols="atmosphere")` then builds the briefing tables directly.

One line inside the sensor factory is easy to miss and load-bearing:

```python
s.set("performance.niirs.allow_extrapolated", True)
```

These targets are unresolved at GSDs of 4–17 m, far outside the GIQE-5 calibration
envelope, so RADIANT's applicability gate would return NIIRS as N/A by default. The
scenario wants the extrapolated *trend*, so it opts in explicitly. That is the intended
contract: the extrapolation is available, but you have to ask for it in writing.

## Real output — the three matrices

```text
=== Running the matrix: 12 × 4 × 3 = 144 cells ===
  Detection criterion: SCNR ≥ 5 — |contrast| over RSS(noise + clutter),
  scene clutter = 2% of in-pixel background (rural)
  Swath edge: zenith 66° (slant 1,061 km; horizon at 68.0°)
  Running A: MWIR smallsat 18 cm (48 cells)...
  Running B: MWIR flagship 50 cm (48 cells)...
  Running C: LWIR wide 35 cm (48 cells)...
```

**Sensor A — MWIR smallsat, 16.7 m GSD, 278 m² pixel footprint at nadir:**

```text
  Target                         clear            haze   tropical_haze    arctic_clear
  ------------------------------------------------------------------------------------
  MBT tank              not detectable  not detectable  not detectable  not detectable
  APC                   not detectable  not detectable  not detectable  not detectable
  Cargo truck           not detectable  not detectable  not detectable  not detectable
  Technical (pickup)    not detectable  not detectable  not detectable  not detectable
  SAM TEL               not detectable  not detectable  not detectable  not detectable
  Towed artillery       not detectable  not detectable  not detectable  not detectable
  Patrol boat           not detectable  not detectable  not detectable             534
  Fast attack craft     not detectable  not detectable  not detectable             788
  Transport aircraft    not detectable  not detectable  not detectable          1,061*
  Fighter aircraft      not detectable  not detectable  not detectable  not detectable
  Fuel bladder farm                823             813             742          1,061*
  Small UAV (parked)    not detectable  not detectable  not detectable  not detectable
```

**Sensor B — MWIR flagship, 4.0 m GSD, 16 m² pixel footprint at nadir:**

```text
  Target                         clear            haze   tropical_haze    arctic_clear
  ------------------------------------------------------------------------------------
  MBT tank                         696             688             560             901
  APC                              673             666             612             865
  Cargo truck                      773             763             699           1,029
  Technical (pickup)               575             570             527             718
  SAM TEL                          870             858             782          1,061*
  Towed artillery                  893             883             800          1,061*
  Patrol boat                   1,061*          1,061*             998          1,061*
  Fast attack craft             1,061*          1,061*             924          1,061*
  Transport aircraft             1,047           1,022             737          1,061*
  Fighter aircraft               1,059           1,033             753          1,061*
  Fuel bladder farm             1,061*          1,061*           1,059          1,061*
  Small UAV (parked)               686             678             621             901
```

**Sensor C — LWIR wide, 12.1 m GSD:**

```text
  Target                         clear            haze   tropical_haze    arctic_clear
  ------------------------------------------------------------------------------------
  MBT tank              not detectable  not detectable  not detectable  not detectable
  APC                   not detectable  not detectable  not detectable  not detectable
  Cargo truck           not detectable  not detectable  not detectable  not detectable
  Technical (pickup)    not detectable  not detectable  not detectable  not detectable
  SAM TEL               not detectable  not detectable  not detectable             565
  Towed artillery       not detectable  not detectable  not detectable             523
  Patrol boat                      841             830             711          1,061*
  Fast attack craft             1,061*          1,061*             981          1,061*
  Transport aircraft            1,061*          1,061*          1,061*          1,061*
  Fighter aircraft                 938             926             782          1,061*
  Fuel bladder farm             1,061*          1,061*           1,029          1,061*
  Small UAV (parked)    not detectable  not detectable  not detectable  not detectable
```

```text
=== Worst-case target ===
  Hardest: Technical (pickup) — mean detection range 199 km
           across all 12 sensor×atmosphere cells
  Easiest: Fuel bladder farm — mean 991 km

==========================================================================
  DONE — 144 cells evaluated (0 failures recorded)
==========================================================================
```

All ranges are **slant range in kilometers** at SCNR = 5; `*` marks a cell that is
swath-edge limited (SCNR ≥ 5 all the way out to the 66° practical edge, slant
1,061 km). The full run takes 5 min 15 s — about 1,300 chain evaluations.

## What the matrix says

**Regime: sub-pixel, forced, in every cell.** The script sets both
`source.scene_type` and `source.regime_override` to `sub_pixel`. The override is
deliberate and worth understanding: left to itself, RADIANT's classifier picks
`point_source` for the smaller targets, and the point-source path drops the in-pixel
background photons entirely. Detection against a bright Earth background *needs* those
photons — they are the thing the target must be distinguished from, and they carry the
clutter term the criterion is limited by. Forcing `sub_pixel` keeps the background and
clutter terms in every cell, which is the physically correct description of a target
that fills part of a pixel while the scene fills the rest.

### Aperture buys targets; size buys range

The single clearest read on the slide. Sensor B's 4.0 m GSD gives a 16 m² pixel
footprint; sensor A's 16.7 m GSD gives 278 m² — seventeen times larger. Fill fraction is
target area over footprint, so B fills a pixel with targets that vanish into A's.
**B detects all twelve targets in all four conditions. A detects exactly one — the fuel
bladder farm — in the three temperate columns.**

Within a sensor, larger targets reach further, because fill stays near unity out to
longer slant ranges before the growing footprint dilutes it: on B, the fuel bladder farm
runs to the swath edge in clear air while the Technical pickup stops at 575 km.

For the program review this is the constellation-versus-exquisite decision reduced to
one table. Many small apertures buy revisit; one large aperture buys the target set.

### The hardest target is not the smallest or the coldest

**Technical (pickup)** — 10.1 m², ε = 0.88, 303 K — has a mean detection range of 199 km
across all twelve sensor × atmosphere cells and falls out entirely on the LWIR sensor.
The easiest is the **fuel bladder farm** at a mean of 991 km.

But the ordering is *not* a size ranking and *not* a temperature ranking, and the matrix
shows why. On sensor B in clear air, the cool 12 m² Small UAV at 294 K reaches 686 km and
the hot 28.4 m² MBT tank at 310 K reaches 696 km — within 1.5 % of each other, despite a
2.4× difference in area and 16 K in temperature. Both beat the *smaller, cooler*
Technical pickup.

The mechanism is the EE_box-weighted contrast introduced earlier. Detectability is
$f\!f \cdot |L_{target} \cdot \mathrm{EE_{box}} - L_{bg}|$: how far the target pixel
departs from the background **in either direction**, times fill. The Technical pickup is
simply the target whose EE_box-weighted radiance lands closest to the background's after
weighting, so its pixel departs least and it separates worst. It is nearest the null.

Two consequences follow, and Lisa should carry both into the room:

- **Which target sits at the null is model-dependent, not a property of the target
  library.** It has moved before, under changes to the EE_box weighting and to the
  down-looking path emission, and it will move again. "The Technical pickup is our
  hardest target" is a statement about the current model, not about the pickup.
- **A multi-pixel matched filter would recover the hardest targets.** EE_box spreads the
  target's energy into neighbouring pixels and the single-pixel criterion throws that
  energy away. Summing it back is a real detection-model refinement, and it is exactly
  the targets marked "not detectable" here that it would recover. This is recorded in the
  scenario's `gaps.md`.

### The atmosphere sets how far, not what

Every sensor's `arctic_clear` column leads its temperate columns, by 25–35 % on sensor B,
and on sensor A the arctic column is the *only* one where three extra targets — patrol
boat, fast attack craft, transport aircraft — clear threshold at all.

The mechanism is not target-path absorption. That axis was recalibrated away years ago,
and real MODTRAN columns span only about 1.3× in band-mean MWIR transmittance across
these profiles. What drives the spread now is the **atmosphere's own thermal emission**:
the down-looking path carries a $(1-\tau)B(\lambda, T_{eff})$ term, so a warm, moist
column puts more radiance into the in-pixel background — and the criterion is limited by
2 % of that background. A cold, dry subarctic column emits least, so its clutter floor is
lowest and every range lengthens. The `tropical_haze` column, warmest and wettest, is
uniformly the worst.

This is a case where the correct qualitative conclusion ("climate matters") was reached
for the wrong reason for a long time, corrected to the opposite conclusion ("climate
barely matters") when the spurious absorption response was removed, and then restored on
genuinely different physics when the emission term landed. The scenario's `walkthrough.md`
keeps a full drift archaeology of that history; it is worth reading before quoting any
number in this matrix as settled.

### NIIRS is present and should be read as nothing

Every cell also reports NIIRS at nadir, and every value is a **GIQE-5 extrapolation**
far outside the regression's calibration envelope: these GSDs are 4–17 m against a
calibration range that stops below about 0.8 m. The script says so in its own physics
notes. It is reported because the briefing template asks for it. Treat it as a relative
ordering at best, and never as a rating.

## Numbers: this run versus the committed walkthrough

The runner was re-executed unmodified for this chapter. **142 of the 144 cells reproduce
the scenario's committed `walkthrough.md` matrices exactly**, including every
detectable / not-detectable verdict, every swath-edge flag, the hardest-target identity
and mean (Technical pickup, 199 km) and the easiest (fuel bladder farm, 991 km).

Two cells differ, both on sensor B, and both are reported here with both values rather
than reconciled away:

| Cell | Walkthrough, as committed | This run | Δ |
|---|---:|---:|---:|
| Fighter aircraft, `haze` | 1,029 km | **1,033 km** | +4 km (+0.39 %) |
| Small UAV (parked), `clear` | 685 km | **686 km** | +1 km (+0.15 %) |

Both shifts are below the bisection's own stated resolution — nine steps give ~0.13° in
zenith, about 0.5 % in range — so a sub-resolution change in the underlying physics is
enough to move a bisection midpoint across a reporting boundary. Neither changes a
verdict, a ranking, or a conclusion in this chapter. They are recorded because a
detection matrix that is re-run and silently re-quoted is how two results-affecting
landings previously passed through this scenario unremarked; nothing in the machine
baselines covers a script-side SCNR bisection.

A related inconsistency, noted in passing and not corrected here: the walkthrough's
own refresh note attributes its single moving cell to "sensor A's small UAV,
686 → 685 km", but sensor A's Small UAV is `not detectable` in every column in both the
walkthrough's own table and this run. The cell it describes is sensor B's, which this run
reports back at 686 km. The walkthrough's physics discussion also quotes "688 vs 695 km"
for the Small UAV and MBT tank on sensor B where its own table says 685 and 696; the
prose rounds, the table is the record.

## The takeaway

1. **Sensor B detects all twelve targets in all four conditions; sensor A detects one.**
   The difference is GSD, hence pixel footprint, hence fill fraction — a 17× ratio in
   footprint area.
2. **The hardest target is the one nearest the weighted-background null**, not the
   smallest or the coldest. Right now that is the Technical pickup at a 199 km mean.
   It is a model-dependent verdict.
3. **Climate sets range, not target set.** `arctic_clear` leads by 25–35 % because a cold
   dry column emits less thermal path radiance and therefore carries less clutter.
4. **Detection here is clutter-limited, not noise-limited.** Noise-limited SNR exceeds 19
   in every cell of the matrix and discriminates nothing.
5. **The recoverable margin is in the detection model, not the sensor.** A multi-pixel
   matched filter would bring back the targets the single-pixel SCNR marks undetectable.

## The same study in the GUI

The scenario ships a GUI-openable baseline of one representative cell,
`inputs/4.1_target_detection_matrix.gui.yaml`, with headline metrics snapshotted in
`.gui.expected.json` — enough to open a single configuration in the window and inspect
what the batch does 144 times in a loop: the forced sub-pixel regime, the fill fraction,
the in-pixel background, and the clutter term the criterion is limited by. The scenario's
`gui_workflow.md` specifies what a full matrix workflow would need: a **Target Library**
import that shows the derived `projected_area_m2` column and flags duplicate or
non-numeric rows before accepting; a deprecation *banner* rather than a console warning
when sensor C's aged `platform.h_sensor` is loaded; a matrix builder with target,
atmosphere and sensor axes backed by the same `BatchRunner`; a progress grid that fills
in cell by cell with failures shown in red rather than dropped; per-sensor result
heatmaps carrying the "not detectable" and swath-edge states and a GIQE-extrapolation
caveat chip on the NIIRS column; and a worst-case panel that explains the EE_box
occlusion mechanism in place rather than leaving the reader to infer it. The two
committed figures, `outputs/fig1_detection_range_matrix.png` and
`outputs/fig2_nadir_scnr_by_target.png`, are what that panel would show.
