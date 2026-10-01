# Verification of the 2026-09-30 external review

**Status:** Complete (point-in-time record, Rule 24 — immutable)
**Date:** 2026-09-30
**Verified against:** `v0.3.0-1-g8948dd43` (`main`, clean tree)
**Reviewed document:** `external_findings.md`

The reviewer's `repro_lwir_point_source.yaml` was not supplied with the report.
Every finding was therefore re-confirmed against in-repo artifacts instead, so
the verification stands on its own.

---

## Verdict

**Seven findings, seven confirmed, zero false positives.** Three are worse than
the report could see from outside; two are Rule 30 violations; one was already
known internally and lost (see `dispositions.md`, CU-387).

| # | Finding | Verified | Note |
|---|---|---|---|
| 1 | Warm optics silently zero | **CONFIRMED** | reproduced on a *shipped* example; already known internally |
| 2 | 1/f co-added as uncorrelated | **CONFIRMED** | two further coupled defects found; half already known internally |
| 3 | `dark_rate_e_per_s` ceiling | CONFIRMED | bound `(0.0, 1e9)` at `detector/_schema.py:219` |
| 4 | `validate` ≠ `evaluate` | CONFIRMED | `validate_all` is resolution-only by design |
| 5 | Conditional params in studies | CONFIRMED | dense-by-construction vs. conditional legality |
| 6 | Windows cp1252 crash | **CONFIRMED, broader** | no stream reconfiguration anywhere in `cli/` |
| 7 | Tests dirty the tree | **CONFIRMED, harder** | unconditional Rule 30 breach, two sites |

---

## Finding 1 — reproduced on a shipped example

The report used a bespoke f/1 LWIR config. The same mechanism fires on
`examples/mwir_leo_minimal.yaml`, **unmodified** — 3.5–5.0 µm,
`transmission_scalar: 0.70`, `optics.nearfield_enabled` defaulted to 1:

```
elements:                        [('lumped', 0.0 K)]
optics.nearfield_irradiance_at_fpa (sum):  0.0
optics.nearfield_per_element:    {}
detector.nearfield_e:            0.0
warnings raised:                 []
```

So RADIANT's own documented MWIR reference case models zero warm optics and
says nothing. Magnitude, re-declaring the same net τ = 0.70 as two 290 K gold
mirrors (`R = √0.70` each):

| | `nearfield_e` [e-] | `signal_e` [e-] | SNR |
|---|---|---|---|
| scalar (as shipped) | 0 | 1.2635e6 | 1124.03 |
| 290 K two-mirror train | 4.652e5 | 1.2635e6 | 960.98 |

The shipped reference number is **17 % optimistic**, and the omitted warm term
is 37 % of signal. It is modest *here* only because the case is
signal-dominated (extended scene, 300 K target filling the pixel); the
reviewer's f/1 LWIR point-source case was 19× on the same mechanism. **The
error scales with how background-dominated the case is.**

**Exposure across the repo**, by transmission mode and band:

| | count |
|---|---|
| `scenarios/` + `examples/` files using a non-prescription transmission mode | 54 |
| …of those, thermal band (`filter_max_um > 2.5 µm`) | **39** |
| …of those 39, point-source / sub-pixel / detection-range | **5** |
| files declaring an `optical_elements:` train | 25 |

The 5 point-source cases are where this flips verdicts rather than shading
them. The other 34 are extended-scene thermal, in the ~17 % class.

---

## Finding 2 — confirmed, plus two further coupled defects

Co-add scaling confirmed directly:

```
K=   1  temporal x   1.000   fpn x     1.0
K= 100  temporal x  10.000   fpn x   100.0
K= 500  temporal x  22.361   fpn x   500.0      (sqrt(500) = 22.360679...)
```

Two defects the report did not reach, both already recorded in
`scenarios/02_mike_detector_engineer/2.2_1f_noise_corner_frequency/gaps.md`
(Gaps 1 and 2 there, both `Open`):

| | defect | direction of error | found by |
|---|---|---|---|
| a | `f_high` not capped at the corner frequency `f_c`; above `f_c` the PSD is white and already counted as read noise | σ **too big** — 64–170 % measured at 30–120 Hz | scenario 2.2 Gap 1 |
| b | `f_low` is a free parameter whose default (0.01 Hz) corresponds to no timing in the model; scenario 2.2's own script uses the frame rate instead | either | scenario 2.2 Gap 2 |
| c | co-add ×√K averages down power that cannot average | σ **too small** — up to ×√K | external F2 |

**(a) and (c) pull in opposite directions and partially cancel.** That is why
the term looked plausible for so long and why no test caught it: the model is
wrong in two directions at once. Additionally, σ_1f is currently independent of
`t_int` altogether — a 100 µs frame and a 100 ms frame get the identical value.

**Architectural note.** The correlation-aware dispatch this needs already
exists at `readout/stage.py:222`: `clutter` is scene-correlated so always ×N,
while PRNU/DSNU go ×N under digital TDI and ×√N under analog. `flicker_1f`
wants ×√N analog TDI / ×N digital TDI (same pixel re-read), ×√M ×√P on
binning, and correlated treatment on co-add. **It stays in `TEMPORAL_TERMS`** —
1/f *is* temporal noise, so the RSS classification is already right and only
the scaling dispatch is wrong. Reclassifying it as spatial (the report's
option 1) would mis-report it as fixed-pattern in the RSS.

**Blast radius: `flicker_K` defaults to 0.0.** The only things that set it are
one GUI test and scenario 2.2's script (whose own `gui.yaml` sets 0.0). No
golden baseline moves.

---

## Findings 3–7

**F3.** Bound `(0.0, 1e9)` confirmed at `detector/_schema.py:219`, with
`default_justification="Order-of-magnitude room-temperature Si CCD reference."`
— the rationale for the *default* (100.0), applied to the ceiling. The same
default-justifies-ceiling pattern needs a sweep, not a single fix:
`glow_e_per_s` capping at 1e6 is the reviewer's own evidence.

**F4.** Confirmed structural. `ConfigurationSet.validate_all`
(`api/config_set.py:1152`) documents itself as *"Resolution only — no physics
runs"*, while `_validate_architecture_params` runs inside `ReadoutStage.run`.
Nothing is wrong with either; there is simply no stage-level dry-run
validation hook between them.

**F5.** Confirmed. Dense-by-construction `configurations.parameters` (ADR-0010
D-A) vs. parameters whose legality is conditional on another parameter's value,
where *being explicitly set* is the trigger. No in-study workaround exists.

**F6 — broader than reported.** There is no `sys.stdout.reconfigure` anywhere
in `src/radiant/cli/`. Non-ASCII in schema descriptions confirmed across three
`_schema.py` files (`µ` in spectral_integration and platform; `α`, `Ω`, `₀` in
detector). Worse: RADIANT's *error messages* routinely carry `µ` and `°`, so on
a default Windows console a parameter-bounds error can itself die in
`UnicodeEncodeError` — the diagnostic fails exactly when it is needed. Rule 30
requires unmodified Windows operation; the CLI does not meet it.

**F7 — harder than reported.** Both coverage writers call `write_text()` with
**no `encoding="utf-8"` and no `newline="\n"`**:

- `tests/integration/test_use_case_matrix.py:371`
- `tests/integration/test_spec_form_matrix.py:176`

Those are unconditional Rule 30 breaches independent of the dirty-tree
symptom, which they compound: a test run should not write a tracked file at
all. Note `.gitattributes` already carries `* text=auto eol=lf`, so the
CRLF-diff symptom is dependent on local git configuration; the Rule 30
violation is not.

---

## Confirmed in RADIANT's favour

Spot-checked and upheld: the exact étendue acceptance cone
`Ω = 2π(1 − cos(arctan(1/2N)))` (`optics/etendue_cone.py:33`) against the
paraxial `π/(4N²)` the reviewer's model used; the digital-counting well
derivation refusing an explicit `full_well_capacity_e`; `Q_pkt/√12` on the
counting path; smear as an MTF rather than a linear box-width addition; and the
`up_down` reference-phase shot-noise charge. No action beyond one doc note (the
acceptance-cone convention in `RADIANT_Optics.md` §7), logged to
`Findings_Log.md`.

---

## Reproduction

Commands used are in `reproduce.py` in this folder (run with `PYTHONPATH=./src python docs/reports/external_review_2026-09/reproduce.py` from the repo root). All results above were
measured on `v0.3.0-1-g8948dd43` with `PYTHONPATH=./src`.
