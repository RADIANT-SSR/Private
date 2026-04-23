# Gap G — Shared CSV Loader Implementation Plan

**Scope**: close the three deferred YAML-surface CSV paths so every spec form in the Target Definition Matrix is reachable from a scenario file.

**Audit source**: [`Target_Definition_gaps.md`](Target_Definition_gaps.md) Gap G (2026-04-22).

**Paths to wire**:
1. `source.target.reflectance_path` (S5 — spectral ρ(λ))
2. `source.target.albedo_path`       (S6 — spectral α(λ), alias of reflectance)
3. `source.target.brightness_temperature_path` (S11 — spectral T_B(λ))

**Already-working reference implementations** (Phases 4 / 5):
- `source.target.user_radiance_path` → [`src/radiant/source/converters/user_radiance.py`](../src/radiant/source/converters/user_radiance.py) (`_load_csv` + `load_user_radiance_csv`)
- `source.target.user_intensity_path` → [`src/radiant/source/converters/user_intensity.py`](../src/radiant/source/converters/user_intensity.py)

Both loaders share the same two-column auto-header-detecting CSV format. Goal: extract that shared format loader once and have all five path surfaces consume it.

---

## Execution rules (same as Target Definition Implementation Plan)

1. One step = one conversation.
2. Every step is Category B or C. Report per CLAUDE.md `Structured Report Template`.
3. Regression gate MANDATORY before declaring a step complete:
   ```
   pytest src/ -v -m "not golden"
   pytest tests/integration/ -v
   pytest tests/integration/test_use_case_matrix.py -v
   pytest tests/integration/test_spec_form_matrix.py -v   # spec-form coverage JSON must flip
   mypy --strict src/radiant/core src/radiant/api
   lint-imports
   ruff check src/
   ```
4. New tests land in the same commit as the implementation.
5. No golden drift without explicit authorization.

---

## Phase map

| Step | Scope | Category | Estimated |
|------|-------|----------|-----------|
| G.1 | Extract shared two-column CSV reader into `converters/_csv.py`; back-port `user_radiance` and `user_intensity` to use it (no behavior change) | B | ~0.25 day |
| G.2 | Wire `reflectance_path` + `albedo_path` through inferrer (S5 / S6 spectral) | C | ~0.3 day |
| G.3 | Wire `brightness_temperature_path` through inferrer (S11 spectral) | C | ~0.3 day |
| G.4 | Flip 9 `_use_case_coverage.json` cells from `raise` to `pass`; add direct spec-form assertions; update gaps doc + matrix revision log | D | ~0.15 day |

Total: ≤ 1 day.

---

## Step G.1 — Shared CSV reader

**Category**: B — Core Abstractions (refactor; behavior-preserving)

**Prompt to paste**:
```
Category B task: extract a shared two-column CSV reader for boundary converters.

Read first:
  - src/radiant/source/converters/user_radiance.py (_load_csv + error paths)
  - src/radiant/source/converters/user_intensity.py (same pattern)
  - docs/Gap_G_CSV_Loader_Plan.md (this plan)
  - CLAUDE.md Rules 2, 15, 17, 19

Scope — modify only:
  - NEW: src/radiant/source/converters/_csv.py
  - src/radiant/source/converters/user_radiance.py  (delegate to the shared reader)
  - src/radiant/source/converters/user_intensity.py (same)
  - src/radiant/source/converters/tests/test_csv_loader.py (NEW)

Implementation:
  Expose a single function:

    def load_two_column_csv(
        path: Path | str,
        *,
        value_unit: str,                 # canonical unit for the value column
        column_label: str,               # "L_t_source", "I_t_source",
                                         # "reflectance", "brightness_temperature", ...
        sd_name: str,                    # SpectralData.name
        sd_source_prefix: str,           # SpectralData.source preamble
    ) -> SpectralData

  Behavior must match the current user_radiance._load_csv contract byte-for-byte:
    - auto-detect header row (first field of line 1 parseable as float ⇒ no header)
    - minimum 2 data rows
    - per-line malformed/empty/non-float → ParameterBoundsError with
      (what, why, action, context) populated
    - returns SpectralData on the CSV's native grid (NO resampling; that's the caller's job)

  Rule 15: keep error messages actionable (path, line number, column name).
  Rule 17: no silent skipping of bad rows.
  Rule 19: this file owns ONLY the CSV → SpectralData transport.
  Rule 2: loader does not convert units; it records `unit=value_unit` verbatim.

  Backport user_radiance.load_user_radiance_csv and user_intensity.load_user_intensity_csv
  to delegate to load_two_column_csv with the appropriate unit / label arguments.
  Preserve their public signatures; they remain the boundary-converter entry points.

Regression gate (must all pass, unchanged):
  pytest src/ -v -m "not golden"
  pytest tests/integration/ -v
  pytest tests/integration/test_spec_form_matrix.py -v
  mypy --strict src/radiant/core src/radiant/api
  lint-imports
  ruff check src/

New tests (MANDATORY):
  test_csv_loader.py:
    1. Valid two-column, no header → SpectralData with expected wl/values/unit/name.
    2. Valid two-column, with header → same result (header auto-skipped).
    3. Missing file → ParameterBoundsError with path in context.
    4. Empty file → ParameterBoundsError.
    5. Single-row file → ParameterBoundsError (min 2 rows).
    6. Malformed line (1 column) → ParameterBoundsError with line_number.
    7. Non-float token → ParameterBoundsError with line_number.
    8. value_unit propagates to SpectralData.unit.
    9. sd_name / sd_source_prefix propagate.

  Also: re-run the existing user_radiance and user_intensity CSV tests (no
  behavior change expected — zero golden drift).

Report per Category B template. Emphasize: this is a behavior-preserving
refactor; any regression in user_radiance or user_intensity tests means
the shared reader has drifted from the original contract.
```

---

## Step G.2 — Wire reflectance_path / albedo_path (S5 / S6 spectral)

**Category**: C — Physics Implementation (user-visible pipeline change)

**Context**:
- Deferred-raise site: [`src/radiant/source/_inferrer.py:997–1023`](../src/radiant/source/_inferrer.py) (`if rho_path_user or alb_path_user: raise ParameterBoundsError(...)`).
- Target converter: [`reflectance_to_descriptor`](../src/radiant/source/converters/reflectance.py) at line 98 — already accepts λ-varying ρ via `SpectralData`.
- Schema entries already exist: [`_schema.py`](../src/radiant/source/_schema.py) lines 613 (`reflectance_path`), 632 (`albedo_path`).

**Prompt to paste**:
```
Category C task: wire reflectance_path / albedo_path through the source inferrer
so S5 / S6 spectral forms are reachable from YAML.

Read first:
  - src/radiant/source/_inferrer.py (lines 990–1050; deferred-raise site)
  - src/radiant/source/converters/_csv.py (from G.1)
  - src/radiant/source/converters/reflectance.py (reflectance_to_descriptor)
  - tests/integration/test_spec_form_matrix.py (S5 cells currently tracked as raise)
  - docs/RADIANT_Target_Definition_Matrix.md §1 S5/S6
  - CLAUDE.md Rules 2, 15, 17, 19

Scope — modify only:
  - src/radiant/source/_inferrer.py (replace the deferred raise with loader + resample + converter dispatch)
  - src/radiant/source/converters/reflectance.py (add a load_reflectance_csv
    helper that delegates to the shared _csv reader; keep reflectance_to_descriptor
    unchanged — it already accepts SpectralData)
  - src/radiant/source/tests/test_inferrer_reflective.py (ADD cases for CSV path)

Implementation:
  1. In reflectance.py, add:
       def load_reflectance_csv(path: Path | str, *, is_albedo: bool) -> SpectralData
     delegating to load_two_column_csv with unit="dimensionless", column_label=
     "albedo" if is_albedo else "reflectance", sd_name="source.target.reflectance",
     sd_source_prefix="source.converters.reflectance".

  2. In _inferrer.py, replace the current `if rho_path_user or alb_path_user: raise`
     block with:
       - Pick the user-set surface (validator already forbids both being set; keep
         the existing mutual-exclusion check untouched).
       - rho_native = load_reflectance_csv(path, is_albedo=<which>)
       - Validate values: ρ ∈ [0, 1] inclusive (Rule 15; ParameterBoundsError with
         min/max in context; no silent clipping).
       - Resample onto the chain grid via np.interp with explicit out-of-grid
         handling: if chain grid extends beyond the file's native grid, raise
         ParameterBoundsError (Rule 17; no silent extrapolation).
       - Construct SpectralData on the chain grid, hand to reflectance_to_descriptor
         with A_t + shape from _resolve_projected_area_and_shape (same contract as
         the scalar branch directly below the removed raise).

  3. Maintain mutual exclusion with every other surface (temperature, user_radiance,
     user_intensity, brightness_temperature_*, radiance_temperature_*, the scalar
     reflectance/albedo) — the existing guards above the deferred raise ALREADY
     reject these combinations for the *_path surface via the _is_user_set checks
     in the validator; verify and extend if a gap is found.

Regression gate:
  pytest src/ -v -m "not golden"
  pytest tests/integration/ -v
  pytest tests/integration/test_use_case_matrix.py -v    (80/10 unchanged)
  pytest tests/integration/test_spec_form_matrix.py -v   (S5 cells flip pass→pass
                                                          outcome; S6 stays pass)
  mypy --strict src/radiant/core src/radiant/api
  lint-imports
  ruff check src/

New tests (MANDATORY):
  test_inferrer_reflective.py additions:
    1. reflectance_path CSV, constant ρ=0.3 across grid → T2Reflective with
       ρ(λ)=0.3 to 1e-12 (round-trip identity; scalar-limit truth anchor).
    2. reflectance_path CSV, step ρ(λ) (0.1 below λ_cut, 0.6 above) → at-aperture
       radiance carries the step in the correct band.
    3. albedo_path CSV, same scalar payload → same descriptor (identity: albedo
       and reflectance paths are aliases; the inferrer picks up whichever the
       user set).
    4. reflectance_path + albedo_path both set → ParameterBoundsError (validator
       already covers this; regression only).
    5. reflectance_path with ρ > 1 on any row → ParameterBoundsError with
       min/max in context, raised at the CSV boundary (not at T2Reflective).
    6. reflectance_path with chain grid wider than file grid →
       ParameterBoundsError (no silent extrapolation).
    7. reflectance_path + source.target.temperature both set → ParameterBoundsError
       (mutual exclusion; regression).

Numerical truth anchors (Category C §1):
  - Anchor 1: Constant ρ=0.3 from CSV → at-aperture L_refl = ρ · E_solar/π to
    1e-6 rel (pure Lambertian identity; already covered for the scalar branch
    in test_inferrer_reflective.py — reuse the anchor for the CSV path).
  - Anchor 2: Cross-check CSV ρ vs scalar ρ at the same constant value → bit-
    identical at-aperture radiance (proves the CSV path adds no extra physics).
  - Anchor 3: Step-ρ CSV produces the same L(λ) as a manually-constructed
    T2Reflective(rho=SpectralData(...)) published via stage_outputs override.

Dimensional audit table MANDATORY (unitless ρ in, unitless ρ out; no unit
conversion in the loader).

Fragility analysis:
  - Chain grid wider than file grid → hard raise (not silent extrapolation).
  - File grid non-monotonic → np.interp requires monotonic x; add explicit
    check with ParameterBoundsError if violated.
  - File grid with duplicate wavelengths → raise (ambiguous interpolation).

Report per Category C.
```

---

## Step G.3 — Wire brightness_temperature_path (S11 spectral)

**Category**: C

**Context**:
- Deferred-raise site: [`src/radiant/source/_inferrer.py:566–593`](../src/radiant/source/_inferrer.py).
- Target converter: [`brightness_temperature_to_descriptor`](../src/radiant/source/converters/brightness_temperature.py) at line 154 — already accepts λ-varying T_B via `SpectralData`; routes to T1Thermal when T_B is constant and to T6TabulatedAtSource otherwise (see the Phase 2.1 docstring).

**Prompt to paste**:
```
Category C task: wire brightness_temperature_path through the source inferrer
so S11 spectral form is reachable from YAML.

Read first:
  - src/radiant/source/_inferrer.py (lines 400–625; deferred-raise site at 566)
  - src/radiant/source/converters/_csv.py (from G.1)
  - src/radiant/source/converters/brightness_temperature.py
    (brightness_temperature_to_descriptor — already handles constant AND
    λ-varying T_B)
  - tests/integration/test_spec_form_matrix.py (S11 cells: scalar form passes
    today via brightness_temperature_K; path form currently raises)
  - docs/RADIANT_Target_Definition_Matrix.md §1 S11
  - CLAUDE.md Rules 2, 15, 17, 19

Scope — modify only:
  - src/radiant/source/_inferrer.py (replace deferred raise with loader +
    resample + converter dispatch)
  - src/radiant/source/converters/brightness_temperature.py (add
    load_brightness_temperature_csv helper)
  - src/radiant/source/tests/test_brightness_temperature_converter.py (extend)

Implementation:
  1. In brightness_temperature.py, add:
       def load_brightness_temperature_csv(path: Path | str) -> SpectralData
     delegating to load_two_column_csv with unit="K",
     column_label="brightness_temperature",
     sd_name="source.target.brightness_temperature",
     sd_source_prefix="source.converters.brightness_temperature".

  2. In _inferrer.py, replace the `if t_b_path_user: raise` block with:
       - T_B_native = load_brightness_temperature_csv(path)
       - Validate: T_B ∈ (0, 10000] K everywhere (ParameterBoundsError at the
         boundary; matches the scalar validator).
       - Resample onto the chain grid via np.interp; out-of-grid → raise.
       - Hand to brightness_temperature_to_descriptor (same call shape as the
         scalar path; the converter already handles λ-constant vs λ-varying
         internally and routes to T1Thermal or T6TabulatedAtSource).

  3. Mutual exclusion: the existing guards above the deferred raise already
     cover brightness_temperature_K + brightness_temperature_path (raise),
     temperature/emissivity combos, reflectance/albedo combos, and
     user_radiance/user_intensity combos — verify no gap opens by wiring
     the path surface.

Regression gate:
  pytest src/ -v -m "not golden"
  pytest tests/integration/ -v
  pytest tests/integration/test_spec_form_matrix.py -v   (S11 cells all pass
                                                          both scalar and path)
  mypy --strict src/radiant/core src/radiant/api
  lint-imports
  ruff check src/

New tests (MANDATORY):
  test_brightness_temperature_converter.py additions:
    1. Constant T_B=300 K CSV → T1Thermal with T_t ≈ 300 K, ε ≡ 1; L(10 µm) =
       B(10 µm, 300 K) to 1e-6 rel (Planck identity).
    2. λ-varying T_B CSV (300 K at 8 µm, 330 K at 12 µm linear) → routes to
       T6TabulatedAtSource (NOT T1Thermal); tabulated L(λ) matches
       hand-computed Planck at the grid midpoint.
    3. T_B < 0 anywhere in CSV → ParameterBoundsError at the boundary.
    4. T_B > 10000 K anywhere → ParameterBoundsError.
    5. Chain grid wider than file grid → ParameterBoundsError.
    6. brightness_temperature_path + brightness_temperature_K both set →
       ParameterBoundsError (regression).

Numerical truth anchors (Category C §1):
  - Anchor 1: Constant T_B=300 K round-trip: descriptor → L(λ) at 10 µm matches
    B(10 µm, 300 K) to 1e-6 rel.
  - Anchor 2: Varying T_B(λ) tabulated: at three sampled wavelengths the
    tabulated L equals the Planck value B(λ, T_B(λ)) evaluated on the file
    grid (inner agreement; no extrapolation).
  - Anchor 3: CSV-constant-T_B and scalar-T_B (brightness_temperature_K)
    forms produce bit-identical T1Thermal descriptors when T_B scalar values
    match.

Dimensional audit table MANDATORY (K in, K out at the boundary; Planck
applies inside the converter with hc from constants.py).

Fragility analysis: same as G.2 (grid monotonicity, extrapolation, duplicates)
plus the Wien-tail underflow warned about in the existing scalar path.

Report per Category C.
```

---

## Step G.4 — Coverage JSON + documentation

**Category**: D — Integration and UX

**Prompt to paste**:
```
Category D task: promote the spec-form coverage JSON and close out Gap G in docs.

Read first:
  - tests/integration/_use_case_coverage.json (post-G.2/G.3 run)
  - tests/integration/test_spec_form_matrix.py
  - docs/Target_Definition_gaps.md Gap G
  - docs/RADIANT_Target_Definition_Matrix.md revision log
  - CLAUDE.md Category D requirements

Scope — modify only:
  - tests/integration/test_spec_form_matrix.py (flip S5 cells from
    outcome="raise" to outcome="pass"; add albedo_path cells if not already
    enumerated — currently S6 only exercises the scalar albedo path; extend
    to also exercise albedo_path CSV for one representative scene_type)
  - tests/integration/_use_case_coverage.json (will auto-update via the
    autouse fixture; confirm the spec_forms block shows S5 all pass)
  - docs/Target_Definition_gaps.md (mark Gap G CLOSED; move to the "closed"
    section with a back-reference; update the Remaining Work table)
  - docs/RADIANT_Target_Definition_Matrix.md (append a revision-log entry
    noting the shared CSV loader delivered)

Implementation:
  1. In test_spec_form_matrix.py, flip the S5 SpecCell entries from "raise"
     to "pass" (and drop the "reflectance_path CSV not yet wired" note).
     Update the leading comment block explaining the coverage.
  2. Run pytest tests/integration/test_spec_form_matrix.py -v; confirm the
     JSON finalizer writes the flipped cells.
  3. Update the gaps doc executive summary: "⚠ Scalar-only" row drops to
     zero forms; move Gap G out of "Remaining Work" into the post-fact
     revision log.
  4. Matrix revision log: append a 2026-MM-DD entry naming the shared
     loader delivery and pointing to the three call sites.

Regression gate:
  pytest src/ -v -m "not golden"
  pytest tests/integration/ -v                         (full green)
  pytest tests/integration/test_use_case_matrix.py -v  (80/10 unchanged)
  pytest tests/integration/test_spec_form_matrix.py -v (all pass, including
                                                        S5 extended/sub/point)
  mypy --strict src/radiant/core src/radiant/api
  lint-imports
  ruff check src/

Regression check (Category D §8): confirm no golden files drifted.

Report per Category D template. Include the before/after status table for
S5, S6, S11 cells and paste the final spec_forms block from
_use_case_coverage.json.
```

---

## Final acceptance (end of Step G.4)

1. `pytest tests/integration/test_spec_form_matrix.py -v` — all 36 cells pass, zero `raise` outcomes remain.
2. `_use_case_coverage.json` `spec_forms` block shows S5/S6/S11 all `pass` for all three scene types.
3. Gaps doc: executive summary shows **12** forms ✅ fully supported, **0** ⚠ scalar-only.
4. Matrix revision log entry added.
5. Regression gate clean on all six commands.
6. No golden drift.

---

## Out of scope (explicitly deferred)

- **Gap H** — automatic `ScalarLambertianReflectance` wrap at assembly. Deferred to the first consumer of the `ReflectanceDescriptor` protocol (Phase 6 docstring plan).
- **Pre-existing regression-gate violations** in `api/plot.py`, `api/sweep.py`, `api/tolerance.py`, and the `cli → optics / platform` import-linter violations. Separate cleanup task.

---

## Revision log

- **2026-04-22**: Initial plan. 4 steps (G.1 refactor, G.2 reflectance CSV, G.3 brightness-temperature CSV, G.4 coverage + docs). Each step has its own regression gate.
