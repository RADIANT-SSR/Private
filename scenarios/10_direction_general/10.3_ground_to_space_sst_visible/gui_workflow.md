# GUI workflow — scenario 10.3 (ground-to-space SST, visible)

**Persona context.** A space-surveillance site operator has a tasking card for a
700 km LEO object in the evening terminator window and needs, in one sitting: proof
that the tool understands "telescope below, target above", the angles the mount
actually points at, an SNR for the pass, and an honest read on whether the night's
seeing or the aperture is the limit.

This scenario is the GUI's **`ground_to_space` up-looking exercise**. It is the class
that puts the sensor at the *bottom* of the viewing triangle, drives θ_o obtuse, and
turns the ground-projection metric family off. Every Phase-4 direction-aware surface
is touched below.

Everything the operator does maps 1:1 to a scripting-API call (§ *Script window*).

---

## Step 1 — Import the tasking card

**Action:** `File → Open Configuration…`, or build it from the vendor workbook with
the scenario runner's factory.

**GUI components.** Standard file dialog; the right-rail *Messages* panel stays empty
on a clean load.

**Unit-conversion highlights the operator must see on screen.** The GUI must render
each field in the unit the operator typed, never in canonical units (HARD RULE —
display units are symmetric with entry):

| Field | Shown as | Stored as |
|---|---|---|
| Entrance pupil | 1000 mm | 1.000 m |
| Focal length | 10 000 mm | 10.000 m |
| Filter band | 400–900 nm | 0.400–0.900 µm |
| Exposure | 5 ms | 0.005 s |
| Object altitude | 700 km | 7.00 × 10⁵ m |
| Pointing zenith | 20° | 0.34907 rad |
| Solar depression | 12° below horizon | θ_s = 102° = 1.78024 rad |

The solar-depression → solar-zenith conversion is the one an SST operator will get
wrong if it is hidden. The Geometry screen must show **both**: the entered depression
and the derived θ_s, with the identity θ_s = 90° + δ visible on hover.

## Step 2 — Geometry ▸ Inputs: the scene-class steering card

**Action:** select the **Geometry** stage, **Inputs** tab. The `SceneClassPanel` leads
the tab.

**What the operator sees, verbatim from `stage_outputs["geometry"]`:**

- **Derived class chip:** `ground_to_space` — with the two halves beside it,
  `observer_class = ground` / `target_class = space`. Pre-evaluate the chip shows the
  neutral placeholder, not a guess.
- **Assertion field** (`geometry.scene_class`, the mission-type entry point). The
  operator types `ground_to_space`; the card stays neutral and the next evaluate is
  silent.
- **Relevance preview** — the ten metrics this class turns off by default, read
  through the `radiant.api.scene_relevance` bridge with human labels:
  GSD (cross-track / along-track / geometric mean), swath width, ground range,
  ground-projected diffraction limit, access rate, max integration time, NIIRS and
  NIIRS-extrapolated. The card must also state that an explicitly-set
  `performance.metrics.*` group flag still wins.

**The assertion is worth exercising deliberately here.** The site is at **900 m MSL**
and the ground/air band edge is **1 km**. Have the operator mistype the site elevation
as 1900 m and re-evaluate: the derived class flips to `air_to_space`, the assertion
disagrees, and the card must go to `[state="conflict"]` with the
`GeometrySpecificationError` what-line beside the chip —

> `geometry.scene_class asserts 'ground_to_space', but the altitudes derive
> 'air_to_space' (sensor 1900 m ⇒ air, target 700000 m ⇒ space)`

— rather than silently computing a self-consistent scene of the wrong class. This is
the whole point of the optional assertion and it should be in the demo script.

**Mode form.** Below the card, `GeometryModeForm` must show the ADR-0011 wording:
the entered angle row reads **"Path zenith at lower endpoint (V1)"**, not "off-nadir".
For this scene the lower endpoint is the *telescope*, which is exactly what the mount
reports, so the operator types the tasking card's 20° with no mental translation.

**Derived readout** (frame-grouped, symbols + units, verbatim):

| Symbol | Value | Note the GUI must carry |
|---|---|---|
| `los_direction` | `up` | derived from the altitude pair, never a switch |
| θ_o | 162.0489° | canonical target-side path zenith, **obtuse** |
| ζ_low | 20.0000° | zenith at the telescope (the entered angle) |
| η | 160.0000° | interior angle at the sensor |
| slant range | 739.156 km | |
| ground range | 227.828 km | |
| incidence angle | 162.0489° | ≡ θ_o on a spherical Earth |
| θ_s | 102.000° | sun 12° below the site horizon |

## Step 3 — Geometry ▸ Schematic: the up-looking composition

**Action:** switch to the **Schematic** tab (`GeometryViewer`, 2D orthographic
QPainter canvas — not 3D).

**Composition the operator must get for this class** (keyed by the stage-derived
`los_direction = "up"`, read verbatim, never re-derived):

- The **sensor glyph sits ON the ground plane** — `observer_class = ground` puts it
  there rather than at the abstract off-ground height used for an airborne observer.
- The **target is carried above it along the θ_o ray**, so the SENSOR→TARGET vector
  **ascends**. This is the visual proof the operator needs that the tool is not
  quietly modelling a down-look.
- The **sensor→ground and sun→ground dashed vectors are absent.** They are drawn only
  for a down-looking elevated target; looking up, the LOS never terminates on the
  ground and the footprint below a space target is not a scene participant. Drawing
  them would assert a ground interaction this scene does not have.
- **Both altitude leader pills are shown** — `h_s ≈ 0.9 km` and `h_t = 700 km` — since
  both endpoints are drawn apart. Magnitudes are leader-label text; the drawing is
  deliberately **not to scale** (a 700 km target beside a 0.9 km site cannot be drawn
  to scale and be legible).
- **No Δh sag pill.** The Δh tangent-sag pill is a *level-arm* annotation: it reports
  the LOS's tangent-height depression for an `interior_tangent` topology. This scene
  is an ordinary ascending slant (`endpoint_minimum`), so the pill is correctly
  absent. The operator sees it in the air-to-air level scenario, not here. If it ever
  appears on an up-looking slant, that is a bug.

## Step 4 — Reveal the two angle arcs

**Action:** on the `AngleToggleOverlay` (bottom-left of the canvas), tick **θ_o (path
zenith)** and **ζ_low (lower-endpoint zenith)**.

**What must be drawn — and this is the subtle part of the whole class:**

- The **θ_o arc is swept at the TARGET**, from the target's local zenith to the
  target→sensor ray, and its value pill reads **162.0°**. An obtuse arc that visibly
  wraps past the horizontal is correct, not a rendering error.
- The **ζ_low arc moves to the SENSOR glyph** (`_arc_apex` follows the lower
  endpoint), sweeping from the site's local zenith to the sensor→target ray, pill
  **20.0°**.
- The two arcs are swept to **different rays** (`theta_o_dir` vs `zeta_low_dir`),
  because they are read at different vertices of one triangle. They differ by the
  Earth-centre central angle φ = 2.05°, so `ζ_low ≠ 180° − θ_o` — 180° − 162.0489° is
  17.95°, not 20°. Sharing one ray would pin a stage-true number on a visibly wrong
  arc.
- The ζ_low value has **no single stage key**; the viewer derives it through
  `angle_catalog.lower_zenith_rad`, which for an up-looking scene is **π − η**
  (η = 160.0000° → ζ_low = 20.0000°) and *not* π − θ_o. The operator never sees that
  distinction, but a 2° error in a pointing angle is exactly the sort of thing that
  ends up in a mount-model bug report, so the arc must be right.
- Also reveal **θ_s** to see the sun below the site horizon (102°) — the annotation
  that makes the terminator window legible at a glance.

## Step 5 — Atmosphere: the column and the solar leg

**Action:** select the **Atmosphere** stage.

The operator needs three readouts and one caveat:

| Readout | Value | Why it matters here |
|---|---|---|
| τ_up(λ) plot | band-mean 0.5330; 0.4492 at 0.55 µm | the observer leg, telescope → h_atm_top |
| τ_sun | 1.0000 | vacuum solar leg: the object is above h_atm_top |
| r₀ | 19.820 cm at 0.650 µm | profile-driven (HV-5/7), not entered |

**GUI requirement (new).** The Atmosphere screen must show the **GF-9 illumination
verdict** in words — "object at 700 km is above the terminator shadow height of
142.3 km ⇒ SUNLIT; solar leg is vacuum" — because that sentence is the difference
between a valid tasking and an eclipse pass. Today it exists only in an INFO log
record (`gaps.md` G12); the panel has nothing to bind to.

**Caveat the Messages panel must carry.** With the intensity door the sky background
is numerically zero (`gaps.md` G3/G4). A screen that plots a flat-zero sky and says
nothing is misleading. Until the engine fix lands, the GUI should surface the
condition as a Messages entry.

## Step 6 — Optics / Platform: seeing versus aperture

**Action:** **Optics ▸ MTF** tab, then **Platform** for the kernel attribution.

The single most useful comparison for this operator is the **system MTF with and
without the turbulence term**, which the GUI can produce by toggling
`atmosphere.cn2_profile` between `hufnagel_valley` and `direct` and keeping both
curves on the axes:

| | with HV-5/7 | without |
|---|---|---|
| MTF at Nyquist (333.3 cycles/mrad) | 0.00862 | 0.46250 |
| PSF FWHM (x) | 35.41 µm | 15.24 µm |
| RER | 0.3317 | 0.7704 |
| EE 3×3 | 0.6246 | 0.9445 |

with the headline in angular units on the sky: seeing FWHM **3.214 µrad (0.663″)**
against a diffraction limit of **0.793 µrad (0.164″)** — a ratio of **4.05**. The
verdict *seeing-limited, not aperture-limited* should be stated in the panel, not left
for the operator to infer.

## Step 7 — Performance: what a space target does to the metric set

**Action:** **Performance** stage.

The grouped metric cards must show the *Sampling / geometry* group **without** GSD or
swath rows, and **with** the target-plane family:

| Metric | Value |
|---|---|
| target-plane sample distance (x, y, geo-mean) | 1.10873 m at the object |
| diffraction limit, angular | 0.7930 µrad |
| SNR | 186.89 |
| detection range | 4 519.0 km |
| Q_center | 0.433 |

The *Interpretability* card is empty (NIIRS is off by class). The card must say
**why** — "turned off by scene class `ground_to_space`" — with a link back to the
Geometry steering card, not simply omit the rows.

`nedt_K` (0.0227 K) is present because the thermal group is on by default; it is
meaningless for a reflective VIS point source. A future refinement would let the
scene-class relevance map default the thermal group off for a reflective target.

## Step 8 — Walk the pass

**Action:** sweep `geometry.path_zenith_rad` over the ladder 0 → 75° and plot τ, r₀
and SNR against it (the three panels of `outputs/zenith_ladder.png`).

The GUI must let the operator drag a threshold line at their acquisition SNR and read
off the elevation at which the pass drops below it. Two guard behaviours should be
demonstrated live:

- At **ζ_low = 88.6°** the chain computes and the *Messages* panel carries the
  quantified refraction warning ("1.4000° from the geometric horizontal … refraction
  is NOT modelled in v1.x").
- At **ζ_low = 89.8°** the evaluate **fails** with an actionable
  `ParameterBoundsError`; the error dialog and Messages must carry the what/why/action
  triple, and the Geometry mode form must highlight the offending selector.

Do **not** sweep past 80° for transmittance work: the air-mass handover artifact
(`gaps.md` G5) makes τ non-monotonic there, and a GUI plot would show a physically
impossible upturn.

---

## Interactive features this scenario needs

| Feature | Why |
|---|---|
| Hover tooltip on θ_o showing "obtuse ⇒ sensor below target's horizon plane" | the obtuse angle is the single most confusing readout in this class |
| Hover tooltip on ζ_low showing "= π − η for an up-looking path; differs from π − θ_o by the central angle φ = 2.05°" | prevents the 2° pointing-model bug |
| Click-through from a greyed metric card row to the Geometry steering card | closes the loop "why is NIIRS missing?" |
| Solar-depression entry field (δ) alongside solar zenith, with live θ_s = 90° + δ | matches how an SST tasking card is written |
| Shadow-height readout keyed to the target altitude, live as δ is dragged | turns the eclipse boundary (25.71° here) into a visible limit |
| Dual-curve MTF overlay (turbulence on/off) held on one axis | the seeing-vs-aperture verdict is a *comparison*, not a number |
| Not-to-scale badge on the schematic | a 0.9 km site and a 700 km target cannot be to scale; the badge prevents mis-reading |

## Script-window equivalents

```python
from radiant.api import Sensor
from radiant.api.scene_relevance import default_off_metrics
import math

# Step 1 — the scenario's validated nominal Sensor (module-level factory)
import sys; sys.path.append("scenarios/10_direction_general/10.3_ground_to_space_sst_visible/scripts")
from run_ground_to_space_sst_visible import make_sensor
sensor = make_sensor()

# Step 2 — scene class: derived chip, then the assertion
result = sensor.evaluate()
geo = result.stage_outputs["geometry"]
geo["scene_class"], geo["observer_class"], geo["target_class"], geo["los_direction"]
sensor.set("geometry.scene_class", "ground_to_space")      # agreeing → silent
default_off_metrics(geo["scene_class"])                     # the relevance preview

# Steps 3-4 — the angles the schematic draws
math.degrees(geo["theta_o_rad"])        # 162.0489  (θ_o arc, at the TARGET)
180.0 - math.degrees(geo["eta_rad"])    #  20.0000  (ζ_low arc, at the SENSOR)
geo["slant_range_m"] / 1e3              # 739.156 km

# Step 5 — atmosphere
atm = result.stage_outputs["atmosphere"]
atm["r0_m"] * 100.0                                        # 19.820 cm
atm["r0_resolution"].detail                                # how r0 was produced
float(atm["atm_quantities"].tau_sun.mean())                # 1.0 — vacuum solar leg
from radiant.atmosphere.solar_shadow import shadow_height_m, sunlit
shadow_height_m(geo["theta_s_rad"]) / 1e3                  # 142.3 km
sunlit(geo["h_target_m"], geo["theta_s_rad"])              # True

# Step 6 — seeing vs aperture
no_turb = sensor.clone().set("atmosphere.cn2_profile", "direct").evaluate()
result.metrics["mtf_system_at_nyquist_x"], no_turb.metrics["mtf_system_at_nyquist_x"]
result.metrics["fwhm_x_m"] * 1e6, no_turb.metrics["fwhm_x_m"] * 1e6      # µm

# Step 7 — metrics
result.metrics["snr"], result.metrics["target_plane_sample_distance_x_m"]

# Step 8 — the pass
sensor.sweep("geometry.path_zenith_rad",
             [math.radians(d) for d in (0, 20, 40, 55, 65, 75)],
             metric="snr")
```

## GUI requirements table

| # | Requirement | Priority | Status / gap |
|---|---|---|---|
| 1 | Scene-class chip renders `ground_to_space` + observer/target halves verbatim | Must | **exists** (`SceneClassPanel`, Phase 4) |
| 2 | `geometry.scene_class` assertion field; conflict tints the card with the error's what-line | Must | **exists** (Phase 4) |
| 3 | Relevance preview through `radiant.api.scene_relevance`, never a GUI-side copy | Must | **exists** (guardrail G3) |
| 4 | Up-looking schematic composition: sensor on the ground plane, target above, ascending LOS, no ground-projection vectors | Must | **exists** (Phase 4, `los_direction`-keyed) |
| 5 | θ_o arc at the target and ζ_low arc at the sensor, on their own rays, with degree pills | Must | **exists** (`_arc_apex`, `theta_o_dir`/`zeta_low_dir`) |
| 6 | Δh sag pill **absent** on an up-looking slant (level-arm only) | Must | **exists** — correct behaviour to verify, not to add |
| 7 | Both altitude leader pills shown for up/level; not-to-scale badge | Should | **exists** (pills); badge is a request |
| 8 | Direction-general mode wording ("Path zenith at lower endpoint (V1)") | Must | **exists** (Phase 4) |
| 9 | Solar-depression entry with live θ_s = 90° + δ | Should | **new** — the SST-native entry form |
| 10 | GF-9 illumination verdict shown in words on the Atmosphere screen | Should | **blocked** — provenance is dropped before `ChainResult` (`gaps.md` G12) |
| 11 | Messages entry when the sky background is structurally zero for the chosen door | Should | **blocked** — engine gaps G3/G4 |
| 12 | Dual-curve MTF overlay (turbulence on/off) on one axis, with the seeing-limited verdict in words | Should | **new** |
| 13 | Live shadow-height readout as solar depression is dragged | Could | **new** |
| 14 | Greyed metric rows explain "off by scene class" and link to the steering card | Should | **new** (today they are simply absent) |
| 15 | Refuse/warn behaviour of the horizon guard surfaces in Messages + highlights the offending mode selector | Must | **exists** (Messages + `geoModeFamily` conflict tint) |

## Interpolated-atmosphere availability

No bundled interpolated-atmosphere family serves this scene: 'midlat_summer_sst_column_fan' is rendered from a fixed lower endpoint at 0 m and carries no 'sensor_altitude_m' axis; this scene asks for 900 m (rows M9-M13 of docs/plans/modtran_run_matrix.csv are the authored, not-yet-run decks that lift this fan's lower endpoint to a 900 m elevated site). Switching **Atmosphere → Model** to `interpolated` therefore produces exactly one Messages-rail advisory saying so — not a sequence of refusals — and the scene stays on `atmosphere.model = 'simple'`, which serves any geometry.
