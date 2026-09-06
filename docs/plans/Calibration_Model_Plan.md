# Calibration Stage and Radiometric Error-Budget Capability — Development and Test Plan

**Status:** Active — §12 decisions D1–D7 ratified by the owner 2026-09-06 (all
recommended options adopted). The architecture direction (dedicated `CalibrationStage`
+ dedicated GUI screen, bias kept apart from noise) was owner-shaped in discussion
2026-09-06. Phase 0 is ready to start.

**Date:** 2026-09-06
**Gap:** 120 (`docs/tracking/gaps.md`)
**Category:** C overall (physics implementation); Phase 0 is Category B (core
abstractions + schema), Phases 3–4 are Category D (GUI integration, scenarios).

**Read first:**
`docs/architecture/RADIANT_Master_Architecture.md`,
`docs/architecture/RADIANT_Signal_Chain_Architecture.md`,
`docs/architecture/RADIANT_Parameter_System.md`,
`docs/architecture/RADIANT_Detector_Complete.md`,
`docs/architecture/RADIANT_Metrics.md`,
`docs/architecture/RADIANT_Testing_Validation.md`,
`docs/architecture/RADIANT_GUI_Architecture.md` (Phase 3),
`docs/archive/Digital_Pixel_Readout_Plan.md` (Gap 117 — the structural precedent this
plan follows for a chain-capability + GUI + scenario expansion).

---

## 1. Objective

Add a **calibration error model** to RADIANT: the residual errors left by a real
system's radiometric calibration process — post-NUC residual fixed-pattern noise,
gain/offset drift since the last calibration event, and calibration-source
uncertainty — and a **radiometric accuracy budget** that is reported alongside, and
never mixed into, the precision metrics (SNR, NEDT).

The physics this makes expressible, none of which the current model can state:

1. **Calibration-limited NEDT.** For cooled staring IR systems the achieved NEDT is
   frequently set by post-NUC residual FPN, not by the temporal noise floor. Today
   RADIANT reports the temporal floor as *the* NEDT and systematically flatters
   designs.
2. **Correlated errors do not average down.** TDI, coadds, and on/off-chip binning
   reduce temporal noise by $\sqrt{N}$. Calibration residuals are correlated
   frame-to-frame (and along-column for TDI/pushbroom — the origin of streaking and
   banding), so they are exempt from that gain. The current model overstates
   integration gain exactly when an analyst leans on it.
3. **Precision vs. accuracy.** NEDT/NEdL are precision metrics. Absolute calibration
   error (gain/responsivity uncertainty, offset drift, blackbody cal-source $T$ and
   $\varepsilon$ uncertainty) sets *accuracy* — the bias of a retrieved radiance or
   temperature. `performance/temperature_retrieval.py` currently carries no accuracy
   statement at all.

The governing constraint mirrors Gap 117's: **everything upstream is unchanged**, and
the default configuration (`calibration.scheme = none`) reproduces today's results
bit-identically. Golden drift is zero until an analyst turns the model on.

---

## 2. Architecture

### 2.1 A new terms-only stage: `CalibrationStage`

A new physics stage `src/radiant/calibration/`, registered in `api/session.py`
**between Readout and Performance**. Precedent: `PlatformStage` is already a
terms-only stage (smear/jitter MTF contributions, no frame transformation); the
calibration stage is the same species on the noise/bias side. It transforms no frame
and collapses no spectrum; it reads upstream `stage_outputs` (signal level, detector
and readout gain context) and contributes:

- **noise terms** (spatial, post-NUC residual FPN family) via `state.with_noise(...)`;
- **bias terms** (accuracy budget) via the new `state.with_bias(...)` (§2.3);
- **stage outputs** (`stage_outputs["calibration"]`): the derived residual budget the
  GUI readout panel and the accuracy metric consume.

Why a stage and not modules inside detector/readout (the alternative considered and
rejected 2026-09-06):

- **The chain position does physics work** (§2.2) — the $\sqrt{N}$ exemption falls
  out of ordering instead of a term-classification convention.
- **Screen-per-stage invariant.** The GUI's single primary navigation is the
  signal-chain strip; every screen is a chain stage 1:1
  (`STAGE_COMPOSITIONS` keyed by `RadiantSession.stage_names`). Calibration as a
  stage gets its own screen without breaking that invariant — the owner's explicit
  UX requirement.
- **One namespace, one YAML block.** `calibration.*` parameters live in one
  `_schema.py`, and a saved config reads with one `calibration:` block instead of
  fragments under `detector:` and `readout:`.
- **Growth path.** Cal cadence trades, scene-based NUC, and onboard-source modeling
  (a cal source that does not see the fore-optics) are ops-level concepts spanning
  detector and readout; the stage is where they will live.

### 2.2 Ordering enforces the correlation physics

Readout applies TDI/coadd/binning scaling to temporal noise terms
(`tdi_scaling.py`, `coadds.py`). The calibration stage runs **after** readout, so its
residual-FPN terms are added to `ChainState.noise_terms` *post-scaling* and are
structurally exempt from $\sqrt{N}$ averaging — no scaling code needs to know about
them. This is the load-bearing ordering argument; it is asserted by an explicit
contract test (§6) and documented in the stage doc so a future refactor cannot move
the stage without tripping both.

For explicitness (and to guard any future re-scaling code path), the calibration term
names are also registered in a `CALIBRATION_TERMS` frozenset in
`core/noise_budget.py`, parallel to Gap 117's `COUNTING_TERMS`. Classification sets:
the new terms join `SPATIAL_TERMS` (they are spatial noise); `CALIBRATION_TERMS`
additionally marks them correlated-across-integration.

### 2.3 One `ChainState` addition: the bias accumulator

New frozen dataclass `BiasTerm` in `core/radiometry.py` (parallel to `NoiseTerm`):
`name`, `value` (canonical unit: fractional radiance bias, dimensionless; converted
to K-at-scene-temperature by the metric layer), `origin` (which uncertainty produced
it), plus a short `description`. New `ChainState` field
`bias_terms: tuple[BiasTerm, ...] = ()` and method `with_bias(term)` in
`core/chain.py`.

The separation is **type-enforced**: SNR/NEDT consume `noise_terms` only; the
radiometric-accuracy metric consumes `bias_terms` only. Nothing expressed as a
`BiasTerm` can leak into $\sigma_{total}$, and a guard test (§6) asserts the SNR path
never reads `bias_terms`. Biases combine by RSS *within* the accuracy budget
(independent sources) but are never RSS'd with noise.

This is a documented `ChainState` surface change → lock-step update to
`RADIANT_Signal_Chain_Architecture.md` in the same PR (Rule 20).

### 2.4 ADR

`docs/adr/0012-calibration-stage.md` records: terms-only stage between Readout and
Performance; ordering-enforced $\sqrt{N}$ exemption; `BiasTerm` accumulator and the
bias-never-RSS'd-with-noise rule; the rejected alternative (modules scattered in
detector/readout + a non-stage GUI screen) and why the screen-per-stage invariant and
the ordering argument decided it. Written in Phase 0, before code.

### 2.5 What this deliberately does NOT touch

- **The spatial/MTF dual path (Rule 4).** Residual FPN is spatial *noise*, not a
  spatial *degradation*: it has no PSF kernel and no MTF term. Neither path gains a
  contributor; `consistency_check.py` is unaffected. Stated in the stage doc so
  nobody "helpfully" adds an FPN MTF term later.
- **Spectral integration (Rule 8).** All calibration computation is post-integration,
  scalar per-pixel.
- **The Gap 117 counting chain.** DROIC packet/residue terms are orthogonal;
  `scheme=none` interacts with nothing. Two-point NUC on a counting readout is
  supported by the same formulas (they operate on integrated signal $S$ regardless of
  readout architecture).

---

## 3. Physics model

### 3.1 Calibration schemes

`calibration.scheme ∈ {none, one_point, two_point}`.

- **`none` (default):** today's model, restated. `detector.prnu_pct` acts as gain
  dispersion on the full signal ($\sigma = \mathrm{prnu} \cdot S$, the existing
  `prnu_noise`); `detector.dsnu_e_rms` passes through unchanged. The calibration
  stage contributes zero terms. Bit-identical goldens, asserted.
- **`one_point`:** offset corrected at cal flux $S_1$; residual offset dispersion
  is zeroed at the cal instant and re-grows by drift (§3.3); gain dispersion is
  uncorrected, acting on the *departure* from the cal point:
  $\sigma_{gain}(S) = \mathrm{prnu} \cdot |S - S_1|$.
- **`two_point`:** per-pixel gain and offset corrected at cal fluxes $S_1, S_2$
  (from cal-source temperatures $T_1, T_2$ through the band — computed with the
  chain's own Planck/band machinery, not a new one). Linear response error vanishes
  at both cal points; the residual is set by per-pixel **nonlinearity dispersion**
  (§3.2) plus drift (§3.3).

Under `one_point`/`two_point`, `detector.prnu_pct` and `detector.dsnu_e_rms` are
re-documented as **pre-correction** dispersions — the inputs the calibration process
acts on. This closes the double-counting hole by construction: the detector-stage
`prnu_noise`/`dsnu_noise` terms are suppressed when a scheme is active and replaced
by the calibration stage's residual terms (decision D2 fixes the exact mechanism).

### 3.2 Post-NUC residual FPN (two-point)

v1 model: per-pixel quadratic response dispersion. Pixel response
$S_{pix} = g\,(S + \beta S^2/S_{ref})$ with $g$ dispersed by PRNU and $\beta$
dispersed with standard deviation `calibration.nonlinearity_pct` (fraction, of the
full-scale-referenced quadratic coefficient; $S_{ref}$ = detector full well). Exact
two-point correction of the *linear* model leaves the quadratic residual; the
per-pixel residual after correction is

$$\Delta S(S) = \sigma_\beta \cdot \frac{(S - S_1)(S_2 - S)}{S_{ref}}$$

in RMS across the array — a parabola that vanishes at both cal points, peaks between
them, and grows quadratically outside them. This is the classical two-point
correctability result (Schulz & Caldwell form; truth anchor §13.1); the exact
normalization is pinned by the Level-0 derivation in Phase 1, not by this plan.
Output: noise term `nuc_residual` [e⁻ RMS], spatial, calibration-correlated.

Fidelity note (decision D1): the fallback v1, if the owner prefers fewer knobs, is a
direct user-specified residual (`calibration.nuc_residual_pct` of signal) with the
parabolic model deferred. The plan is written for the parametric model; D1 chooses.

### 3.3 Gain and offset drift

Between calibration events the correction decays. v1 is time-linear:

- gain: $\sigma_{gain\_drift} = r_g \cdot t_{cal} \cdot S$ with $r_g$ =
  `calibration.gain_drift_frac_per_s` (input unit %/hour), $t_{cal}$ =
  `calibration.time_since_cal_s` (input unit hours);
- offset: $\sigma_{offset\_drift} = r_o \cdot t_{cal}$ with $r_o$ =
  `calibration.offset_drift_e_per_s`.

Both enter as spatial, calibration-correlated noise terms (`gain_drift`,
`offset_drift`). FPA-temperature-driven drift ($\partial/\partial T_{FPA}$ terms) is
explicitly deferred (D4) — time-domain drift is the v1 abstraction.

### 3.4 Cal-source uncertainty → bias

The calibration source's own uncertainty does not disperse pixel-to-pixel — it moves
the whole array's radiometric scale. Two inputs:

- `calibration.source_temp_uncertainty_K` ($\Delta T_{src}$): fractional radiance
  bias $\Delta L / L = \frac{1}{L}\frac{\partial L}{\partial T}\Big|_{T_{cal}} \cdot
  \Delta T_{src}$, evaluated with the chain's band-integrated Planck derivative
  (LWIR at 300 K ≈ 1.5–1.7 %/K; anchor §13.4).
- `calibration.source_emissivity_uncertainty` ($\Delta\varepsilon$): radiance scale
  bias $\Delta L / L = \Delta\varepsilon / \varepsilon_{src}$.

Plus a direct `calibration.gain_uncertainty_pct` for systems whose absolute cal
budget is known as a number. All three produce `BiasTerm`s, never `NoiseTerm`s.

### 3.5 Noise-vs-bias classification (normative)

| Effect | Kind | Enters | Term/field |
|---|---|---|---|
| Post-NUC residual FPN | spatial noise, correlated | $\sigma_{total}$ (post-scaling) | `nuc_residual` |
| Gain drift since cal | spatial noise, correlated | $\sigma_{total}$ (post-scaling) | `gain_drift` |
| Offset drift since cal | spatial noise, correlated | $\sigma_{total}$ (post-scaling) | `offset_drift` |
| Cal-source $\Delta T$ | bias | accuracy budget only | `BiasTerm(source_temp)` |
| Cal-source $\Delta\varepsilon$ | bias | accuracy budget only | `BiasTerm(source_emissivity)` |
| Absolute gain uncertainty | bias | accuracy budget only | `BiasTerm(gain)` |

---

## 4. Parameter schema (`calibration/_schema.py`)

All defaults produce the `none` limit; every parameter is a `ParameterDef` (Rule 12);
canonical units per `RADIANT_Conventions.md` (time in s, fractions dimensionless,
temperatures K); input units chosen for the analyst (hours, %) with conversion at
`params.set()` only (Rule 2).

| Parameter | dtype | canonical / input unit | default |
|---|---|---|---|
| `calibration.scheme` | enum | — | `none` |
| `calibration.cal_temp_low_K` | float | K / K | `None` (required if scheme ≠ none) |
| `calibration.cal_temp_high_K` | float | K / K | `None` (required if two_point) |
| `calibration.nonlinearity_pct` | float | fraction / % | 0.0 |
| `calibration.time_since_cal_s` | float | s / hour | 0.0 |
| `calibration.gain_drift_frac_per_s` | float | 1/s / %/hour | 0.0 |
| `calibration.offset_drift_e_per_s` | float | e⁻/s / e⁻/hour | 0.0 |
| `calibration.source_temp_uncertainty_K` | float | K / K | 0.0 |
| `calibration.source_emissivity_uncertainty` | float | fraction / fraction | 0.0 |
| `calibration.source_emissivity` | float | fraction / fraction | 1.0 |
| `calibration.gain_uncertainty_pct` | float | fraction / % | 0.0 |

Validation (Rule 16, actionable per Rule 15): `cal_temp_high_K > cal_temp_low_K`;
cal temps required by scheme (a scheme with missing cal points raises
`CalibrationConfigError` telling the analyst which parameter to set); uncertainties
non-negative; `source_emissivity ∈ (0, 1]`. Cal-point *fluxes* $S_1, S_2$ are derived
from cal temps inside the stage — never independent inputs (over-specification
guarded the same way Rule 5 guards emissivity).

Schema change ⇒ **full GUI suite runs on every phase** (the `_schema.py` rule), and
`gen_param_reference.py` regeneration rides each schema-touching PR.

---

## 5. Module layout (Rule 19 — one computation, one module)

```
src/radiant/calibration/
├── __init__.py
├── _schema.py            # §4 ParameterDefs
├── errors.py             # CalibrationConfigError (RadiantError subclass)
├── stage.py              # CalibrationStage — orchestration only, no formulas
├── cal_points.py         # cal temps → cal fluxes S1, S2 via chain band machinery
├── nuc_residual.py       # §3.2 residual FPN (scheme dispatch: none/1pt/2pt)
├── gain_drift.py         # §3.3 gain drift term
├── offset_drift.py       # §3.3 offset drift term
├── cal_source_bias.py    # §3.4 bias terms (ΔT, Δε, gain uncertainty)
└── tests/
    ├── test_nuc_residual.py      # Level 0 first (Rule 18)
    ├── test_drift.py
    ├── test_cal_source_bias.py
    ├── test_stage.py             # scheme dispatch, none ⇒ zero terms
    └── test_schema_roundtrip.py  # serialization + failure modes (Category B)
```

Core changes: `core/radiometry.py` (`BiasTerm`), `core/chain.py` (`bias_terms`,
`with_bias`), `core/noise_budget.py` (`CALIBRATION_TERMS`, `SPATIAL_TERMS` additions).
Detector change: `detector/noise/fixed_pattern.py` PRNU/DSNU suppression under an
active scheme (mechanism per D2). API change: `api/session.py` stage registration.
Tooling: `pyproject.toml` import-linter contracts add `radiant.calibration` to the
physics-stage lists (three contract sites).

---

## 6. Performance integration

- **`performance/radiometric_accuracy.py`** (new, own module per Rule 19): consumes
  `bias_terms`, reports total bias as % radiance and as K at scene temperature
  (via the chain's $\partial L/\partial T$ at the scene, the same machinery NEDT
  uses), with a per-source breakdown and a result-typed failure path (Rule 17
  metric-layer carve-out). Registered in `performance/registry.py` and the Gap 96
  metric-selection machinery; relevance rules in `scene_relevance.py` (accuracy is
  relevant whenever a thermal scene is declared; always available on demand).
- **NEDT share diagnostic:** `stage_outputs["calibration"]` carries each residual
  term's NEDT-equivalent ($\sigma_i / (\partial S/\partial T)$) so the GUI can show
  "calibration share of NEDT" without a new metric.
- **Contract tests (the two structural guarantees):**
  1. *$\sqrt{N}$ exemption:* with TDI/coadds at $N$ and $N' > N$, calibration terms
     in the final budget are identical while temporal terms scale — asserted on a
     full-chain run.
  2. *Bias isolation:* SNR/NEDT results are bit-identical with bias terms present
     vs. absent; the accuracy metric changes. (Plus a static check: nothing under
     `performance/snr.py`/`nedt.py` references `bias_terms`.)

---

## 7. GUI — the Calibration screen

Registration in `api/session.py` puts `calibration` into
`RadiantSession.stage_names`, which drives the signal-chain strip and parameter-panel
ordering automatically; the center composite is a new `STAGE_COMPOSITIONS`
entry in `stage_views.py`. Composition (one screen, edit-and-watch like Source/GT-0):

1. **Scheme selector card** leads the screen (it steers what the rest means — same
   rationale as the Geometry scene-class card), reusing the Gap 117
   `architecture_switch.py` selector pattern: `none / one-point NUC / two-point NUC`,
   evaluate-time errors surfaced as advisories (the Phase-3 third-pass convention).
2. **Contextual parameter groups**, shown per scheme (the Gap 117 contextual-group
   convention): cal points (two_point shows both temps), drift (time-since-cal +
   rates), source uncertainty ($\Delta T$, $\Delta\varepsilon$, gain %).
   `scheme=none` shows the selector plus a short "model off — today's PRNU/DSNU
   behavior" note, nothing else.
3. **Derived readout panel** (the edit-and-watch payoff): residual FPN terms in
   e⁻ RMS, their NEDT-equivalents and share of total NEDT, and the accuracy budget
   (% and K) with per-source breakdown — precision and accuracy side by side,
   visibly separate columns, never one number.
4. **Noise-budget plot hook:** the existing `result.plot.noise_budget` gains the
   calibration terms automatically (they are ordinary `NoiseTerm`s); the Detector and
   Readout views' budget note gets a pointer to the Calibration view.

Hard-rule compliance: display units follow the user's chosen units everywhere
(hours for time-since-cal, %/hour for drift — entry/display symmetric, no mental
math); every displayed number carries units; pinned-card support and Edit-Config YAML
round-trip come from the standard parameter machinery but are explicitly tested (§8).

**Live-review loop applies (hard rule, ratified 2026-09-01): the Phase 3 branch
launches for the owner before any merge; the gate battery runs only after approval.**

---

## 8. GUI testing

New tests in `src/radiant/gui/tests/` (full suite runs at every phase anyway — schema
change rule):

1. **Registration/strip:** `calibration` appears in `stage_names` between `readout`
   and the performance surface; `STAGE_COMPOSITIONS` has the key; strip renders one
   node per stage (count assertion catches a missed composition).
2. **Scheme switch on real configs** (the Gap 117 live-review lesson, learned twice):
   switching `none → one_point → two_point → none` on a *loaded real config* (mission
   template + a scenario YAML) never raises, never strands hidden-group values, and
   restores the `none` limit exactly.
3. **Contextual visibility:** per-scheme group show/hide matrix.
4. **Display-unit symmetry:** time-since-cal entered as hours reads back as hours;
   drift-rate round-trip; unit labels present on every readout value.
5. **Readout-panel truth:** panel values equal the scripting-API values
   (`result` / `stage_outputs["calibration"]`) — one action ↔ one API call, no
   GUI-side arithmetic.
6. **Default regression:** fresh session shows `scheme=none`, zero calibration terms
   in the noise-budget plot, and no accuracy card — the screen exists but is quiet.
7. **YAML round-trip / export:** Edit-Config round-trips the `calibration:` block;
   xlsx export includes the namespace.
8. **Advisory surface:** an incomplete scheme (two_point with one cal temp) at
   evaluate time surfaces as an advisory in Messages, never a crash, and never a
   swallowed error (Rule 17).

---

## 9. Documentation deliverables

**New documents:**

| Document | Content |
|---|---|
| `docs/architecture/RADIANT_Calibration.md` | Stage doc: §2 architecture, §3 model, term/bias tables, the two structural guarantees, the Rule-4 non-interaction note, deferred items (D4, ops-level cal cadence) |
| `docs/adr/0012-calibration-stage.md` | §2.4 decision record |

**Lock-step updates (Rule 20), each in the PR that crosses the surface:**

| Document | Change |
|---|---|
| `RADIANT_Master_Architecture.md` | Stage list + document map + chain-flow line gain `calibration` |
| `RADIANT_Signal_Chain_Architecture.md` | `ChainState.bias_terms` + `with_bias`; stage roster |
| `RADIANT_Parameter_System.md` | `calibration.*` namespace |
| `RADIANT_Detector_Complete.md` | PRNU/DSNU re-documented as pre-correction dispersions; suppression semantics (D2) |
| `RADIANT_Metrics.md` | Radiometric-accuracy metric; NEDT precision-vs-accuracy note |
| `RADIANT_GUI_Architecture.md` | §4.4.1 composition table row for the Calibration screen |
| `RADIANT_Testing_Validation.md` | New golden set registration |
| `CLAUDE.md` | Package-layout tree + import-rules table gain `calibration/` |
| `CHANGELOG.md` | Per phase: (b) new surface at Phase 0/2, (c) capability at Phase 2, results-affecting note scoped to scheme≠none |

Generated: `gen_param_reference.py` output regenerated in every schema-touching PR.

---

## 10. Scenarios

Per the scenario hard rules: every scenario carries `walkthrough.md`,
`gui_workflow.md` (GUI requirements — the calibration screen actions the operator
performs), scenario-local `gaps.md`, `inputs/`, `outputs/`, `scripts/`; script output
explains regime and physics with units on every number.

1. **New — `scenarios/02_mike_detector_engineer/2.7_calibration_limited_nedt`**
   (rides Phase 4). LWIR staring HgCdTe, two-point NUC at 290/310 K, scene swept
   280–340 K. Deliverables: NEDT vs. scene temperature showing the parabolic
   calibration floor vanishing at cal points and dominating away from them; a
   time-since-cal sweep showing drift re-growth; temporal-vs-calibration NEDT share.
   The workflow-visible proof that the capability answers Gap 120's headline defect.
2. **Modification — `scenarios/01_sarah_systems_engineer/1.4_tdi_pushbroom_optimization`**
   (rides Phase 4). Add a calibration-on variant: TDI stage-count sweep with
   `nonlinearity_pct` and drift set. The optimization's answer *changes* — SNR
   plateaus where the correlated floor takes over instead of climbing as $\sqrt{N}$ —
   which is exactly impact (2) of the gap made visible in an existing workflow.
   Walkthrough + gui_workflow updated in place; original variant kept as the
   baseline branch of the study.
3. **New (small) — temperature-retrieval accuracy demo** (rides Phase 4; folded into
   2.7's walkthrough unless the owner wants it standalone — D6): cal-source
   $\Delta T = 0.5$ K and $\Delta\varepsilon = 0.005$ propagated to retrieved-
   temperature bias, reported next to (not inside) NEDT.

Golden tests: 2.7 mints a golden set (calibration-on full chain); 1.4's existing
goldens are untouched (its baseline variant unchanged — asserted).

---

## 11. Phases and gates

Each phase: one task, one short-lived branch, one merge. Schema is touched at Phase 0
⇒ **full battery + full GUI suite at every phase**; no GUI-scoped narrowing applies
anywhere in this plan (diffs touch `src/` outside `gui/`).

- **Phase 0 — ADR + core abstractions + stage skeleton (Category B).**
  ADR-0012. `BiasTerm`, `bias_terms`, `with_bias`. `CALIBRATION_TERMS`.
  `calibration/` package with `_schema.py` and a `stage.py` that dispatches
  `scheme=none` to a no-op (terms: none) and raises the actionable
  not-yet-implemented error for active schemes. Session registration,
  import-linter contracts, param-reference regen. **Zero-golden-drift asserted
  explicitly.** Lock-step: Master, Signal-Chain, Parameter-System, CLAUDE.md.
  Serialization round-trip + failure-mode tests (Category B battery).
  CHANGELOG (b). Exit: chain runs with the stage present, all goldens identical.
- **Phase 1 — Calibration physics (Category C).** `cal_points.py`,
  `nuc_residual.py`, `gain_drift.py`, `offset_drift.py`, `cal_source_bias.py`.
  Level-0 tests written first (Rule 18); truth anchors §13 (three minimum, five
  targeted); dimensional audit; fragility per Category C. Detector-side PRNU/DSNU
  suppression under active scheme (D2 mechanism) with its own tests. Lock-step:
  Detector-Complete.
- **Phase 2 — Chain + metrics integration (Category C/D).** Terms live end-to-end;
  `radiometric_accuracy.py` + registry + metric-selection + relevance; the two
  contract tests (§6); integration tests; golden: scheme=none bit-identical
  (re-asserted), new calibration-on golden minted under the §5.3 review protocol.
  Lock-step: Metrics, Testing-Validation. CHANGELOG (b)+(c). Gap 120 → core
  DELIVERED note (full closure waits for Phase 4).
- **Phase 3 — GUI (Category D).** §7 screen + §8 tests. **Live-review loop: owner
  sees the running branch before merge; battery after approval.** Lock-step: GUI
  doc §4.4.1. `gui_workflow.md` authoring for 2.7 starts here (the screen defines
  the workflow).
- **Phase 4 — Scenarios + validation (Category D).** §10 scenarios 1–3; golden
  registration; walkthroughs; scenario-local gaps.md for anything found (Rule 21
  applies to findings en route). Integration/regression section per Category D.
- **Phase 5 — Closure.** Gap 120 closure record (CU-style `Gap` status flip with
  commit trailer discipline), CHANGELOG tidy, plan → `docs/archive/` with
  HISTORICAL banner (Rule 24), doc sweep against Rules 23–27.

Rough effort: Phase 0 ≈ S–M; Phase 1 ≈ M; Phase 2 ≈ M; Phase 3 ≈ M–L (live-review
iterations included); Phase 4 ≈ M; Phase 5 ≈ S. Overall L, consistent with the gap
entry.

---

## 12. Owner decisions — ratified 2026-09-06

All seven adopted as recommended (owner ratification of the plan as written):

- **D1 — NUC-residual fidelity: RATIFIED —** v1 parametric quadratic-dispersion
  model (§3.2); cal-point placement is a real trade. (Rejected alternative: direct
  user-specified residual percentage.)
- **D2 — PRNU/DSNU suppression mechanism: RATIFIED —** the detector stage reads
  `calibration.scheme` and, when a scheme is active, emits the pre-correction
  dispersions as stage outputs instead of noise terms; the calibration stage
  consumes them. Invariant either way: *no double counting*, tested. (Rejected:
  emit-then-replace inside the calibration stage.)
- **D3 — Accuracy reporting units: RATIFIED —** both % radiance and K at scene
  temperature.
- **D4 — Drift domain: RATIFIED —** time-linear v1; FPA-ΔT-driven drift deferred to
  a follow-on gap when a scenario needs it.
- **D5 — TDI demo: RATIFIED —** modify scenario 1.4 (calibration-on variant beside
  the untouched baseline); no standalone TDI scenario.
- **D6 — Temperature-retrieval accuracy demo: RATIFIED —** folded into 2.7's
  walkthrough, not standalone.
- **D7 — Term granularity: RATIFIED —** three residual noise terms (`nuc_residual`,
  `gain_drift`, `offset_drift`), not one aggregate.

---

## 13. Numerical truth anchors (Phase 1 exit criteria)

1. **Two-point correctability form** — Schulz & Caldwell, *Infrared Phys. Technol.*
   36 (1995) (nonuniformity correction and correctability): residual after two-point
   correction is parabolic in flux, zero at cal points, amplitude set by
   nonlinearity dispersion. Anchor: §3.2 formula reproduces the published
   correctability shape; hand-computed value at mid-band for a chosen
   $\sigma_\beta$.
2. **Monte-Carlo identity** — synthetic pixel ensemble with quadratic dispersion,
   exact two-point correction applied numerically; array RMS vs. the analytic §3.2
   expression, $<1\%$ over the cal span (deterministic seed).
3. **NEDT-equivalent FPN** — 3D-noise framework (D'Agostino & Webb, SPIE 1488,
   1991): $\mathrm{NEDT}_{fpn} = \sigma_{vh} / (\partial S/\partial T)$; hand
   calculation against the chain's $\partial S/\partial T$ for a 300 K LWIR scene.
4. **Planck-derivative bias** — hand calculation: $\Delta T_{src} = 1$ K at 300 K
   band-integrated over 8–12 µm gives $\Delta L/L \approx 1.5\text{–}1.7\,\%$;
   chain value must land in the hand-computed band.
5. **Correlated-averaging identity** — analytic: $N$ coadds of a fully correlated
   error leave $\sigma$ unchanged while a white term drops $\sqrt{N}$; the §6
   contract test is the executable form.

---

## 14. Assumptions (v1)

- **Quadratic per-pixel nonlinearity** is the residual driver for two-point NUC.
  *Breaks:* strongly non-polynomial response (e.g., near saturation).
  *Detected:* documented validity span (cal span ± the span itself); readout-panel
  advisory when the scene flux leaves it.
- **Time-linear drift.** *Breaks:* thermal-cycling-driven drift.
  *Detected:* D4 deferral note in the stage doc; parameter description says
  "effective linear rate over the cal interval".
- **Calibration residuals fully correlated across TDI/coadds.** True for FPN by
  definition on a staring array; for TDI, along-column averaging of per-pixel gain
  dispersion partially decorrelates — v1 conservatively takes full correlation
  (upper bound on the floor). *Breaks:* long-TDI-column PRNU averaging is
  understated as a benefit. *Detected:* documented limitation + fragility note;
  candidate v1.1 refinement.
- **Cal source fills the aperture the same way the scene does** (no fore-optics
  exclusion). *Breaks:* internal flag/shutter cal where fore-optics emission is
  uncorrected — the known ops-level growth item (§2.1). *Detected:* stage-doc
  limitation; future gap.

---

## 15. Fragility

- $S_2 \to S_1$ (cal points converge): two-point correction ill-conditioned;
  validation requires a minimum cal-temperature separation (bounds error, Rule 15).
- Scene flux far outside the cal span: parabolic residual grows quadratically —
  physically real, but the quadratic model's own validity fades; readout advisory
  (§14).
- $\partial S/\partial T \to 0$ (reflective-band thermal retrieval): NEDT-equivalent
  and K-bias conversions blow up; the accuracy metric returns a result-typed failure
  (`failure_reason="no thermal derivative"`), never NaN (Rule 17 carve-out).
- Zero-signal scenes: all signal-proportional residuals vanish correctly; offset
  terms remain — covered by edge-case tests.

---

## 16. Regression contract

- `calibration.scheme = none` (the universal default): every existing golden,
  scenario output, and GUI snapshot is **bit-identical**, asserted at Phases 0, 2,
  and 4.
- Scheme active: results-affecting by design and by user opt-in only; CHANGELOG
  entries scope the direction ("NEDT increases toward its calibration floor;
  SNR-vs-TDI plateaus").
- `mypy --strict` on touched `core/` and `api/`; import-linter green with the new
  stage in all three contract lists; `check_org_rules` green (new docs in their
  taxonomy homes, no top-level additions).
