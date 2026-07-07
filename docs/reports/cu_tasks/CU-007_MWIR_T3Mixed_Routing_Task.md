# CU-007 — Stage-2 inferrer: route atmosphere-aware MWIR cases through `T3Mixed`

**Category:** B (core abstraction — inferrer routing) with C-level radiometric impact (`T3Mixed` adds reflected-solar + reflected-sky terms vs. `T1Thermal`'s pure-emit). Validation must clear the C-level bar on the affected snapshot rows even though no new physics is being authored — only the existing `T3Mixed` Kirchhoff path is being switched on for scenarios that were silently routed through `T1Thermal`.
**Triggered from:** [docs/Cleanup_Backlog.md](Cleanup_Backlog.md) CU-007, escalated 2026-04-26 after stage-deferral expired and investigation found the suggested 50–100-line "Category B inferrer routing" undercounts the snapshot regression burden.
**Scope:** ~50–80 lines of production code in [src/radiant/source/_inferrer.py](../src/radiant/source/_inferrer.py) (routing decision + suppression removal), one new Level 0 test, plus a 6-row snapshot refresh on `tests/integration/snapshots/option_c_baseline.yaml` and `src/radiant/source/tests/snapshots/` for the MWIR scenarios.

---

## Problem statement

[src/radiant/source/_inferrer.py:1542](../src/radiant/source/_inferrer.py#L1542) wraps every legacy ε+T `T1Thermal` construction in `warnings.catch_warnings() / simplefilter("ignore", UserWarning)`:

```python
# _inferrer.py:1535–1555
# Silence the MWIR non-mixed warning emitted by T1Thermal.__post_init__
# during Stage-2 back-compat inference.  The scalar-ε legacy surface
# cannot distinguish "MWIR with ρ ≈ 0 (hot target)" from "MWIR that
# should really use T3 mixed", so firing the warning here produces
# noise on every MWIR scenario in the snapshot.  Stage 3/6 addresses
# MWIR mixed explicitly; until then the warning suppression is
# scoped narrowly to this back-compat construction only.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", UserWarning)
    return T1Thermal(...)
```

The comment's deferred fix ("Stage 3/6 addresses MWIR mixed explicitly") is now overdue. Stage 6 (commit `b9244fd`) landed the E_sky decomposition that `T3Mixed` consumes, but the inferrer never started using it — every MWIR snapshot scenario still flows through `T1Thermal` under the suppression wrapper. The legitimate Rule-17 modelling flag (`_warn_mwir_non_mixed`, [core/descriptors.py:273](../src/radiant/core/descriptors.py#L273)) is silenced for every MWIR cell that lands going forward, including ones where it would correctly identify a missing reflected term.

### Root cause

The legacy ε+T scalar-input surface in `_build_target_descriptor` cannot distinguish two MWIR sub-cases that map to different descriptors:

| MWIR sub-case             | Correct descriptor | Why                                                                |
|---------------------------|--------------------|--------------------------------------------------------------------|
| Hot target, ρ ≈ 0          | `T1Thermal`        | Self-emission dominates; reflected terms vanish (Rule 5)           |
| Ambient target, ρ = 1 − ε | `T3Mixed`          | Kirchhoff requires reflected-solar + reflected-sky (matrix §3.2)   |

Without an explicit signal in the input YAML (a `scene.kind` enum, an `is_hot_target` flag, or an explicit `ρ(λ)` field that's near-zero), the inferrer cannot route between the two. Today it picks `T1Thermal` unconditionally and gags the warning that would tell the user it might be the wrong choice.

### Why the fix is needed now

- **Stage 6 is in.** `T3Mixed` no longer requires a stub atmosphere — `_assemble_t3` ([atmosphere/assembly.py:786](../src/radiant/atmosphere/assembly.py#L786)) returns the full §6.1 equation with the Kirchhoff-derived reflected-direct-solar and reflected-diffuse-sky terms plumbed through `_direct_solar_term` and `_diffuse_sky_term`. The downstream consumer is ready.
- **Suppression masks real signal.** Any MWIR scenario added post-Stage-8 that *should* be `T3Mixed` but is misconfigured in YAML will silently land as `T1Thermal` with no surfaced warning. Rule 17's actionable-error invariant is undermined every time `simplefilter("ignore", UserWarning)` fires.
- **Anchor cells are safe.** Cells 28 and 58 are LWIR `T1Thermal` with ρ ≡ 0 — they are bit-invariant under the routing change because their wavelength grid does not overlap MWIR (the `_is_mwir_spectral_data` predicate at [core/descriptors.py:265](../src/radiant/core/descriptors.py#L265) tests `lam.min() ≤ 3.0 and lam.max() ≥ 1.0`). The fix can land without re-pinning anchors.

### Affected scenarios

Six of the 14 baseline scenarios route through MWIR on `_is_mwir_spectral_data`:

- `examples/ground_truth_mwir.yaml`
- `examples/mwir_leo_minimal.yaml`
- `examples/templates/mwir_aerial_flir.yaml`
- `examples/templates/mwir_ground_test.yaml`
- `examples/templates/mwir_leo_pushbroom.yaml`
- `examples/templates/mwir_leo_starer.yaml`

Each will move from `T1Thermal` (`ε·B·τ_up + L_path_up`) to `T3Mixed` (adds `ρ·(τ_sun·E·cosθ_s + E_sky_diffuse)·τ_up`), changing `L_aperture`, `nedt_K`, and `snr` in `option_c_baseline.yaml`. `mtf_at_nyquist` is independent of the radiometric path and must not move.

The remaining 8 (LWIR / SWIR / VNIR) are out of scope: LWIR is correctly `T1Thermal` (ρ ≈ 0 by physics, no warning fires); SWIR/VNIR `T1Thermal` is rare on the legacy surface and not in the baseline; SWIR-hot-target warning ([core/descriptors.py:295](../src/radiant/core/descriptors.py#L295)) is a separate Rule-17 flag and not in scope here.

---

## Required reading (do not skip)

1. [CLAUDE.md](../CLAUDE.md) — Rules 5 (Kirchhoff derivation), 14 (`RadiantError` for actionable failures), 16 (validate before compute), 17 (no silent failures — and the metric-layer carve-out, which **does not apply** here because `_inferrer.py` is in `source/`).
2. [docs/RADIANT_Source.md](RADIANT_Source.md) — TargetDescriptor variant matrix §3.2 (T1/T2/T3 selection rules); Q3 shape-wins precedence (matrix §4).
3. [src/radiant/core/descriptors.py:273–323](../src/radiant/core/descriptors.py#L273) — `_warn_mwir_non_mixed` and `_warn_swir_hot_non_mixed` warning helpers; `T1Thermal.__post_init__` and `T3Mixed.__post_init__` (lines 348–369 and 443–461).
4. [src/radiant/atmosphere/assembly.py:786–870](../src/radiant/atmosphere/assembly.py#L786) — `_assemble_t3` and `_components_t3` (the consumer side; verify they accept the descriptor signature emitted by `_inferrer.py` after the change).
5. [src/radiant/source/_inferrer.py:1438–1555](../src/radiant/source/_inferrer.py#L1438) — `_build_target_descriptor` legacy ε+T branch (the file you will edit).
6. [docs/reports/cu_tasks/CU-003_Rect_Kernel_Fix_Task.md](CU-003_Rect_Kernel_Fix_Task.md) — pattern this task follows (Category-C-grade validation, snapshot refresh protocol, stop-trigger discipline).
7. [docs/architecture/RADIANT_Testing_Validation.md](RADIANT_Testing_Validation.md) §5.3 — golden-snapshot review protocol. **Snapshot updates require an explicit "expected radiometric drift" entry in the commit body for each affected row.**

---

## Approach decision (raise to user before coding)

The legacy ε+T scalar surface still cannot distinguish hot-target MWIR from ambient MWIR by itself. The task is therefore "what defaults the routing rule?". Three candidates:

### Approach 1 — MWIR-overlap defaults to `T3Mixed`; explicit opt-out required for hot-target cells (recommended)

If `_is_mwir_spectral_data(epsilon)` is true, build `T3Mixed(...)` instead of `T1Thermal(...)`. Hot-target MWIR scenarios (those that should stay `T1Thermal`) must explicitly set a new `source.target.is_hot_target: true` parameter in YAML (or supply an explicit `source.target.reflectance` of zero, which already routes through `_build_target_descriptor`'s separate `T2/T3` branch).

**Pros.**
- Matches matrix §3.2's stated rule: "MWIR ambient → T3 mandatory."
- Removes the suppression entirely; warnings fire only when a scenario explicitly opts into `T1Thermal` against the matrix recommendation, which is the *correct* signal.
- Reflects the real engineering default — most MWIR EO-sensor scenarios are ambient.
- All six MWIR baseline scenarios re-baseline (expected); the other 8 are bit-invariant.

**Cons.**
- Adds one new schema parameter (`source.target.is_hot_target`, dtype `bool`, default `False`) on the `SourceStage` schema. Doc update in `docs/architecture/RADIANT_Parameter_System.md` and `docs/RADIANT_Source.md` required (Rule 20).
- The 6 MWIR snapshot rows must be reviewed and accepted as the new physics ground truth — not "drift to investigate" but "improvement per matrix §3.2."

### Approach 2 — Always emit `T3Mixed` for MWIR, no opt-out

Same as Approach 1 minus the hot-target escape hatch.

**Pros.**
- Smallest schema surface change.
- Matrix §3.2 doesn't explicitly carve out hot-target MWIR.

**Cons.**
- Loses the ability to model genuine hot-target MWIR scenes (engine plumes, missile signatures) where ρ ≈ 0 is the correct physics. The reflected terms are tiny but non-zero, so the answer is "slightly wrong" rather than "subtly wrong" — but it still requires the user to explicitly set `source.target.reflectance = 0` to recover, which means the legacy ε+T surface stops being the back-compat path it was.

### Approach 3 — Keep T1Thermal for legacy ε+T, just remove the suppression

Drop the `simplefilter("ignore", UserWarning)` wrapper. Let the warning fire on every MWIR snapshot scenario.

**Pros.**
- Zero physics change, zero snapshot refresh.
- Smallest production diff (~5 lines).

**Cons.**
- Re-creates the noise problem the original suppression was added to fix. Every MWIR scenario in every CI run, every test invocation, every snapshot regeneration, fires `_warn_mwir_non_mixed`.
- Doesn't actually fix anything — the MWIR scenarios remain misclassified as `T1Thermal` when matrix §3.2 says they should be `T3Mixed`.
- **Reject.**

**Recommended: Approach 1.** It moves the legacy surface to the matrix's recommended default, gives users an explicit opt-out, and surfaces the warning only when the user has explicitly chosen to ignore the matrix — which is exactly when Rule 17 says the warning should fire.

---

## Implementation steps (after approach decision)

1. **Branch.** `git switch -c chore/cu-007-mwir-t3-routing`.
2. **Schema (Approach 1 only).** Add `source.target.is_hot_target` as a new `ParameterDef` in `src/radiant/source/_schema.py` (`dtype=bool`, `default=False`, `canonical_unit=""`, `input_unit=""`, with a docstring that cites matrix §3.2 and explains "set to true for ρ ≈ 0 hot-target MWIR scenes; default routing for MWIR is T3Mixed").
3. **Routing (in `_inferrer.py::_build_target_descriptor`).**
   - Read `is_hot_target = params.get("source.target.is_hot_target")`.
   - Compute `is_mwir = _is_mwir_spectral_data(epsilon)` (import from `core.descriptors` — already a permitted import per Rule 11; verify `import-linter` accepts it).
   - If `is_mwir and not is_hot_target`: build `T3Mixed(...)` with the same `(epsilon, T_t, A_t, shape)` signature (`T3Mixed` has identical fields; `ρ` is derived inside `_assemble_t3` via Kirchhoff).
   - Otherwise: build `T1Thermal(...)` as today.
   - **Remove the `warnings.catch_warnings()` wrapper.** With routing fixed, the only `T1Thermal` constructions left are: (a) LWIR (no warning fires), (b) explicit hot-target MWIR (user opted in; the warning is genuinely a false positive and the user accepted it). Approach 1 deliberately does not re-suppress — if it fires on a hot-target scenario, that's a signal worth surfacing to the user as documentation of their choice.
4. **Level 0 test (write before edits).** New file `src/radiant/source/tests/test_inferrer_mwir_routing.py`:
   - **A1.** Build a minimal MWIR `ParameterSet` (wavelength grid 3–5 µm, ε = 0.95, T_t = 290 K, no `is_hot_target`). Assert `_build_target_descriptor` returns `T3Mixed`. Today this fails (returns `T1Thermal`); after the fix it passes.
   - **A2.** Same `ParameterSet` plus `is_hot_target=True`. Assert returns `T1Thermal`.
   - **A3.** LWIR `ParameterSet` (wavelength grid 8–12 µm, ε = 0.95, T_t = 300 K). Assert returns `T1Thermal` regardless of `is_hot_target` (LWIR routing is unchanged).
   - **A4.** Suppression-removal guard: in pytest's `recwarn` fixture, build the MWIR-hot-target case (A2) and assert exactly one `UserWarning` matching `_warn_mwir_non_mixed`'s text fires. Today no warning fires (silenced); after the fix it fires (Rule 17 visibility). Build the MWIR-default case (A1) and assert *zero* MWIR warnings fire (because `T3Mixed` doesn't trigger the warning at all).
   - **A5.** LWIR case (A3) with `recwarn`: assert zero warnings fire (regression guard against accidentally introducing an LWIR warning path).
5. **Run the new tests.** A1 and A4 must fail before the routing change; all five must pass after.
6. **Re-run the snapshot regenerator.**
   ```
   python scripts/capture_option_c_baseline.py
   ```
   Then diff `tests/integration/snapshots/option_c_baseline.yaml`.
   - **Expected:** the 6 MWIR rows' `L_aperture`, `nedt_K`, `snr` shift (the reflected terms now contribute).
   - **Expected:** `mtf_at_nyquist` unchanged on every row to ≤1e-10 (`T3Mixed` doesn't enter the spatial-frequency path).
   - **Expected:** the 8 non-MWIR rows bit-invariant.
   - **Expected:** Cells 28 and 58 (`tests/integration/test_option_c_anchors.py::CELL28_PINNED`, `CELL58_PINNED`) bit-invariant — both are LWIR T1Thermal.
7. **Snapshot regeneration on the source side.** Re-run `pytest src/radiant/source/tests/test_inferrer.py` and refresh any per-scenario snapshot YAMLs under `src/radiant/source/tests/snapshots/` that test the MWIR scenarios. Document each refreshed file in the commit body.
8. **Doc updates (Rule 20).**
   - `docs/architecture/RADIANT_Parameter_System.md`: add `source.target.is_hot_target` to the parameter table.
   - `docs/RADIANT_Source.md`: update matrix §3.2 description to note that the inferrer now defaults MWIR to `T3Mixed`; document the opt-out parameter.
9. **Full regression gate.**
   ```
   pytest src/ -q                       # +5 new tests
   pytest tests/integration/ -q         # 6 MWIR row deltas accepted
   mypy --strict src/radiant/core src/radiant/api
   ruff check src/
   ruff format --check src/
   lint-imports --config pyproject.toml
   ```
10. **Move CU-007 to Resolved** in `docs/Cleanup_Backlog.md` with the commit hash, the affected scenario list, and a one-line summary that the suppression is gone (Rule 22 — phantom closure forbidden).
11. **Commit.** Format: `chore(debt): CU-007 — route MWIR ambient cases through T3Mixed; remove warning suppression`. Body cites the 6 affected scenarios with before/after `L_aperture` deltas, confirms anchor cells 28/58 bit-invariant, lists the new schema parameter and doc updates, and confirms the warning-suppression wrapper is removed.

---

## Stop triggers

Stop and ask the user before continuing if any of these fire:

- **Anchor cell 28 or 58 (`CELL28_PINNED`, `CELL58_PINNED` at [tests/integration/test_option_c_anchors.py:69](../tests/integration/test_option_c_anchors.py#L69)) shifts at all.** Both are LWIR T1Thermal with ρ ≡ 0 — they are bit-invariant by construction. Any drift means the routing rule is firing on cells it shouldn't (e.g. `_is_mwir_spectral_data` is misidentifying an LWIR grid).
- **An LWIR or SWIR or VNIR row in `option_c_baseline.yaml` shifts.** The fix should only touch MWIR rows. Drift on the other 8 means `_is_mwir_spectral_data`'s wavelength predicate is matching scenarios it shouldn't, or a path other than `_build_target_descriptor`'s legacy branch is being affected.
- **`mtf_at_nyquist` shifts on any row.** `T3Mixed` vs `T1Thermal` is purely radiometric — it cannot affect optical MTF. Any drift means an unintended coupling.
- **A test in `src/radiant/source/tests/test_inferrer.py` or `tests/integration/test_option_c_anchors.py` fails for a reason other than "MWIR rows now route to T3Mixed."** Investigate before regenerating snapshots.
- **`is_hot_target` lands as a parameter on a stage other than `SourceStage`.** It belongs in `source/_schema.py` only.
- **The change touches `radiant.atmosphere.assembly` or `radiant.core.descriptors`.** This is a routing fix in `_inferrer.py`. Both consumer-side modules should be unchanged. If you find yourself editing them, you have crossed scope.
- **Any new `simplefilter("ignore", ...)` or `catch_warnings()` block appears in production code.** The point of this CU is to *remove* the silenced surface, not relocate it.

---

## Validation requirements (Category B with C-level radiometric audit)

### Numerical truth anchors (≥3 required, focused on the radiometric delta)

1. **MWIR-ambient T3 vs T1 hand calculation.** For one representative MWIR scenario (e.g. `examples/templates/mwir_aerial_flir.yaml`), compute by hand at one wavelength bin (say λ = 4.0 µm, T_t = 290 K, ε = 0.95):
   - `L_T1 = ε · B(λ, T_t) · τ_up + L_path_up`
   - `L_T3 = L_T1 + ρ · (τ_sun · E_sun · cosθ_s + E_sky_diffuse) · τ_up` with ρ = 1 − ε
   - Confirm the snapshot delta `L_aperture(T3) − L_aperture(T1)` for that bin agrees with `L_T3 − L_T1` to **rel ≤ 1e-6**.
2. **LWIR bit-invariance.** For one LWIR scenario (e.g. `examples/templates/lwir_geo.yaml`), confirm `L_aperture` is identical bit-for-bit before and after the fix (numpy `==`, not `pytest.approx`).
3. **Hot-target opt-out parity.** Build a synthetic MWIR scenario with `is_hot_target=True` and confirm its `L_aperture` is bit-invariant relative to the pre-fix code (the routing escape hatch reproduces the legacy ε+T behavior exactly when explicitly opted in).

### Dimensional audit

| Quantity                                | Input units              | Output units            | Path                          | Check |
|-----------------------------------------|--------------------------|-------------------------|-------------------------------|-------|
| `epsilon` (SpectralData)                | dimensionless            | dimensionless           | from `_grey_spectraldata`     | ✓     |
| `_is_mwir_spectral_data(epsilon)`       | dimensionless            | bool                    | wavelength grid `≤3 ≤ ≤≥1`     | ✓     |
| `is_hot_target`                         | bool                     | bool                    | `params.get(...)`             | ✓     |
| Routing decision                        | (bool, bool) → ctor      | TargetDescriptor        | branch                        | ✓     |
| `T3Mixed.epsilon`                       | dimensionless SpectralData | dimensionless         | passthrough from inferrer     | ✓     |
| Downstream ρ via Kirchhoff (in assembly) | dimensionless ε(λ)      | dimensionless ρ = 1−ε   | `_assemble_t3`                | ✓     |

The radiometric audit (W/m²/sr/µm units throughout the assembly) is already enforced by Stage 6's tests; this CU does not change it.

### Failure modes

- **MWIR scenario with `is_hot_target=True` but explicit `source.target.reflectance` also supplied.** Today the reflectance branch routes through `_build_target_descriptor`'s reflectance path before reaching the legacy ε+T fallback. Verify behavior is unchanged — `is_hot_target` only affects the legacy branch.
- **Wavelength grid exactly at the MWIR boundary (λ_min = 3.0 µm or λ_max = 1.0 µm).** Per `_is_mwir_spectral_data`, both inclusive comparisons evaluate to true. Verify the routing fires (`T3Mixed`) for the exact-boundary case.
- **Wavelength grid spanning MWIR and LWIR (e.g. 3–10 µm).** `_is_mwir_spectral_data` still returns true. Verify routing is `T3Mixed` (the matrix-§3.2 stricter recommendation wins).
- **`is_hot_target` parameter not set in YAML.** Default `False` per schema. Verify default behavior is "MWIR routes to T3Mixed."
- **`is_hot_target=True` on an LWIR scenario.** Routing remains `T1Thermal` (unchanged); the parameter is ignored outside MWIR. Verify with A3 in the test plan.

### Assumptions

- **Matrix §3.2 default is correct.** "MWIR ambient → T3 mandatory" is the published rule; the inferrer's job is to apply it unless the user explicitly opts out.
- **`_is_mwir_spectral_data` is the right predicate.** It tests `lam.min() ≤ 3.0 and lam.max() ≥ 1.0` — meaning "any wavelength grid that overlaps 1–3 µm." The 1 µm lower bound is the SWIR-MWIR boundary; revisit if the predicate is overly broad. Document this explicitly.
- **Cells 28 and 58 stay bit-invariant.** Both are LWIR T1Thermal with ρ ≡ 0 by construction; routing change cannot reach them. Verified at task design time, must be re-verified at landing time.

### Fragility analysis

- **Schema parameter rename collision.** `is_hot_target` is a new bool on `source.target.*`. Verify no existing parameter shares the name. If it does, choose `is_hot_target_mwir` to disambiguate.
- **Per-scenario YAML drift.** The 6 MWIR scenario YAMLs do *not* need to set `is_hot_target` — they take the new default. If any of them is genuinely a hot-target scene (engine, plume, missile), the resulting snapshot delta is a *correction* of pre-existing physics drift, not a regression — but the YAML should be updated to set `is_hot_target=True` and the snapshot row pinned to the legacy values. Audit each of the 6 scenarios for hot-target intent before accepting the snapshot delta.
- **Mid-band MWIR vs near-3 µm overlap.** Snapshot scenarios with grids that just-barely-overlap MWIR (e.g. 2.8–3.2 µm) may see a smaller radiometric delta than mid-MWIR scenarios. Document the per-scenario delta range in the commit body so reviewers can sanity-check.

### Cross-model consistency

- The new T3-routed `L_aperture` for each MWIR snapshot row must agree with `_assemble_t3`'s output to bit-precision (the inferrer is just choosing the descriptor; the radiometry is the assembly's job). Verify by direct call comparison: build the MWIR scenario, get `target_descriptor` from `_build_target_descriptor`, run `assemble_at_aperture(target_descriptor, atm, los)`, compare to the `option_c_baseline.yaml` row.

### Traceability

- Same inputs → identical outputs: yes (no RNG; the routing is purely deterministic on the wavelength grid and the `is_hot_target` flag).
- Deterministic seed: N/A.
- Intermediate values inspectable: yes — `target_descriptor` is exposed on `ChainState.stage_outputs["source"]["target_descriptor"]`; tests can assert on it directly.

---

## Out of scope (do not touch)

- **`_warn_swir_hot_non_mixed`** ([core/descriptors.py:295](../src/radiant/core/descriptors.py#L295)). Separate Rule-17 flag with its own routing question; not this task.
- **`T2Reflective` or `T3Mixed` selection in the `source.target.reflectance`-supplied branch.** That branch is already routing correctly per matrix §3.2; only the legacy ε+T fallback is broken.
- **`_build_background_descriptor`** and the `GroundBackground` placeholder. That's CU-008.
- **`_infer_los`** and the Kármán-line default. That's CU-009.
- **MODTRAN backend's single-τ alias.** That's CU-011, blocked on CU-009.
- **The `simplefilter` warning suppression in test fixtures** (e.g. anywhere in `src/radiant/source/tests/`). If a test fixture suppresses warnings, that's a separate test-side decision; this CU touches production code only.
- **Cell 28 / Cell 58 anchor pinning.** They stay bit-invariant; the pinning is unchanged.

---

## Completion criteria

- [ ] CU-007 entry in `docs/Cleanup_Backlog.md` moved to Resolved with this task's commit hash, the 6 affected scenario list, and confirmation that the `simplefilter("ignore", UserWarning)` wrapper is removed.
- [ ] New `src/radiant/source/tests/test_inferrer_mwir_routing.py` covers the five Level 0 anchors plus the failure-mode cases above.
- [ ] `pytest src/`, `pytest tests/integration/`, `mypy --strict`, `ruff check`, `ruff format --check`, `lint-imports` all green.
- [ ] `option_c_baseline.yaml`'s 6 MWIR rows updated; the other 8 rows bit-invariant; anchor cells 28/58 bit-invariant.
- [ ] `docs/architecture/RADIANT_Parameter_System.md` and `docs/RADIANT_Source.md` updated to document `source.target.is_hot_target` and the new MWIR-default routing (Rule 20).
- [ ] Structured Category-B-with-C-radiometric-audit report attached to the commit body or PR description: Numerical Truth Anchors (≥3), Dimensional Audit, Failure Modes, Assumptions, Fragility, Traceability, Cross-Model Consistency, Integration & Regression — with explicit sign-off on each affected MWIR scenario's `L_aperture` delta as "expected per matrix §3.2."
