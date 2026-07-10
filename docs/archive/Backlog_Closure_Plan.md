> **HISTORICAL — archived 2026-07-10 (completed by the coding agent; all waves landed).** Wave 0 dispositions (`b733cb0`); Wave 1: CU-005 option b + Gap 40 (`c8a6f70`); Wave 2: CU-003 + CU-045 (`2d5da44`); Wave 3: CU-008 (`76b8bd1`), Gap 59 (`19ae3b9`), Gap 60 partial (`d3274ab`); Wave 4: CU-044 (`c0febaf`). Exit criteria verified: every CU and gap is Resolved (commit-linked) or carries a current Declined/Deferred record with gate + re-audit date; all gates green (full pytest, mypy --strict core/api, ruff, import-linter, check_org_rules; goldens bit-invariant except the documented §5.3 repins in Wave 2).

# Backlog Closure Plan

Status: Complete (2026-07-10)
Author: Coding agent, directed by project owner
Owner constraints (2026-07-10): RADIANT stays a **single-pixel model** (no 2-D
scene work); **no MODTRAN access**; **GUI work is imminent but not now**.
Scope: disposition every open CU and registry gap — close what is closable,
and give every non-closable item an explicit Declined or Deferred record
(Rule 28 dispositions; Rule 22 deferral protocol).
Registries of record: `docs/tracking/Cleanup_Backlog.md`, `docs/tracking/gaps.md`
(Rule 25 — referenced, not re-enumerated).

---

## Wave 0 — Dispositions (owner-constraint fallout, no code)

| Item | Disposition | Rationale |
|------|-------------|-----------|
| Gap 56 (2-D scene model) | **Declined** | Owner decision 2026-07-10: single-pixel model is the product. Re-open only on explicit re-scope. |
| Gap 58 (GeoTIFF reader) | **Deferred** | Value is predicated on map-driven backgrounds (Gap 56); CSV transcription workaround is adequate. Gated on any 2-D re-scope. |
| Gap 55 (PDF spec-sheet parser) | **Declined** | Large build (text + plot digitisation), low value — workbook transcription (scenario 3.3 pattern) is the accepted workflow. |
| Gap 39 + CU-011 (MODTRAN parity / two-leg τ) | **Deferred (refresh)** | Gated on MODTRAN access; re-audit when acquired. |
| Gap 38 (E_sky ω₀ fidelity) | **Deferred (refresh)** | Implementable without MODTRAN but not *validatable* to the parity fidelity the gap demands. Same gate as Gap 39. |
| Gap 21 (jitter PSD) | **Deferred (refresh)** | Large; needs a PSD input-format design decision. Gated on a future platform-modeling task; re-audit 2026-10-01. |
| CU-024, CU-025, CU-052, CU-053, CU-054, CU-056 (GUI v2) | **Deferred (refresh)** | Owner: GUI work imminent but not now. Gated on GUI-v2 track restart; re-audit at kickoff. |
| Scenarios 1.1, 6.2 | unchanged | MODTRAN-gated; deferral records already in place. |

## Wave 1 — Small closures

1. **CU-005** (`theta_o_from_eta` unwired): take the entry's option **(b)** —
   document the η-input opt-out as deliberately deferred behind the
   SensorDescriptor ADR (users supply `geometry.path_zenith_rad` directly;
   the converter stays tested and reserved). Close the CU. Effort S.
2. **Gap 40** (lab dark-cal mode not first-class): promote to a first-class
   parameter per the entry's suggestion; Level-0 test. Effort S.

## Wave 2 — Consistency pair (Category C, golden-gated)

3. **CU-003**: adopt investigation option **(a)** — area-integration
   (anti-aliased) pixel rect kernel, improving FFT-vs-analytic agreement
   13× (4.5e-2 → ~3.5e-3 floor at detector Nyquist). Keeps the two paths
   independent (options b/c traded independence or PSF nonnegativity).
   Results-affecting on PSF-path EE/RER → golden review per §5.3.
4. **CU-045**: with the new floor, retune the default tolerance
   (measure max error across the integration corpus, set with margin
   ~2×), keep the loud `UserWarning` (raising on a diagnostic invariant
   would brick user runs on edge configs), and document the decision.
   Closes with CU-003.

## Wave 3 — Physics closures (Category C)

5. **CU-008** (spectral `GroundBackground`): execute the escalated task doc
   (`docs/reports/cu_tasks/CU-008_GroundBackground_Spectral_Task.md`),
   Approach 1 — `source.background.material ∈ {grey, vegetation, snow}` via
   the existing `SpectralLibrary`, plus `source.background.emissivity_path`
   override; scalar `source.background.emissivity` stays as the grey
   back-compat path. Three truth anchors per the task doc. Effort M.
6. **Gap 59** (day/night solar mode): first investigate whether the existing
   mixed emissive+reflective source path (T3Mixed) already expresses it —
   if so, close with a documented recipe + test; if not, add a
   solar-illumination toggle for emissive scenes. Effort S–M.
7. **Gap 60 (partial)** (stray-light spatial impact): give veiling glare its
   Rule-4 kernel+MTF pair by routing the stray fraction through the
   existing scatter-halo machinery (Gap 31 pattern: halo kernel on the PSF
   path + exact analytic MTF term on the product path). The 2-D PST/vendor
   PSF import stays deferred (aligned with the single-pixel decision).
   Effort M.

## Wave 4 — Sweep

8. **CU-044** (Rule 12 hardcoded tuneables): promote genuinely tuneable
   quantities to `ParameterDef`s (defaults chosen to preserve results
   bit-exactly), move fixed empirical constants to named module constants
   with citations, dedupe the `0.25·IFOV` regime threshold. Effort M–L.

## Exit criteria

- Every CU in `Cleanup_Backlog.md` and every gap in `gaps.md` is either
  Resolved (commit-linked) or carries a current Declined/Deferred record
  with gate + re-audit date.
- All gates green after each wave: full pytest, mypy --strict (core/api),
  ruff, import-linter, `check_org_rules`, goldens (regenerated only under
  the §5.3 protocol where a wave is results-affecting).
- Plan archived per Rule 24 when the last wave lands.
