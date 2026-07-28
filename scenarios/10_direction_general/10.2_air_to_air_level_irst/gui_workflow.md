# Scenario 10.2 — GUI Workflow

**Persona context.** Sarah is sizing an airborne MWIR IRST and needs to see —
before she trusts a single number — that the GUI understood her scene as an
*air-to-air level arm* and not as a space-to-ground look with a typo in it.

This workflow deliberately exercises the **Phase-4 direction-aware surfaces**:
the scene-class chip and its optional assertion, the level composition of the
schematic, the θ_o and ζ_low angle arcs, and the Δh sag pill.

Baseline artifact: `inputs/10.2_air_to_air_level_irst.gui.yaml` (generated from
`scripts/run_air_to_air_level_irst.py::make_sensor()` by
`scenarios/tools/emit_gui_yaml.py` — never hand-written).

---

## Step 1 — Open the baseline

**Action:** `File → Open YAML…` → `inputs/10.2_air_to_air_level_irst.gui.yaml`

**What Sarah sees:** the stage strip populates; the Geometry chip is first.
No results yet — the metric readouts are empty rather than stale.

**Script window equivalent:**

```python
from radiant.api import Sensor
sensor = Sensor.from_yaml("inputs/10.2_air_to_air_level_irst.gui.yaml")
```

---

## Step 2 — Geometry → **Inputs** tab: the scene-class chip (Phase-4 surface #1)

**Action:** click the **Geometry** stage chip; the *Inputs* sub-tab opens.

**What Sarah sees, top card first** (`SceneClassPanel` — the mission-type entry
point, ADR-0011 decision 8):

| Element | Before first evaluate | After evaluate |
|---|---|---|
| Derived chip | neutral placeholder `Scene: evaluate to derive` — never a guess | **`air_to_air`** with its two pieces `air` / `air` |
| `Assert scene class` field | `auto` (not asserted) | unchanged — the assertion is *never* required |
| “Off by default for this scene class” list | empty (no class known) | the ten ground-projection metrics, in physics reading order |

The card reads the derived label **verbatim** from
`stage_outputs["geometry"]`; it never re-derives a band from an altitude.

**The assertion, exercised.** Sarah sets `Assert scene class = air_to_air` via
the shared parameter-editor dialog (one validated `sensor.set` on a throwaway
clone first, so a rejected value never touches the live sensor). Re-evaluate:
nothing changes — the assertion agrees with the derivation.

**Then she proves the guard works.** She changes
`geometry.target_altitude_m` from `10 000 m` to `10 m` (the classic
wrong-magnitude typo) and re-evaluates. The scene now derives `air_to_ground`,
which contradicts the assertion, and `GeometryStage` raises
`GeometrySpecificationError`. The GUI response is three-part and simultaneous:

1. the actionable-error dialog (what / why / action verbatim),
2. a row in the right-rail **Messages** panel,
3. the scene-class card tints (`[state="conflict"]`) and shows the error's
   *what* line beside the chip — the in-place locator, so the contradiction is
   visible where the assertion was made.

She reverts the altitude; the tint clears on the next clean evaluate.

**Units note:** altitudes are entered and displayed in the analyst's chosen
length unit. The vendor card says 10 km; the field shows 10 km if that is the
display unit, and the canonical 10 000 m never has to be typed.

**Script window equivalent:**

```python
sensor.set("geometry.scene_class", "air_to_air")
r = sensor.evaluate()
print(r.stage_outputs["geometry"]["scene_class"])       # 'air_to_air'
print(r.stage_outputs["geometry"]["los_direction"])     # 'level'
```

---

## Step 3 — Geometry → Inputs: the mode forms and the derived readout

**Action:** scroll to the input-mode forms below the scene-class card.

**What Sarah sees:** the viewing family sits in mode **V0** — she entered a
slant range (`geometry.target_range_m = 50 km`), not an angle. The
`viewing_mode` row of the readout says so in words:

> `geometry.target_range_m (level path — chord ⇒ central angle)`

The derived readout is grouped **by reference frame**:

| Group | Rows relevant here | Value at 50 km |
|---|---|---|
| Target frame | `theta_o_rad` (θ_o) | 1.574714 rad = 90.2245° |
| | `incidence_angle_rad` | identical to θ_o on a spherical Earth |
| Ground / platform frame | `eta_rad` (η) | 1.566878 rad = 89.7755° |
| | `slant_range_m` | 50 000 m |
| | `ground_range_m` | 49 922 m |
| | `h_sensor_m` / `h_target_m` | 10 000 m / 10 000 m |
| | `ground_speed_m_s` | 246.93 m/s |
| Resolution | `viewing_mode`, `kinematics_mode`, `solar_illumination` | V0 chord / direct / night |

**The thing to notice:** θ_o is **greater** than 90°. That is the level-arm
signature — both endpoints look slightly *down* at each other because the chord
sags below the constant-altitude shell — and it is the value that used to be
rejected outright.

**Angle-unit note:** the readout renders radians or degrees per the analyst's
display setting; the underlying stage value is always radians.

---

## Step 4 — Geometry → **Schematic** tab: the level composition (Phase-4 surface #2)

**Action:** switch to the **Schematic** sub-tab.

**What Sarah sees:** the 2D orthographic Qt schematic, drawn in the **level
composition** — not the pre-ADR-0011 down-looking layout. Concretely:

- Both endpoints are drawn **apart at the same abstract height**, with the
  ground plane pushed below both (the scene class places the ground plane; the
  composition is chosen from `los_direction`, never from a user switch).
- The sensor and target both carry altitude leader pills (`h_s`, `h_t`), both
  reading **10 km** — the not-to-scale idiom: altitude is *told*, never drawn to
  scale.
- The ground-projection cues that a down-looking scene draws (nadir point,
  ground footprint) are **omitted** — there is no ground scene here.

**Checkpoint:** if the schematic still draws the down-looking layout with the
sensor above and the target on the ground plane, the composition split is
broken; that is a Phase-4 regression, not a cosmetic issue.

---

## Step 5 — Schematic: reveal the **θ_o** and **ζ_low** angle arcs (Phase-4 surface #3)

**Action:** in the schematic's annotation toggles, enable **Path zenith θ_o**
and **Lower-endpoint zenith ζ_low**.

**What Sarah sees:**

| Toggle | Symbol | Frame | Value at 50 km | Where the arc is drawn |
|---|---|---|---|---|
| Path zenith | **θ_o** | target | 90.2245° | at the **target** vertex, from the target's local vertical to the LOS |
| Lower-endpoint zenith | **ζ_low** | target | 90.2245° | at the segment's **lower** endpoint — for a level arm both endpoints qualify and the two arcs coincide |
| Off-nadir | η | ground | 89.7755° | at the **sensor** vertex, from the sensor's nadir |

**The teaching moment this scenario exists for:** θ_o and η are read at
*different vertices of the same spherical triangle* and differ by the
Earth-centre central angle φ = 0.44896° at 50 km. On a level arm the identity is
exact and checkable on screen: θ_o + η = 180.0000°, and θ_o = π/2 + φ/2.

For a level arm `ζ_low = θ_o` exactly (the catalog's `lower_zenith_rad`
down/level branch), and the up-looking form `π − η` returns the same value — the
two branches meet continuously at equal altitudes. Toggling both arcs on and
seeing them coincide *is* the visual proof of that continuity.

**Values come from the stage.** Every arc displays a
`stage_outputs["geometry"]` value; the schematic draws the arc and never
recomputes the angle.

---

## Step 6 — Schematic: the **Δh sag pill** (Phase-4 surface #4)

**What Sarah sees:** a leader pill reading **`Δh  49 m`** — no toggle, it is
drawn whenever the scene is a level arm and hidden otherwise, exactly like the
`h_s` / `h_t` altitude pills.

**Why it is text and not geometry:** the sag is 49 m over a 50 km arm. At any
honest schematic scale it is invisible, so it is *annotated*, in line with the
not-to-scale rule that governs the altitude pills.

**Why it matters:** Δh is the quantity the ADR-0011 horizon guard classifies a
level path on. The pill is the analyst's early warning that a longer arm will
trip the guard.

**The value is not recomputed GUI-side.** The schematic calls
`radiant.core.viewing_triangle.classify_horizon_topology(θ_o, h, h)` and formats
`result.dh_m`, so the pill and the guard cannot disagree. The runner prints the
same number from the same function — 48.97 m at 50 km — which is how this
workflow is verified against the backend.

**Script window equivalent:**

```python
from radiant.core.viewing_triangle import classify_horizon_topology
g = r.stage_outputs["geometry"]
res = classify_horizon_topology(g["theta_o_rad"], g["h_sensor_m"], g["h_target_m"])
print(res.topology, f"{res.dh_m:.2f} m", res.action)   # interior_tangent 48.97 m clean
```

---

## Step 7 — Sweep the range and watch the guard trip

**Action:** `Analysis → Sweep…` → parameter `geometry.target_range_m`,
25 km → 100 km, 16 points.

**What Sarah sees:**

- The sweep table gains SNR, detection range, τ band-mean and well margin
  columns, all unit-labelled.
- From the **75 km** row onward the right-rail **Messages** panel fills with the
  horizon-guard `UserWarning` — one row per warned point, clickable to the full
  quantified text (tangent depression 110.2 m … 195.9 m, tangent altitude,
  the named refraction exclusion, the ±0.5° / 2000 m hard-guard thresholds).
- Returning to the Schematic at a warned point, the **Δh pill** reads
  `Δh  196 m` at 100 km — the same number the warning quotes.

**Checkpoint:** the guard must **warn, not raise**, everywhere in 25–100 km.
A raise means the topology classifier fell back to the angular band instead of
the tangent-depression band, which over-rejects benign level arms.

**Script window equivalent:**

```python
import warnings
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    sweep = sensor.sweep("geometry.target_range_m", [25e3, 50e3, 75e3, 100e3])
print([str(w.message)[:60] for w in caught])
```

---

## Step 8 — Performance: see the metric-relevance flip

**Action:** open the **Performance** stage; look at the metric group cards and
the metric table.

**What Sarah sees:** no GSD, no ground range, no swath width, no access rate, no
NIIRS — the whole ground-projection family is **off by default for an air
target**, and the scene-class card back on Geometry lists exactly those ten
metrics under *“Off by default for this scene class.”* In their place the
**target-plane sample distance** rows are present (2.2222 m at 50 km).

**Override semantics, on the card's face:** these are *defaults*. If Sarah
explicitly ticks the ground-projection group, she gets it computed whatever the
scene class says — an explicitly set `performance.metrics.*` flag always wins.
The card says so, so she is never left guessing whether a metric is missing
because it is irrelevant or because it failed.

---

## Step 9 — Target kinematics: both Gap 111 doors

**Action:** back on Geometry → Inputs, set the target-velocity triple:
`geometry.target_speed_m_s = 298.38 m/s`, `geometry.target_heading_rad = 270°`,
`geometry.target_climb_rad = 2°`.

**What Sarah sees:** `los_rate_mode` in the readout switches from
`platform-only (derived)` to `target velocity (K2)`, and the published
`los_angular_rate_rad_s` goes from 4.9387 mrad/s to **10.9046 mrad/s**.

**Then she cross-checks with the other door.** She *also* sets
`geometry.los_angular_rate_rad_s = 0.0109046 rad/s`. The mode string becomes
`geometry.los_angular_rate_rad_s + target velocity (K2) (consistent)` — the
agreement check accepted them. Typing a wrong value instead (say 0.0218 rad/s)
raises `GeometrySpecificationError` naming both implied values, routed to the
error dialog and the Messages panel.

**Unit note:** the LOS rate is entered and displayed in the analyst's chosen
angular-rate unit (mrad/s here); the canonical rad/s never has to be typed.

---

## Step 10 — Export

**Action:** `File → Export results…` → Excel; `File → Save YAML…` for the config.

The exported workbook carries the same unit-labelled column headers the script
writes (`Range [km]`, `Delta-h [m]`, `omega_LOS K2 [mrad/s]`, …), so the GUI and
scripted paths produce interchangeable artifacts.

---

## Interactive features this scenario needs

| Feature | Why this scenario needs it |
|---|---|
| Scene-class chip updating on every evaluate | The whole point of the class is that it is *derived*; a stale chip is worse than none |
| In-place conflict tint on the scene-class card | A wrong-magnitude altitude typo is the failure this card exists to catch |
| Schematic composition switching on `los_direction` | A level arm drawn as a down-look silently misleads about the whole scene |
| Individually revealable angle arcs (θ_o, ζ_low, η) | The three angles differ by fractions of a degree; showing all of them always is unreadable |
| Δh pill always-on for level scenes | It is the guard's own classification variable and it is invisible at scale |
| Messages panel accumulating sweep warnings | 6 of 16 sweep points warn; a modal dialog per point would be unusable |
| Hover tooltip on suppressed metrics | "Off by default for `air_to_air` — no ground plane at the target" beats a blank row |
| Click-through from a Messages row to the offending sweep point | The warning names a range; the analyst wants that row selected |

## GUI requirements table

| # | Requirement | Priority | Status / reference |
|---|---|---|---|
| 1 | Scene-class card: derived chip + optional assertion + relevance list | Must | Delivered — `widgets/scene_class_panel.py` |
| 2 | Assertion mismatch tints the card and surfaces what/why/action | Must | Delivered — `names_scene_class_assertion` routing |
| 3 | Schematic level/up composition selected from `los_direction` | Must | Delivered — `viewer/schematic_view.py` composition split |
| 4 | θ_o and ζ_low arcs as separate revealable annotations | Must | Delivered — `viewer/angle_catalog.py` |
| 5 | Δh leader pill on level scenes, from the core classifier | Must | Delivered — `_level_sag_label` |
| 6 | Horizon-guard warnings accumulate in Messages, one row per point | Must | Delivered — right-rail Messages panel |
| 7 | Metric relevance driven by the one declarative map, override wins | Must | Delivered — `api.scene_relevance` bridge (guardrail G3) |
| 8 | LOS-rate doors K1/K2 selectable with the agreement check surfaced | Must | Delivered — `los_rate_mode` in the readout |
| 9 | Per-input mission-type dimming (which *inputs* a scene class greys) | Should | **Not implemented** — Gap 85 |
| 10 | Tooltip on a suppressed metric explaining *why* it is off | Should | Not implemented — would read the same relevance map |
| 11 | Click a Messages row to select the sweep point that raised it | Could | Not implemented |
| 12 | Schematic annotation for the target-plane sample distance | Could | Not implemented — the air-target analogue of the GSD footprint cue |
