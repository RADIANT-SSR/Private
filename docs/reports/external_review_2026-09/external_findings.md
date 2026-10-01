# RADIANT findings — LWIR point-source / co-adding review

**Status:** Complete (point-in-time record, Rule 24 — immutable; corrections are new documents)
**Received:** 2026-09-30
**Author:** external reviewer (independent radiometric model reconciliation)
**Engine reviewed:** `v0.3.0-1-g8948dd43` (clean checkout, editable install)
**Reproduction config:** `repro_lwir_point_source.yaml` — NOT SUPPLIED with the report; see
`verification.md` for the in-repo reproduction RADIANT used to confirm each finding.

> Filed verbatim as received. RADIANT's own verification, measured independently,
> is in `verification.md`; dispositions are in `dispositions.md`.

---

## Context

These findings come from reconciling RADIANT against an independently developed
radiometric model of the same sensor — a fast (f/1) LWIR point-source detection
case, cold-space background, no atmosphere, heavy frame co-adding. The two
models were built from different first principles, so where they disagreed one
of them was wrong; each disagreement was chased to a mechanism.

Everything below is stated in RADIANT's own terms and is reproducible from the
attached config alone. No external model or data is needed. All numbers were
measured, not derived on paper — where a first reading of the source turned out
to be wrong, the empirical result is what is reported.

The reproduction case is deliberately round-numbered and generic: f/1, 50 mm
focal length, 8–10 µm, 20 µm pitch, QE 0.5, a 300 K / 20 m² / ε 0.5 point source
at 1000 km, one reflective element at 290 K. It is not a real design.

---

## Finding 1 — Warm-optics emission silently becomes zero in scalar transmission mode

**Severity: critical.** Wrong answer, no warning, changes the detection verdict.

`optics.nearfield_enabled` defaults to 1, and modes 1–4 of
`optics.transmission_input_mode` synthesize lumped elements with ε = 0 and
T = 0 K (`src/radiant/optics/transmission_modes.py:43`,
`_SYNTHESIZED_TEMPERATURE_K`). The nearfield loop skips any element at 0 K
(`src/radiant/optics/nearfield_irradiance.py:139`), so a config using
`transmission_input_mode: scalar` produces **identically zero** warm-optics
irradiance while `nearfield_enabled: 1` is set — and nothing warns.

For any thermal-band system the warm optics is usually the dominant background.
In the reproduction case it is 95 % of it.

**Measured** (attached config, only change is swapping the `optical_elements:`
document for the equivalent `transmission_scalar: 0.6`):

| | element document | scalar mode |
|---|---|---|
| `detector.nearfield_e` | 7.787e8 | **0** |
| `snr` | 2.377 | **45.302** |
| warnings raised | — | **0** |

**19× optimistic SNR, silently.** In a variant of this case the effect also
flipped `detection_range_m` from *declined* (below the SNR threshold) to a
confidently reported 1 117 783 m — a fabricated detection range for an
undetectable target.

The underlying design is defensible: a synthesized lump is not a surface, so
its Kirchhoff emissivity is 0, and `optics.optics_temperature_K` was removed
2026-09-10 on exactly that ground. **The defect is not the model, it is the
silence.**

**Suggested fix, in priority order:**

1. Warn when `nearfield_enabled = 1` and the active transmission mode contains
   no emitting surface: *"nearfield is enabled but no declared surface can emit;
   warm-optics irradiance is identically zero — declare an `optical_elements:`
   train or set `nearfield_enabled: 0`."*
2. Consider promoting it to an error when the band is thermal (say
   `filter_max_um > 3`), where a zero warm-optics term is almost never intended.
3. Optionally add a lumped-emissive convenience (scalar ε + T) so the common
   case does not require a full prescription.

This is the highest-value single change in this document.

---

## Finding 2 — 1/f noise is co-added as if it were uncorrelated

**Severity: critical.** Systematic, large (√N), and silent.

`flicker_1f` is listed in `TEMPORAL_TERMS`
(`src/radiant/core/noise_budget.py:22-31`), so under `coadd_mode: sum` it is
scaled by **√K** (`coadd_scale_temporal_noise`,
`src/radiant/readout/coadds.py:47-67`).

1/f noise is *temporally correlated by definition*. Power at frequencies below
1/T_total is common to every frame in the stack and does not average down.
RADIANT already has the correct machinery for this — `coadd_scale_fpn`
(`src/radiant/readout/coadds.py:70-79`) scales correlated systematics by **K**,
with the comment "FPN is the same systematic in every frame" — but 1/f is not
routed through it.

**Measured** (attached config, `detector.flicker_K: 1.0e8`):

| `n_coadds` | `flicker_1f` [e-] |
|---|---|
| 1 | 42 919.3 |
| 500 | 959 705 |

Ratio **22.36 = √500**. Correlated scaling would give 500. **RADIANT
under-reports co-added 1/f by up to √N — a factor of 22 at 500 co-adds.**

**Why it matters beyond the factor.** For a 1/f-limited staring sensor, 1/f
grows ∝ N while signal also grows ∝ N, so co-adding does **not** improve SNR —
it can make it worse once any per-frame efficiency loss is included. That is
the central design trade between a staring sensor and a modulated/chopped one
that moves its signal off the 1/f knee. **RADIANT currently cannot reach that
conclusion**: it reports co-adding as a large win in exactly the regime where
the physics says it is not. In the reconciliation that surfaced this, RADIANT
gave SNR 7.9 for a co-added staring case the other model put at 0.32 — a 25×
disagreement, and the entire disagreement was this term.

**Suggested fix.** Neither √N nor N is exactly right; the honest model is
frequency-aware, since 1/f power above 1/T_total partially averages while power
below it does not. But √N is the *optimistic bound* and is wrong for any
1/f-limited stack. Options, in increasing fidelity:

1. Reclassify `flicker_1f` as correlated (×K under SUM). Conservative, one-line,
   and defensible — it is the standard engineering treatment.
2. Better: scale it with an explicit correlation model over the stack duration,
   using `readout.frame_period_s` × `n_coadds` as T_total against
   `flicker_f_low_hz`. Power below 1/T_total scales ×K, above it ×√K.
3. Whichever is chosen, report the applied exponent per term (see
   *Recommended outputs* below) so the assumption is visible rather than buried.

Note also that `flicker_1f_noise`
(`src/radiant/detector/noise/detector_material.py:96`) is
**signal-independent**: `σ = √(K·ln(f_hi/f_lo))`. Many hand-built sensor models
parameterise 1/f as *signal-proportional* (`σ = α·S·√(ln(...))`), because
that is what is measured on a real ROIC. The two forms are not algebraically
interchangeable, so `flicker_K` can only be calibrated at a single operating
point and does not transfer across integration time, signal level, or co-add
count. **Consider accepting an α + frame-bandwidth input mode alongside
`flicker_K`.** Without it, cross-validating RADIANT against a vendor or
in-house noise model requires a per-point refit.

---

## Finding 3 — `detector.dark_rate_e_per_s` upper bound excludes real LWIR detectors

**Severity: blocking.** A legitimate detector cannot be expressed.

Bound is `(0.0, 1e9)` e-/s/pixel (`src/radiant/detector/_schema.py:219`). A
20 µm pixel at a dark-current density of 1 A/m² (a routine LWIR figure —
1e-4 A/cm²) requires **2.5e9 e-/s**:

    1 A/m^2 * (20e-6 m)^2 / 1.602e-19 C = 2.50e9 e-/s

Large-pixel LWIR parts exceed the ceiling by design, not by mistake. The
bound's stated justification — *"order-of-magnitude room-temperature Si CCD
reference"* — is the rationale for the **default** (100.0), not for the
ceiling.

**Effect when pinned at the ceiling:** dark contributed 40 % of its true value
in the reconciliation case, making RADIANT ~1.5 % optimistic on total noise
there (dark was only 5 % of that background; in a dark-dominated design the
error would be far larger and would not be recoverable by any workaround —
`detector.glow_e_per_s` caps at 1e6 and cannot absorb the remainder).

**Suggested fix:** raise the ceiling to ~1e12. There is no modelling cost;
nothing downstream assumes a magnitude.

---

## Finding 4 — `validate` passes configs that `evaluate` rejects

**Severity: moderate.** Undermines the purpose of a validate command.

`radiant validate` reported **"Study OK — 3 configuration(s), 0 failed"** for a
study in which two of three configurations could not run. Evaluating them
raised:

    ReadoutStage: up/down-only parameter(s) ['readout.reference_source',
    'readout.reference_integration_s'] are explicitly set while
    readout.counting_mode = 'up'. ...

The error itself is excellent — precise, actionable, names the remedy. The
problem is that the check lives in `_validate_architecture_params`
(`src/radiant/readout/stage.py:124`), which runs during
`ReadoutStage.run`, i.e. only under `evaluate`.

**Suggested fix:** run the architecture cross-parameter validators from the
validate path too. More generally, audit which stage-level cross-checks are
reachable from `validate` — a validate that misses whole classes of
configuration error trains users not to rely on it.

---

## Finding 5 — A `configurations:` study cannot express architecture-conditional parameters

**Severity: moderate.** Structural limitation, no workaround within a study.

`configurations.parameters` lists are **dense by construction** — one value per
name, mismatch is an error, never padded (ADR-0010 D-A,
`src/radiant/io/config_set_section.py`). But some parameters are legal only for
certain values of another parameter: `readout.reference_integration_s` and
`reference_source` are accepted only under `counting_mode: up_down`, and being
*explicitly set* is what triggers the refusal — including when set to 0.

So a study comparing an `up` configuration against an `up_down` one **cannot
name the reference parameters at all**. Density and conditional legality are in
direct conflict.

In the case that surfaced this there was a clean escape: an unset
`reference_integration_s` defaults to equal phases (`t_down = t_up`, ruling D7,
`src/radiant/readout/stage.py:752`), which was the wanted value anyway. That is
luck, not a general answer — a study that needs a *non-default* conditional
parameter has nowhere to put it.

**Suggested fix:** allow an explicit null/omitted sentinel in a
`configurations.parameters` list meaning "leave at default for this member",
distinct from a set value. This preserves density (the list length still
matches) while restoring expressiveness.

---

## Finding 6 — `radiant schema` crashes on a default Windows console

**Severity: minor bug, trivially fixed.**

    UnicodeEncodeError: 'charmap' codec can't encode character 'α'
      in position 159: character maps to <undefined>

A parameter description contains `α`; the click `echo` path writes through
cp1252 on a default Windows terminal. The command is unusable without
`PYTHONIOENCODING=utf-8`.

**Suggested fix:** force UTF-8 on the CLI output stream (or ASCII-fold
descriptions at the point of tabular output). Worth a sweep for other
non-ASCII in schema descriptions — `µ`, `λ`, `ε`, `Ω`, `τ` are all likely
present and all fail the same way.

---

## Finding 7 — The integration tests dirty the working tree

**Severity: minor, but it corrupts provenance.**

A plain `pytest` run rewrites the tracked file
`tests/integration/_use_case_coverage.json` with CRLF line endings on Windows.
Content is unchanged; the diff is line endings only. The consequence is real
though: `git describe --dirty` then reports `-dirty`, and since RADIANT resolves
the git commit at the loaded package location for export stamps, **every result
exported after a test run is stamped dirty** even though the source is
byte-identical.

**Suggested fix:** write the coverage artifact under `build/` and gitignore it,
or add `* text eol=lf` for it via `.gitattributes`, or stop tracking it. A test
run should not modify tracked files.

---

## Where RADIANT was demonstrably the better model

Recorded so the list above is not read as a scorecard. In each of these the
external model was wrong and RADIANT was right.

**Acceptance cone.** RADIANT uses the exact
`Ω = 2π(1 − cos(arctan(1/2N)))` (`src/radiant/optics/etendue_cone.py:33`).
Hand-built models very often use the paraxial `π/(4N²)`. At f/1 these are
0.6633 sr and 0.7854 sr — the paraxial form is **18.4 % high**, and since it
multiplies the warm-optics term directly it can dominate a whole noise budget
disagreement. In the reconciliation, the Ω ratio (0.844582) matched the
warm-optics signal ratio (0.844553) to 3e-5, i.e. it accounted for the entire
discrepancy in that term.

*Suggestion:* state the convention explicitly in `RADIANT_Optics.md` §7 with
the divergence from `π/(4N²)` at fast f/#. Anyone reconciling against another
model will otherwise spend a day finding this. A short doc note is enough; an
optional paraxial mode is probably not worth the footgun.

**Saturation and well bookkeeping.** Under
`readout.architecture: digital_counting` the effective well is derived as
`2^counter_bits × count_packet_e`, and RADIANT *refuses* an explicit
`full_well_capacity_e` as over-specification. That refusal caught a real
problem: at a 16-bit counter the reproduction-class case overflows on
**background alone**, before any target. A model without a counter-depth
concept cannot see that, and will happily report SNR for a configuration that
physically cannot integrate. This is RADIANT working exactly as intended.

**Quantization on the counting path.** With `residue_readout: false`,
`counting_quantization_noise_e` returns `Q_pkt/√12`
(`src/radiant/readout/counting_quantization.py`) — which agreed with the
external model to **13 significant figures** (2309.401077 e- at an 8000 e-
packet). No discrepancy at all.

**Sub-pixel smear.** RADIANT applies motion as an MTF. A common closed-form
alternative adds the motion *linearly* to the source box width, which gives a
20.5 % signal loss for 0.33 px of motion against a 1.02 px PSF. Quadrature —
`σ' = √(σ² + m²/12)` — gives 2.34 %, and RADIANT measured 2.07 %. Linear
addition is valid only when smear ≫ PSF width. RADIANT is right by an order of
magnitude here, and a model using the linear form will be badly pessimistic on
detection range.

**Reference-phase noise.** `counting_mode: up_down` charges the down phase its
own shot noise and the docstring explicitly forbids omitting it ("any model
subtracting the mean without adding reference-phase noise is flattering and
forbidden here"). Measured penalty at equal phases: **×1.4118 = √2**. Many
chopped-sensor models subtract the background mean and charge √(background)
only once, which is optimistic by up to √2. Keep this strictness.

One bonus from that strictness: it was possible to *explain* an empirically
fitted "excess noise factor" of 1.12 in the external model — documented there
only as unexplained excess above the shot limit — as the reference-phase penalty
of a short down phase. Sweeping the duration, a ratio of 0.2544 gives 1.1192.
A first-principles model that reproduces someone else's fudge factor is the best
possible advertisement for it.

---

## Unit and interop mismatches

None of these are errors; all of them are hand-conversion steps where a silent
factor-of-10^n mistake is easy and undetectable. Each is a candidate for an
accepted alternate input unit, since RADIANT already has a unit layer
(`radiant convert`) and an `input_unit` concept in its schema.

| Quantity | Common external convention | RADIANT wants | Conversion needs |
|---|---|---|---|
| Dark current | **A/m²** or A/cm² (current density) | `dark_rate_e_per_s` [e-/s/pixel] | pixel area **and** q — two chances to slip, and the m²/cm² choice is a 10⁴ trap |
| Radiance / flux | photons: ph/s/m²/sr | watts: W/m²/sr/µm | photon energy, hence an effective wavelength |
| Noise-equivalent | photon NER / NEI [ph/s/m²] | `W/m²/sr`, `W/m²` | same |
| 1/f | α, dimensionless, signal-proportional | `flicker_K` [e-²], signal-independent | not convertible in general — see finding 2 |
| DFPA gain | "conversion gain [e-/DN]" | `count_packet_e` [e-/count] | none numerically, but the *meaning* differs: an analog gain and a charge-subtraction quantum are not the same parameter, and picking `analog_well` + `gain_e_per_dn` for a digital focal plane silently mis-models the well and the quantization |
| Acceptance cone | paraxial π/(4N²) | exact 2π(1−cosθ) | 18.4 % at f/1 — see above |
| Band→scalar | effective wavelength, e.g. λ_min + ⅔Δλ | full spectral integration | RADIANT is right; just know the other model's λ_eff when comparing |

**Highest-value additions:** accept `detector.dark_current_density_A_per_m2`
(and `_A_per_cm2`) with internal conversion, and offer photon-unit NER/NEI
outputs. Between them they remove most of the hand arithmetic in a
cross-model check.

---

## Recommended informational outputs

The single biggest lesson from this exercise: **RADIANT's failures of
communication cost far more time than its failures of physics.** The physics was
right nearly everywhere it was checked. What burned hours was a dominant term
silently evaluating to zero, and a co-add scaling assumption that is invisible
in the output.

Ranked by value:

1. **Warn on silently-zero dominant terms.** Finding 1 is the archetype. The
   general rule: if a term is *enabled by a parameter* and evaluates to exactly
   zero because of a modelling choice elsewhere, say so. Candidates:
   `nearfield_enabled` with no emitting surface; `flicker_K` = 0 while
   `noise_regime` implies 1/f matters; stray-light enabled with a zero
   coefficient.

2. **A background-composition breakdown.** Report each contributor to the
   no-target background as an absolute and a **percentage of total**:
   nearfield, dark, scene, stray, glow. One line of output would have made
   finding 1 obvious in seconds instead of after a code read. It also tells a
   designer immediately where to spend effort.

3. **Per-term co-add scaling exponent in the noise breakdown.** Alongside each
   scaled term, report what scaling was applied (×√K, ×K, ÷√K) and its
   correlation class. Finding 2 is invisible today: the number is simply
   smaller than it should be, with nothing to indicate why. This also makes the
   temporal/spatial classification auditable by the person best placed to
   notice it is wrong.

4. **Echo derived and converted quantities.** `Omega_cone` is already in
   `stage_outputs` and was decisive — surface that class of value prominently,
   with units: acceptance cone, effective well (and whether it came from a
   counter or an analog well), counts, IFOV, effective wavelength, per-pixel
   dark rate if it was converted from a density. Anything RADIANT *computed*
   from user input is exactly what an external model will disagree about.

5. **Photon-unit NER/NEI alongside radiometric.** See the units table.

6. **Say when a metric is declined *and* what would change that.** RADIANT
   already names the reason a metric is absent (the `metric_selection` record
   is good). For `detection_range_m` specifically, it is declined whenever the
   current range is below threshold — but detection *range* is the natural
   headline output of a point-source model, and it is precisely what you want
   when the current range does **not** meet threshold. `solve_for`
   (`src/radiant/api/solve.py`) already does brentq root-finding on any
   parameter, so the machinery exists. Either wire it to detection range, or
   document the recipe prominently as the supported route.

---

## Summary

| # | Finding | Severity |
|---|---|---|
| 1 | Warm optics silently zero in scalar transmission mode | **critical** |
| 2 | 1/f co-added as uncorrelated (√N, should be ≈N) | **critical** |
| 3 | `dark_rate_e_per_s` ceiling excludes real LWIR parts | blocking |
| 4 | `validate` passes configs `evaluate` rejects | moderate |
| 5 | Studies cannot express architecture-conditional parameters | moderate |
| 6 | `radiant schema` crashes on Windows cp1252 | minor bug |
| 7 | Tests dirty the tree, corrupting export provenance | minor |

Findings 1 and 2 are both silent and both large. Neither produces an error, a
warning, or an implausible-looking number — they produce a confident, wrong,
optimistic answer. They should be fixed before RADIANT is used to size a
co-adding thermal point-source system.
