# CU-008 — Stage-2 inferrer: replace grey `GroundBackground` placeholder with spectral ε_g(λ)

**Category:** C (physics implementation — touches the radiometric path through `_assemble_ground_background`'s Kirchhoff `ρ_g = 1 − ε_g`).
**Triggered from:** [docs/tracking/Cleanup_Backlog.md](Cleanup_Backlog.md) CU-008, escalated 2026-04-26 after stage-deferral expired (Stage 3 was supposed to replace this; Stage 6 landed without the replacement).
**Scope:** Schema design for spectral ε_g(λ) input + ~30–60 lines of production code in [src/radiant/source/_inferrer.py](../src/radiant/source/_inferrer.py) + new sub-pixel terrestrial scenario added to a test/baseline + new Level 0 / Level 2 tests. **Zero existing baseline snapshot regressions** — every current baseline scenario is `scene_type: extended` with `background: null`, so the placeholder fires nowhere in production today. The fix lights up dormant code; it does not change live snapshot values.

---

## Problem statement

[src/radiant/source/_inferrer.py:1707–1726](../src/radiant/source/_inferrer.py#L1707) builds a `GroundBackground` for every sub-pixel / point-source terrestrial / airborne scenario by inflating the scalar `source.background.emissivity` parameter into a flat grey `SpectralData` via `_grey_spectraldata`:

```python
# _inferrer.py:1707–1726
bg_T: float = params.get("source.background.temperature")
bg_eps_scalar: float = params.get("source.background.emissivity")
warnings.warn(
    "source._inferrer: terrestrial/airborne sub-pixel scenario is "
    "using a Stage-2 GroundBackground placeholder built from "
    "scalar source.background.temperature / .emissivity.  Stage 3 "
    "of the Option C plan will replace this with spectral "
    "emissivity inference.  Until then, spectral ε_g(λ) is grey.",
    UserWarning,
    stacklevel=3,
)
epsilon_g = _grey_spectraldata(
    wavelength_um=wavelength_um,
    value=bg_eps_scalar,
    name="source.background.emissivity",
    unit="",
)
return GroundBackground(epsilon_g=epsilon_g, T_g=bg_T)
```

The deferred fix ("Stage 3 will replace this") never landed. Stage 6's E_sky decomposition consumes `epsilon_g` spectrally — `_assemble_ground_background` ([atmosphere/assembly.py:1112–1148](../src/radiant/atmosphere/assembly.py#L1112)) computes `rho_g = 1.0 − epsilon_g` per Kirchhoff and multiplies it through both `_diffuse_sky_term` and `_direct_solar_term`, so for any non-grey ground material (vegetation NDVI bands, snow's strong wavelength dependence, urban asphalt at SWIR, etc.) the placeholder silently degrades the reflected solar and reflected sky terms.

### What's actually broken right now

Investigation 2026-04-26 found the placeholder fires on **zero baseline scenarios**:

- All 14 baseline scenarios in `tests/integration/snapshots/option_c_baseline.yaml` and `src/radiant/source/tests/snapshots/*.yaml` are `scene_type: extended`.
- For `extended`, `_build_background_descriptor` returns `None` at [_inferrer.py:1701](../src/radiant/source/_inferrer.py#L1701) — no `GroundBackground` is constructed, the placeholder warning never fires.
- The only live consumer of the placeholder code path today is one unit test (`src/radiant/source/tests/test_inferrer.py:472` asserts the warning fires for a synthesized sub-pixel terrestrial scenario).

The CU-008 entry's claim that "the UserWarning is still emitted on every terrestrial / airborne sub-pixel scenario" was correct *in principle* but the live code base has no such scenarios. **The placeholder is dormant production code**, not silently-corrupting production code.

### Why a fix is still needed

- **Rule 17 (no silent failures).** A "placeholder that emits a warning" is the warning-and-continue antipattern Rule 17 forbids in production. Once a real sub-pixel scenario lands (likely soon — CU-009 reframing of `source.observer_geometry.*`, CU-NEW-x scenarios that exercise sub-pixel point-target geometry), the warning starts firing and the silent-grey ε_g(λ) becomes a real radiometry bug for non-grey materials.
- **Rule 19 (one computation, one module).** The "build spectral ε_g(λ) from a user surface" computation should be a real first-class capability of the source schema, not a dispatched-to-grey fallback inside the legacy ε+T converter.
- **Rule 20 (doc-and-code in lock-step).** `docs/RADIANT_Source.md` describes spectral ε_g(λ) as the supported background surface; `_inferrer.py` only accepts a scalar. The doc claims something the code doesn't deliver.
- **Capability gap.** The ground-background subsystem under [src/radiant/source/backgrounds/](../src/radiant/source/backgrounds/) (`BlackbodyBackground`, `TabulatedBackground`, `ConstantBackground`) is a parallel, legacy at-target-frame system separate from the Option-C `GroundBackground` descriptor. It does not feed `_inferrer.py::_build_background_descriptor`. The two were never connected; the bridge is what this task builds.

### Affected scenarios

**Zero in the current baseline.** The fix introduces (or requires the user to author) a new sub-pixel terrestrial / airborne scenario to exercise the spectral path. The task's regression burden is one or two new snapshot fixtures — not a refresh of existing ones.

**Future scenarios.** Any user-authored sub-pixel / point-source terrestrial / airborne scenario lands on this path. The schema decision below determines whether they get a useful spectral surface or stay on the legacy scalar.

---

## Required reading (do not skip)

1. [CLAUDE.md](../CLAUDE.md) — Rules 5 (Kirchhoff: ρ_g = 1 − ε_g), 13 (constants), 16 (validate before compute), 17 (no silent failures), 19 (one computation, one module), 20 (doc-and-code lock-step).
2. [docs/RADIANT_Source.md](RADIANT_Source.md) — `BackgroundDescriptor` taxonomy (matrix §3.7); `GroundBackground` purpose and contract.
3. [docs/architecture/RADIANT_Parameter_System.md](RADIANT_Parameter_System.md) — `ParameterDef` rules; how to register a new `SpectralData`-typed parameter; `SpectralDataStore` integration patterns.
4. [src/radiant/core/spectral.py:432–550](../src/radiant/core/spectral.py#L432) — `SpectralDataStore.add()` + interpolation behaviour.
5. [src/radiant/core/descriptors.py:858–895](../src/radiant/core/descriptors.py#L858) — `GroundBackground` class (the descriptor you're populating).
6. [src/radiant/source/_inferrer.py:1563–1726](../src/radiant/source/_inferrer.py#L1563) — `_build_background_descriptor` (the file you will edit).
7. [src/radiant/atmosphere/assembly.py:1112–1148](../src/radiant/atmosphere/assembly.py#L1112) — `_assemble_ground_background` (the consumer; `rho_g = 1 − ε_g` and the reflected terms).
8. [docs/reports/cu_tasks/CU-007_MWIR_T3Mixed_Routing_Task.md](CU-007_MWIR_T3Mixed_Routing_Task.md) — pattern this task follows (multi-approach decision, stop triggers, Category-C validation).

---

## Approach decision (raise to user before coding)

The schema surface for spectral ε_g(λ) is the actual design question. Three candidate surfaces; **recommended: Approach 1**, with Approach 2 as an explicit fallback if no spectral library exists for the user's material.

### Approach 1 — Named spectral library + optional override file (recommended)

Add a new `source.background.material` parameter (`dtype=str`, default `"grey"`, vocabulary `{"grey", "vegetation", "snow", "asphalt", "soil", "water"}` initially). When `material == "grey"`, fall back to the existing scalar `source.background.emissivity` (preserves back-compat). Otherwise, look up the named material's ε_g(λ) from a built-in spectral library (a YAML file shipped with `radiant.data` that the SpectralDataStore knows how to load).

Add a parallel `source.background.emissivity_path` parameter (`dtype=str`, default `""`) that, when set, overrides the named library with a user-supplied CSV/YAML spectral file (loaded via `SpectralDataStore.load_csv` or equivalent).

**Pros.**
- Smallest-step usability: 90% of users want "vegetation" or "soil" by name; supplying a CSV is the escape hatch.
- Names are testable as enum vocabulary; the library file is a first-class asset reviewed in PRs (no drift).
- Each library entry is itself a test fixture (one numerical truth anchor per material).
- The grey scalar path is preserved verbatim — no breaking change for existing scenarios.

**Cons.**
- Requires authoring/curating a small spectral library (start with 3 materials: grey, vegetation, snow; expand opportunistically). Library data needs documented sources.
- Adds two new schema parameters.

### Approach 2 — Path-only (`source.background.emissivity_path`)

Drop the named-library option; require users to supply a CSV/YAML spectral file path or accept the scalar default.

**Pros.**
- Simplest schema surface (one new parameter).
- No library curation burden.

**Cons.**
- Every user authoring a non-grey scenario has to find/build their own spectral file. High friction; in practice users will fall back to the scalar default and the placeholder warning will keep firing.
- Doesn't deliver real test infrastructure — no built-in materials means no built-in numerical truth anchors.

### Approach 3 — Scalar-only with `SpectralData` ABC accept

Allow `source.background.emissivity` to accept either a `float` or a `SpectralData` (or path to one) at the parameter-resolver level. Single parameter, polymorphic input.

**Pros.**
- Smallest schema diff (just relaxes the `dtype` on an existing parameter).

**Cons.**
- Polymorphic dtypes break `ParameterDef`'s strict-type contract (per CLAUDE.md Rule 12 every parameter has a `dtype`). Adding a polymorphic exception undermines the whole parameter system.
- **Reject.** The principle (every parameter has one type, type is checked at the boundary) is more important than saving one parameter slot.

**Recommended: Approach 1.** Approach 2 is a documented Plan B if owner pushback says "no spectral library curation." Approach 3 is rejected.

---

## Implementation steps (after approach decision)

1. **Branch.** `git switch -c chore/cu-008-spectral-ground-background`.
2. **Schema.**
   - Add `source.background.material` (`dtype=str`, default `"grey"`, bounds-checked against the legal-vocabulary list) to [src/radiant/source/_schema.py](../src/radiant/source/_schema.py).
   - Add `source.background.emissivity_path` (`dtype=str`, default `""`) to the same schema.
   - Update `ALL_PARAMETERS` and `__all__`.
3. **Spectral library (if Approach 1).**
   - Create `src/radiant/data/spectral_library/ground_emissivity.yaml` with 3 entries: `grey` (constant 0.95 across the canonical 0.4–14 µm grid for back-compat), `vegetation` (typical NDVI band shape — chlorophyll absorption + NIR plateau), `snow` (high VNIR, drops in MWIR, rises again in LWIR).
   - Each entry: `name`, `wavelength_um: [...]`, `emissivity: [...]`, `source: "<citation>"`, `notes: "..."`.
   - One unit test per library entry that validates the YAML loads, monotonic-grid, values in [0, 1].
4. **Loader (if Approach 1).**
   - Add `radiant.io.spectral_library.load_ground_emissivity(name: str) -> SpectralData` that reads the library YAML and returns a `SpectralData` keyed on the named material.
   - Add `radiant.io.spectral_library.load_emissivity_csv(path: str) -> SpectralData` for the path override.
5. **Routing (in `_inferrer.py::_build_background_descriptor`).**
   - Read `material = params.get("source.background.material")` and `emissivity_path = params.get("source.background.emissivity_path")`.
   - **If `emissivity_path` is set:** load the spectral file, pass through `SpectralDataStore` if a store is already in scope, otherwise interpolate to `wavelength_um` directly. Return `GroundBackground(epsilon_g=<spectral>, T_g=bg_T)` with no warning.
   - **Else if `material == "grey"`:** preserve the existing scalar fallback verbatim. Remove the `warnings.warn(...)` call — the grey scalar is now an explicit user choice (`material="grey"`), not a placeholder.
   - **Else if `material` is a known library name:** load via the spectral library, return the descriptor with no warning.
   - **Else:** raise `ParameterBoundsError` with the legal-vocabulary list (Rule 17 — fail loudly on unknown materials).
6. **Test suite (write before edits).** New file `src/radiant/source/tests/test_inferrer_ground_background.py`:
   - **A1 (Level 0).** `material="grey"`, scalar `source.background.emissivity=0.95`. Verify `_build_background_descriptor` returns `GroundBackground` with constant ε_g(λ) = 0.95. Verify *no* `UserWarning` fires (grey is now explicit). Today this fails (warning fires); after the fix it passes.
   - **A2 (Level 0).** `material="vegetation"`. Verify the returned `epsilon_g` matches the library's tabulated values to ≤1e-9 at every wavelength.
   - **A3 (Level 0).** `material="snow"`. Same shape match.
   - **A4 (Level 0).** `material="vegetation"`, `emissivity_path="/tmp/override.csv"` containing a different spectral table. Verify the path overrides the named library (path wins).
   - **A5 (Level 0).** `material="bogus_unknown_material"`. Verify `ParameterBoundsError` raised with the legal-vocabulary list in the action message.
   - **A6 (Level 2).** End-to-end: build a sub-pixel terrestrial MWIR scenario YAML (e.g. ambient vehicle target on vegetation background), run through `RadiantSession.run()`, capture `L_aperture`, `nedt_K`, `snr`. Verify the values change non-trivially when switching `material` from `grey` to `vegetation` (>5% delta in L_aperture for at least one wavelength bin), and that they match `_assemble_ground_background`'s closed-form expression to ≤1e-6.
7. **Update existing test fixture.** [src/radiant/source/tests/test_inferrer.py:472](../src/radiant/source/tests/test_inferrer.py#L472) currently asserts the placeholder warning fires; flip it to assert the warning *does not* fire (Rule 17 — the placeholder is gone). Replace the warning-fires assertion with a structural check (the returned `GroundBackground.epsilon_g` is non-`None` and has the expected scalar value).
8. **Doc updates (Rule 20).**
   - `docs/RADIANT_Source.md` — describe the new `material` enum + `emissivity_path` override; remove any "spectral ε_g(λ) is deferred" language.
   - `docs/architecture/RADIANT_Parameter_System.md` — add the two new parameters to the parameter table.
9. **Full regression gate.**
   ```
   pytest src/ -q                       # +6 new tests; existing test_inferrer.py warning assertion flipped
   pytest tests/integration/ -q         # zero baseline drift expected
   mypy --strict src/radiant/core src/radiant/api
   ruff check src/
   ruff format --check src/
   lint-imports --config pyproject.toml
   ```
10. **Move CU-008 to Resolved** in `docs/tracking/Cleanup_Backlog.md` with the commit hash and a one-line note: "placeholder removed, named spectral library + path override landed, three Level 0 anchors covered." (Rule 22 — phantom closure forbidden.)
11. **Commit.** Format: `chore(debt): CU-008 — spectral GroundBackground; remove Stage-2 placeholder`. Body lists the new schema parameters, library entries, and confirms zero existing-baseline drift.

---

## Stop triggers

Stop and ask the user before continuing if any of these fire:

- **Any existing baseline scenario's `L_aperture`, `nedt_K`, `snr`, or `mtf_at_nyquist` shifts.** All 14 baseline scenarios are `extended` with `background: null`; the fix should not reach them. Drift means a routing change is firing for `extended` cases — investigate before continuing.
- **Anchor cells 28 / 58 (`CELL28_PINNED`, `CELL58_PINNED`) shift.** Same reason as above (both are extended LWIR). Bit-invariance must hold.
- **The change touches `_assemble_ground_background` or `_diffuse_sky_term` / `_direct_solar_term`.** Those are the spectral consumer; this CU is a producer-side fix only. If you find yourself editing the assembly, you've crossed scope.
- **The library YAML adds materials beyond `{grey, vegetation, snow}`.** Three is enough for the initial PR; soil/asphalt/water can come in a follow-on. If a fourth wants to land mid-task, defer it.
- **`source.background.emissivity` (the scalar) is removed or its meaning changed.** The scalar must remain as the `material="grey"` back-compat path. Deleting it breaks every existing sub-pixel test.
- **The library YAML format requires a new I/O layer beyond `SpectralDataStore`.** If you find yourself writing custom YAML parsing, route through the existing data-loader pattern in `radiant.io` instead.
- **`SpectralDataStore` interpolation produces NaN or extrapolated values outside the library's documented wavelength range without a clear warning.** That's a Rule-17 silent-failure regression — fix the loader or the library coverage, not the test.

---

## Validation requirements (Category C — full)

### Numerical truth anchors (≥3 required)

1. **Grey-limit sanity.** With `material="grey"` and `source.background.emissivity=0.95`, the resulting `GroundBackground.epsilon_g.values` must equal `0.95` at every wavelength bin to **abs ≤ 1e-15** (no interpolation artefacts; this is the back-compat invariant).
2. **Vegetation NDVI signature.** With `material="vegetation"`, the library entry's tabulated values must round-trip: load → interpolate to canonical grid → compare to source values at the original wavelengths to **abs ≤ 1e-9**. Cite the source spectral library (e.g. ASTER, ECOSTRESS).
3. **Snow MWIR drop.** With `material="snow"`, verify the documented spectral feature (high VNIR, drop near 1.5 µm, recovery toward 3 µm) is present in the loaded values within tolerance of the source library to **abs ≤ 1e-3** (looser because snow libraries vary across the literature).

### Dimensional audit

| Stage                                         | Input units                | Output units               | Conversion           | Check |
|-----------------------------------------------|----------------------------|----------------------------|----------------------|-------|
| `material` (enum)                             | string                     | string                     | bounds-check         | ✓     |
| `emissivity_path` (string)                    | filesystem path            | filesystem path            | I/O                  | ✓     |
| Library YAML `wavelength_um`                  | µm                         | µm                         | none                 | ✓     |
| Library YAML `emissivity`                     | dimensionless              | dimensionless              | none                 | ✓     |
| Loaded `SpectralData`                         | (µm, dimensionless)        | (µm, dimensionless)        | wrap                 | ✓     |
| `SpectralDataStore` interpolation to grid     | (µm grid, dimensionless)   | dimensionless on grid      | linear interp        | ✓     |
| `_assemble_ground_background`: `rho_g = 1 − ε_g` | dimensionless           | dimensionless              | subtract             | ✓     |
| `rho_g · diffuse·τ_full_up`                   | dimensionless · W/m²/sr/µm | W/m²/sr/µm                 | multiply             | ✓     |

### Failure modes

- **`material="vegetation"`, `emissivity_path="not_a_real_file.csv"`.** Verify `FileNotFoundError` raised with actionable message (per Rule 15). The path-override branch must fail loudly when the file is missing.
- **`material="vegetation"`, library YAML missing the entry.** Verify `ParameterBoundsError` raised, listing the available library entries.
- **`emissivity_path` points to a CSV with values outside [0, 1].** Validate at load time (per Rule 16); raise `ParameterBoundsError`.
- **`emissivity_path` covers a wavelength range narrower than the canonical grid.** `SpectralDataStore` constant-extrapolates; verify a `UserWarning` is logged (Rule 17 — the user is silently extending physics outside their data).
- **`source.background.emissivity` (scalar) and `material="vegetation"` both set.** Decide precedence: `material` wins, scalar is ignored. Document explicitly in `docs/RADIANT_Source.md`.
- **`emissivity_path` and `material="grey"` both set.** Path wins (it's the explicit override). Log a `UserWarning` so the user sees the precedence resolution.
- **`scene_type="extended"` with `material="vegetation"`.** Background descriptor is `None` (extended scenes have no background descriptor); the material parameter is silently unused. Verify a `UserWarning` per the existing extended-scene Decision-#15 pattern at [_inferrer.py:1686](../src/radiant/source/_inferrer.py#L1686).

### Assumptions

- **Library values are absolute emissivity (Kirchhoff coefficient), not normalized.** Document in the library YAML schema. ε_g ∈ [0, 1].
- **Library wavelength grid spans at least 0.4–14 µm.** Outside this range constant extrapolation kicks in via `SpectralDataStore`. Document the supported range per material.
- **Approach 1's vocabulary is closed at PR time.** Adding a new material is a separate (small) PR; the schema parameter's bounds list is the authoritative vocabulary.
- **The legacy at-target-frame `radiant.source.backgrounds` subsystem is untouched.** That's a separate parallel system for `BlackbodyBackground` / `TabulatedBackground` / `ConstantBackground`, not the Option-C `GroundBackground` descriptor. Out of scope.

### Fragility analysis

- **Library curation drift.** If the source library cited in the YAML is later updated by its publisher, our copy may go stale. Mitigation: cite the access date in the YAML; re-fetch annually.
- **CSV loader edge cases.** Empty file, missing columns, non-monotonic wavelengths. All must raise `ParameterBoundsError` at load time.
- **Memory.** Library YAMLs are small (KB); `SpectralDataStore.add` interpolates onto the canonical grid (already-paid cost). No memory concern.
- **Performance.** Library YAML is loaded once per scenario at descriptor construction; subsequent calls hit the cache. No performance concern.

### Cross-model consistency

- The new spectral path's output (`GroundBackground.epsilon_g.values`) must equal `_grey_spectraldata(value=scalar).values` to bit-precision when `material="grey"`. This is the back-compat invariant.
- The Level 2 test (A6) must compare `_assemble_ground_background`'s output for the new sub-pixel scenario against a closed-form hand-calculation of `(L_self + direct + diffuse) * tau_full_up + L_path_full` using a single-bin spectral grid — proves the spectral plumbing doesn't introduce a side-channel error.

### Traceability

- Same inputs → identical outputs: yes (no RNG; library YAML is read-only at load time).
- Deterministic seed: N/A.
- Intermediate values inspectable: yes — `target_descriptor`, `background_descriptor` are exposed on `ChainState.stage_outputs["source"]`. Library load returns a `SpectralData`, fully inspectable.

---

## Out of scope (do not touch)

- **`_assemble_ground_background`** ([atmosphere/assembly.py:1112](../src/radiant/atmosphere/assembly.py#L1112)). Consumer side; unchanged.
- **`_assemble_t1` / `_assemble_t2` / `_assemble_t3`** target-side assembly. Unrelated.
- **`radiant.source.backgrounds.{BlackbodyBackground,TabulatedBackground,ConstantBackground}`** legacy at-target-frame subsystem. That's a parallel surface; not the Option-C `GroundBackground` path.
- **`source.background.temperature`** scalar. Stays as a scalar parameter; spectral `T_g(λ)` is non-physical (temperature is a single number).
- **CU-005, CU-007, CU-009, CU-011** related backlog items. CU-009 may interact (it adds `source.observer_geometry.*` parameters that would also benefit from a sub-pixel scenario added by this CU), but the schemas are independent. Don't mix.
- **Adding sub-pixel scenarios to the existing 14-cell baseline.** That's a separate scenario-design decision. This CU may add one or two test-only fixtures but should not modify `tests/integration/snapshots/option_c_baseline.yaml` rows.

---

## Completion criteria

- [ ] CU-008 entry in `docs/tracking/Cleanup_Backlog.md` moved to Resolved with this task's commit hash, one-line summary citing the new schema parameters and the placeholder removal (Rule 22).
- [ ] New `src/radiant/source/tests/test_inferrer_ground_background.py` covers the six Level 0 / Level 2 anchors plus the failure-mode cases above.
- [ ] New `src/radiant/data/spectral_library/ground_emissivity.yaml` with three entries: `grey`, `vegetation`, `snow`. Each cites a source.
- [ ] `src/radiant/io/spectral_library.py` (or equivalent) provides the loader functions; covered by its own Level 0 unit tests.
- [ ] Existing `test_inferrer.py:472` warning-fires assertion flipped to warning-does-not-fire + structural check on `GroundBackground.epsilon_g`.
- [ ] `docs/RADIANT_Source.md` and `docs/architecture/RADIANT_Parameter_System.md` updated; the "Stage-2 GroundBackground placeholder" language removed (Rule 20).
- [ ] `pytest src/`, `pytest tests/integration/`, `mypy --strict`, `ruff check`, `ruff format --check`, `lint-imports` all green.
- [ ] All 14 baseline scenarios bit-invariant (zero drift in `option_c_baseline.yaml` and the per-scenario source-stage snapshots); anchor cells 28/58 bit-invariant.
- [ ] Structured Category C report attached to the commit body or PR description: Numerical Truth Anchors (≥3), Dimensional Audit, Failure Modes, Assumptions, Fragility, Traceability, Cross-Model Consistency, Integration & Regression — with the new sub-pixel scenario's `L_aperture` / `nedt_K` / `snr` deltas explicitly attributed to `material="vegetation"` vs `material="grey"`.
