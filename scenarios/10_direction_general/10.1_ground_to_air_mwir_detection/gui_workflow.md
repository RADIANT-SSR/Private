# Scenario 10.1 GUI Workflow — Ground-to-Air MWIR Detection

## Persona

A range test engineer with a vendor camera datasheet and a pointing plan, who needs to
know what elevation costs him and how far he can hold a small UAS at 10 km — and who has
never entered an *up-looking* scene in RADIANT before.

This workflow is the **`ground_to_air` rider** required by Geometry-Flexibility Phase 4:
it exercises every direction-aware GUI surface that phase shipped — the derived
scene-class chip, the optional `geometry.scene_class` assertion, the up-looking schematic
composition, the θ_o and ζ_low angle arcs, the Δh sag pill's **deliberate absence**, and
the per-class default-off metric preview.

Baseline artifacts (generated, not hand-written — see `scenarios/README.md`):

* `inputs/10.1_ground_to_air_mwir_detection.gui.yaml` — File ▸ Open YAML
* `inputs/10.1_ground_to_air_mwir_detection.gui.expected.json` — verify-gate snapshot
* `scripts/gui_console_10.1_ground_to_air_mwir_detection.py` — scripting-window script

Both are emitted from the runner's module-level factory `make_sensor()` by
`scenarios/tools/emit_gui_yaml.py`; there is no second transcription of the config.

---

## Step 1 — Import the vendor datasheet

* **Action**: File ▸ Import Spreadsheet → `inputs/ground_mwir_tracker_data.xlsx`
* **GUI components**:
  * Sheet selector maps "Camera Datasheet" → optics + detector + readout, "Site and
    Target" → geometry + atmosphere + source, "Pointing Plan" → a sweep axis,
    "MODTRAN Anchors" → a reference table (no parameters).
  * **Unit-conversion preview** (the GUI must show vendor value → canonical value side by
    side before committing — the display-units hard rule):
    * 100 mm → 0.100 m, 200 mm → 0.200 m
    * 75 % → 0.75, 20 °C → 293.15 K, 276.85 °C → 550 K
    * 3000/5000 nm → 3.0/5.0 µm, 0.5 ms → 5.0 × 10⁻⁴ s
    * 10 km → 10 000 m, 60 mm nozzle diameter → 2.827 × 10⁻³ m²
    * **cold shield 90 % efficient → `optics.nearfield_fraction` = 0.10** — the import
      preview must show the *inversion* explicitly, with the vendor convention named.
      This is the single import step that silently changes the answer by 10× if flipped.
* **Alternative**: File ▸ Open YAML → `inputs/10.1_ground_to_air_mwir_detection.gui.yaml`
  reproduces the validated baseline in one action.

---

## Step 2 — Geometry Inputs tab: the scene-class chip (Phase-4 surface)

* **Action**: Geometry Inputs ▸ scene-class card
* **What must be on screen after the first evaluation**:
  * **Derived chip** reading `ground → air (ground_to_air)`, populated verbatim from
    `stage_outputs["geometry"]` (`scene_class`, `observer_class`, `target_class`). Before
    any evaluation the chip shows the neutral placeholder — never a guess.
  * The mode label for the viewing family must read the **direction-general** wording:
    *V1 path zenith — angle at the path's lower endpoint*. For this scene the lower
    endpoint is the **sensor**, and the card should say so; entering 30° here means 30°
    from the sensor's zenith, i.e. 60° elevation.
* **Check to perform**: change `geometry.target_altitude_m` from 10 km to 0.5 km and
  confirm the chip flips to `ground → ground (ground_to_ground)` and the default-off
  metric list (Step 3) changes with it. Change it back.

---

## Step 3 — Assert the scene class, and see the mismatch tint

* **Action**: Geometry Inputs ▸ scene-class card ▸ **Assertion** field (one `sensor.set`
  per edit, `geometry.scene_class`).
* **Pass case**: set `ground_to_air`. The chip becomes
  `ground → air (ground_to_air); assertion agrees`. No warning, no metric change.
* **Fail case**: set `ground_to_space`. The evaluation raises
  `GeometrySpecificationError`, and the GUI must:
  * tint the scene-class card **in context**,
  * show the error's *what* line beside the chip:
    `geometry.scene_class asserts 'ground_to_space', but the altitudes derive
    'ground_to_air' (sensor 0 m ⇒ ground, target 10000 m ⇒ air)`,
  * still surface the full what/why/action in the window dialog and the Messages panel.
* **Why it is in this workflow**: this assertion is the Gap-85 mission-type entry point.
  It is what catches a 10 000 m / 10 000 km typo that pure derivation would render as a
  perfectly self-consistent scene of the wrong class.
* **Clear the assertion back to `auto` before continuing.**

---

## Step 4 — Schematic tab: the up-looking composition (Phase-4 surface)

* **Action**: Schematic tab (2D Qt/QPainter orthographic view — *not* a 3D viewer)
* **What the composition must show for `los_direction = "up"`**:
  * The **ground plane drawn at the sensor**, because `observer_class = ground`. The
    sensor glyph sits *on* the ground plane; the target glyph is above it.
  * The **LOS ascending** from sensor to target — the opposite sense from every
    down-looking scenario in series 01–09.
  * Not-to-scale **leader pills**: `h_s 0 m` and `h_t 10 km`. Altitudes are annotated,
    never drawn to scale.
* **Regression check**: open any down-looking scenario (e.g. 3.4) side by side and
  confirm its render is unchanged — Phase 4 proved byte-identical render parity for
  down-looking scenes, and that parity is what makes the new composition safe.

---

## Step 5 — Angle arcs: θ_o and ζ_low, swept to their own rays

* **Action**: Schematic tab ▸ angle toggles ▸ enable **path zenith θ_o** and
  **lower-endpoint zenith ζ_low**; leave **off-nadir η** on.
* **What must be visible at the nominal point**:

  | Toggle | Symbol | Frame | Value shown | Arc swept at |
  |---|---|---|---|---|
  | `path_zenith` | θ_o | target | **150.05°** | the **target** vertex, to the target's local vertical |
  | `lower_zenith` | ζ_low | target | **30.00°** | the **sensor** vertex — the path's lower endpoint |
  | `off_nadir` | η | ground | **150.00°** | the sensor vertex, from the sensor's nadir |

* **The three checks that make this step worth doing**:
  1. **θ_o is obtuse.** An arc past 90° is the visual signature of an up-looking scene;
     it must render as an obtuse arc, not wrap or clamp.
  2. **Each arc is swept to its own ray.** η, θ_o and ζ_low are read at *different
     vertices* of one spherical triangle. Confirm ζ_low's arc sits at the **sensor** and
     θ_o's at the **target** — not both at one glyph.
  3. **ζ_low = π − η, not π − θ_o.** The displayed ζ_low must be exactly 30.00° (the
     value entered), not 29.95°. The 0.05° difference *is* the Earth-centre central
     angle; at LEO altitudes the same slip is ~2°. The stage is the single source of
     angle truth — the schematic transforms stage outputs, it never recomputes geometry.

---

## Step 6 — The Δh sag pill: confirm it is **absent**, and why

* **Action**: Schematic tab, nominal scene.
* **Expected**: **no `Δh` pill is drawn.** The level-arm tangent-sag pill is a
  level-scene annotation: it appears only when `los_direction = "level"`, where the LOS
  is drawn horizontal and the true tangent depression
  $\Delta h = (R_E + h)(1 - \sin\zeta_{low})$ is invisible on the drawing. A
  `ground_to_air` path has `endpoint_minimum` topology — the foot of the perpendicular
  from the Earth centre lies *outside* the segment — so there is no interior tangent
  point and no sag to report. A Δh pill appearing here would be a defect.
* **To see the pill** (one edit, then undo): set `geometry.sensor_altitude_m` = 10 000 m
  so both endpoints are at 10 km and supply `geometry.target_range_m` = 50 000 m. The
  chip flips to `air → air (air_to_air)`, `los_direction` becomes `level`, the LOS is
  drawn horizontal, and the pill appears reading `Δh ≈ 49 m` at the LOS midpoint. Its
  value comes from the **core** horizon-guard classifier
  (`core.viewing_triangle.classify_horizon_topology`), so the schematic and the guard can
  never disagree. Undo both edits.

---

## Step 7 — Metric relevance preview (Phase-4 surface)

* **Action**: Geometry Inputs ▸ scene-class card ▸ relevance list, and Metrics ▸ group
  toggles.
* **What must be shown**: the ten metrics `ground_to_air` turns **off by default** —
  GSD (cross / along / geometric mean), ground range, swath width, access rate, ground
  projection of the diffraction limit, the pushbroom dwell limit, NIIRS and its
  extrapolated form. The list comes through `radiant.api.scene_relevance`
  (`default_off_metrics`), a pure re-export — the GUI holds **no second copy** of the map
  (guardrail G3).
* **The label must say "default"**, not "unavailable": an analyst who sets a
  `performance.metrics.*` group flag gets that group verbatim.
* **Override demonstration** (do both, in this order):
  1. Metrics ▸ enable **Sampling**. Target-plane sample distance stays present; **GSD
     stays absent**. The GUI must explain the difference — GSD is *undefined* for
     `incidence_angle_rad ≥ π/2`, a computability gate, not a relevance default.
  2. Metrics ▸ disable **Sampling**. Target-plane sample distance disappears too — an
     explicit flag wins in *both* directions.
  3. Return the group to its unset state.
* **What replaced GSD**, visible in the Results ▸ Metrics table:
  `target_plane_sample_distance_{x,y,geometric_mean}_m` = 0.8658 m and
  `diffraction_limit_angular_urad` = 48.80 µrad.

---

## Step 8 — Run the pointing sweep

* **Action**: Sweep ▸ axis `geometry.path_zenith_rad`, values 0 … 60 deg
  (the GUI accepts degrees and converts once; the axis label must read
  **"zenith at the sensor (lower endpoint) [deg]"**, and a secondary axis or tooltip
  should give elevation = 90° − ζ_low, because that is the number on the test card).
* **Results views**:
  * Band-mean transmittance and up-path radiance vs ζ_low — the two must be plotted on
    opposite axes and *move in opposite directions*; that is the Kirchhoff signature and
    it is the single most instructive plot in this scene class.
  * SNR / SCNR vs ζ_low with the threshold = 5 line. The two curves coincide exactly;
    the GUI should annotate why (point-source regime ⇒ contrast SNR ≡ SNR) rather than
    leaving the reader to wonder whether one is missing.
  * Noise breakdown at each point: signal shot / background shot / read / quantization.
    Background shot carries 55 % of the variance at the nominal point.

---

## Step 9 — Detection range, and reading a *named* metric failure

* **Action**: Results ▸ Metrics.
* **Expected**: `detection_range_m` is **absent**, and the Messages panel carries the
  result-typed failure reason from `detection_range_result`. The GUI must show that
  reason verbatim — "…the ray leaves the modelled column only at 115174 m, past the
  11544 m reference range…" — and must not render a blank or a zero.
* **This is the ADR-B convention on screen**: a metric that cannot be computed is
  *absent with a named reason*, never a silent NaN. A GUI that renders `—` with no
  message would be hiding the one thing the analyst needs.
* **The workaround, from the scripting window** (see Step 11): walk the ray with the full
  chain. The runner does this and reports 58.4 km at the nominal 30° pointing.

---

## Step 10 — Horizon guard on screen

* **Action**: drag the pointing angle down toward the horizon.
* **Expected GUI behaviour**:
  * ζ_low ≤ 88.0° — clean.
  * ζ_low = 88.5° — evaluation succeeds and a `UserWarning` lands in the Messages panel:
    "near-horizontal path … 1.5000° from the geometric horizontal". The GUI must show
    warnings, not swallow them; a scene that computed with a caveat looks identical to
    one that did not unless the panel says otherwise.
  * ζ_low = 89.7° — evaluation **raises**; the schematic keeps the last valid scene on
    screen and the error names the ±0.5° hard guard.
* Both thresholds are ADR-0011 decision 6 as refined by `RADIANT_Geometry.md` §4.1.

---

## Step 11 — Scripting window (script equivalents)

Every GUI action above has a one-line scripting equivalent; the console script ships as
`scripts/gui_console_10.1_ground_to_air_mwir_detection.py`.

```python
# the baseline the GUI opened
result = sensor.evaluate()

# Step 2 — the derived chip's source of truth
geo = result.stage_outputs["geometry"]
geo["scene_class"], geo["observer_class"], geo["target_class"], geo["los_direction"]

# Step 3 — the assertion
sensor.set("geometry.scene_class", "ground_to_air")     # agrees -> silent
sensor.set("geometry.scene_class", "ground_to_space")   # raises GeometrySpecificationError
sensor.set("geometry.scene_class", "auto")

# Step 5 — angle truth behind the arcs
import math
math.degrees(geo["theta_o_rad"])              # 150.05  (target vertex, obtuse)
math.degrees(math.pi - geo["eta_rad"])        #  30.00  (sensor vertex = zeta_low)
math.degrees(geo["theta_o_rad"] - geo["eta_rad"])  # 0.0518 = the central angle

# Step 7 — the relevance map, through the sanctioned bridge
from radiant.api.scene_relevance import default_off_metrics
sorted(default_off_metrics(geo["scene_class"]))
sensor.set("performance.metrics.sampling", True)   # override wins; GSD still absent

# Step 8 — the sweep
sensor.sweep("geometry.path_zenith_rad", [math.radians(d) for d in (0, 10, 20, 30, 40, 45, 50, 60)])

# Step 9 — the named failure
result.stage_outputs["performance"]["detection_range_result"].failure_reason
```

---

## GUI requirements table

| # | Requirement | Priority | Status / reference |
|---|---|---|---|
| 1 | Scene-class chip populated verbatim from `stage_outputs["geometry"]`, neutral placeholder before evaluation | High | Shipped — Phase 4 `scene_class_panel.py` |
| 2 | `geometry.scene_class` assertion field; agreeing value silent, mismatch tints the card in context and shows the *what* line | High | Shipped — Phase 4 |
| 3 | Schematic composes by `los_direction`: ground plane at the observer, LOS ascending for `up` | High | Shipped — Phase 4 `schematic_view.py` |
| 4 | θ_o arc renders obtuse; θ_o and ζ_low arcs swept to their **own** vertices | High | Shipped — Phase 4 angle catalog |
| 5 | ζ_low displayed as π − η for up-looking (not π − θ_o) | High | Shipped — `angle_catalog.lower_zenith_rad` |
| 6 | Δh sag pill drawn **only** for `los_direction = "level"` | Medium | Shipped — `_level_sag_label` |
| 7 | Per-class default-off metric preview via `radiant.api.scene_relevance`, labelled "default" | High | Shipped — Phase 4 |
| 8 | Import preview shows the cold-shield **inversion** (blocked % → passed fraction) | High | **Gap** — no scenario-level import mapping exists yet; the runner does it in code |
| 9 | Sweep axis labelled "zenith at the sensor (lower endpoint)" with an elevation secondary readout | Medium | **Gap** — generic parameter-name axis labels today |
| 10 | Absent metrics shown with their `failure_reason` in the Messages panel, never blank | High | Needed for scenario G10.1-1 to be readable in the GUI |
| 11 | `UserWarning`s (horizon shoulder, saturation) surfaced in Messages, not swallowed | High | Shipped — Messages panel |
| 12 | Detection-range walk-the-ray helper available from the scripting window | Low | Scenario-side today (`run_ground_to_air_mwir_detection.py`); see gap G10.1-1 |
