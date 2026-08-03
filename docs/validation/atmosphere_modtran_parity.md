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
| **M** SST full-column fan | M1–M13 | Ground sensor → 100 km top, uniform sec ladder; M6–M8 the 85/88/89.5° probes; **M9–M13 the 900 m elevated-site mirror** | **8/13** | library (M6–M8 dev) |
| **N** up-looking zenith fan | N1–N10 | Targets 1–20 km × lower-endpoint zenith 48.2°/60° (rectangular with K) | 10/10 | fixture + library |
| **O** upwelling emission anchor | O1–O5 | Down-looking partners of K/N/H on identical columns — the direction-pair set | 5/5 | fixture + library |
| **P** elevated downwelling | P1–P8 | Sky radiance at 48.2° from elevated lower endpoints 1–80 km; **P7/P8 the 60/80 km rungs** | **6/8** | fixture + library |
| **Q** horizon guard / twilight | Q1–Q8 | Long horizontal arms past the sag thresholds (Q1–Q4), the **refraction on/off pair (Q5/Q6)**, twilight tangent transits (Q7/Q8) | **6/8** | dev |

**Counts.** 132 authored rows; **123 delivered tape7 runs** plus 4 Block-E flux sidecars =
127 delivered artifacts. Batch 1 (A–L) is 88 rows, all delivered 2026-07-17 / 2026-07-26.
Batch 2 as authored at delivery (M1–M8, N, O, P1–P6, Q) is 37 rows, of which 35 were
delivered 2026-08-02. Seven further rows were authored *after* that delivery and are
unrun: M9–M13 (2026-08-02, CU-322 intake) and P7/P8 (2026-08-02, CU-181 closure).

**The nine pending rows, and why:**

| Rows | Why pending |
|---|---|
| M9–M13 | Authored after the batch-2 delivery. They mirror the delivered M-fan with the lower endpoint lifted to 900 m — the elevated-site SST geometry. At ingestion they either add a sensor axis to `midlat_summer_sst_column_fan` or ship as a sibling family. |
| P7, P8 | Authored at CU-181 closure. The shipped 60 km and 80 km downwelling rungs are currently **modelled** (log-linear extrapolation on the measured 29→50 km slope, clamped non-increasing); these runs replace them with measurements. |
| Q5, Q6 | **Deck-builder gap.** `render_tape5` has no refraction field, so RADIANT cannot express the refraction-OFF leg: Q5.tp5 renders byte-identical to Q3.tp5 and Q6.tp5 to M8.tp5 on purpose. The operator must disable MODTRAN's ray-bending for those two runs and record which switch was used. Q3−Q5 is the interior-tangent half of the refraction calibration; M8−Q6 the endpoint-minimum half at the 0.5° raise-band edge. |

Q7/Q8 (twilight tangent transits) *were* delivered, with Card-3 ANGLE hand-set to 93°/96°
and `LENN = 1` per the matrix instruction, and the hand edit is verified against the matrix
by the Card-3 echo sweep. Both rows are `dev_only`: no family ingests them and no
radiometric parity test consumes them, so the twilight branch's transmittance is still
unanchored (§3).

*Enforced by:* `tests/integration/test_batch2_atmosphere_families.py` (the 35-row delivered
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
| 60 † | 3.387948e−3 | 156.0 | 2.865881e−3 | 1 300 | — |
| 80 † | 3.021602e−3 | 174.9 | 3.471554e−4 | 1.073e+4 | 766 300 |
| 100 | 0 (exact) | ∞ | 0 (exact) | ∞ | 6.44e+7 |

† modelled by log-linear extrapolation on the measured 29 → 50 km slope, clamped
non-increasing. P7/P8 replace them with measurements when run.

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
criterion and ratifying the modelled 60/80 km rungs pending P7/P8.
*Enforced by:* `tests/integration/test_batch2_atmosphere_families.py` (the altitude-resolved
downwelling, the measured decay pinned against the entry's own table, 12 distinct arrays
where there was 1, ground-target nodes byte-identical). Independently reproduced from the
shipped NPZs 2026-08-03, all digits.

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
with its own fitted constants (theory §2.11). Band-integrated model / MODTRAN at the fit:

| Run | LWIR | MWIR | Pre-fix LWIR | Pre-fix MWIR |
|---|---:|---:|---:|---:|
| H2 `us_standard` | 1.24 | 0.70 | 0.21 | 0.02 |
| H4 `tropical` | 1.41 | 1.34 | 0.21 | 0.03 |

The residual ±40 % tracks the region-flat spectral-shape fragility, not temperature
structure. These ratios are **unchanged by CU-321** — the hemispheric product does not
move, because its $z_{em}$/$D$ pair is fit jointly through its own closed form and a
directional product cannot inherit it.

*Record:* CU-155 resolved 2026-07-18 (commit `77d8ad2`), scope narrowed 2026-08-02.
*Enforced by:* `tests/integration/test_segment_modtran_anchors.py` Truth Anchors 2 and 3;
`tests/integration/test_modtran_real_runs.py` (the H2/H4 flux parity envelope,
[1.0, 1.6] LWIR and [0.55, 1.5] MWIR, and the $\omega_{0,\text{eff}}$ re-derivation guard).

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
edges. Vertical ground → 700 km, θ_o = 0, rural-23, `midlat_summer` PWV 2.92 cm, τ_up
evaluated ±1e−9 µm either side of each edge:

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

*Record:* CU-267, resolved 2026-08-01, owner-ratified.
*Enforced by:* `src/radiant/atmosphere/tests/test_gas_region_blend.py` (40 Level-0 tests;
the interior-control bands, the no-overlap invariant, the exact edge-mean hand anchors).
The step table above is **(record only)** — the tests pin the *blended* behaviour, which is
what ships.

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

---

## 3. Known limitations register

Each entry names what is not measured or not modelled, and where it is tracked.

| # | Limitation | Magnitude | Tracking home |
|---|---|---|---|
| 1 | **Region-flat spectral shape.** No line structure inside the 15 calibrated regions; the 0.04 µm edge ramps remove the discontinuity, not the flatness. Now the *named dominant residual* of the thermal path radiance. | Under-reads up-looking MWIR thermal by 25–40 % on columns deeper than 5 km; over-reads down-looking MWIR by ~20 % on tall ones. Fixing needs a line-resolved or sub-region opacity model, not a further temperature refinement. | CU-161 resolution + `RADIANT_Atmosphere.md` §3.1 fragility paragraph. **No open registry entry** — a recorded model limitation, not scheduled debt. |
| 2 | **Provisional single-scatter VIS/NIR sky.** Multiple scattering dominates the daytime sky below ~3 µm. | Under-predicts the daytime VIS sky by roughly **2×** near the horizon (model/MODTRAN 0.55–0.59 at 85–89.5°, 0.76 at ζ = 0). Also the ~2×-high rural VIS aerosol OD. | Gap 38; the sub-3 µm `UserWarning` (`SCATTERED_SKY_PROVISIONAL_MAX_UM`) is the operator-facing statement. |
| 3 | **Refraction is unmodelled and guard-banded.** The geometry is unrefracted. | ~0.5° of refractive lift near the horizon — comparable to the 0.5° raise band itself. The dominant geometric error inside the horizon guard's warn band, so numbers past ~85° are a better-conditioned model, not a validated one. | ADR-0011 decision 5; the on/off calibration pair Q5/Q6 is **unrun** (deck-builder gap, §1). |
| 4 | **Emission-placement refinements.** (a) the $z_{em} = 200$ m downwelling proxy, now computable rather than approximated; (b) O₃ lumped with the well-mixed gases, so 9.6 µm emission is placed too low; (c) grazing arcs distribute opacity vertically rather than along the arc. | Each results-affecting if pursued; none operator-visible today. | **CU-324, Open** (family head, three checklist items). |
| 5 | **Grazing thermal is unanchored.** No delivered deck exercises a grazing *thermal* product, so item 4(c) is unmeasured. | Unknown — needs an anchor before it can be sized. | CU-324 checklist item 3 (an anchor is named as a prerequisite). |
| 6 | **sec-space is unvalidated past 88.8°.** The interpolation coordinate diverges at the horizon and is refused there. | M6–M8 (85/88/89.5°) were run and *are* usable as physics anchors (§2.4), but are excluded from every shipped node set, so the interpolated backend cannot serve that band at all. | `_MAX_ZENITH_RAD` refusal in `interpolated.py`; M6–M8 marked `dev_only` in the run matrix. |
| 7 | **No elevated-site SST column.** The SST full-column fan has its lower endpoint at 0 m; a 900 m observatory/SST site is not measured. | Unquantified — M9–M13 mirror the delivered fan at 900 m specifically to size it. | Run-matrix rows M9–M13 (authored 2026-08-02 at CU-322 intake); surfaced programmatically as the `pending_runs` field on `midlat_summer_sst_column_fan`. |
| 8 | **Modelled 60/80 km downwelling rungs.** Log-linear extrapolation on the measured 29 → 50 km slope, clamped non-increasing. | The measured profile is non-monotonic in the MWIR below 50 km, so the extrapolation's shape assumption is not verified above it. | Owner ruling 2026-08-02 (ratified pending measurement); run-matrix rows P7/P8. |
| 9 | **Long-range MWIR horizontal paths.** The analytic arm's $\tau(2L) = \tau(L)^2$ collapses against a band model. | model/MODTRAN 1.09 → 0.01 over 5 → 100 km at 3 km altitude in the MWIR (§2.6); LWIR degrades to 0.82. | Measured and documented; the remedy is a MODTRAN or interpolated backend. No A5 horizontal library family is built. |
| 10 | **Airmass linearity on saturated bands.** The air-mass factor stays linear while real saturated bands grow sub-linearly off-nadir. | Measured MWIR OD ×1.18 at 45° against Beer's ×1.41. | CU-161 fragility list, `RADIANT_Atmosphere.md` §3.1. |
| 11 | **Twilight transit is unanchored.** Q7/Q8 were delivered but are `dev_only` — no family or parity test consumes them. | The transit carries 30–70 air masses, where both the exponential τ and the unmodelled refraction are at their worst. Treat as an order-of-magnitude bound. | `RADIANT_Atmosphere.md` §4.2e PROVISIONAL banner; run-matrix rows Q7/Q8. |
| 12 | **`theta_s` stripped for pure-thermal targets.** A `T1Thermal` target has its solar geometry stripped upstream, and the sky background is a second consumer of it, so a pure-thermal target on a VIS/NIR grid gets a thermal-only sky at noon — and no provisional warning, because the trigger condition is never met. | The scattered sky component is absent for that scene class. | Documented in `RADIANT_Atmosphere.md` §4.2g and pinned as a characterization by `tests/integration/test_direction_aware_atmosphere.py::TestProvisionalScatteredSkyWarning`. **No registry entry.** |
| 13 | **Aerosol Ångström law beyond 5 µm.** Frozen at its 5 µm value rather than decaying. | A deliberate clamp toward physical behaviour, warned once per run; a tabulated IR aerosol cross-section remains the higher-fidelity alternative. | CU-088, resolved 2026-07-12; `RADIANT_Atmosphere.md` §12 open question 2. |
| 14 | **VIS aerosol absolute OD.** Not recalibrated by the CU-161 gas-band pass. | ~2× high at rural-23. | CU-161 fragility list; Gap 38. |

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
