# Gap Closure Plan

Status: Active (execution started 2026-07-07; owner approved with MODTRAN-blocked items skipped)
Author: Coding agent (session 2026-07-07), approved by project owner
Scope: All 20 OPEN entries in `docs/tracking/gaps.md` as of 2026-07-07
Registry reference: `docs/tracking/gaps.md` (Rule 25 — this plan references gap numbers; it does not re-enumerate registry content)

---

## Objective

Drive every OPEN gap in the gap registry to FIXED, CLOSED, or an explicit
deferral record (gating condition + re-audit date, per Rule 22/27 protocol).
No gap is closed without rerunning its originating scenario, per the registry's
own verification rule.

## Ground rules for every work package

1. One gap (or one explicitly merged pair) per task, per Agent Task Discipline.
2. Category declared per work package below; the report must carry that
   category's validation sections (truth anchors for Category C, etc.).
3. Rule 19: each new computation gets its own module.
4. Rule 20: any schema, public API, or metric change updates the matching
   `RADIANT_*.md` doc in the same PR.
5. Closure = registry entry moved to FIXED/CLOSED with the fix description and
   originating-scenario rerun result, mirroring the existing closed entries.
6. Rule 29: every work package here adds/changes a public surface or computed
   result, so every closure PR adds a `CHANGELOG.md [Unreleased]` entry
   (**Results-affecting:** prefix where defaults, physics, or goldens change —
   e.g. WP-1.1's nearfield fix when `scalar_emissivity` is set).

---

## Phase 0 — Re-audit stale entries (before any implementation)

Two entries predate architecture work that may have already resolved them.
Verify against current code before scheduling implementation; close as
already-fixed or refresh the entry.

| Gap | Suspected staleness | Verification step |
|-----|--------------------|-------------------|
| 19 (MTF budget decomposition) | The dual-path architecture (Rule 4) now maintains a per-contributor MTF product path (optics, detector aperture, jitter, smear, diffusion, IPC, turbulence, TDI). The "budget table" may be a thin reporting layer over data that already exists — or already exposed. | Inspect `performance/` MTF product path outputs; run scenario 5.4/7.3 script and check `stage_outputs` for per-contributor curves. |
| 27 (MTF frequency axis units) | Gap 9's resolution states curves are stored in cycles/m, contradicting this entry's claim of cycles/pixel. | Check `mtf_freq_x` units in `_compute_spatial_metrics`; if cycles/m, the remaining ask is only a cycles/mm / cycles/mrad convenience conversion. |

Effort: half a day total. Output: refreshed or closed registry entries.

---

## Phase 1 — Physics correctness (highest priority)

These change predicted numbers or prevent silently wrong results.

### WP-1.1 — Gap 37: Nearfield emission = 0 in scalar transmission mode
- **Severity HIGH — first in line.** 30–40% noise underestimate for warm-optics
  MWIR/LWIR; blocks meaningful cold-stop sweeps.
- Fix: optional `optics.scalar_emissivity` parameter (default `None` preserves
  current behavior). Explicit user-provided value sidesteps the
  refractive-lump `ε = 0` assumption without violating Rule 5 (the user is
  declaring the lumped train's emissivity, not over-specifying a single
  surface — document this distinction in `RADIANT_Optics.md`).
- Category: C (truth anchors: hand-computed warm-optics photon flux;
  key_elements-mode equivalent configuration; published warm-optics NEDT
  contribution example).
- Effort: Small–Medium. Rerun: scenarios 7.4 and 7.1.

### WP-1.2 — Gap 22: RER below GIQE-5 calibration range
- Fix: calibration-range checks in `performance/giqe.py`; `UserWarning` +
  a structured flag in the result (metric-layer result-typed pattern, Rule 17
  carve-out) when RER/SNR are outside the published GIQE-5 fit range.
- Category: B. Effort: Small. Rerun: scenario 5.4.

### WP-1.3 — Gap 41: Earth-LOS-intercept negative integration test
- Fix: one negative-path test in `tests/integration/test_use_case_matrix.py`
  (sensor below space target → validator raises end-to-end).
- Category: A. Effort: Trivial. Do alongside WP-1.2.

---

## Phase 2 — Small, high-leverage additions

Each is Small effort, independently shippable, ordered by user leverage.

| WP | Gap | Work | Category | Rerun |
|----|-----|------|----------|-------|
| 2.1 | 20 | `giqe5_sensitivity()` in its own module (`performance/giqe_sensitivity.py`, Rule 19) — analytic d(NIIRS)/d(GSD, RER, SNR, H, G) | C (derivatives checked against finite differences + hand calc + GIQE-5 spec) | 5.4 |
| 2.2 | 32 | Electronics MTF: `readout/electronics_mtf.py`, Gaussian `MTF_elec = exp(-2π²σ_e²f²)`, new readout param. **Rule 4:** must enter both paths — spatial kernel on the EffectivePSF and analytic term in the MTF product — or be justified as MTF-only like TDI mis-registration (it is a readout-timing effect; decide explicitly and document in `RADIANT_Signal_Chain_Architecture.md`) | C | 7.3 |
| 2.3 | 17 | `optics.psf_weighting_spectrum` override parameter for polychromatic PSF weighting | B | 5.3 |
| 2.4 | 12 | `cold_stop_efficiency` naming: recommend rename to `nearfield_fraction` with deprecation alias (Rule 20 doc updates + GUI tooltip text). Sequence **after** WP-1.1 since both touch the same schema/docs | A | 7.4 |
| 2.5 | 27 | (Pending Phase 0 outcome) frequency-axis conversion utility (cycles/m ↔ cycles/mm ↔ cycles/mrad), own module | B | 5.1 |

---

## Phase 3 — Medium capability builds

Ordered: GUI-critical first (per project priorities), then analysis tooling.

### WP-3.1 — Gap 6: Unit-aware parameter input
- `ParameterSet.set(name, value, unit=...)` using the existing
  `canonical_unit` / `input_unit` fields and the `core/units.py` registry.
  Conversion at the `set()` boundary only (Rule 2 — this *is* the boundary).
- Critical for the GUI; unblocks friction in every scenario with non-RADIANT
  inputs. Category: B. Effort: Medium. Rerun: scenario 6.3.

### WP-3.2 — Gaps 23 + 28 merged: generic error budget utility
- One RSS budget model (contributors → RSS total, allocation tracking,
  budget table report) parameterized for jitter (µrad) and WFE (waves).
  Registry entries already suggest the merge; it is one computation
  (Rule 19 bundling carve-out: shared math, meaningless apart).
- Home: `radiant/api/error_budget.py` (it composes stage inputs; not stage
  physics). Category: B. Effort: Medium. Rerun: 5.4 and 5.1.

### WP-3.3 — Gap 10: Inverse solver
- `Sensor.solve_for(parameter, target_metric, target_value, bounds)` —
  scipy Brent root-finding wrapper around the forward model.
- Category: B (plus convergence failure modes). Effort: Medium. Rerun: 7.4.

### WP-3.4 — Gap 30: Measurement import / overlay
- `io/` readers (CSV first; Excel second) for measured MTF/NEDT +
  `api/` comparison utility (interpolate to model grid, residuals).
- Category: B. Effort: Medium. Rerun: 7.3.

### WP-3.5 — Gap 31: Surface scatter (TIS) model
- TIS approximation `(4πσ/λ)²` first; Harvey-Shack explicitly out of scope
  (own future gap if needed). **Rule 4:** scatter halo must enter both the
  PSF path (kernel) and MTF product path consistently.
- Category: C. Effort: Medium. Rerun: 7.3.

### WP-3.6 — Gap 26: Zemax Zernike importer
- `io/` parser for Zemax Zernike-coefficient text output (not full .ZMX
  prescription — scope to the coefficient report format Tom actually exports).
  Feeds the Gap 24/25 Zernike pipeline already in place.
- Category: B. Effort: Medium. Rerun: 5.1.

### WP-3.7 — Gap 19: MTF budget reporting (only if Phase 0 confirms it's real)
- If per-contributor MTFs already exist in the product path, this is a
  reporting/export task (budget table at Nyquist). Category: A–B.
  Effort: Small–Medium (re-estimated after Phase 0). Rerun: 5.4, 7.3.

---

## Phase 4 — Blocked / deferred (explicit deferral records, not silent carry)

| Gap | Disposition | Gating condition | Re-audit |
|-----|-------------|------------------|----------|
| 39 (A3 MODTRAN parity) | **Blocked** — no MODTRAN access since 2026-04-21. ~2 days once unblocked. | Licensed MODTRAN install or donated tape7 fixtures | 2026-10-01 or on access, whichever first |
| 38 (E_sky ω₀ fidelity) | **Deferred** behind MODTRAN lookup-table wiring (same blocker family as Gap 39) | MODTRAN LUT wiring lands | Same re-audit as Gap 39 |
| 21 (Jitter PSD) | **Deferred** — Large effort; RMS assumption is standard for preliminary design; no scenario blocked | A scenario or user request requiring colored-jitter partition | 2026-10-01 |
| 40 (Lab dark-cal flag) | **Deferred** — registry itself says "when a user actually asks for it" | User/GUI request for explicit dark-cal mode | Next GUI scenario touching D-lab cells |

These four get their registry entries updated with the deferral records above
in the PR that lands this plan — no silent OPEN carry.

---

## Sequencing summary

```
Phase 0 (0.5 d)  → re-audit 19, 27
Phase 1 (~3 d)   → 37 (HIGH), 22, 41
Phase 2 (~4 d)   → 20, 32, 17, 12, 27
Phase 3 (~3 wk)  → 6, 23+28, 10, 30, 31, 26, [19]
Phase 4 (0 d)    → deferral records for 39, 38, 21, 40
```

Result: 16 gaps actively closed, 4 carried with explicit deferral records,
0 silently open.

## Exit criteria

- Every registry entry either FIXED/CLOSED (with fix note + scenario-rerun
  result) or carrying a deferral record with gating condition + re-audit date.
- Full test suite, `mypy --strict` (core, api), `import-linter`,
  `check_org_rules.py` green after each work package.
- This plan moved to `docs/archive/` with a HISTORICAL banner in the PR that
  completes the last work package (Rule 24).
