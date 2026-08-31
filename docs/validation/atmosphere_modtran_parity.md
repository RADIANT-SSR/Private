# Atmosphere Model Parity Against the MODTRAN 6 Run Set

**Truth source**: the owner-run MODTRAN 6 run matrix, `docs/plans/modtran_run_matrix.csv`
(132 authored rows), delivered as tape7 files tracked in git under `modtran/real_runs/`.
**Scope**: measured accuracy of RADIANT's atmosphere backends against that set — model ×
band × geometry class — plus the register of what is still unmeasured.
**Companion documents**: the physics is [`docs/theory/atmosphere_models.md`](../theory/atmosphere_models.md);
the contract is [`docs/architecture/RADIANT_Atmosphere.md`](../architecture/RADIANT_Atmosphere.md).

Every table below names the test that pins it. A number whose only home is a CU record,
with no committed test asserting it, is marked **(record only)** — that is a standing
statement about its verification status, not a footnote.

---

## 0. How to read a parity ratio

Nearly every number here is a **band-mean ratio**. The conventions, once:

**Band mean.** A trapezoid integral of the spectrum over the band, divided by the band
width in µm:

$$\bar{X}_{[\lambda_1,\lambda_2]} \;=\; \frac{1}{\lambda_2 - \lambda_1}\int_{\lambda_1}^{\lambda_2} X(\lambda)\,\mathrm{d}\lambda$$

Where a **band integral** is quoted instead (π·L sky fluxes, the K-ladder radiances), the
division by band width is omitted and the units carry an extra µm. Each table says which.

**Direction of the ratio.** Two conventions are in use, inherited from the records they
came from, and each table states which it uses:

- **model / MODTRAN** — the default. $> 1$ means the model over-reads; $< 1$ under-reads.
- **MODTRAN / model** — used by the species-split tables (§2.3), because the adoption
  criterion was written that way. $> 1$ means the model under-reads.

**Aggregate score.** Where a whole anchor set is summarized, the statistic is the
**RMS $|\ln r|$** over its cells:

$$\mathrm{RMS}|\ln r| \;=\; \sqrt{\frac{1}{N}\sum_{j=1}^{N}\left(\ln r_j\right)^2}$$

The log is what makes over- and under-reading symmetric: $r = 2$ and $r = 0.5$ score the
same. A value of 0.10 corresponds to roughly $\pm 10$ %, 0.30 to roughly a factor 1.35,
0.69 to a factor 2. **RMS $|\ln r|$ is only comparable across two numbers computed over
the same cells** — the anchor sets in §2.1 and §2.4 differ, so their scores are not
interchangeable, and each is labelled with its cell count.

**Standard bands.** VIS 0.45–0.85 µm, NIR 0.85–1.40 µm, SWIR 1.40–2.50 µm, MWIR 3–5 µm,
LWIR 8–12 µm (8–13 µm where a table says so). All model runs are on the profile, aerosol
regime, visibility and water column of the deck they are compared against.

**Both sides are pinned.** In every anchor suite the MODTRAN reference number is asserted
*as well as* the ratio, so a re-staging accident, a parser regression and an unexplained
improvement all fail loud rather than silently re-baselining the record.

---

## 1. The run inventory

| Block | Rows | What it measures | Delivered | Destination |
|---|---|---|---|---|
| **A** profile baseline | A1–A6 | Full-column nadir τ / L_path for all six standard profiles | 6/6 | fixture + library |
| **B** zenith fan | B1–B3 | Full column at LOS zenith 30°/45°/60° — the airmass-axis holdout | 3/3 | fixture + library |
| **C** partial column | C1–C7 | 35 km sensor → ground and partial-column variants (Table C configs) | 7/7 | fixture + library |
| **D** aerosol / water | D1–D6 | Visibility ladder + the H₂O ×0.5/×1/×2 water ladder (the CU-161 calibration set) | 6/6 | fixture, dev |
| **E** sky irradiance | E1–E4 | Ground-level flux runs (IEMSCT=3) with `*_flux.csv` sidecars — the $\omega_{0,\text{eff}}$ and downwelling reference | 4/4 | fixture, dev |
| **F** airborne sensor | F1–F3 | 3 km airborne sensor → ground, nadir | 3/3 | dev, library |
| **G** space partial column | G1–G11 | LEO/GEO sensor → elevated targets (the boost ladder) | 11/11 | library |
| **H** thermal downwelling | H1–H5 | Up-looking zenith thermal sky at the 48.2° diffusivity angle — the CU-155 fit set | 5/5 | fixture + library |
| **I** boost off-nadir | I1–I9 | Space sensor → ground/elevated at 45°/60° LOS zenith | 9/9 | library |
| **J** airborne sensor ladder | J1–J2 | 10 km / 20 km sensor → ground, nadir (the K-block reciprocity partners) | 2/2 | library |
| **K** up-looking partial column | K1–K7 | Ground sensor → targets 1–20 km vertical, plus two 45° slants (K7 elevated lower endpoint) | 7/7 | fixture + library |
| **L** horizontal path | L1–L25 | ITYPE=1 5×5 grid: altitude 0/3/5/10/15 km × range 5–100 km | 25/25 | dev |
| **M** SST full-column fan | M1–M13 | Ground sensor → 100 km top, uniform sec ladder; M6–M8 the 85/88/89.5° probes; M9–M13 the 900 m elevated-site mirror | 13/13 | library (M6–M8 dev) |
| **N** up-looking zenith fan | N1–N10 | Targets 1–20 km × lower-endpoint zenith 48.2°/60° (rectangular with K) | 10/10 | fixture + library |
| **O** upwelling emission anchor | O1–O5 | Down-looking partners of K/N/H on identical columns — the direction-pair set | 5/5 | fixture + library |
| **P** elevated downwelling | P1–P8 | Sky radiance at 48.2° from elevated lower endpoints 1–80 km; P7/P8 the 60/80 km rungs | 8/8 | fixture + library |
| **Q** horizon guard / twilight | Q1–Q8 | Long horizontal arms past the sag thresholds (Q1–Q4), the **refraction on/off pair (Q5/Q6)**, twilight tangent transits (Q7/Q8) | **6/8** | dev |

**Counts.** 132 authored rows; **130 delivered tape7 runs** plus 4 Block-E flux sidecars =
134 delivered artifacts. Batch 1 (A–L) is 88 rows, all delivered 2026-07-17 / 2026-07-26.
Batch 2 as authored at delivery (M1–M8, N, O, P1–P6, Q) is 37 rows, of which 35 were
delivered 2026-08-02. Seven further rows were authored *after* that delivery — M9–M13
(CU-322 intake) and P7/P8 (CU-181 closure) — and were delivered 2026-08-03 and ingested the
same day: M9–M13 as the sibling family `midlat_summer_sst_column_fan_site900m`, P7/P8 as the
measured 60/80 km rungs of the CU-181 downwelling ladder (and as two further nodes of
`midlat_summer_uplooking_sensor_ladder`, which is built from the same runs).

**The two pending rows, and why:**

| Rows | Why pending |
|---|---|
| Q5, Q6 | **Deck-builder gap.** `render_tape5` has no refraction field, so RADIANT cannot express the refraction-OFF leg: Q5.tp5 renders byte-identical to Q3.tp5 and Q6.tp5 to M8.tp5 on purpose. The operator must disable MODTRAN's ray-bending for those two runs and record which switch was used. Q3−Q5 is the interior-tangent half of the refraction calibration; M8−Q6 the endpoint-minimum half at the 0.5° raise-band edge. |

Q7/Q8 (twilight tangent transits) *were* delivered, with Card-3 ANGLE hand-set to 93°/96°
and `LENN = 1` per the matrix instruction, and the hand edit is verified against the matrix
by the Card-3 echo sweep. Both rows are `dev_only`: no family ingests them and no
radiometric parity test consumes them, so the twilight branch's transmittance is still
unanchored (§3).

*Enforced by:* `tests/integration/test_batch2_atmosphere_families.py` (the 42-row delivered
count, the ITYPE=1 sweep, the family↔matrix cross-check),
`tests/integration/test_uplooking_horizontal_anchors.py::test_slant_block_decks_still_match_their_delivered_card3`
(≥ 94 slant rows, including the Q7/Q8 hand-edit verification),
`tests/integration/test_batch2_fixture_anchors.py::test_the_promoted_set_is_exactly_what_the_matrix_marks_as_a_fixture`.

### 1.1 Deck-side verification — the Card-3 convention

Every delivered row's Card-3 echo is compared field-for-field against what `render_tape5`
writes for the same matrix row. This is the three-way agreement (builder output = matrix
hand-worked column = delivered echo) that closes the deck-geometry conventions:

- **Down-looking**: the sensor is the path's upper endpoint, so Card-3 ANGLE renders
  $180° - \zeta_{low}$ while the matrix's `path_zenith_deg_radiant` keeps the
  lower-endpoint value. On the five O rows the two columns are *different numbers*
  (180 / 131.8 / 120 against 0 / 48.2 / 60), so a builder that fed a sensor-referenced
  angle through would have failed the check.
- **Up-looking**: the sensor **is** the lower endpoint, so ANGLE renders unchanged.
- **K7 (5 → 15 km at 45°)** separates "at H1" from "at the ground" for the first time. Its
  echo reads `H1 5.000  H2 15.000  ANGLE 45.000` with `PHI = 135.083°` at H2 — the
  supplement of ANGLE plus 0.083° of Earth curvature, which it can only be if ANGLE belongs
  to H1 — and `RANGE = 14.132 km`, MODTRAN's own spherical slant range, slightly shorter
  than the flat-Earth 14.142 km.
- **ITYPE=1** rows: ANGLE is a literal 90.000 and the path length comes from Card-3 RANGE;
  ≥ 29 staged horizontal rows are swept.

*Record:* CU-065 / CU-067 (deck conventions), CU-224 checklist item ex-CU-223 (batch-2
ingestion), verified 2026-08-02.

### 1.2 Parse-side verification — the promoted fixtures

Five batch-2 rows are promoted to fixtures (M1, N4, N9, O1, P1). Their **full-resolution**
band means are pinned straight off the parser, before any interpolation or slit
degradation can average an error away [τ dimensionless; radiances W/m²/sr/µm]:

| Run | Band [µm] | τ_total | L_thermal | L_scattered |
|---|---|---:|---:|---:|
| M1 | 0.5–0.7 | 0.663890 | 3.567647e−25 | 1.156627e+02 |
| M1 | 3.5–4.1 | 0.779188 | 4.827541e−02 | 4.907478e−02 |
| M1 | 8.0–12.0 | 0.582553 | 2.869921e+00 | 4.059390e−04 |
| N4 | 0.5–0.7 | 0.586558 | 4.891194e−25 | 2.520987e+02 |
| N4 | 3.5–4.1 | 0.717442 | 6.641847e−02 | 1.704368e−01 |
| N4 | 8.0–12.0 | 0.520694 | 3.642793e+00 | 1.128885e−03 |
| N9 | 0.5–0.7 | 0.492641 | 6.031937e−25 | 1.999640e+02 |
| N9 | 3.5–4.1 | 0.655133 | 8.237745e−02 | 9.203124e−02 |
| N9 | 8.0–12.0 | 0.433470 | 4.335199e+00 | 6.987200e−04 |

*Record:* batch-2 promotion, 2026-08-02; `tests/integration/fixtures/modtran/MANIFEST.md`.
*Enforced by:* `tests/integration/test_batch2_fixture_anchors.py` (band anchors, physicality,
the up/down bracketing check, and per-run geometry vs the matrix row).

---

## 2. Parity tables

### 2.1 Thermal path radiance — both directions, the emission-temperature landing

Band-mean **model / MODTRAN** thermal path radiance. `midlat_summer` unless noted,
$\theta_s = 30°$. Each cell reads *pre-CU-321 → post-CU-321*, i.e. one-temperature
graybody → escape-resolved layered $T_{\text{eff}}(\lambda)$ (theory §2.10).

| Run | Column | Direction | MWIR 3–5 µm | LWIR 8–12 µm |
|---|---|---|---:|---:|
| O1 | ground ↔ 1 km, nadir | down | 0.407 → **0.380** | 0.533 → **0.517** |
| O2 | ground ↔ 5 km, nadir | down | 1.057 → **0.731** | 1.109 → **0.947** |
| O3 | ground ↔ 10 km, ζ = 48.2° | down | 2.013 → **1.141** | 1.326 → **1.055** |
| O4 | ground ↔ 10 km, ζ = 60° | down | 2.249 → **1.221** | 1.352 → **1.060** |
| O5 | ground ↔ 100 km, ζ = 48.2° | down | 2.422 → **1.217** | 1.430 → **1.093** |
| K1 | ground ↔ 1 km, nadir | up | 0.379 → **0.358** | 0.530 → **0.515** |
| K3 | ground ↔ 5 km, nadir | up | 0.664 → **0.502** | 1.054 → **0.930** |
| K5 | ground ↔ 20 km, nadir | up | 0.878 → **0.586** | 1.230 → **1.033** |
| N4 | ground ↔ 10 km, ζ = 48.2° | up | 0.926 → **0.660** | 1.216 → **1.050** |
| N9 | ground ↔ 10 km, ζ = 60° | up | 1.012 → **0.743** | 1.225 → **1.070** |
| N10 | ground ↔ 20 km, ζ = 60° | up | 1.090 → **0.784** | 1.260 → **1.090** |
| H1 | ground ↔ 100 km, nadir, `us_standard` | up | 1.006 → **0.624** | 1.530 → **1.189** |
| H4 | ground ↔ 100 km, ζ = 48.2°, `tropical` | up | 1.046 → **0.754** | 1.226 → **1.080** |
| H5 | ground ↔ 100 km, ζ = 48.2° | up | 1.041 → **0.721** | 1.263 → **1.074** |

The MODTRAN reference band means these ratios divide by are pinned in the same table (e.g.
O5 MWIR 0.19268, LWIR 3.26974 W/m²/sr/µm).

**The filed defect collapses.** The tall down-looking columns O3/O4/O5 went from
2.01/2.25/2.42 to 1.14/1.22/1.22 in the MWIR — a factor of two, not a tolerance.

**Aggregate scores.** Two are on record and they cover different cells; read the labels:

| Score | Cells | Before | After |
|---|---|---:|---:|
| LWIR RMS $\|\ln r\|$ | 14 anchors above | 0.3342 | **0.2611** (−22 %) |
| LWIR RMS $\|\ln r\|$ | full 25-run set **(record only)** | 0.330 | 0.269 (−19 %) |
| MWIR RMS $\|\ln r\|$ | full 25-run set **(record only)** | 0.474 | 0.522 (+10 %) |
| Direction-balanced | full 25-run set **(record only)** | 0.484 | 0.409 (−16 %) |

Honest accounting on the LWIR row that *is* enforced: three rungs move slightly away from
unity, and all three are shallow columns (O1 and K1 at 1 km, K3 at 5 km) whose residual is
the CU-161 τ deficit — too little absorbing column ⇒ too little emitting column — which no
emission temperature can reach. That cost is bounded at 3.5 % in $|\ln r|$ per rung by the
test, against 25–34 % won on the deep columns the change was filed about.

**Where the up-looking MWIR degradation comes from.** It is *un-masking*, not new error —
see §2.2.

*Record:* CU-224 resolved 2026-08-02 (the term existed nowhere down-looking before it);
CU-321 resolved 2026-08-03.
*Enforced by:* `tests/integration/test_emission_temperature_anchors.py` —
`test_thermal_path_radiance_parity_per_rung` (both sides, every rung),
`test_the_tall_down_looking_columns_no_longer_double_the_mwir`,
`test_lwir_parity_improves_or_holds_on_every_anchor` (the 0.3342 → 0.2611 pair).

### 2.2 The temperature-recovery scoreboard

MODTRAN reports τ and thermal path radiance separately, so its own effective emission
temperature is recoverable exactly:

$$T_{\text{MODTRAN}}(\lambda) \;=\; B^{-1}\!\left(\frac{L_{\text{thermal}}(\lambda)}{1 - \tau(\lambda)}\right)$$

Comparing the model's $T_{\text{eff}}$ against that isolates the temperature error from the
τ error. Emissivity-weighted band means, so the comparison is weighted the way the radiance
is:

| Metric | Band | One-temperature | Height-resolved |
|---|---|---:|---:|
| $\max\|\Delta T\|$ over the anchor set | MWIR | 25.2 K | **10.4 K** |
| $\max\|\Delta T\|$ over the anchor set | LWIR | 23.2 K | **9.5 K** |
| RMS $\|\Delta T\|$ | MWIR | 9.5 K | **4.3 K** |
| RMS $\|\Delta T\|$ | LWIR | 10.4 K | **3.2 K** |

(The 10.4 / 9.5 pair appears in both halves of this table with the bands swapped. That is a
coincidence of the measurements, not a transcription: the max-MWIR and the RMS-LWIR both
land on 10.4 K, the max-LWIR and the RMS-MWIR both on 9.5 K.)

**Scoring the radiance with MODTRAN's own emissivity** — which removes the τ error
entirely and leaves the emission temperature as the only model input — the RMS $|\ln r|$
across the set improves **0.287 → 0.148** **(record only)**.

That is the measurement behind the un-masking claim: on the up-looking MWIR rungs the
*full-radiance* ratio gets worse under the new model while the *temperature-only* ratio and
the recovered $\Delta T$ both get better. The retired one-temperature form was warm-biased
in a way that partly cancelled the CU-161 region-flat spectral-shape deficit; removing the
temperature error leaves the shape error visible.

*Record:* CU-321, resolved 2026-08-03.
*Enforced by:* `tests/integration/test_emission_temperature_anchors.py::test_effective_temperature_is_closer_to_the_modtran_one`
— asserts $|\Delta T| < 11$ K on every rung × band, and asserts the new value beats the old
wherever the old was wrong by more than 4 K.

### 2.3 The single-scatter species split — adoption measurement

Band-mean **MODTRAN / model** sky radiance against the shipped
`midlat_summer_uplooking_ladder` (ground sensor, ζ = 0°, $\theta_s = 30°$, five
non-degenerate rungs). Worst-rung excursion $\max(r, 1/r)$ per band:

| Band | Arithmetic-mean split (retired) | Lower-endpoint split (shipped) | + CU-321 |
|---|---:|---:|---:|
| VIS 0.45–0.85 µm | 3.085× | **1.360×** | 1.361× |
| NIR 0.85–1.40 µm | 3.024× | **1.262×** | 1.262× |
| SWIR 1.40–2.50 µm | 8.712× | **1.666×** | 1.666× |
| MWIR 3–5 µm | 2.404× | **2.334×** | 2.448× |
| LWIR 8–12 µm | 1.885× | 1.885× | 1.937× |

Lower-endpoint weighting is closer on **18 of the 25** rung × band cells and halves the
all-band RMS $|\ln r|$, **0.717 → 0.351**. The off-band thermal region is inert to the
choice (the two candidates differ by $\le 4.1\times10^{-4}$ relative on LWIR), which was
the condition the adoption criterion required.

The three bands the species split actually governs — VIS/NIR/SWIR — are untouched by the
later emission-temperature change and still discriminate by 2×–5×. The two thermal bands no
longer discriminate at all: CU-321 moved the worst MWIR excursion from 2.334× *past* where
the retired weighting sat, so the MWIR and LWIR columns are now regression guards rather
than comparisons, and the claim they support is narrowed accordingly.

**What this does not claim.** These ratios are large in absolute terms. They do not say the
model matches MODTRAN; they say the *weighting choice* is the better of the two available
ones. The single-scatter source still under-predicts the daytime VIS/NIR sky by tens of
percent, which is what the sub-3 µm provisional warning says (§3).

The full 25-cell ratio table is pinned per cell; representative rows (MODTRAN/model):

| Rung | VIS | NIR | SWIR | MWIR | LWIR |
|---|---:|---:|---:|---:|---:|
| 1 km | 1.103 | 0.792 | 0.607 | 2.448 | 1.937 |
| 5 km | 1.343 | 0.908 | 0.629 | 1.674 | 1.074 |
| 10 km | 1.360 | 0.930 | 0.610 | 1.514 | 0.988 |
| 20 km | 1.342 | 0.940 | 0.600 | 1.410 | 0.967 |

*Record:* CU-260 (folded into CU-224), adopted 2026-08-01; thermal rows repinned 2026-08-02
at CU-321.
*Enforced by:* `tests/integration/test_species_split_anchors.py` — all 25 cells pinned to
0.2 % relative, plus the adoption-criterion ceiling test and the thermal-inertness test.

### 2.4 Near-horizon — the hand-over and the first anchors past 60°

**How wrong `sec ζ` is.** Plane-parallel air mass against the exact spherical
density-weighted integral (molecular scale height, ground → 100 km):

| ζ | 30° | 60° | 75° | 80° | 85° | 89.4° |
|---|---:|---:|---:|---:|---:|---:|
| `sec ζ` high by | 0.042 % | 0.373 % | 1.687 % | 3.752 % | 13.15 % | 236.5 % |

and the error is **species dependent** — at 89.4° water (2 km scale height) is overstated
by 104.4 % against molecular's 236.5 %, a 2.27× divergence. That is the measurement that
forced a per-species air mass rather than one corrected scalar.

**The size of the hand-over step at 80°.** Straddling `SPHERICAL_SWITCH_RAD` by a
thousandth of a degree on a ground → 100 km column (`midlat_summer`, rural 23 km, PWV
1.4 cm, 0.4–14 µm on 301 points): the **molecular air mass** drops 3.6 %, the **median
optical depth** drops 2.0 %, and the **median transmittance** rises 10.6 % — up to 49 % at
wavelengths where the column is nearly opaque, because τ is exponential in a large OD.

Context for those numbers: the geometric-chord branch CU-274 deleted dropped the air mass
by **18 %** across its own switch, and deferring the hand-over to the 89.5° ceiling would
place it where the two forms differ by a **factor of two**. The residual step is the
plane-parallel model's own error at the point where it is retired.

For the up-looking sky the same hand-over shows as a radiance step. Band-mean LWIR
(8–13 µm) sky from the ground, grazing/column:

| ζ | 0° | 30° | 48.2° | 60° | **80°** | 85° | 89.4° |
|---|---:|---:|---:|---:|---:|---:|---:|
| ratio | 1.00000 | 0.99979 | 0.99929 | 0.99852 | **0.99359** | 1.08665 | 1.07785 |

i.e. the discontinuity fell from $\approx 8$ % at the old 89.5° ceiling to **0.64 %**.

**Making the step uniform across bands.** Aligning the linearisation reference column
across all three segment evaluators (theory §2.8) removed the last spectral artefact from
the step. Band-mean grazing/column at the 80° hand-over, ground → $h_{\text{atm,top}}$,
$\theta_s = 30°$:

| Band | Before (2026-08-01) | After (CU-320) |
|---|---:|---:|
| VIS 0.45–0.85 µm | 1.078 | **0.995** |
| NIR 0.85–1.40 µm | 1.568 | **0.995** |
| SWIR 1.40–2.50 µm | 1.497 | **0.992** |
| MWIR 3–5 µm | 1.024 | **0.998** |
| LWIR 8–13 µm | 0.998 | **0.998** |

Within 0.8 % in every band and, more to the point, *uniform* across them.

**Against MODTRAN, that change is a wash.** Over the batch-2 M block (M1–M5, ground →
100 km up-looking sky at ζ = 0/60/70.5/75.5/78.5°, `midlat_summer`, $\theta_s = 30°$) the
overall RMS $|\ln r|$ goes **0.316 → 0.318** **(record only)**: NIR improves sharply
(0.278 → 0.098) and VIS improves (0.513 → 0.461), while SWIR degrades (0.290 → 0.449) and
MWIR slightly (0.177 → 0.199); LWIR is identical (thermal control). With the convention
divergence removed, what is left is the single-scatter source's own accuracy limits, which
no choice of reference column can fix. The win is cross-evaluator consistency, not accuracy
— the CU-320 closure records that correction to its own filed claim.

**The first anchors past 60°.** M6–M8 exercise the grazing evaluator, which no earlier run
touched. Band-mean model/MODTRAN, ground → 100 km, $\theta_s = 30°$:

| Band | 85° (M6) | 88° (M7) | 89.5° (M8) |
|---|---:|---:|---:|
| VIS 0.45–0.85 µm | 0.549 | 0.568 | 0.589 |
| NIR 0.85–1.40 µm | 0.931 | 0.918 | 0.972 |
| SWIR 1.40–2.50 µm | 1.254 | 1.181 | 1.206 |
| MWIR 3–5 µm | 1.138 | 1.083 | 1.071 |
| LWIR 8–13 µm | 1.058 | 1.021 | 1.011 |

The thermal bands are the model's *best* region here — LWIR within 6 % and MWIR within
14 % all the way to the 89.5° ceiling, better than the 1.16–1.28 the same bands show inside
80°, because a near-horizon path saturates toward $B(T_{\text{eff}})$ and the graybody's
ceiling is exact. The scattered bands are the weak ones: the daytime VIS sky is
under-predicted by roughly a factor of two near the horizon (VIS model/MODTRAN falls from
0.76 at ζ = 0 to 0.55 at 78.5°, and sits at 0.55–0.59 through the grazing band).

M6–M8 are **anchors, not library nodes**: they are `dev_only` and are excluded from every
shipped node set, because past the 88.8° sec-space ceiling the interpolation coordinate is
unvalidated and a node there would sit inside a hull the interpolator may traverse.

*Record:* CU-274 resolved 2026-07-29; CU-225 resolved 2026-07-29 (the sky's hand-over);
CU-224 checklist ex-CU-275 landed 2026-08-01; CU-320 resolved 2026-08-02 (the band table
and the M6–M8 anchors).
*Enforced by:* `src/radiant/atmosphere/tests/test_near_horizon_air_mass.py` (the `sec ζ`
overstatement table, the 2.27× species divergence, the sign),
`src/radiant/atmosphere/tests/test_near_horizon_handover.py` (zero drift inside the band,
the bounded step, all three call sites, the retired solar clamp),
`tests/integration/test_batch2_atmosphere_families.py` (M6–M8 excluded from every family).
The M-block band ratios themselves are record-only.

### 2.5 Downwelling at altitude — a measurement that refuted its own analytic prediction

The shipped down-looking families used to attach the single ground-level H5 downwelling to
**every** target-altitude node. The CU-181 entry predicted, from `SimpleAtmosphere`'s own
`E_sky_thermal`, that the true value should decay by $\gtrsim 10^4$ across 0 → 50 km, and
set that as its acceptance criterion. The batch-2 P block measured it. The two disagree by
one to two orders of magnitude, and **MODTRAN is the authority**:

Shipped `atm_emission_down` band means [W/m²/sr/µm] and decay ratio to the ground rung,
`midlat_summer_boost_ladder`:

| $h_{tgt}$ [km] | 3–5 µm | ratio | 8–12 µm | ratio | Analytic prediction (refuted) |
|---:|---:|---:|---:|---:|---:|
| 0 | 5.284379e−1 | 1.000 | 3.726067e+0 | 1.000 | 1 |
| 1 | 3.742912e−1 | 1.412 | 2.203498e+0 | 1.691 | 1.48 |
| 5 | 7.469476e−2 | 7.075 | 3.680689e−1 | 10.12 | 7.7 |
| 10 | 1.015924e−2 | 52.02 | 1.769970e−1 | 21.05 | 81.7 |
| 20 | 3.787847e−3 | 139.5 | 1.335638e−1 | 27.90 | 391 |
| 29 | 5.089107e−3 | 103.8 | 8.748766e−2 | 42.59 | 1 201 |
| 35 | 4.343333e−3 | 121.7 | 4.425610e−2 | 84.19 | 2 541 |
| 40 | 3.999377e−3 | 132.1 | 2.529624e−2 | 147.3 | — |
| **50** | 3.709306e−3 | **142.5** | 8.426179e−3 | **442.2** | **16 579** |
| **60** ‡ | 3.191869e−4 | **1 656** | 5.835672e−4 | **6 385** | — |
| **80** ‡ | 3.437181e−7 | 1.537e+6 | 9.954564e−7 | 3.743e+6 | 766 300 |
| 100 | 0 (exact) | ∞ | 0 (exact) | ∞ | 6.44e+7 |

‡ **measured** since the 2026-08-03 P7/P8 delivery. These two rungs were previously
*modelled* — log-linear extrapolation on the measured 29 → 50 km slope, clamped
non-increasing — and the measurement shows how badly that slope under-predicted the
collapse above 50 km:

| Rung | Band | Modelled (retired) | Measured (P7/P8) | Model / measured | Model error |
|---:|---|---:|---:|---:|---:|
| 60 km | 3–5 µm | 3.387948e−3 | 3.191869e−4 | **10.61×** | +961 % |
| 60 km | 8–12 µm | 2.865881e−3 | 5.835672e−4 | 4.91× | +391 % |
| 80 km | 3–5 µm | 3.021602e−3 | 3.437181e−7 | **8 791×** | +879 000 % |
| 80 km | 8–12 µm | 3.471554e−4 | 9.954564e−7 | 349× | +34 774 % |

The model was wrong in the direction `scripts/downwelling_altitude.py` claimed for it —
*over*-stating, i.e. conservative for a reflected-sky term — but by up to four orders of
magnitude, and worst in the MWIR, where the shallow stratospheric CO₂/O₃ slope it
extrapolated from is exactly the feature that does **not** persist above 50 km. Two
assumptions it made are confirmed by the measurement: the profile really is non-increasing
through 50 → 60 → 80 km (the slope clamp was right), and the 100 km identity really is the
limit the measured rungs approach. What remains modelled is only an off-node query strictly
between 80 km and 100 km, bracketed by a measured value below and exactly zero above; no
shipped family holds a node there.

Three findings the runs contradict the entry on:

1. **The $\gtrsim 10^4$ acceptance criterion fails.** The real decay across 0 → 50 km is
   142× (MWIR) / 442× (LWIR), because the parametric model's water-dominated column
   collapses far faster than real stratospheric CO₂/O₃ emission does.
2. **The MWIR profile is not monotonic.** The 29 km rung is *brighter* than the 20 km one
   (stratospheric CO₂/O₃), so any monotone-decay model would have been wrong a second way.
3. **The 100 km rung is exactly zero** — a physical identity (no sky above the atmosphere
   top), not an extrapolation, replacing what the entry measured as a 6.44e7× worst case.

The lesson the contrast teaches is the one Rule 18 states: the analytic table was RADIANT
predicting itself. Both halves of the original entry's *physical* argument still hold — the
constant was real (12 nodes, one distinct array) and the fix is large — but the number it
set as its own success criterion was wrong by two orders of magnitude.

The exposure that motivated the fix, also measured: with the constant in place, a
300 K / ε = 0.3 body on the 50 km rung read **+99 %** too bright and a 230 K / ε = 0.3 body
**+2 567 %** (26×), while a hot boost body (1200 K, ε = 0.9) moved by ≤ 7.0e−4 %.

*Record:* CU-181, resolved 2026-08-02; owner ruling 2026-08-02 retiring the $10^4$
criterion and ratifying the then-modelled 60/80 km rungs pending P7/P8 — which were
delivered and ingested 2026-08-03, closing that ratification.
*Enforced by:* `tests/integration/test_batch2_atmosphere_families.py` (the altitude-resolved
downwelling, the measured decay pinned against the entry's own table, 12 distinct arrays
where there was 1, ground-target nodes byte-identical, the retired extrapolation's error
ratios pinned in both bands). The P7/P8 regeneration moved exactly the 10 NPZ nodes at
target 60 km and 80 km; the other 136 shipped nodes are SHA-256 identical, so every rung at
or below 50 km — and every ground-target node — is unchanged.

### 2.6 Transmittance parity — columns, slants and arms

**Up-looking partial columns (K1–K5, vertical).** Band-mean τ, MODTRAN | model:

| Run | Column | 8–12 µm | 3–5 µm |
|---|---|---|---|
| K1 | 0 → 1 km | 0.781 \| 0.889 | 0.581 \| 0.755 |
| K2 | 0 → 3 km | 0.670 \| 0.731 | 0.478 \| 0.624 |
| K3 | 0 → 5 km | 0.648 \| 0.664 | 0.450 \| 0.566 |
| K4 | 0 → 10 km | 0.631 \| 0.612 | 0.428 \| 0.503 |
| K5 | 0 → 20 km | 0.601 \| 0.591 | 0.420 \| 0.462 |

The model is systematically *transparent* for the shallowest columns — the water/gas
calibration was fit to full columns, so a 1 km column carries too little of the
near-surface continuum — and converges to within 2 % (LWIR) by 10–20 km. The MWIR bias is
the region-flat spectral-shape fragility. Enforced ratio bands: LWIR 0.95–1.16, MWIR
0.99–1.35.

**Slant columns at 45°, including an elevated lower endpoint.** MODTRAN | model:

| Run | Geometry | 8–12 µm | 3–5 µm |
|---|---|---|---|
| K6 | 0 → 10 km at 45° | 0.5378 \| 0.5007 | 0.3705 \| 0.3863 |
| K7 | 5 → 15 km at 45° | 0.9153 \| 0.9041 | 0.6808 \| 0.7027 |

**Constant-altitude arms against the horizontal grid.** Band-mean τ, 8–12 µm,
MODTRAN | model:

| Run | Altitude, range | 8–12 µm |
|---|---|---|
| L6 | 3 km, 5 km | 0.8194 \| 0.8421 |
| L7 | 3 km, 10 km | 0.7054 \| 0.7151 |
| L12 | 5 km, 10 km | 0.8829 \| 0.8565 |
| L17 | 10 km, 10 km | 0.9521 \| 0.9409 |
| L22 | 15 km, 10 km | 0.9456 \| 0.9674 |

The analytic arm holds to ±3.5 % in the LWIR across the altitude sweep — the regime the
air-to-air and ground-to-air scene classes need.

**Where the exponential arm stops working.** $\tau(2L) = \tau(L)^2$ is exact for the arm
and is precisely where a correlated-$k$ band model disagrees: strong lines saturate first
and flux keeps leaking through the windows. Down the 3 km row of the L grid, model/MODTRAN:

| Range | 5 km | 10 km | 25 km | 50 km | 100 km |
|---|---:|---:|---:|---:|---:|
| LWIR 8–12 µm | 1.03 | 1.01 | 0.95 | 0.87 | 0.82 |
| MWIR 3–5 µm | 1.09 | 0.88 | 0.43 | 0.11 | 0.01 |

The degradation is monotone with range — the signature of the model difference, not of
noise — and it is the documented reason long-range MWIR horizontal work needs a MODTRAN or
interpolated backend rather than the simple arm.

*Enforced by:* `tests/integration/test_segment_modtran_anchors.py` — Truth Anchors 1
(K ladder), the K6/K7 slant test, and Truth Anchor 4 (L grid) plus
`test_level_arm_exponential_divergence_from_the_band_model_is_bounded`, which asserts the
monotone degradation as well as the five ratios.

### 2.7 Sky radiance and the hemispheric downwelling flux

**Directional sky radiance** at the 48.2° diffusivity angle, band-integrated $\pi L$
[W/m²], MODTRAN thermal | model:

| Run | Profile | 8–12 µm | ratio | 3–5 µm | ratio |
|---|---|---|---:|---|---:|
| H2 | `us_standard` | 20.85 \| 26.24 | 1.26 | 1.82 \| 1.37 | 0.76 |
| H4 | `tropical` | 66.75 \| 72.11 | 1.08 | 3.65 \| 2.75 | 0.75 |

Before the height-resolved emission temperature these read 1.59 / 1.16 and 1.22 / 1.04 —
the whole 100 km column emitted at near-surface temperature. Resolving the emission
temperature in altitude cut the LWIR over-prediction by two thirds and turned the MWIR from
a small over-prediction into a ~25 % under-prediction: the region-flat spectral-shape
deficit, which the retired warm bias had been masking here.

**Band-integrated up-path radiance** against the K ladder [W/m²], MODTRAN | model
(repinned 2026-08-02):

| Run | Column | 8–12 µm | ratio | 3–5 µm | ratio |
|---|---|---|---:|---|---:|
| K1 | 0 → 1 km | 7.084 \| 3.649 | 0.52 | 0.648 \| 0.232 | 0.36 |
| K2 | 0 → 3 km | 10.337 \| 8.338 | 0.81 | 0.774 \| 0.358 | 0.46 |
| K3 | 0 → 5 km | 10.863 \| 10.101 | 0.93 | 0.795 \| 0.399 | 0.50 |
| K4 | 0 → 10 km | 11.135 \| 11.259 | 1.01 | 0.802 \| 0.439 | 0.55 |
| K5 | 0 → 20 km | 11.320 \| 11.689 | 1.03 | 0.803 \| 0.470 | 0.59 |

The deep-column LWIR excess this record carried before CU-321 (1.05 / 1.18 / 1.23×) *was*
the one-temperature warm bias, and it is gone (0.93 / 1.01 / 1.03×). The MWIR fell with it
(0.65 / 0.78 / 0.87 → 0.50 / 0.55 / 0.59) for the same un-masking reason.

**Hemispheric downwelling flux** — a different product from the directional radiance above,
with its own calibration (theory §2.11). Band-integrated model / MODTRAN on the two decks
the CU-155 emission height was fit against, with MODTRAN's thermal **+ scattered** path
radiance as the reference (the historical convention for this table; the 3–5 µm reference
is ~18 % larger than the thermal column alone, which matters when comparing against
§2.14(a)'s ladder):

| Run | LWIR | MWIR | Pre-CU-324 LWIR | Pre-CU-324 MWIR | Pre-CU-155 LWIR | Pre-CU-155 MWIR |
|---|---:|---:|---:|---:|---:|---:|
| H2 `us_standard` | 1.59 | 0.87 | 1.24 | 0.71 | 0.21 | 0.02 |
| H4 `tropical` | 1.23 | 0.93 | 1.03 | 0.78 | 0.21 | 0.03 |

The 2026-08-29 exponent swap ($D = 1.1 \to \sec 48.2° = 1.50030$, §2.14(a)) moves all four:
MWIR toward unity on both profiles, LWIR further above it. **That direction is expected
here and is not the criterion** — H2 and H4 are the two decks $D = 1.1$ was fitted against,
so any change must look like a regression when scored on its own fit set. The criterion is
the nine-rung ladder in §2.14(a), which the fit never saw. The residual ±40 % continues to
track the region-flat spectral-shape fragility, not temperature structure.

These ratios were **unchanged by CU-321** — the hemispheric product did not move there,
because it is a separate closed form a directional product cannot inherit.

*Record:* CU-155 resolved 2026-07-18 (commit `77d8ad2`), scope narrowed 2026-08-02,
exponent re-derived 2026-08-29 (CU-324 item 1).
*Enforced by:* `tests/integration/test_segment_modtran_anchors.py` Truth Anchors 2 and 3;
`tests/integration/test_modtran_real_runs.py` (the H2/H4 flux parity envelope,
[1.1, 1.8] LWIR and [0.7, 1.2] MWIR with the four measured points pinned to ±0.005, the
nine-rung ladder anchor, and the $\omega_{0,\text{eff}}$ re-derivation guard).

### 2.8 Direction asymmetry and τ reciprocity

**The up/down asymmetry, closed.** Measured against the batch-2 direction pairs (O1–O5
against K1/K3/N4/N9/H5 — identical columns run both ways), band-mean thermal path radiance,
up ÷ down:

| Source | LWIR | MWIR |
|---|---|---|
| MODTRAN's own | 1.006 – 1.14 | 1.07 – 2.34 |
| RADIANT, before the down-looking thermal term | 2e2 – 4e7 | 2e2 – 4e7 |
| RADIANT, now | 1.000 – 1.007 | 1.18 – 1.44 |

(The middle row is band-agnostic: the down-looking side carried no thermal term at all, so
the ratio was set by whatever residual scattered radiance the column had.)

The model still under-states the true directional spread — the one-slab graybody makes
emission direction-symmetric by construction and only the scattering term breaks the
symmetry — but it is the right order, which the previous form was not.

**τ reciprocity.** Three independent column pairs, each the same air run in opposite
directions:

| Pair | Column |
|---|---|
| K2 / F2 | 0 ↔ 3 km |
| K4 / J1 | 0 ↔ 10 km |
| K5 / J2 | 0 ↔ 20 km |

Band-mean τ ratios are **1.000000 to six figures** in LWIR, MWIR and VIS/NIR for all three
pairs. The largest *per-wavelength* disagreement anywhere in the 0.37–14.4 µm grid is
$\Delta\tau = 9.9\times10^{-5}$ (K4/J1 at 0.746 µm, τ ≈ 0.79 — a $1.3\times10^{-4}$
relative difference), sitting in the ozone Chappuis band where the two decks' solar-path
bookkeeping differs most. The assertion tolerances are set at ~5× those measurements and
are deliberately tight: the identity is exact physics, so loosening it to pass would hide a
real defect.

Path radiance is **not** compared, and must not be: the up-looking deck's radiance arrives
at the ground observer and the down-looking partner's at the aircraft. Those are the two
distinct directional fields of one segment.

*Record:* CU-224 resolved 2026-08-02 (asymmetry); ADR-0011 decision 3 (reciprocity as the
premise of a single-valued τ).
*Enforced by:* `tests/integration/test_uplooking_horizontal_anchors.py::test_transmittance_reciprocity_uplooking_vs_downlooking`,
`src/radiant/atmosphere/tests/test_downlooking_path_thermal.py` (the asymmetry collapse and
the bit-identical τ).

### 2.9 Cross-backend and resample consistency

These are not physics comparisons — they are checks that one stored column returns one
answer whatever path it takes to the chain grid.

| Check | Configuration | Before | After |
|---|---|---:|---:|
| log-τ midpoint identity, stored grid | `midlat_summer_ladders`, 12 983 λ | 1.110e−16 abs | unchanged |
| log-τ midpoint identity, off-node grid | same family | 2.077e−02 abs | **1.110e−16 abs** |
| Realistic 200-point MWIR chain grid | interpolated backend | ≤ 1.51 % relative τ (downward) | — |
| Cross-backend spread, three backends | 41-pt stored → 200-pt MWIR chain grid | 1.44e−02 | **0.0** (float round-off) |
| Stored-grid query | any backend | — | **bit-identical** |
| Per-backend midpoint identity | tabulated / MODTRAN / interpolated | — | **exactly 0** |

τ moved strictly **downward** under both changes, because the geometric mean is $\le$ the
arithmetic mean.

**Zenith-axis interpolation.** The real B-fan 45° holdout lands **−0.10 %** band-mean τ in
sec-space, against **−4.07 %** under the earlier linear-in-angle axis. The Level-0 identity
$\tau(\zeta) = \tau_{\text{vert}}^{\sec\zeta}$ is reproduced at every query angle to
$10^{-10}$.

*Record:* CU-306 resolved 2026-08-01; CU-316 resolved 2026-08-02; CU-160 resolved
2026-07-17 (commit `863e923`).
*Enforced by:* `src/radiant/atmosphere/tests/test_log_tau_resample.py` (the geometric-mean
key equation, the three-backend agreement, the realistic-grid agreement, the floor and
no-cap semantics), `src/radiant/atmosphere/tests/test_interpolated.py`,
`tests/integration/test_shipped_atmosphere_library.py`.

### 2.10 Exo-target vacuum equivalence

For a **full-column** up-looking family (measured ceiling reaching $h_{\text{atm,top}}$),
the composed observer leg for any exo-altitude target must be *identically* the family's
own top-of-column run:

| Check | Result |
|---|---|
| Composed products at 100 km / 400 km / GEO, all eight fields | bit-identical |
| Composed τ vs the stored M1 full-column run | agrees to 5.6e−17 |
| Bundled up-looking families satisfying "below the top ⇒ refuse, or at the top ⇒ exact" | all |
| Sabotage run (ceiling seam disabled) | 7 of 11 guard tests fail |

The last row is what makes the first three meaningful: the invariant is tested to fail.

*Record:* CU-224 checklist item ex-CU-308, landed 2026-08-02.
*Enforced by:* `tests/integration/test_uplooking_backend_dispatch.py`.

### 2.11 The hybrid split — measured divergence between the two legs

The up-looking hybrid composes a library-backed observer leg with a `SimpleAtmosphere`
companion (theory §3.7). The divergence the owner ratified, on the observer leg, 3–5 µm,
ground to 10 km:

| Quantity | Run family | `SimpleAtmosphere` companion | Difference |
|---|---:|---:|---:|
| τ | 0.4725 | 0.5715 | −17.3 % |
| L [W/m²/sr/µm] | 0.5414 | 0.3995 | +35.5 % |
| SNR | 1152.72 | 1207.21 | −4.5 % |

i.e. the parametric model runs 26 % low up-looking on this leg. Where the two models must
agree — $\tau_{\text{sun}}$, $E_{\text{TOA}}$, $E_{\text{sky,scattered}}$,
$E_{\text{sky,thermal}}$, all served by the companion alone — they are bit-identical.

*Record:* CU-224 checklist item ex-CU-305, owner-ratified 2026-08-01. Divergence numbers
are **(record only)**; the *declaration* of the split is what is enforced.
*Enforced by:* `src/radiant/atmosphere/tests/test_uplooking_backend_dispatch.py` — the
`UserWarning`, the INFO log record, and the `backend_split` provenance marker each have a
test, which is the condition the ratification was made under.

### 2.12 Gas-region edges — the discontinuity that was removed

The calibrated region table read as a step function made τ(λ) jump at all fourteen interior
edges the table then had (CU-330 has since raised that to sixteen — see §2.15 — and the two
new edges are blended by the same rule, with no separate measurement needed because the
mechanism is identical). Vertical ground → 700 km, θ_o = 0, rural-23, `midlat_summer` PWV
2.92 cm, τ_up evaluated ±1e−9 µm either side of each edge:

| Edge [µm] | τ below | τ above | Δτ | relative |
|---:|---:|---:|---:|---:|
| 0.45 | 0.609247 | 0.605374 | −0.003873 | −0.64 % |
| 0.70 | 0.824152 | 0.680287 | −0.143866 | −17.46 % |
| 1.30 | 0.764954 | 0.197539 | −0.567415 | −74.18 % |
| 1.50 | 0.200055 | 0.881041 | +0.680986 | +340.40 % |
| 1.75 | 0.890645 | 0.233132 | −0.657513 | −73.82 % |
| 2.05 | 0.235205 | 0.827919 | +0.592714 | +252.00 % |
| 2.40 | 0.833784 | 0.079252 | −0.754532 | −90.49 % |
| 3.10 | 0.079942 | 0.330011 | +0.250069 | +312.81 % |
| 3.50 | 0.331062 | 0.500298 | +0.169237 | +51.12 % |
| 5.00 | 0.503748 | 0.010935 | −0.492812 | −97.83 % |
| 7.50 | 0.010936 | 0.057940 | +0.047005 | +429.84 % |
| 8.00 | 0.057940 | 0.533682 | +0.475741 | +821.09 % |
| 10.00 | 0.533682 | 0.636775 | +0.103093 | +19.32 % |
| 12.00 | 0.636775 | 0.254203 | −0.382572 | −60.08 % |

Every edge steps; only 0.45 µm is under 1 %.

**The operator-visible symptom was grid dependence.** Band-mean τ_up sampled at N = 31
against N = 1001:

| Band [µm] | Grid dependence (step table) | Adopted-blend impact |
|---|---:|---:|
| 0.5–0.8 (crosses 0.70) | 0.324 % | −0.204 % |
| 0.4–0.9 (crosses 0.45, 0.70) | 0.351 % | −0.121 % |
| 3.0–5.0 (crosses 3.10, 3.50) | 1.830 % | −0.711 % |
| 8.0–12.0 (crosses 10.00) | 0.772 % | −0.245 % |
| 8.0–14.0 (crosses 10.00, 12.00) | 0.964 % | −0.170 % |
| 11.5–12.5 (crosses 12.00) | 1.389 % | −0.193 % |
| 3.7–4.8 (interior control) | **0.000 %** | **0.000 %** |
| 10.6–11.2 (interior control) | **0.000 %** | **0.000 %** |

The two interior controls are the discriminating rows: a band that crosses no edge moved by
exactly zero in both columns, which is what says the effect is the edge and not the
quadrature.

**One claim corrected at closure.** The blend removes the *discontinuity* — band-mean τ now
converges under grid refinement — but "removes the grid dependence entirely" was an
over-claim: at N = 31 the 8–12 / 8–14 µm quadrature spread grows (1.77 → 3.28 % and
1.47 → 3.44 %), because the 0.04 µm ramp is itself under-resolved by a coarse grid.

Both the edge table and the band table above are **(record only)**, measured on the
pre-CU-330 fifteen-region partition; the numbers are not re-derived here because CU-330
changed the partition, not the blend. The invariant CU-330 does move is the no-overlap
bound's binding region: the narrowest region is now the 0.10 µm ozone tail
(9.90–10.00 µm) rather than the 0.20 µm 1.30–1.50 µm region — still 2.5× the 0.04 µm full
ramp width.

*Record:* CU-267, resolved 2026-08-01, owner-ratified.
*Enforced by:* `src/radiant/atmosphere/tests/test_gas_region_blend.py` (40 Level-0 tests;
the interior-control bands, the no-overlap invariant, the exact edge-mean hand anchors —
the edge-parametrised cases read the shipped table, so they cover the two CU-330 edges
automatically) and `src/radiant/atmosphere/tests/test_gas_region_o3_split.py` (which
region binds the width bound, and the two new edges' hand-computed mean values).
The tests pin the *blended* behaviour, which is what ships.

### 2.13 The level whole path

Whole-path evaluator ÷ the two-segment composition it replaced, band-mean sky radiance,
`midlat_summer` rural 23 km:

| Altitude | Arm | Sag | MWIR 3.5–5 µm | LWIR 8–12 µm | VIS 0.45–0.85 µm, θ_s = 30° |
|---|---|---|---:|---:|---:|
| 0 m | 8 km | 1.3 m | 1.00000 | 1.00000 | 2.433 |
| 3 km | 100 km | 196 m | 1.00000 | 1.00183 | 2.085 |
| 10 km | 50 km | 49 m | 1.00002 | 1.00032 | 1.125 |
| 10 km | 150 km | 441 m | 1.00017 | 1.00609 | 1.259 |
| 15 km | 100 km | 196 m | 1.00078 | 1.00248 | 1.155 |

The thermal bands move by ≤ 0.6 % (they saturate — both forms tend to $B(T_{\text{eff}})$),
while a **daytime VIS/NIR** level sky moves by 1.13× to 2.43×, because the composed form
multiplied the continuation's scattered term by $\tau_{\text{arm}}$ and weighted the two
halves separately.

**Why the obvious alternative is wrong.** Rooting a single ascending arc at the sensor —
the up-looking branch's shape — recovers only this fraction of the true traversed molecular
column:

Sea-level-equivalent molecular column [km], sensor-rooted arc ÷ true traversed path:

| Arm | Altitude | Sag | Filed (CU-276) | Enforced (re-measured) |
|---|---|---|---:|---:|
| 8 km | 0 m | 1.3 m | 0.9859 † | **1.0142** † |
| 100 km | 3 km | 196.3 m | 0.8303 | **0.8304** |
| 150 km | 10 km | 442.1 m | 0.7508 | **0.7512** |

† The sea-level row is degenerate and is the exception to the argument: an 8 km arm at MSL
has its perigee 1.3 m *below* the ellipsoid, so the model clamps the integration floor at
MSL and warns, and the sensor-rooted arc comes out 1.4 % **longer**, not shorter. CU-276
filed 0.9859 here from an unclamped integral; 1.0142 is what a clamped model can actually
produce, and it is the enforced value. The two material rows reproduce as filed.

**A correction to the filed claim.** The entry filed the level join as "the same
non-additive-graybody mechanism CU-254 measured at 12.3 %". Measured, it was not: both
composed sub-segments were keyed to the *same* altitude, so both carried the identical
$T_{\text{eff}}$ — 227.850 K either side of the join. What the fix actually removes is the
constant-density chord approximation and the split-weighted scattering, which is why the
level reference scenario moved by 2.6e−6 relative, not 12 %.

*Record:* CU-276 (folded into CU-224), landed 2026-08-01.
*Enforced by:* `src/radiant/atmosphere/tests/test_level_whole_path.py` — the sag formula,
the sensor-rooted-arc column loss re-measured, the exact zero-arm ↔ grazing identity, the
one-graybody property, and the MSL clamp warning.

### 2.14 Emission placement — three refinements measured, none adopted

CU-324 asked three follow-on questions of the CU-321 layered-emission machinery. All three
placement refinements were measured 2026-08-29 against the delivered run set and **none was
adopted**. The measurement pass changed no code; the one change that did land is the
**emissivity exponent** the item-1 decomposition isolated (owner-ratified 2026-08-29,
below), which moves $E_{\text{sky,thermal}}$ and hence §2.7's hemispheric table and every
reflected-sky term. Directional path-radiance ratios (§2.1–§2.6, §2.8–§2.13) are unmoved:
they never used this exponent. These tables are the evidence for the rulings.

All three are *placement* questions: they redistribute a segment's existing opacity in
altitude and never change the total. Where a candidate was evaluated, the total optical
depth was asserted bit-identical to the shipped one (`np.array_equal`) before any parity
was read.

**(a) The $z_{em} = 200$ m downwelling proxy** — measured on the full nine-rung P ladder,
model / $\pi L_{\text{MODTRAN}}$ band means, against MODTRAN's **thermal** path-radiance
column. "Layered" is the sky column's emergent radiance at 48.2° escaping toward the
ground, from §2.10's machinery, replacing both constants. "Then-shipped" is the pre-swap
$D = 1.1$ form; "ships" is the post-swap $\sec 48.2°$ form this section's ruling adopted:

| Run | $h_{tgt}$ | $\pi L_{\text{MOD}}$ MWIR | then-shipped | layered | **ships** | $\pi L_{\text{MOD}}$ LWIR | then-shipped | layered | **ships** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| H5 | 0 km | 1.4154 | 0.864 | 0.721 | **1.041** | 11.708 | 1.020 | 1.074 | **1.263** |
| P1 | 1 km | 1.0337 | 0.791 | 0.636 | **0.974** | 6.9251 | 1.006 | 1.037 | **1.286** |
| P2 | 5 km | 0.23195 | 0.646 | 0.455 | **0.835** | 1.1571 | 1.173 | 1.073 | **1.558** |
| P3 | 10 km | 0.031291 | 0.439 | 0.448 | **0.582** | 0.55622 | 0.524 | 0.618 | **0.706** |
| P4 | 20 km | 0.011584 | 0.250 | 0.338 | **0.338** | 0.41967 | 0.173 | 0.235 | **0.235** |
| P5 | 29 km | 0.015777 | 0.060 | 0.082 | **0.082** | 0.27487 | 0.086 | 0.118 | **0.118** |
| P6 | 50 km | 0.011707 | 0.0059 | 0.0080 | **0.0080** | 0.026489 | 0.065 | 0.089 | **0.089** |
| P7 | 60 km | 0.0010019 | 0.0196 | 0.0268 | **0.0268** | 0.001835 | 0.268 | 0.366 | **0.366** |
| P8 | 80 km | 8.9015e-07 | 1.676 | 2.286 | **2.286** | 3.1301e-06 | 11.92 | 16.26 | **16.26** |

(From P4 up the "layered" and "ships" columns coincide to three figures: above the
tropopause the ICAO profile is isothermal at 222.65 K, so the layered temperature *is* the
proxy temperature and only the exponent distinguishes the forms.)

RMS $|\ln$ ratio$|$ then-shipped → layered: MWIR 2.4233 → 2.2628, LWIR 1.6615 → 1.5478,
both bands 2.0776 → 1.9385. On the stated criterion the layered form wins — but the win is
confounded, and the 2×2 decomposition separates it. The swap changes two things at once:
the emissivity exponent (fitted $D = 1.1$ → the ladder's own $\sec 48.2° = 1.50030$) and
the temperature.

| RMS $|\ln$ ratio$|$ | $T(h + z_{em})$ | layered $T_{\text{eff}}$ |
|---|---:|---:|
| $D = 1.1$ (retired) | 2.0776 | 2.1080 |
| $\sec 48.2°$ (**ships** since 2026-08-29) | **1.9233** ← best | 1.9385 |

Per-band for the corner that ships: MWIR 2.4233 → 2.2319, LWIR 1.6615 → 1.5547.

The exponent carries the entire gain; the layered temperature costs against *either*
exponent. Restricted to the four tropospheric rungs — the only ones where the two
temperatures differ at all, since the ICAO profile returns 222.65 K at every stratospheric
rung — the ranking is starker: shipped 0.4167, $\sec$+$z_{em}$ 0.3087, $\sec$+layered
0.4771, $D$+layered 0.6785.

Borrowing MODTRAN's own emissivity isolates the temperature (the CU-321 attribution
metric). Over the eight tropospheric band-means:

| T_eff-only RMS $|\ln$ ratio$|$ | $z_{em}$ proxy | layered |
|---|---:|---:|
| MWIR | **0.1187** | 0.4380 |
| LWIR | 0.3110 | **0.0827** |
| both | **0.2354** | 0.3152 |

The split is physical, not noise. Against MODTRAN's recovered emission temperature the
proxy runs +10.4 / +12.7 / +21.6 / +4.8 K in the LWIR on H5/P1/P2/P3 where the layered form
runs +1.3 / +1.4 / +6.2 / +0.5 K — the semi-transparent window genuinely samples the whole
column and the layered solution gets it right. In the MWIR the layered form runs 3.5–10.6 K
*cold*: with the region-flat 3–5 µm gas floor supplying too little opacity, its weighting
reaches too high, and the proxy's warm bias had been compensating for a $\tau$-shape error.
This is the CU-321 un-masking pattern, and it is why the aggregate loses.

**Ruling (layered temperature):** not adopted — the layered form is strictly worse than the
$(\sec, z_{em})$ corner already available.

**Ruling (exponent), owner-ratified 2026-08-29: adopted.** $D$ is no longer fitted; it is
$\sec 48.2° = 1.50030$, the secant of the angle every deck in this reference set was run
at. Scoring the model against $\pi L(48.2°)$ and then weighting its emissivity by anything
else mixes two hemispheric approximations; taking the exponent from the reference geometry
removes a free parameter rather than re-tuning one. The retired $D = 1.1$ was fitted
2026-07-18 against H2 and H4 alone — the only up-looking decks that then existed — and the
ladder that would have constrained it postdates that fit by six weeks. Measured effect on
the ladder: composite RMS 2.0776 → 1.9233, tropospheric-only 0.4167 → 0.3087. The
composite is dominated by P6–P8, where a 50–80 km target sees a near-vacuum sky and both
forms are wrong by orders of magnitude; the tropospheric figure is the one describing a
scene anybody images, and both are pinned so neither can be traded for the other.

Direction of the results change: the downwelling effective emissivity rises everywhere
(the exponent multiplies the optical depth), by $\sec/1.1 = 1.364\times$ in the optically
thin limit and asymptotically not at all where the column already saturates. Every
reflected-sky term rises with it.

**(b) O₃ lumped into the well-mixed gas floor** — **the one refinement of the three that
was eventually adopted**, landed 2026-08-30 (CU-324 item 2). The measurement history below
is left intact because the adoption rests on it; the shipped numbers are in the last block.

The fourteen matched pairs read in the
9.4–9.9 µm O₃ feature rather than in the whole LWIR band, model / MODTRAN:

| Run | dir | MODTRAN 9.6 µm | shipped | O₃-split | LWIR shipped | LWIR split |
|---|---|---:|---:|---:|---:|---:|
| O1 | upper | 1.3417 | 0.823 | 0.814 | 0.517 | 0.516 |
| O2 | upper | 2.3632 | 1.095 | 0.991 | 0.947 | 0.935 |
| O3 | upper | 3.1994 | 1.148 | 0.861 | 1.055 | 1.020 |
| O4 | upper | 3.7031 | 1.157 | 0.849 | 1.060 | 1.023 |
| O5 | upper | 2.6246 | 1.438 | 0.960 | 1.099 | 1.050 |
| K1 | lower | 1.3452 | 0.824 | 0.814 | 0.515 | 0.514 |
| K3 | lower | 2.4409 | 1.099 | 1.014 | 0.930 | 0.920 |
| K5 | lower | 3.0321 | 1.047 | 0.817 | 1.033 | 1.001 |
| N4 | lower | 3.6502 | 1.111 | 0.933 | 1.050 | 1.027 |
| N9 | lower | 4.3787 | 1.115 | 0.952 | 1.070 | 1.049 |
| N10 | lower | 4.6406 | 1.096 | 0.895 | 1.090 | 1.063 |
| H1 | lower | 1.8440 | 1.090 | 0.645 | 1.189 | 1.106 |
| H4 | lower | 5.0792 | 1.123 | 0.971 | 1.080 | 1.062 |
| H5 | lower | 4.0707 | 1.064 | 0.840 | 1.074 | 1.043 |

The "O₃-split" column places 100 % of the in-feature gas-floor OD on a **Gaussian layer of
standard deviation 5 km centred at 25 km**. (The 2026-08-29 measurement pass described this
as a "Chapman layer"; the 2026-08-30 implementation re-derived the layer shape from this
section's own centre/width grid and the label was wrong. A Gaussian with $\sigma =$ the
tabulated width reproduces all nine corners of the grid below to a mean absolute 0.004 in
RMS $|\ln|$, including the discriminating 30 km / 3 km corner; a true Chapman production
profile $\exp(1 - y - e^{-y})$ with $H =$ the width misses them by 0.046 and degenerates
entirely at narrow widths, where its razor-sharp underside leaves partial columns with no
overlap at all. The numbers in this section are Gaussian numbers; only the prose was
wrong.) The defect is real and one-sided — twelve of fourteen pairs over-predict, worst on
the deepest columns (O5 1.44×) — which is the signature of emission placed too low. The
feature's RMS $|\ln$ ratio$|$ is 0.1519 against 0.2611 for the LWIR band mean containing
it, i.e. a 15 % error hiding inside a 4 µm average because the feature is 0.5 µm wide.

Placing 100 % overcorrects (0.1519 → 0.1731). Sweeping the moved fraction:

| O₃ share of the in-feature gas floor | 0.1 | 0.2 | 0.3 | 0.4 | **0.5** | 0.6 | 0.8 | 1.0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 9.4–9.9 µm RMS $|\ln|$ | 0.1363 | 0.1222 | 0.1105 | 0.1027 | **0.1000** | 0.1036 | 0.1290 | 0.1731 |
| 8–12 µm RMS $|\ln|$ | 0.2605 | 0.2598 | 0.2592 | 0.2587 | 0.2581 | 0.2576 | 0.2566 | 0.2558 |

There is a real 34 % improvement available (0.1519 → 0.1000), and the LWIR band mean barely
moves either way — confirming the feature must be measured on its own sub-band. But the
improvement is governed by exactly **one free parameter**, and the layer's physical
parameters are nearly unobservable next to it:

| centre / width (at share 0.4) | 3 km | 5 km | 8 km |
|---|---:|---:|---:|
| 20 km | 0.1026 | 0.1033 | 0.1117 |
| 25 km | 0.1011 | 0.1027 | 0.1055 |
| 30 km | 0.1055 | 0.1026 | 0.1032 |

That degeneracy has one cause: the ICAO profile is isothermal above 11 km, so every
candidate layer sits in air at 222.65 K and only the *quantity* of opacity moved above the
tropopause matters. Re-expressing the fraction as narrower band limits at share 1.0 does
not escape it — $(9.5, 9.7)$ µm scores 0.1045 against $(9.4, 9.9)$ µm at share 0.4 scoring
0.1027, i.e. the same single degree of freedom wearing different units.

**Ruling (2026-08-29, superseded the same day by the measurement below):** not adopted. The
blocker was upstream, on the $\tau$ side: the CU-161 region table's 8.00–10.00 µm region is
2 µm wide and flat, so it contained no identifiable ozone band and could not say what share
of its floor OD is O₃. Adopting would put the first fitted coefficient into
`emission_temperature.py`, whose zero-fit construction is the CU-321 design premise. The
unblocking condition named here was "a 9.6 µm region in the CU-161 table."

**Re-measured 2026-08-29 with that region in place (CU-330).** The split table (§2.15) does
supply the share, and it is arithmetic rather than fitted: the in-feature floor is 0.8877
and the adjacent clean window's — the same well-mixed continuum with no ozone in it — is
0.1494, so

$$\text{share}_{\mathrm{O_3}} \;=\; \frac{0.8877 - 0.1494}{0.8877} \;=\; 0.832 .$$

The earlier expectation of "1.0 by construction" was wrong by the continuum's share: an
ozone *band* still sits on top of the same CO₂/N₂O/CH₄ floor its neighbours carry, so the
excess, not the total, is the ozone.

The sweep re-run with the split table — same fourteen matched pairs, same 25 km / 5 km
Gaussian layer, same construction, total optical depth asserted bit-identical to the
shipped one at every share:

| O₃ share of the in-feature gas floor | 0.0 | 0.2 | 0.4 | 0.6 | **0.70** | 0.8 | **0.832** | 0.9 | 1.0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9.4–9.9 µm RMS $|\ln|$ | 0.3581 | 0.2873 | 0.2171 | 0.1548 | **0.1365** | 0.1390 | **0.1456** | 0.1696 | 0.2279 |
| 8–12 µm RMS $|\ln|$ | 0.2632 | 0.2601 | 0.2575 | 0.2554 | 0.2546 | 0.2540 | 0.2539 | 0.2537 | 0.2538 |
| pairs biased warm | 12/14 | 12/14 | 11/14 | 9/14 | 9/14 | 6/14 | 5/14 | 3/14 | 2/14 |

Two things changed against the pre-CU-330 sweep, and they point the same way. **The
un-split baseline is much worse than it was** — 0.1519 → 0.3581 at share 0, with the worst
pair going 1.44× → 1.95× — because the flat slab had been carrying only 0.2751 of in-band
floor OD where the band actually holds 0.8877. It under-supplied the opacity and thereby
under-supplied the error. **And the optimum moved from 0.5 to ~0.70**, i.e. toward the
share the τ table independently determines.

That is the whole content of the unblocking. Before: one free parameter, an unconstrained
optimum at 0.5, and nothing outside the emission parity to say whether 0.5 was right.
After: the share is read off two committed table entries as 0.832, and *scoring* it against
the emission parity — a measurement it was not fitted to — puts it within 7 % of that
parity's own best (0.1456 against 0.1365 at 0.70). A one-parameter fit that lands within
7 % of the optimum without having seen it is a corroborated number, not a tuned one.

The layer's own geometry stays weakly observable, as before, but less so than it was — the
30 km / 3 km corner is now clearly rejected where every corner used to be within 13 %:

| centre / width (at the τ-determined share 0.832) | 3 km | 5 km | 8 km |
|---|---:|---:|---:|
| 20 km | 0.1482 | 0.1374 | 0.1331 |
| 25 km | 0.1457 | 0.1456 | 0.1329 |
| 30 km | 0.1913 | 0.1483 | 0.1381 |

**Ruling (2026-08-29): the τ-side blocker is discharged; the emission split itself is
CU-324 item 2's own action.** CU-330 deliberately did not implement it — a τ recalibration
and an emission-placement change are separate results-affecting movements and are not
landed in one PR. What CU-330 handed item 2 is a share it no longer has to fit. Until it
landed, 9.4–9.9 µm path-thermal parity was *worse* than before CU-330 (0.1519 → 0.3581) —
a deliberate interim regression, recorded on both CUs, that the block below clears.

#### The shipped placement (CU-324 item 2, landed 2026-08-30)

**Owner go (2026-08-30):** implement at the τ-derived share (zero-fit construction),
measure the parity at both it and the independent optimum, and stop-and-flag if the derived
share materially underperforms. It does not.

The construction that ships derives the share **in code** from the two committed table
rows rather than carrying the 0.832 decimal (`atmosphere/ozone_placement.py`): the model
evaluates the blended floor twice — once as shipped, once with the band row carrying its
clean-window neighbour's floor — and takes $1 - \text{continuum}/\text{floor}$. So the
share is 0.8317 today, it follows any re-fit of either row automatically, and it inherits
the CU-267 smoothstep at 9.40 and 9.90 µm instead of needing a second ramp implementation
(the earlier sweeps used a hard band edge; the difference is 0.1391 → 0.1389).

Measured on the same fourteen matched pairs, model / MODTRAN in the feature:

| | un-split (share 0) | **shipped** (τ-derived 0.8317, blended) | free optimum (0.80) | at the 2026-08-29 optimum (0.70) |
|---|---:|---:|---:|---:|
| 9.4–9.9 µm RMS $|\ln|$ | 0.3581 | **0.1389** | 0.1347 | 0.1382 |
| 8–12 µm RMS $|\ln|$ | 0.2632 | **0.2522** | 0.2525 | 0.2533 |
| pairs biased warm | 12/14 | **5/14** | 6/14 | 9/14 |

**The derived share lands 3.1 % above the free optimum** — inside the ruling's 15 % bar by
a factor of five, so no flag. The one-sidedness that made this a defect is gone: 12 of 14
pairs over-predicted, 5 do now, and the worst pair falls 1.95× → 1.27×. The feature
improves 2.6×; the 8–12 µm band mean containing it moves 4 %, which is the same concealment
asymmetry §2.14(b) opened with, read in the other direction.

The blend also re-measures the layer geometry at the shipped share, and it stays weakly
observable — the whole grid spans 0.133–0.146, so the 25 km / 5 km physical choice costs
2.4 % against the grid's own best and is not worth tuning:

| centre / width (shipped, blended share) | 3 km | 5 km | 8 km |
|---|---:|---:|---:|
| 20 km | 0.1432 | 0.1357 | 0.1400 |
| 25 km | 0.1445 | **0.1389** | 0.1383 |
| 30 km | 0.1459 | 0.1405 | 0.1380 |

**Blast radius.** Wherever the share is zero — any wavelength grid that does not reach
9.4–9.9 µm — no layer species is constructed and $T_{\text{eff}}$ is bit-identical to the
pre-CU-324 four-species form. On a grid that *does* reach the band, the layer contributes
sub-layer edges that also refine the quadrature elsewhere; measured on the deepest anchor
columns that is $\le 0.004$ K at off-band wavelengths, four times below the 0.016 K
discretisation error the shipped layer count already carries. The MWIR is unmoved on every
anchor.

**Where it does not help.** The three shallow rungs (1–5 km columns) move slightly *away*
from unity in the LWIR — the same rungs §2.15 flags on the τ side. The calibrated floor
rides the molecular scale height, so a 0–5 km column is handed ozone opacity it does not
physically hold; placing that opacity correctly makes the τ-side mis-attribution visible
instead of cancelling it. That is a τ-table limitation, not a placement one, and it is the
open half of the ozone story.

**(c) Grazing-arc opacity distribution** — M6–M8 evaluated as candidate anchors, model /
MODTRAN band-mean thermal radiance, vertical (shipped) against along-arc placement:

| Run | ζ | MODTRAN MWIR | vertical | along-arc | MODTRAN LWIR | vertical | along-arc |
|---|---:|---:|---:|---:|---:|---:|---:|
| M6 | 85° | 0.64694 | 1.053 | 1.057 | 7.930 | 1.045 | 1.047 |
| M7 | 88° | 0.67987 | 1.058 | 1.066 | 8.3017 | 1.030 | 1.033 |
| M8 | 89.5° | 0.69274 | 1.061 | 1.074 | 8.3904 | 1.029 | 1.034 |

RMS $|\ln$ ratio$|$ 0.0464 vertical, 0.0524 along-arc. The largest shift the placement
choice produces anywhere on the fan is $|\ln| = 0.01196$ — **1.2 %** — against a
model/MODTRAN residual of 3–6 %. The recovered temperatures differ by 0.08–0.24 K. A
ground-rooted column already concentrates its opacity at the escape end however it is
weighted, so the $ds/dz$ enhancement is redundant there.

**Ruling:** M6–M8 **cannot discriminate**, so no code changed. The geometry that would is
an ascending arc rooted at its own tangent point *below* the tropopause, where the along-arc
weighting holds opacity in measurably warmer air than the vertical column mean. Modelled
separation, along-arc ÷ vertical band-mean radiance, tangent endpoint to 100 km:

| tangent endpoint | 2 km | 5 km | **8 km** | 10 km | 15 km |
|---|---:|---:|---:|---:|---:|
| MWIR | 1.029 | 1.079 | **1.161** | 1.152 | 1.000 |
| LWIR | 1.024 | 1.098 | **1.131** | 1.067 | 1.000 |
| Δ$T_{\text{eff}}$ LWIR | +1.30 K | +4.52 K | **+4.74 K** | +2.06 K | 0.00 K |

The exact 1.000 at 15 km is the isothermal stratosphere again — an elevated rung above the
tropopause is as blind as M6–M8. Run-matrix rows **R1–R3** (5 / 8 / 10 km tangent
endpoints, ANGLE 90°, `midlat_summer` rural 23 km to 100 km) were authored for this and are
unrun; the item is gated on them, not declined.

*Record:* CU-324, measured 2026-08-29. Of the three placement refinements, **item 2 was
adopted 2026-08-30** (this section's shipped block); item 1's layered downwelling was
declined by measurement, though the emissivity exponent it isolated was adopted 2026-08-29
on a separate owner ruling; item 3 remains gated on R1–R3.
*Enforced by:* `tests/integration/test_emission_placement_cu324.py` — the four-corner
downwelling ranking, the assertion that its $(\sec, z_{em})$ corner is bit-identical to the
shipped form, the shipped O₃ parity and the collapse of its one-sided warm bias, the
re-derived free optimum and the ruling's 15 % stop-and-flag tolerance, the concealment
inside the LWIR band mean, the M6–M8 residual-exceeds-signal arithmetic, and a delivery
tripwire on R1–R3;
`src/radiant/atmosphere/tests/test_ozone_placement.py` for the share's derivation from the
table rows, its continuity across both CU-267 ramps, τ bit-identity under a placement
change, and the emission-altitude sign in both directions;
`tests/integration/test_modtran_real_runs.py::test_esky_thermal_vs_the_nine_rung_downwelling_ladder`
for the adopted exponent against the shipped `evaluate`;
`src/radiant/atmosphere/tests/test_simple.py` for the constant's derivation from the anchor
angle and the shipped $E_{\text{sky,thermal}}$ equation that consumes it.

### 2.15 The 9.6 µm ozone region — τ parity before and after the split

CU-330 partitioned the calibrated table's 8.00–10.00 µm row at the O₃ ν₂ band. The fit is
the CU-161 machinery unchanged — the same three-point closed form on the same water ladder
(D4/A1/D5, us_standard rural 23 km, H₂O ×0.5/×1/×2), against the same "non-water =
Rayleigh + aerosol" convention. Only the partition moved, which is what makes the before
and after commensurable: re-running the identical form over the retired 8.00–10.00 µm span
returns the retired row (0.2751, 0.0877, 1.268) exactly.

**Where the edges are.** Per-wavelength water-free optical depth from the same closed form,
band means over the delivered ladder:

| Window [µm] | 8.60–9.30 | 9.30–9.40 | **9.40–9.90** | **9.90–10.00** | 10.00–10.30 |
|---|---:|---:|---:|---:|---:|
| water-free OD | 0.100 | 0.260 | **0.951** | **0.316** | 0.097 |

The rise completes inside 9.372 → 9.416 µm (OD 0.24 → 0.89) and the fall begins at
9.901 → 9.911 µm (0.52 → 0.33), so 9.40 and 9.90 µm each sit inside a ~0.05 µm transition
rather than on a plateau — and the 0.04 µm CU-267 ramp centred on 9.40 µm covers exactly
the interval the rise occupies. The tail is a genuine third level, 3.3× the continuum
beyond it, so it is its own region rather than part of either neighbour.

**The fitted rows.**

| Region [µm] | `floor_od` | $k$ | $b$ | role |
|---|---:|---:|---:|---|
| 8.00–9.40 | 0.1494 | 0.0992 | 1.204 | clean window — continuum + water |
| 9.40–9.90 | 0.8877 | 0.0409 | 1.701 | O₃ ν₂ core — 5.9× the window's floor |
| 9.90–10.00 | 0.3013 | 0.0379 | 1.805 | long-wave tail |
| *(retired)* 8.00–10.00 | *0.2751* | *0.0877* | *1.268* | one flat slab over all three |

The water term falls where the gas floor rises ($k$ 0.0992 → 0.0409) on a steeper exponent
($b$ 1.204 → 1.701), which is the consistency check that the split found gas and not
re-labelled water.

**Band-mean τ parity, model / MODTRAN, RMS $|\ln$ ratio$|$.** Thirteen full-column anchors
(D4, A1, D5, A2–A6, O5, H1, H2, H4, H5 — ground → 100 km) and twelve partial-column ones
(the K/N/O ground-to-air rungs, 1–20 km):

| Band [µm] | full column, before | full column, after | partial column, before | partial column, after |
|---|---:|---:|---:|---:|
| 8.0–9.4 (clean window) | 0.1606 | **0.0397** | 0.1755 | **0.0955** |
| 9.4–9.9 (O₃ core) | 0.5637 | **0.1747** | 0.1696 | **0.4731** |
| 9.9–10.0 (tail) | 0.0840 | **0.0814** | 0.2623 | **0.2163** |
| 8–12 | 0.0510 | **0.0482** | 0.1073 | **0.1047** |
| 8–14 | 0.0701 | **0.0676** | 0.1331 | **0.1306** |
| 11.5–12.5 (control) | 0.2238 | **0.2238** | 0.1794 | **0.1794** |

The 11.5–12.5 µm control is the discriminating row: it crosses no edge the split moved and
is unchanged to four decimals, which says the movement is the ozone region and not the
quadrature.

On the full columns — the geometry the fit was performed at — the clean window improves
**4.0×** and the band core **3.2×**. On the ladder anchors themselves the core ratio is
1.006/1.006/1.005 (D4/A1/D5), i.e. the fit reproduces its own anchors, and the held-out
profiles land at 0.81–1.12.

**The partial columns get worse in the core, and that is the finding.** 0.1696 → 0.4731,
with the shallow slant rungs worst (N9 0.452, O4 0.454, N4 0.561, K6 0.582 — all
model-too-opaque). The cause is not the fit: the calibrated floor rides the *molecular*
scale height, so the newly-identified ozone opacity is distributed as if it were well
mixed, and a 0–10 km column that in reality holds almost no ozone is handed most of it. The
flat slab concealed the same error by carrying only a third of the in-band opacity. This is
the τ-side face of CU-324 item 2, and §2.14(b) is the emission-side face of the same defect.

Why the wide LWIR bands move at all: the retired slab was fitted to $-\ln\langle\tau\rangle$
over 2 µm containing a deep 0.5 µm feature, and $-\ln\langle\tau\rangle < \langle-\ln\tau\rangle$
by Jensen's inequality, so a slab fitted to a band-mean τ *understates* the opacity it
stands in for. Width-weighted, the three new floors give 0.342 against the slab's 0.275.

*Record:* CU-330, owner-scheduled 2026-08-29, landed the same day. Results-affecting on
every 8–12 / 8–14 / 11.5–12.5 µm product; see the CHANGELOG entry for the moved goldens.
*Enforced by:* `tests/integration/test_gas_region_o3_fit_cu330.py` (the three rows
re-derived from the delivered ladder; the retired row re-derived from the same form; the
measured band edges; both parity tables above, pinned to ±0.002);
`src/radiant/atmosphere/tests/test_gas_region_o3_split.py` (the partition, the ozone
contrast, the derived share, the blend at the two new edges).

### 2.16 The VIS/NIR/SWIR floors — τ parity before and after the CU-335 re-fit

CU-161 fitted the calibrated table on 2026-07-17 against a model whose Rayleigh optical
depth was ~8× too large. `floor_add` is defined as the measured band opacity *in excess
of* what Rayleigh and aerosol already supply, clamped at zero rather than allowed to go
negative, so the inflated Rayleigh term drove every floor below 1.5 µm to the clamp.
CU-253 corrected Rayleigh on 2026-07-28 and the fit was never re-run. CU-335 re-runs it,
with the same generator, the same three-point closed form and the same D4/A1/D5 water
ladder.

**Per-row coefficients, before → after.** Only `floor_od` moves; $k$ and $b$ are solved
from the MODTRAN band optical depths alone and are bit-identical on all seventeen rows.

| Region [µm] | `floor_od` before | after | Δ |
|---|---:|---:|---:|
| 0.30–0.45 | 0.0000 | 0.0000 | 0 (still clamped — the rural-23 aerosol over-supplies this band) |
| 0.45–0.70 | 0.0000 | **0.1597** | +0.1597 |
| 0.70–1.30 | 0.0000 | **0.0517** | +0.0517 |
| 1.30–1.50 | 0.0000 | 0.0000 | 0 (saturated branch, floor-free by construction) |
| 1.50–1.75 | 0.0133 | **0.0219** | +0.0086 |
| 1.75–2.05 | 0.0000 | 0.0000 | 0 (saturated branch) |
| 2.05–2.40 | 0.0725 | **0.0749** | +0.0024 |
| 2.40–3.10 | 0.7434 | **0.7444** | +0.0010 |
| 3.10–3.50 | 0.1366 | **0.1371** | +0.0005 |
| 3.50–5.00 | 0.4497 | **0.4498** | +0.0001 |
| 5.00 µm and beyond (6 rows, incl. the CU-330 ozone triple) | — | — | **bit-identical** |

The ordering VIS > NIR > SWIR > MWIR > 0 is the Rayleigh $\lambda^{-4}$ signature, which
is the check that this re-fit followed a Rayleigh change and not, say, a change to the
water ladder. Every floor moved *up*, so the model is uniformly less transmissive or
unchanged — never more.

**The A1 anchor.** Over 0.45–0.70 µm on the us_standard full column the model read band
optical depth 0.320 against MODTRAN's 0.456 — τ 0.726 against 0.634, i.e. **14.6 % too
transmissive**. After the re-fit it reads 0.476, a **4.3 % OD overshoot** (τ 1.9 % low).
The residual overshoot is the mixed-grid artefact described below and is a seventh of the
error it replaced.

**Band-mean τ parity, model / MODTRAN, RMS $|\ln$ ratio$|$**, over the same thirteen
full-column and twelve partial-column anchors §2.15 uses:

| Band [µm] | full column, before | full column, after | partial column, before | partial column, after |
|---|---:|---:|---:|---:|
| 0.45–0.70 | 0.1556 | **0.0294** | 0.1456 | **0.0214** |
| 0.40–0.90 | 0.1035 | **0.0244** | 0.0893 | **0.0266** |
| 0.45–0.85 (standard VIS) | 0.1105 | **0.0440** | 0.0938 | **0.0434** |
| 0.85–1.40 (standard NIR) | 0.0461 | **0.0314** | 0.0383 | 0.0634 |
| 0.70–1.30 | 0.0312 | 0.0402 | 0.0263 | 0.0675 |
| 1.40–2.50 (standard SWIR) | 0.0758 | 0.0815 | 0.1141 | 0.1192 |
| 1.50–1.75 | 0.0366 | 0.0463 | 0.0500 | 0.0584 |
| 2.05–2.40 | 0.0430 | 0.0457 | 0.0502 | 0.0526 |
| 3.50–5.00 (MWIR control) | 0.1106 | **0.1107** | 0.1812 | **0.1812** |
| 8.00–12.00 (LWIR control) | 0.0482 | **0.0482** | 0.1047 | **0.1047** |

The two thermal controls are the discriminating rows: they are unchanged to the 0.002
resolution this metric is pinned at, which says the movement is the VIS/NIR/SWIR floors
and not the quadrature. The visible improves **5.3×** on the full columns and **6.8×** on
the partial ones; the two composite bands the scenarios actually integrate over improve
**4.2×** (0.40–0.90) and **2.5×** (0.45–0.85).

**0.70–1.30 µm gets worse, and the reason is measured.** The generator evaluates its
non-water reference on a uniform-$\lambda$ grid (3000 points over 0.30–14.29 µm) while
the ladder's band optical depth comes off the tape7 grid, which is uniform in
*wavenumber* and therefore weights the short-$\lambda$ end of a visible band more
heavily. Where the spectrum is steep — Rayleigh goes as $\lambda^{-4}$ — the two band
means disagree, and the difference lands in `floor_add`, always in the direction of an
over-large floor: **+0.022 OD at 0.45–0.70 µm, +0.011 at 0.70–1.30 µm, $\le 0.0004$
beyond 1.3 µm**. A tape7-grid-consistent reference would want ~0.0383 at 0.70–1.30 µm
where the generator gives 0.0517. The old row was under by 0.0383 and the new one is over
by 0.0134, so the *bias* falls ~3× while this particular RMS rises, because the residual
is now spread unevenly across the profile anchors rather than sitting one-sided. It is
recorded rather than corrected because correcting it means changing CU-161's calibration
convention, which is a new calibration and needs its own authorisation.

**A second residual, on attribution rather than magnitude.** 0.16 optical depths is far
more than real 0.45–0.70 µm gas chemistry supplies — the O₃ Chappuis band contributes
~0.03 and the O₂ B/A bands are narrow — so part of the visible floor is standing in for a
deficit in the aerosol model rather than for gas. The band *total* is now right against
MODTRAN; the split between gas and aerosol is not resolved by this fit, and the
consequence shows up wherever a scenario is scored against a source that assumes a
cleaner aerosol than the one configured (scenario 10.3's astronomical-extinction anchor
flips PASS → FAIL on exactly this).

*Record:* CU-335, owner-approved 2026-08-30, landed the same day. Results-affecting on
every VIS/NIR simple-model product — direction: **less transmissive, VIS SNRs drop**; see
the CHANGELOG entry for the moved goldens and scenario values.
*Enforced by:* `tests/integration/test_gas_region_visnir_refit_cu335.py` (the five moved
rows re-derived from the delivered ladder; the clamp mechanism reproduced by restoring
the pre-CU-253 Rayleigh; the mixed-grid offsets; the A1 anchor; both parity tables above,
pinned to ±0.002); `src/radiant/atmosphere/tests/test_gas_region_visnir_refit.py` (all
seventeen shipped rows, the $k$/$b$ bit-identity, the $\ge$ 5 µm bit-identity, and the
CU-267 blend invariants under the new floors).

---

## 3. Known limitations register

Each entry names what is not measured or not modelled, and where it is tracked.

| # | Limitation | Magnitude | Tracking home |
|---|---|---|---|
| 1 | **Region-flat spectral shape.** No line structure inside the 17 calibrated regions; the 0.04 µm edge ramps remove the discontinuity, not the flatness. Now the *named dominant residual* of the thermal path radiance. CU-330 is the one place a region was subdivided to resolve a real feature (the 9.6 µm O₃ band, §2.15) — a precedent for the fix, not the fix. | Under-reads up-looking MWIR thermal by 25–40 % on columns deeper than 5 km; over-reads down-looking MWIR by ~20 % on tall ones. Fixing needs a line-resolved or sub-region opacity model, not a further temperature refinement. | CU-161 resolution + `RADIANT_Atmosphere.md` §3.1 fragility paragraph. **No open registry entry** — a recorded model limitation, not scheduled debt. |
| 2 | **Provisional single-scatter VIS/NIR sky.** Multiple scattering dominates the daytime sky below ~3 µm. | Under-predicts the daytime VIS sky by roughly **2×** near the horizon (model/MODTRAN 0.55–0.59 at 85–89.5°, 0.76 at ζ = 0). CU-335 improved the up-looking VIS sky's worst excursion 1.361× → 1.217× on the shipped ladder, so the residual is now the scattering treatment alone, not scattering plus a τ deficit. See also row 14 for the VIS band's opacity attribution. | Gap 38; the sub-3 µm `UserWarning` (`SCATTERED_SKY_PROVISIONAL_MAX_UM`) is the operator-facing statement. |
| 3 | **Refraction is unmodelled and guard-banded.** The geometry is unrefracted. | ~0.5° of refractive lift near the horizon — comparable to the 0.5° raise band itself. The dominant geometric error inside the horizon guard's warn band, so numbers past ~85° are a better-conditioned model, not a validated one. | ADR-0011 decision 5; the on/off calibration pair Q5/Q6 is **unrun** (deck-builder gap, §1). |
| 4 | **Emission-placement refinements — all three measured; one adopted (§2.14).** (a) the $z_{em} = 200$ m downwelling proxy; (b) O₃ lumped with the well-mixed gases, so 9.6 µm emission was placed too low — **CLOSED 2026-08-30**; (c) grazing arcs distribute opacity vertically rather than along the arc. | (a) The layered replacement loses: it is worse than the $(\sec 48.2°, z_{em})$ corner on the P ladder (1.9385 vs 1.9233) and worse than the proxy on the tropospheric T_eff-only metric (0.3152 vs 0.2354), improving the LWIR 3.8× but degrading the MWIR 3.7×. Separately measured and **owner-ratified 2026-08-29 — adopted**: the fitted $D = 1.1$ exponent loses to the ladder's own $\sec 48.2° = 1.50030$ (composite 2.0776 → 1.9233; tropospheric-only 0.4167 → 0.3087), and the exponent is now geometric rather than fitted. (b) **No longer a limitation.** The τ-derived share of the in-band gas floor (0.8317, arithmetic on two committed table rows) now rides a 25 km Gaussian ozone layer: 9.4–9.9 µm RMS $|\ln|$ 0.3581 → 0.1389, warm pairs 12/14 → 5/14, 3.1 % off the free optimum it was never fitted to. What survives is narrower and belongs to the τ table, not the placement — see entry 15. (c) ≤ 1.2 % on M6–M8, under the 3–6 % residual there. | **CU-324, Open** (family head), items (a) and (b) discharged. (a)'s exponent was swapped 2026-08-29 and its layered-temperature half declined by measurement; **(b) landed 2026-08-30**; (c) is gated on R1–R3. |
| 5 | **Grazing thermal is anchored only where the anchors are blind.** M6–M8 do exercise a grazing thermal product, but their own 3–6 % residual exceeds the 1.2 % placement effect, so they cannot settle item 4(c). | Sized by proxy instead: modelled along-arc ÷ vertical separation is 2.9 %/2.4 % at a 2 km tangent endpoint, 7.9 %/9.8 % at 5 km, 16.1 %/13.1 % at 8 km (MWIR/LWIR) and exactly 0 at 15 km, where the ICAO profile is isothermal. | CU-324 checklist item 3. Run-matrix rows **R1–R3** authored 2026-08-29 for the discriminating geometry (tangent-rooted arcs at 5/8/10 km, ANGLE 90°); **unrun**. A delivery tripwire fails when their tape7s land. |
| 6 | **sec-space is unvalidated past 88.8°.** The interpolation coordinate diverges at the horizon and is refused there. | M6–M8 (85/88/89.5°) were run and *are* usable as physics anchors (§2.4), but are excluded from every shipped node set, so the interpolated backend cannot serve that band at all. | `_MAX_ZENITH_RAD` refusal in `interpolated.py`; M6–M8 marked `dev_only` in the run matrix. |
| 7 | **Only two site elevations have a full-column family.** 0 m (`midlat_summer_sst_column_fan`) and 900 m (`midlat_summer_sst_column_fan_site900m`, M9–M13, ingested 2026-08-03). Neither carries a `sensor_altitude_m` axis, so no third elevation can be interpolated. | Sized by the pair: at nadir the 900 m column transmits 0.702 band-mean 8–12 µm against the 0 m column's 0.583, and at sec 5 it is 0.302 against 0.137 — i.e. the lowest 900 m of air is worth +0.12 to +0.16 in band-mean LWIR τ, which is why a site elevation cannot be ignored. A site at any other elevation is `simple`. | The two families' node geometry; `tests/integration/test_batch2_atmosphere_families.py::TestSstColumnFanSite900m`. The `pending_runs` advisory on the 0 m fan was retired when M9–M13 landed. |
| 8 | **Downwelling above 80 km is modelled.** Every rung at or below 80 km is measured since P7/P8 landed (2026-08-03); only an off-node query strictly between 80 km and the 100 km atmosphere top is still log-linear extrapolation. | Bounded rather than open-ended: such a query is bracketed by a measured 80 km value below and the exact-zero identity above, and **no shipped family holds a node in that band**. The retired 60/80 km extrapolation had over-stated the measured values by 10.6× and 8 791× (MWIR) — see §2.5 — which is the size of the error this delivery removed. | §2.5 model-vs-measured table; `tests/integration/test_batch2_atmosphere_families.py::TestCu181AltitudeDependentDownwelling`. Closes the owner's 2026-08-02 ratification-pending-measurement ruling. |
| 9 | **Long-range MWIR horizontal paths.** The analytic arm's $\tau(2L) = \tau(L)^2$ collapses against a band model. | model/MODTRAN 1.09 → 0.01 over 5 → 100 km at 3 km altitude in the MWIR (§2.6); LWIR degrades to 0.82. | Measured and documented; the remedy is a MODTRAN or interpolated backend. No A5 horizontal library family is built. |
| 10 | **Airmass linearity on saturated bands.** The air-mass factor stays linear while real saturated bands grow sub-linearly off-nadir. | Measured MWIR OD ×1.18 at 45° against Beer's ×1.41. | CU-161 fragility list, `RADIANT_Atmosphere.md` §3.1. |
| 11 | **Twilight transit is unanchored.** Q7/Q8 were delivered but are `dev_only` — no family or parity test consumes them. | The transit carries 30–70 air masses, where both the exponential τ and the unmodelled refraction are at their worst. Treat as an order-of-magnitude bound. | `RADIANT_Atmosphere.md` §4.2e PROVISIONAL banner; run-matrix rows Q7/Q8. |
| 12 | **`theta_s` stripped for pure-thermal targets.** A `T1Thermal` target has its solar geometry stripped upstream, and the sky background is a second consumer of it, so a pure-thermal target on a VIS/NIR grid gets a thermal-only sky at noon — and no provisional warning, because the trigger condition is never met. | The scattered sky component is absent for that scene class. | Documented in `RADIANT_Atmosphere.md` §4.2g and pinned as a characterization by `tests/integration/test_direction_aware_atmosphere.py::TestProvisionalScatteredSkyWarning`. **No registry entry.** |
| 13 | **Aerosol Ångström law beyond 5 µm.** Frozen at its 5 µm value rather than decaying. | A deliberate clamp toward physical behaviour, warned once per run; a tabulated IR aerosol cross-section remains the higher-fidelity alternative. | CU-088, resolved 2026-07-12; `RADIANT_Atmosphere.md` §12 open question 2. |
| 14 | **VIS band opacity is right in total, mis-attributed in detail.** CU-335 (§2.16) closed the *magnitude* error — the 0.45–0.70 µm band total now sits within 4 % of MODTRAN at the anchor geometry, against 30 % under before — but it did so by putting 0.1597 optical depths on the well-mixed **gas** floor, and real 0.45–0.70 µm gas chemistry supplies only ~0.03 (O₃ Chappuis, narrow O₂ B/A). The remainder is the aerosol model's own deficit, wearing a gas label. | Band total: within 4 % (was 30 % under). Attribution: ~0.13 of 0.16 optical depths is aerosol dressed as gas, so any product that separates the two — or is scored against a source assuming a *cleaner* aerosol than the one configured — reads wrong. Scenario 10.3's astronomical-extinction anchor flips PASS → FAIL on exactly this. | §2.16; Gap 38. Superseded the pre-CU-335 statement ("~2× high at rural-23"), whose sign the CU-253 Rayleigh correction had already reversed. |
| 15 | **The gas-floor fit mixes two spectral grids.** `floor_add` is the ladder's band optical depth (tape7 grid, uniform in wavenumber) minus the model's non-water reference (uniform-λ grid). Where the spectrum is steep the two band means differ and the gap lands in the floor. | +0.022 OD at 0.45–0.70 µm, +0.011 at 0.70–1.30 µm, ≤ 0.0004 beyond 1.3 µm — always toward an over-large floor. It is why 0.70–1.30 µm band-mean τ parity moved 0.0312 → 0.0402 while the visible improved 5.3× (§2.16). | §2.16; pinned as a characterization by `tests/integration/test_gas_region_visnir_refit_cu335.py::test_the_nonwater_reference_grid_is_the_generators`. **No open registry entry** — correcting it changes CU-161's calibration convention and would need its own authorisation. |
| 14 | **VIS aerosol absolute OD.** Not recalibrated by the CU-161 gas-band pass. | ~2× high at rural-23. | CU-161 fragility list; Gap 38. |
| 15 | **Ozone opacity rides the molecular scale height on the τ side.** The calibrated `floor_od` is apportioned to a partial column by the fraction $\text{col}_{\text{mol}}/H_{\text{mol}}$, so a 0–5 km column is handed 9.6 µm ozone opacity that is not physically there. The emission side now places whatever ozone a segment is given at 25 km (§2.14b), which makes the τ-side mis-attribution visible instead of cancelling it. Two further narrowings sit alongside: the 9.90–10.00 µm long-wave tail (floor 0.3013, 3.3× its continuum) is still placed as well mixed, and the ICAO profile is isothermal above 11 km, so the layer's own centre/width remain weakly observable. | Shallow-column LWIR: model/MODTRAN moves away from unity on the 1/3/5 km rungs (§2.3, e.g. 1.059 → 1.079 at 5 km) while the 10 and 20 km rungs move toward it (0.950 → 1.020). Full columns are unaffected — that is the geometry the floor was fitted at. Layer geometry is worth ≤ 2.4 % across the measured 20–30 km × 3–8 km grid. | **No open registry entry.** The remedy is an ozone-aware *vertical* apportionment on the τ side (a per-species profile in the region table), which is CU-161-scale work, not a placement refinement. §2.15's partial-column row is the same finding read on τ. |

---

## 4. Reproducing these numbers

- **The run set** is tracked in git under `modtran/real_runs/` (owner decision 2026-08-02;
  gitignored staging before that), with `real_runs_MANIFEST.sha256` and a `README.md`
  recording the delivery. Every anchor suite is `skipif`-guarded on its presence.
- **The library** under `src/radiant/data/tables/atmospheres/` is generated from that set by
  `scripts/build_atmosphere_library.py` (with `scripts/downwelling_altitude.py` for the
  altitude-resolved downwelling ladder), slit-degraded to 5 cm⁻¹ FWHM. Per-file provenance
  and packaging decisions are in that tree's `MANIFEST.md`.
- **The gas-band calibration** is generated by `scripts/fit_simple_atmosphere_gas_bands.py`
  from the D4/A1/D5 water ladder.
- **The anchor suites** listed throughout are the executable form of this document. Running
  them is the check that it is still true:

```bash
pytest tests/integration/test_emission_temperature_anchors.py \
       tests/integration/test_species_split_anchors.py \
       tests/integration/test_segment_modtran_anchors.py \
       tests/integration/test_batch2_fixture_anchors.py \
       tests/integration/test_batch2_atmosphere_families.py \
       tests/integration/test_uplooking_horizontal_anchors.py \
       tests/integration/test_modtran_real_runs.py \
       src/radiant/atmosphere/tests/test_near_horizon_air_mass.py \
       src/radiant/atmosphere/tests/test_near_horizon_handover.py \
       src/radiant/atmosphere/tests/test_log_tau_resample.py \
       src/radiant/atmosphere/tests/test_gas_region_blend.py \
       src/radiant/atmosphere/tests/test_level_whole_path.py \
       src/radiant/atmosphere/tests/test_downlooking_path_thermal.py -q
```
