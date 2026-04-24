# Gap H — Automatic `ScalarLambertianReflectance` Wrap at Assembly

**Status: ✅ COMPLETE (2026-04-24).**  Delivered in three commits on `main`:
- **H.1 + H.3 (bundled, `48bdf73`)** — `T2Reflective.rho` narrowed to `ReflectanceDescriptor | None`; [`reflectance_to_descriptor`](../src/radiant/source/converters/reflectance.py) wraps scalar + CSV ρ into `ScalarLambertianReflectance`; MWIR §3.2 warn fires on the adapter; all downstream tests ported to the protocol surface.  Bundled with Gap G close-out because the type-boundary entanglement made a clean split infeasible without breaking the regression gate.
- **H.2 (`cf6a94d`)** — `_assemble_t2` / `_components_t2` derive view / illumination unit vectors from `LineOfSightGeometry` via `_view_illum_from_los` and pass them through the protocol call.  Spy-descriptor tests in `TestGapH2_ViewIllumFromLOS` guard the vectors and confirm bit-identical output vs. the Lambertian reference.
- **H.4 (this commit)** — docs close-out: Gap H marked CLOSED in all three tracking docs; Remaining Work emptied.

---

**Scope**: make good on the Phase 6 / Step 6.1 docstring promise — every path that builds a `T2Reflective` produces a `rho` that satisfies the `ReflectanceDescriptor` protocol, and that protocol interface is actually exercised end-to-end by at least one consumer.

**Audit source**: [`Target_Definition_gaps.md`](Target_Definition_gaps.md) Gap H (2026-04-22). P3. No user-facing impact today.

**Current state** (for context, verified 2026-04-23):
- [`src/radiant/core/reflectance.py`](../src/radiant/core/reflectance.py) ships `ReflectanceDescriptor` (runtime-checkable Protocol) + `ScalarLambertianReflectance` adapter.
- [`T2Reflective.rho`](../src/radiant/core/descriptors.py) is typed `SpectralData | ReflectanceDescriptor | None`, but the inferrer and the scalar-lift helper in [`reflectance.py`](../src/radiant/source/converters/reflectance.py) only ever hand it a `SpectralData`. Nothing wraps today.
- `LambertianBRDF` and `PhongBRDF` each implement `.reflectance_at(...)` (they satisfy the protocol) but are not reachable from user YAML — only tests construct them.
- `AtmosphereStage` ([`src/radiant/atmosphere/assembly.py`](../src/radiant/atmosphere/assembly.py)) consumes `target.rho` via `_extract_sd_values(target.rho, atm)`, which assumes `SpectralData`. No code calls `.reflectance_at(...)`.

**Why this is cleanup, not a feature**: matrix coverage is already green (S4/S5/S6 scalar + CSV all pass). Nothing user-visible changes. What changes is the *type-level* story: after Gap H, the Phase 6 framing is honest.

---

## Execution rules (same as the Target Definition Implementation Plan)

1. One step = one conversation.
2. Every step is Category B. Report per CLAUDE.md `Structured Report Template`.
3. Regression gate MANDATORY before declaring a step complete:
   ```
   pytest src/ -v -m "not golden"
   pytest tests/integration/ -v
   pytest tests/integration/test_use_case_matrix.py -v
   pytest tests/integration/test_spec_form_matrix.py -v
   mypy --strict src/radiant/core src/radiant/api
   lint-imports
   ruff check src/
   ```
4. New tests land in the same commit as the implementation.
5. No golden drift expected. Any change to `tests/integration/_use_case_coverage.json` or `tests/golden/*` is a red flag — physics does not change in this gap.

---

## Design decision — where to wrap

Three candidate sites were considered; option (c) is chosen.

| Option | Where wrap happens | Rule 11 | Type story at `T2Reflective.rho` | Observability at descriptor boundary | Verdict |
|--------|--------------------|---------|-----------------------------------|--------------------------------------|---------|
| (a) Inside `T2Reflective.__post_init__` | `radiant.core.descriptors` | ✅ (adapter lives in `core.reflectance`) | Field typed `ReflectanceDescriptor` post-construction; `SpectralData` becomes a construction-time convenience | Wrapping hidden in a frozen dataclass — surprising to readers | Defensible but magical |
| (b) Lazily in `AtmosphereStage` / `assembly._extract_sd_values` | `radiant.atmosphere.assembly` | ✅ | `T2Reflective.rho` keeps the union (nothing enforced) | Downstream consumer decides; the descriptor contract is still ambiguous | Moves the decision away from where the type is set; Gap H re-opens the first time a second consumer wants the protocol |
| **(c) At the inferrer + boundary converter, before `T2Reflective` is built** | `radiant.source.converters.reflectance` (+ `source._inferrer` already delegates to it) | ✅ | `T2Reflective.rho: ReflectanceDescriptor \| None` — tight, single-variant | The boundary converter is the place the matrix §6 user surface hands off to a descriptor; auditable and grep-able | **Chosen** |

**Rationale for (c)**:
1. **Rule 11 stays clean**: `source` can import `ScalarLambertianReflectance` from `core.reflectance`; `core.descriptors` can tighten its type to `ReflectanceDescriptor`.
2. **Rule 19 stays clean**: the boundary conversion for reflectance already lives in one module (`source/converters/reflectance.py`). Gap H is a two-line change there (wrap the `rho_sd` before constructing `T2Reflective`), not a new module.
3. **Closes the type union for real**: post-Gap-H, `T2Reflective.rho: ReflectanceDescriptor | None`. The type union narrows (one concrete path = `ScalarLambertianReflectance(SpectralData)`), enabling `isinstance(t2.rho, ReflectanceDescriptor)` as an invariant, and forcing assembly to call the protocol.
4. **Single place to audit**: `reflectance_to_descriptor` is the only current call site that builds a `T2Reflective`. If someone adds a new call site later, mypy catches it the moment it tries to pass a `SpectralData`.
5. **`T2Reflective.__post_init__`** still accepts `ReflectanceDescriptor` (no change) — it loses the `SpectralData` branch in its MWIR-grid warning and delegates that warning to the wrap site, where the grid is trivially knowable.

**What option (c) deliberately does NOT do**:
- No cross-stage import anywhere (Rule 11 preserved).
- No new `AtmosphereDescriptor` / new BRDF concretions / new YAML surface.
- Assembly (`_extract_sd_values`) is updated minimally so it goes through `.reflectance_at(...)` — this is the "downstream consumer exists" closeout criterion. No physics changes; Level-0 anchors stay bit-identical.

---

## Phase map

| Step | Scope | Category | Estimated | Commit |
|------|-------|----------|-----------|--------|
| **H.1 + H.3 (bundled)** | Wrap at the boundary converter: `reflectance_to_descriptor` returns a `T2Reflective` whose `rho` is always `ScalarLambertianReflectance`; narrow `T2Reflective.rho: ReflectanceDescriptor \| None`; relocate MWIR warning to the wrap site; port the ~13 `target.rho.values` assertions in `test_inferrer_reflective.py` to the protocol surface; convert `test_accepts_raw_spectral_data` to a negative test; add the parametrised invariant test | B | ~0.3 day | Single commit — H.1 breaks the tests that H.3 fixes, natural pair |
| H.2 | Update `_assemble_t2` / `_components_t2` to consume `target.rho` via `.reflectance_at(λ, view, illum)` with properly-derived unit vectors from `los` (see decisions #1 below); keep numerical results bit-identical; add spy-descriptor test proving `.reflectance_at(...)` is called | B | ~0.15 day | Its own commit |
| H.4 | Documentation: close Gap H in `Target_Definition_gaps.md`; revision-log entries in `Target_Definition_gaps.md` and `RADIANT_Target_Definition_Matrix.md`; Phase 6 completion-note update in `Target_Definition_Implementation_Plan.md`; strike the Remaining Work row | B | ~0.05 day | Its own commit |

Total: ≤ 0.5 day. Three commits.

---

## Decisions (2026-04-23)

1. **View / illumination unit vectors (Step H.2): option (b) — derive properly from `los`.** In `_extract_reflectance_on_grid`, build `view` and `illum` as 3-vectors from the `LineOfSightGeometry` (`los.theta_view` + azimuth → view unit vector; `los.theta_s` + `los.theta_azimuth` → illumination unit vector). Use the existing RADIANT convention (right-handed, +Z toward target, ZYX Euler per `docs/RADIANT_Conventions.md` §1). The adapter ignores them today, so assembly output stays bit-identical; future anisotropic BRDFs get proper inputs for free. No new abstraction — two short trig helpers next to `_extract_reflectance_on_grid`.
2. **`test_accepts_raw_spectral_data`**: convert to a negative test that asserts `T2Reflective(rho=<SpectralData>)` raises a clear `TypeError` / `ParameterBoundsError` post-Gap-H. Preserves documentation of the "you can't do this directly; use the converter" contract.
3. **T5 / T6 / T7 `SpectralData` fields** (`L_t_source`, `I_t_source`, `L_t_aperture`) — explicitly OUT OF SCOPE for Gap H. Any future protocol for these gets its own gap filing.
4. **Commit granularity**: H.1+H.3 bundled into one commit (tests break in lockstep with the production change); H.2 and H.4 each their own commit.

---

## Step H.1 + H.3 (bundled) — Wrap at the boundary converter + test-surface refactor

**Category**: B — Core Abstractions (type-narrowing refactor; behavior-preserving numerically).

**Why bundled**: H.1 narrows `T2Reflective.rho` and changes the returned object type, which breaks every `target.rho.values` / `target.rho.wavelength_um` assertion in `test_inferrer_reflective.py`. The test-surface port in H.3 is the only thing that keeps the regression gate green once H.1 lands — they must ship in the same commit.

**Files to touch**:
- [`src/radiant/source/converters/reflectance.py`](../src/radiant/source/converters/reflectance.py) — after scalar lift + `_validate_rho`, wrap the resulting `SpectralData` into a `ScalarLambertianReflectance` and hand the adapter (not the `SpectralData`) to the `T2Reflective` constructor.
- [`src/radiant/core/descriptors.py`](../src/radiant/core/descriptors.py) — narrow `T2Reflective.rho: ReflectanceDescriptor | None`; remove the `SpectralData`-branch of the MWIR warning in `__post_init__` (warn site moves to the converter because that is where the grid is known at wrap time); update the docstring to reflect "wrap at assembly" is now an invariant; keep the "rho is required" raise.
- [`src/radiant/core/tests/test_reflectance_descriptor.py`](../src/radiant/core/tests/test_reflectance_descriptor.py) — convert `test_accepts_raw_spectral_data` into a **negative test** that asserts `T2Reflective(rho=<SpectralData>)` raises a clear `TypeError` or `ParameterBoundsError`. Rename to `test_rejects_raw_spectral_data` and document that the supported entry path is the converter.
- [`src/radiant/source/converters/tests/test_reflectance_converter.py`](../src/radiant/source/converters/tests/test_reflectance_converter.py) (new or extend existing) — three new assertions: (a) `rho_sd` input yields `ScalarLambertianReflectance` output; (b) `.reflectance_at(λ, view, illum)` round-trips bit-identical to the input `SpectralData.values` on the native grid; (c) MWIR warning fires at the wrap site when the grid overlaps 3–5 µm, identical text to what `__post_init__` emitted before.
- [`src/radiant/source/tests/test_inferrer_reflective.py`](../src/radiant/source/tests/test_inferrer_reflective.py) — port the ~13 assertions that reach into `target.rho.values` / `target.rho.wavelength_um`. Prefer `target.rho.reflectance_at(wl, zero_vec, zero_vec)` (the protocol surface) over `target.rho.reflectance.values` (the adapter internal) — the protocol call is what future concretions must satisfy.
- [`src/radiant/source/tests/test_gap_h_invariant.py`](../src/radiant/source/tests/test_gap_h_invariant.py) (NEW) — ONE parametrised test `test_every_t2_rho_is_reflectance_descriptor` that sweeps the four user-facing spec forms (`source.target.reflectance` scalar, `source.target.albedo` scalar, `source.target.reflectance_path` CSV, `source.target.albedo_path` CSV) through the inferrer and asserts (i) `isinstance(target, T2Reflective)`, (ii) `isinstance(target.rho, ReflectanceDescriptor)`, (iii) `target.rho.reflectance_at(WL, ZERO_VEC, ZERO_VEC)` returns an array with the right shape and values in [0, 1].

**Prompt to paste**:
```
Category B task (bundled H.1 + H.3): wrap the scalar ρ SpectralData into
ScalarLambertianReflectance at the source-stage boundary so T2Reflective.rho is
always a ReflectanceDescriptor after construction, and port the test surface to
the protocol interface in the same commit.

Read first:
  - src/radiant/core/reflectance.py (ScalarLambertianReflectance adapter + protocol)
  - src/radiant/core/descriptors.py (T2Reflective — current rho union and MWIR warn)
  - src/radiant/source/converters/reflectance.py (reflectance_to_descriptor)
  - src/radiant/source/_inferrer.py (_maybe_build_from_reflectance — does NOT need
    changes; the converter is the single wrap site)
  - src/radiant/source/tests/test_inferrer_reflective.py (the 13 .values/.wavelength_um
    assertions that must be ported)
  - docs/Gap_H_Wrap_At_Assembly_Plan.md (this plan)
  - CLAUDE.md Rules 11, 17, 19

Scope — modify only:
  - src/radiant/core/descriptors.py (narrow rho type; relocate MWIR warning)
  - src/radiant/source/converters/reflectance.py (wrap + emit MWIR warning; keep
    SpectralData as an ACCEPTED INPUT to the converter; the adapter is built here)
  - src/radiant/core/tests/test_reflectance_descriptor.py
      — convert test_accepts_raw_spectral_data into a NEGATIVE test
        (renamed test_rejects_raw_spectral_data) that asserts direct
        T2Reflective(rho=<SpectralData>) raises.
  - src/radiant/source/converters/tests/test_reflectance_converter.py (NEW or
    extend — three new assertions; see plan)
  - src/radiant/source/tests/test_inferrer_reflective.py
      — port ~13 target.rho.values / target.rho.wavelength_um assertions to
        target.rho.reflectance_at(WL, ZERO_VEC, ZERO_VEC).
  - src/radiant/source/tests/test_gap_h_invariant.py (NEW)
      — parametrised test_every_t2_rho_is_reflectance_descriptor over the four
        user surfaces (reflectance, albedo, reflectance_path, albedo_path).

Implementation:
  1. In source/converters/reflectance.py, after `_validate_rho(...)`:
         adapter = ScalarLambertianReflectance(reflectance=rho_sd)
         _warn_mwir_on_reflectance_grid(rho_sd)
     and pass `rho=adapter` to T2Reflective (NOT rho=rho_sd). The MWIR warning
     moves from T2Reflective.__post_init__ to this wrap site (grid is knowable
     here and the warn is deterministic).

  2. In core/descriptors.py:
         rho: ReflectanceDescriptor | None = None
     Remove the `isinstance(self.rho, SpectralData)` branch from __post_init__;
     delete SpectralData import if no longer needed. Keep the "rho is required"
     raise. Add a clear TypeError/ParameterBoundsError if rho is a SpectralData
     (for the negative test in core/tests/test_reflectance_descriptor.py).

  3. Keep reflectance_to_descriptor's SIGNATURE accepting `rho: SpectralData | float`
     — that is the converter's user-facing input; only the OUTPUT changes.

  4. Port test_inferrer_reflective.py: grep the file for `.rho.values` and
     `.rho.wavelength_um` and rewrite each assertion to call
     `target.rho.reflectance_at(expected_wl, np.zeros(3), np.zeros(3))`.
     The numerical values returned on the input grid must be bit-identical to
     the old `.rho.values`, so each assertion's expected value stays the same.

  5. Add src/radiant/source/tests/test_gap_h_invariant.py with a single
     parametrised test over four scenarios (scalar ρ, scalar albedo,
     reflectance_path CSV, albedo_path CSV). Use pytest.mark.parametrize. Assert:
       - isinstance(target, T2Reflective)
       - isinstance(target.rho, ReflectanceDescriptor)
       - target.rho.reflectance_at(WL, np.zeros(3), np.zeros(3)).shape == WL.shape
       - 0.0 <= min <= max <= 1.0

Regression gate (must all pass):
  pytest src/ -v -m "not golden"
  pytest tests/integration/ -v
  pytest tests/integration/test_spec_form_matrix.py -v
  pytest tests/integration/test_use_case_matrix.py -v
  mypy --strict src/radiant/core src/radiant/api
  lint-imports
  ruff check src/

Category B validation requirements:
  - Dimensional audit: ρ dimensionless in → ρ dimensionless out. Adapter does not
    touch units.
  - Failure modes: rho=None still raises (regression); rho SpectralData passed
    directly to T2Reflective now raises (negative test); rho SpectralData with
    empty .values still raises via _validate_rho; rho SpectralData with ρ ∉ [0, 1]
    still raises via _validate_rho; MWIR grid still triggers UserWarning text
    exactly unchanged, now at the converter site.
  - Serialization round-trip: note in the report that dataclasses.asdict on
    T2Reflective now yields a dict whose `rho` is a ScalarLambertianReflectance —
    as of 2026-04-23 there is no YAML dumper that inlines SpectralData, so this
    is a no-op check; list it anyway.

Report per Category B template. Explicit note: physics values (L at aperture,
assembly output) must be bit-identical before and after this step. Any diff is
a bug in the adapter, not a desired outcome. Commit as one commit (H.1 + H.3
bundle).
```

---

## Step H.2 — Teach `_assemble_t2` to use the protocol

**Category**: B — Core Abstractions (consumer added; behavior-preserving numerically).

**Files to touch**:
- [`src/radiant/atmosphere/assembly.py`](../src/radiant/atmosphere/assembly.py) — replace `rho = _extract_sd_values(target.rho, atm)` in `_assemble_t2` and `_components_t2` with a call through the protocol. Add a small helper next to `_extract_sd_values` rather than modifying it (Rule 19 — `_extract_sd_values` owns the grid-match check for `SpectralData`-typed fields used by T1/T3/T6/T7; T2 now takes a different input type).
- [`src/radiant/atmosphere/tests/test_assembly.py`](../src/radiant/atmosphere/tests/test_assembly.py) — add a test that `_assemble_t2` is bit-identical to the pre-Gap-H output on a constant-ρ=0.3 scene (this is the numerical anchor that the adapter introduces no drift).

**Implementation sketch** (decision #1 chose option (b) — derive proper unit vectors):
```
def _unit_vector_from_zenith_azimuth(theta: float, phi: float) -> np.ndarray:
    """RADIANT convention (+Z toward target, right-handed; see
    RADIANT_Conventions.md §1). theta is zenith angle from +Z, phi is
    azimuth from +X toward +Y. Returns a 3-vector in sensor frame."""
    st = math.sin(theta); ct = math.cos(theta)
    return np.array([st * math.cos(phi), st * math.sin(phi), ct], dtype=np.float64)


def _extract_reflectance_on_grid(
    rho: ReflectanceDescriptor,
    atm: AtmosphericQuantities,
    los: LineOfSightGeometry,
) -> np.ndarray:
    """Resolve ρ(λ) on the chain grid via the protocol.

    Builds view + illumination unit vectors from the LOS geometry
    (RADIANT_Conventions.md §1). ScalarLambertianReflectance and both BRDF
    concretions currently ignore these vectors, so assembly output stays
    bit-identical; future anisotropic BRDFs receive proper inputs without
    a second refactor. Guards against grid mismatch analogous to
    :func:`_extract_sd_values`.
    """
    view = _unit_vector_from_zenith_azimuth(los.theta_view, los.phi_view)
    illum = _unit_vector_from_zenith_azimuth(los.theta_s, los.theta_azimuth)
    vals = rho.reflectance_at(atm.wavelength_um, view, illum)
    if vals.shape != atm.wavelength_um.shape:
        raise ParameterBoundsError(
            what=f"ReflectanceDescriptor.reflectance_at returned shape {vals.shape}",
            why="Assembly requires ρ(λ) sampled on the chain grid.",
            action="Ensure the ReflectanceDescriptor implementation resamples to the input grid.",
            context={"expected": atm.wavelength_um.shape, "actual": vals.shape},
        )
    return np.asarray(vals, dtype=np.float64)
```

Exact `LineOfSightGeometry` field names (`theta_view` / `phi_view` / `theta_s` / `theta_azimuth`) must be confirmed against the current struct at implementation time — the implementation task must read `src/radiant/core/los_geometry.py` and adapt the sketch if field names differ.

For the Lambertian adapter, the return is identically `SpectralData.values` on the matching grid — numerically bit-identical to today's `_extract_sd_values(target.rho, atm)`. This is the proof that Gap H introduces no physics drift.

**Regression surface for H.2**:
- No golden file should change. Run `pytest tests/integration/ -m golden` before and after; bit-compare.
- Run the existing `_assemble_t2` truth-anchor tests (constant ρ → direct-solar math); they must pass unmodified.

**Rule 11 check**:
- `assembly.py` already imports from `radiant.core.descriptors` and `radiant.core.los_geometry`. Adding an import of `radiant.core.reflectance.ReflectanceDescriptor` keeps it inside `radiant.core`. ✅

---

## Step H.3 — (rolled into the H.1 commit — see above)

Test-surface refactor bundles with H.1 per decision #4. The H.1 prompt covers:
- porting `test_inferrer_reflective.py` (~13 assertions) to the protocol call,
- converting `test_accepts_raw_spectral_data` to a negative test,
- adding `test_gap_h_invariant.py` with the parametrised invariant.

The atmosphere-side spy-descriptor test (`test_assemble_t2_calls_reflectance_at`) belongs to H.2 since it depends on H.2's new consumer:
```
def test_assemble_t2_calls_reflectance_at(monkeypatch) -> None:
    """Downstream consumer invariant: _assemble_t2 exercises the protocol,
    not the legacy SpectralData-accessing path."""
    # Install a spy ReflectanceDescriptor that counts reflectance_at calls.
    # Assembly output must equal the pre-Gap-H baseline to 0 ULP, AND the spy
    # must record exactly one call per _assemble_t2 invocation.
    # Spy must also record the view / illum unit vectors it receives and
    # assert they are normalized (||v|| ≈ 1 to 1e-12) — this verifies
    # decision #1 (option b) is implemented correctly.
```

---

## Step H.4 — Documentation close-out

**Category**: B (docs-only; the real regression gate was satisfied by H.1–H.3).

**Files to touch**:
- [`docs/Target_Definition_gaps.md`](Target_Definition_gaps.md):
  - Move Gap H into the Closed section with a `✅ CLOSED (YYYY-MM-DD)` banner mirroring Gap G's format.
  - Drop the P3 Gap H row from the Remaining Work table; if the table empties, replace with `_No open items._`.
  - Append a revision-log entry: "Gap H closed. Boundary converter now wraps scalar ρ into `ScalarLambertianReflectance`; `T2Reflective.rho: ReflectanceDescriptor | None`; `_assemble_t2` consumes the protocol. No physics drift."
- [`docs/RADIANT_Target_Definition_Matrix.md`](RADIANT_Target_Definition_Matrix.md):
  - Append a revision-log entry: "Gap H delivered. `ReflectanceDescriptor` protocol is now an invariant on `T2Reflective.rho`; `AtmosphereStage._assemble_t2` exercises `.reflectance_at(...)`. Phase 6 stub framing closed."
- [`docs/Target_Definition_Implementation_Plan.md`](Target_Definition_Implementation_Plan.md) — Phase 6 docstring promise is now delivered; add a line in the Phase 6 completion note confirming "wrap at assembly" is live.

**Regression gate for H.4**: same six commands. Doc changes can still break `lint-imports`-adjacent checks if a cross-reference path is wrong; run the full gate.

---

## Close-out criteria (how we know Gap H is actually done)

Gap H has no numerical-behavior observable today, so close-out is measured against the three type-level / structural criteria the user requested:

1. **Every path that builds a `T2Reflective` produces a `ReflectanceDescriptor`-typed `rho`.**
   - Verified by `test_every_t2_rho_is_reflectance_descriptor` parametrised over the four user surfaces (`reflectance`, `albedo`, `reflectance_path`, `albedo_path`).
   - Verified structurally by the narrowed field type `rho: ReflectanceDescriptor | None` — `mypy --strict` on `core` catches any regression the moment a caller passes `SpectralData`.

2. **A downstream consumer exists that exercises the protocol end-to-end.**
   - `_assemble_t2` calls `.reflectance_at(λ, view, illum)` (Step H.2).
   - `test_assemble_t2_calls_reflectance_at` installs a spy descriptor and asserts the call count is exactly 1 per invocation, with bit-identical output vs. the pre-Gap-H baseline.

3. **The type union on `T2Reflective.rho` is narrowed.**
   - Before: `SpectralData | ReflectanceDescriptor | None` (three-way).
   - After: `ReflectanceDescriptor | None` (two-way — the adapter case is one concrete path; `LambertianBRDF`/`PhongBRDF` remain legal for future callers).
   - `isinstance(t.rho, ReflectanceDescriptor)` is always true when `t.rho is not None` — enforced by `test_reflectance_descriptor.py`.

---

## Regression surface audit

The following existing tests currently assert `SpectralData`-shaped access on `target.rho` and WILL break naively after H.1. They must be updated in H.3 in the same commit:

| File | Line(s) | Current pattern | Required fix |
|------|---------|-----------------|--------------|
| `src/radiant/source/tests/test_inferrer_reflective.py` | 116–123, 134–143, 188–197, 230–254, 278–294, 372, 446–454, 480–491, 520–557 | `target.rho.values`, `target.rho.wavelength_um` | `target.rho.reflectance_at(WL, zero, zero)` OR `target.rho.reflectance.values` (adapter inner) |
| `src/radiant/core/tests/test_reflectance_descriptor.py` | 185–189 (`test_accepts_raw_spectral_data`) | Expects `T2Reflective(rho=rho_sd)` to succeed | After H.1 this should either be renamed to document the rejection OR kept with an update: the test that documents "raw `SpectralData` is not a valid `rho` for `T2Reflective` directly" |
| `src/radiant/atmosphere/assembly.py` | 667, 730 | `rho = _extract_sd_values(target.rho, atm)` | `rho = _extract_reflectance_on_grid(target.rho, atm, los)` (H.2) |

**Strategy for updating**: commit the test edits in the SAME commit as the H.1 production change (Step H.1 + H.3 bundled per decision #4).

**Golden files** (`tests/golden/*`, `_use_case_coverage.json`): expected zero drift. Any change is a bug in the adapter and blocks the PR.

---

## Out of scope (explicitly deferred)

Gap H is cleanup. The following are NOT part of this plan and must be refused if a reviewer asks for them:

- **No new BRDF concretions**. Measured BRDF, microfacet BRDF, bidirectional-reflectance CSV loaders — not Gap H.
- **No protocol plumbing through `OpticsStage`, `PlatformStage`, `DetectorStage`**. The protocol lives at the source/atmosphere boundary today; widening its reach is a future phase.
- **No new YAML surface**. `source.target.brdf_type` or similar are a future feature; the only user surfaces touched here are the four existing reflective inputs (S4/S5/S6).
- **No change to `LambertianBRDF` / `PhongBRDF`**. Both already satisfy the protocol; do not refactor them.
- **No change to the `ScalarLambertianReflectance` adapter itself**. It is already correct and tested.
- **No import-linter contract additions**. The current contracts already forbid `atmosphere → source` imports, which is sufficient.
- **No physics changes**. Assembly output is bit-identical. Any truth-anchor test must stay at its current expected value.

If during implementation an agent finds a tempting "while I was here" scope extension (e.g., "I could wrap the T3-derived ρ into an adapter too"), STOP and file a follow-up task.

---

## Final acceptance (end of Step H.4)

1. `mypy --strict src/radiant/core src/radiant/api` passes with `T2Reflective.rho: ReflectanceDescriptor | None`.
2. `pytest src/ -v -m "not golden"` green, including the two new Gap H invariant tests.
3. `pytest tests/integration/ -v` green; `_use_case_coverage.json` unchanged.
4. `pytest tests/integration/test_spec_form_matrix.py -v` — all 36 cells still pass; S4/S5/S6 identical outputs.
5. `lint-imports` green; no new cross-stage imports.
6. `ruff check src/` green.
7. Gaps doc shows Gap H closed; Remaining Work table empty (or only lists lower-priority items unrelated to Target Definition).
8. Matrix revision log entry landed.
9. Zero golden drift.

---

## Revision log

- **2026-04-23**: Initial plan. 4 steps (H.1 converter wrap, H.2 assembly consumer, H.3 test surface refactor, H.4 docs). All Category B. Option (c) chosen — wrap at the boundary converter. Close-out criterion: type narrowed + downstream consumer + invariant test.
- **2026-04-23 (decisions)**: User-resolved open questions. (1) View/illum vectors in H.2 → option (b), derive proper unit vectors from `los` using RADIANT convention. (2) `test_accepts_raw_spectral_data` → convert to negative test. (3) T5/T6/T7 `SpectralData` fields → explicitly out of scope, future gap filing if needed. (4) Commit granularity → H.1 + H.3 bundled (one commit); H.2 own commit; H.4 own commit.
