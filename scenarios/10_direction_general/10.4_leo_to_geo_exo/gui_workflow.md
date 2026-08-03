# Scenario 10.4 GUI Workflow — LEO → GEO up-looking space-to-space SDA

## Persona

Raj, mission planner on an SDA task force. He has a vendor telescope datasheet,
an FPA datasheet, and a signature-working-group estimate for a reference GEO
communications bus. He needs to know whether a 500 km LEO host can detect that
bus in eclipse, out to what range, and whether the payload must rate-track.

**What this workflow stresses:** every Geometry-Flexibility **Phase-4**
direction-aware GUI surface. This is the first scenario in the GUI campaign whose
observer is in space *and* whose target is in space, and whose LOS points **up** —
so the scene-class chip, the up-looking schematic composition, and both new angle
arcs all have to be right at once.

---

## Step 1 — Import the vendor workbook

- **Action**: `File > Import Spreadsheet` → `inputs/sda_leo_to_geo_sensor_data.xlsx`
- **GUI components**:
  - Sheet mapping: *Telescope Datasheet* → Optics; *FPA Datasheet* → Detector +
    Readout + Spectral Integration; *Mission Geometry* → Geometry;
    *Target Signature* → Source; the two sweep sheets → sweep axes.
  - **Unit conversion highlights** (the GUI must show vendor and canonical side
    by side, R-UNITS):
    - Entrance pupil diameter: 350 mm → 0.35 m (÷ 1000)
    - Effective focal length: 2100 mm → 2.1 m (÷ 1000)
    - Optical transmission: 60 % → 0.60 (÷ 100)
    - Central obscuration: 25 % → 0.25 (÷ 100)
    - Bench temperature: −93.15 °C → 180 K (+ 273.15)
    - Full well: 100 ke- → 1.0 × 10⁵ e- (× 1000)
    - Integration time: 500 ms → 0.5 s (÷ 1000)
    - Band: 3500 / 5000 nm → 3.5 / 5.0 µm (÷ 1000)
    - Sensor orbit altitude: 500 km → 5.0 × 10⁵ m (× 1000)
    - Target orbit altitude: 35 786 km → 3.5786 × 10⁷ m (× 1000)
    - Sensor-side path zenith: 0° → 0 rad (× π/180)
    - Target temperature: 6.85 °C → 280 K (+ 273.15)
- **Equivalent one-liner** (scripting window):
  ```python
  import run_leo_to_geo_exo as r
  sensor = r.make_sensor()
  ```
  `make_sensor()` is the module-level factory the GUI baseline
  (`inputs/10.4_leo_to_geo_exo.gui.yaml`) is generated from — one action, one API
  call.

---

## Step 2 — Geometry → **Inputs** tab: the scene-class chip and the assertion

This is the Phase-4 entry point and the first thing Raj should look at.

- **GUI components** (top card of the tab, `SceneClassPanel`):
  1. **Derived chip** — after the first evaluate it must read
     **`space_to_space`**, with its two pieces `observer_class = space` /
     `target_class = space` and the derived LOS direction **`up`**. Before the
     first evaluate the chip shows a neutral placeholder, never a guess.
  2. **Asserted field** — the optional `geometry.scene_class` enum. This
     scenario *sets* it to `space_to_space`. Editing it opens the shared
     `ParameterEditorDialog`, validates on a throwaway clone, and re-evaluates.
  3. **Relevance block** — the metrics this class turns off **by default**, read
     through the `radiant.api.scene_relevance` bridge. For `space_to_space` it
     must list exactly ten: `access_rate_m2_s`, `diffraction_limit_ground_m`,
     `ground_range_m`, `gsd_along_track_m`, `gsd_cross_track_m`,
     `gsd_geometric_mean_m`, `max_integration_time_s`, `niirs`,
     `niirs_extrapolated`, `swath_width_m`. The card must say on its face that
     these are *defaults* — an explicitly set `performance.metrics.*` group flag
     always wins.

- **Assertion-mismatch exercise (do this one deliberately)**: change the sensor
  orbit altitude from `500 km` to `500 m` while leaving the assertion at
  `space_to_space`. Expected: the next evaluate raises
  `GeometrySpecificationError`, the card tints `[state="conflict"]`, the error's
  *what* line appears **beside the chip** (asserted `space_to_space` vs derived
  `ground_to_space`, both altitudes named), and the full what/why/action lands in
  the window dialog and the Messages panel. Restore 500 km and re-evaluate: the
  tint clears. This is the CU-093 redundant-entry pattern doing the job it exists
  for — catching a wrong-magnitude altitude typo that pure derivation would
  render as a perfectly self-consistent scene of the wrong class.

- **Input-mode form** — the viewing family must resolve to the *lower-endpoint*
  door: `geometry.path_zenith_rad` labelled as the angle **at the sensor** (ζ_low),
  not at the target. The `viewing_mode` readout string must say so:
  `geometry.path_zenith_rad (up-looking — angle at the sensor, the lower endpoint)`.

- **Derived readout** (`GeometryReadout`, grouped by reference frame — every value
  with its unit):
  - *Target-frame angles*: θ_o = 3.141593 rad, θ_i = 3.141593 rad
  - *Ground / platform frame*: η = 3.141593 rad, R = 3.5286 × 10⁷ m,
    ground range = 0.0 m, h_sen = 5.0 × 10⁵ m, h_tgt = 3.5786 × 10⁷ m
  - *Resolution*: illumination `night`, viewing mode as above, kinematics mode,
    `los_rate_mode`

- **Script-window equivalents**:
  ```python
  g = sensor.evaluate().stage_outputs["geometry"]
  g["scene_class"], g["observer_class"], g["target_class"], g["los_direction"]
  from radiant.api.scene_relevance import default_off_metrics
  sorted(default_off_metrics(g["scene_class"]))
  ```

---

## Step 3 — Geometry → **Schematic** tab: the up-looking composition

The schematic is a **not-to-scale** 2D QPainter orthographic line drawing
(ADR-0007 as superseded 2026-07-14 — 2D, never VTK/PyVista). Magnitudes appear
only as leader-label text; direction is faithful.

- **Composition to verify** (`los_direction = "up"`, `observer_class = "space"`):
  1. The **sensor is the path's lower endpoint** and is anchored at the
     elevated abstract height, *not* on the ground plane. The target is carried
     **above** it along the θ_o ray, so the SENSOR → TARGET vector visibly
     **ascends**.
  2. **Both-endpoints-elevated cue** — this is the space-observer case, so the
     ground plane sits *below both* glyphs with clear air between it and the
     sensor. (Contrast the ground-to-air scene, where the sensor sits **on** the
     ground plane. Same `up` composition, different anchor, selected by
     `observer_class` alone.) Nothing in the schematic is translated by the
     metric altitude — 500 km and 35 786 km share one abstract lift.
  3. **Altitude leader pills** — `h_s` = 500 km and `h_t` = 35 786 km as text.
     The target-altitude pill must be shown (`show_target_altitude` is true for
     any ascending composition, independent of the airborne-target test).
  4. **No sun geometry drawn** — illumination is `night`, so nothing
     sun-derived renders. Raj should see this rather than an inert amber vector.

- **Angle arcs** (bottom-left `AngleToggleOverlay`, one checkbox per catalog
  entry, grouped by reference frame). Reveal these two:
  - **θ_o (`path_zenith`, target-frame)** — value pinned verbatim from
    `stage_outputs["geometry"]["theta_o_rad"]`: **180.000°**. The arc is drawn at
    the *target* vertex. For the vertical case it is the degenerate anti-zenith
    arc; open the ζ_low = 30° variant (Step 5) to see it as a real arc at
    175.326°.
  - **ζ_low (`lower_zenith`, target-frame group)** — the path zenith at the
    **lower** endpoint, i.e. at the LEO sensor: **0.000°** for the vertical case.
    Its arc is drawn at the *sensor*, on the opposite scene azimuth from the
    target-anchored arcs, because that is where the ray runs back toward the
    target.
  - **Verify the transform, not just the number**: for an up-looking scene
    ζ_low = **π − η**, not π − θ_o. At ζ_low = 30° the readout must show
    η = 150.000° and ζ_low = 30.000° while θ_o = 175.326° — so π − θ_o would be
    4.674°, a 25° error. If the GUI ever shows 4.674° for ζ_low, the catalog
    transform has regressed.
  - η (`off_nadir`, ground-frame) may also be revealed; it reads 180.000° here,
    which is correct and is *why* ζ_low is 0°.

- **Δh sag pill — the negative check.** The level-arm tangent-sag leader pill
  (`LEVEL_SAG_SYMBOL = "Δh"`) must be **absent** for this scenario. It is drawn
  only when `los_direction == "level"`; this scene is `up`, and there is no
  tangent sag to report because the ray climbs monotonically away from Earth.
  Confirm no `Δh` pill appears. To see the pill *present* for comparison, load a
  level scene (equal altitudes, e.g. the 200 km air-to-air arm at 10 km, where
  Δh ≈ 784 m) — that is the level-composition scenario of this series, not this
  one. Verifying the pill's **absence** here is what proves the schematic is
  keying off the derived direction rather than always drawing it.

- **Orthographic drag** — left-drag rotates yaw/pitch. The ascending SENSOR →
  TARGET vector must stay ascending at every camera orientation.

- **Script-window equivalents**:
  ```python
  import math
  g = sensor.evaluate().stage_outputs["geometry"]
  math.degrees(g["theta_o_rad"]), math.degrees(g["eta_rad"])
  math.degrees(math.pi - g["eta_rad"])   # zeta_low, the schematic's transform
  ```

---

## Step 4 — Atmosphere screen: prove the vacuum path

- **GUI components**:
  - Model selector shows `exo`; the backend badge must indicate the **vacuum /
    no-atmosphere sub-case** (both endpoints above `h_atm_top` = 100 km), and
    every column knob (standard atmosphere, visibility, water vapour) must be
    **dimmed as inapplicable** rather than merely ignored.
  - Transmittance plot: a flat line at τ = 1.0 across 3.5–5.0 µm, axis labelled
    `Transmittance [--]` vs `Wavelength [µm]`.
  - Path-radiance plot: identically 0 W/m²/sr/µm.
  - LOS-termination badge: **cold space** (not sky, not ground), which is what
    selects `ColdSpaceBackground`.
- **Interactive check**: hovering the τ trace must report exactly `1.0000`, not
  `0.9999` — this is an identity, and the tooltip formatting must not disguise a
  regression.
- **Script window**:
  ```python
  q = sensor.evaluate().stage_outputs["atmosphere"]["atm_quantities"]
  import numpy as np
  np.array_equal(q.tau_up, np.ones_like(q.tau_up)), np.array_equal(q.L_path_up, 0 * q.L_path_up)
  ```

---

## Step 5 — Run and read the headline metrics

- **Action**: `Run` (or `Evaluate`)
- **Outputs readout** (every value with its unit):
  - Regime badge: **Point source** (final, from OpticsStage)
  - `SNR` = 24.52 [--]
  - `detection_range_m` = 9.002 × 10⁷ m (display in km via the unit selector —
    90 015 km; the GUI shows the analyst's chosen unit, no mental maths)
  - `target_plane_sample_distance_geometric_mean_m` = 302.45 m
  - `nedt_K` = 1.005 K — present, but the GUI should not headline it for a
    point-source scene (it is a pixel-filling contrast sensitivity; this target
    fills 0.02 % of a pixel)
  - **The ten ground-projection metrics must be absent from the metric grid**,
    and the Metrics panel must explain *why* by pointing at the scene-class
    relevance card rather than showing ten blank cells.
- **Noise budget panel**: signal shot 34.31, dark shot 22.36, read 25.00,
  quantization 1.76, total 48.01 e- RMS — and **background shot exactly 0 e-**,
  which the panel should annotate as "cold-space termination", not hide.
- **Messages panel**: must carry **exactly one** entry for this run —
  CU-261/265's inert-optics-temperature report (`optics.optics_temperature_K =
  180 K` is set while `optics.scalar_emissivity` is 0, so the bench temperature
  contributes nothing). The Rule-4 dual-path consistency check passed
  (2.3 × 10⁻⁴ vs 2.0 × 10⁻² tolerance, 86× margin) and contributes no message. If
  a Rule-4 warning ever appears on this scene class, a spatial degradation has
  been added to one path and not the other.

---

## Step 6 — Kinematics: the two Gap 111 doors

- **GUI components** (Geometry → Inputs, kinematics group):
  - **K1** `geometry.los_angular_rate_rad_s` — direct entry. Display in µrad/s
    via the unit selector: the nominal scenario carries the **1 % rate-track
    residual**, 1.287 µrad/s.
  - **K2** `geometry.target_speed_m_s` / `target_heading_rad` /
    `target_climb_rad` — the target-velocity triple.
  - The `los_rate_mode` readout names which door(s) resolved the rate. With both
    set and agreeing it must read
    `geometry.los_angular_rate_rad_s + target velocity (K2) (consistent)`.
- **Two-door disagreement exercise**: with both doors set, change the K1 value by
  10 %. Expected: an actionable disagreement error naming both candidates and
  their values in rad/s (ADR-0006 rule 2, 1 % tolerance) — the same pattern the
  viewing-angle doors use.
- **Open-loop comparison**: set K1 to the full 128.709 µrad/s. Expected:
  `platform.smear_width_m` = 1.351 × 10⁻⁴ m, which the Platform screen should
  also express in **pixels (7.51 px)** beside the metres; EE_box collapses
  0.2232 → 0.0542 and SNR 24.52 → 7.61. This is the scenario's design driver and
  must be visible in one screen.
- **Script window**:
  ```python
  s2 = r.Sensor.from_dict(r.make_config(kinematics="open_loop"))
  out = s2.evaluate()
  out.stage_outputs["geometry"]["los_rate_mode"]
  out.stage_outputs["platform"]["smear_width_m"] / 18e-6   # px
  ```

---

## Step 7 — Sweeps and trade charts

- **Action**: `Analysis > Sweep`
- **Axis 1 — integration time**, 5 … 1000 ms, run twice (rate-tracked and open
  loop). Chart: smear [pixels, log] over SNR [--], x-axis `Integration time [ms]`.
  The open-loop SNR **maximum at 250 ms** must be visible; the GUI should mark it
  as a stationary point rather than leaving Raj to eyeball it.
- **Axis 2 — sensor-side path zenith ζ_low**, 0 … 60°. Chart: θ_o and η [deg]
  vs ζ_low [deg] with the π and π/2 reference lines, plus slant range and ground
  arc [km]. The **π/2 horizon-guard band must be drawn** so the analyst can see
  how far this scene family sits from it — no guard fires anywhere in the sweep.
- **Interactive features**:
  - Hover a sweep point → full parameter set + the derived scene class for that
    point (sweeps may cross class boundaries; the chip must follow the selected
    point).
  - Click a point → re-binds the Schematic tab to that geometry, so the arcs
    animate across the near-π family.
  - Drag the SNR = 5 detection threshold to re-solve `detection_range_m` live.

---

## Step 8 — Export

- `File > Export Results` → Excel (Nominal / Integration Sweep / Zenith Sweep
  sheets, headers carrying units), PNG figures, and a YAML snapshot
  (`Sensor.to_yaml(scope="inputs")`) that reloads to the same metrics.

---

## GUI requirements table

| # | Requirement | Priority | Notes / reference |
|---|---|---|---|
| 1 | Scene-class chip shows the **derived** class + both bands + LOS direction, never a guess before the first evaluate | Must | `SceneClassPanel`, ADR-0011 dec. 8 |
| 2 | Optional `geometry.scene_class` assertion editable from the same card; mismatch tints the card and shows the *what* line in place | Must | CU-093 pattern |
| 3 | Relevance block lists the class's default-off metrics from the `radiant.api.scene_relevance` bridge, labelled as *defaults* | Must | Guardrail G3 — one map, never transcribed GUI-side |
| 4 | Schematic composition keyed by derived `los_direction`; up-looking anchors the **sensor** as lower endpoint | Must | `schematic_view.build_scene` |
| 5 | Both-endpoints-elevated cue for a **space** observer (ground plane below both glyphs) | Must | `_lower_endpoint_z`, `observer_class` |
| 6 | θ_o arc drawn at the target vertex, value verbatim from the stage | Must | `angle_catalog.path_zenith` |
| 7 | ζ_low arc drawn at the **sensor**, value = π − η for an up-looking scene (never π − θ_o) | Must | `angle_catalog.lower_zenith_rad` |
| 8 | Δh sag pill **hidden** for non-level scenes; present only for `los_direction == "level"` | Must | `_level_sag_label` |
| 9 | Viewing-mode readout states that the entered zenith is at the **lower endpoint** | Must | ADR-0011 dec. 3 |
| 10 | Atmosphere screen shows the exo **vacuum** sub-case and dims inapplicable column knobs; τ tooltip reads exactly 1.0000 | Must | Rule 17 — no disguised identity |
| 11 | LOS-termination badge (ground / sky / cold space) shown on the Atmosphere or Source screen | Should | ADR-0011 dec. 9 |
| 12 | Metric grid omits the ten ground-projection metrics **and explains why**, rather than showing blanks | Must | Gap 96 + G3 |
| 13 | Noise budget annotates the exactly-zero background term as cold-space termination | Should | Avoids "is this broken?" |
| 14 | Smear expressed in **pixels** beside metres on the Platform screen | Should | The design driver is a pixel count |
| 15 | `los_rate_mode` string surfaced; two-door disagreement raises actionably | Must | Gap 111 / ADR-0006 rule 2 |
| 16 | Angular rates selectable in µrad/s as well as rad/s (display-unit symmetry) | Must | R-UNITS hard rule |
| 17 | Sweep charts draw the π/2 horizon-guard band on any angle axis | Should | Makes the ADR-0011 guard visible |
| 18 | Selecting a sweep point re-binds the Schematic tab and the scene-class chip | Should | Sweeps may cross class boundaries |
| 19 | Detection-range card names the solver's noise model (shot-consistent, σ²(R) = S(R) + N₀²) | Should | Gap G10.4-1 closed by CU-263 2026-08-01; the card should still say which model produced the number |
| 20 | Sensor-endpoint velocity entry distinct from ground-track speed for space targets | Should | Gap G10.4-2 — blocked on a schema addition |

---

## Key GUI features exercised

- Scene-class chip, assertion, and mismatch conflict state (Phase 4)
- Scene-class → metric-relevance preview through the sanctioned API bridge
- Up-looking schematic composition with the space-observer elevated anchor
- θ_o and ζ_low angle arcs, including the π − η transform
- Δh sag pill absence as a positive test of direction keying
- Lower-endpoint viewing-mode labelling
- Exo/vacuum atmosphere presentation with identity-preserving tooltips
- Gap 111 K1/K2 kinematics doors with provenance-resolved mode reporting
- Two-axis sweeps with live threshold re-solve and schematic re-binding

## Interpolated-atmosphere availability

Switching **Atmosphere → Model** to `interpolated` works first try — but no MODTRAN data is used: both endpoints sit at or above the 100 km top of the modelled atmosphere, so the whole path is vacuum and the transmittance / path-radiance products are exact identities, whichever backend is selected. The picker pre-selects **`midlat_summer_uplooking_ladder`** so the axes parameter carries a valid value; its coverage line describes the family, not this scene.
