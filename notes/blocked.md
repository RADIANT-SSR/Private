# Overnight Blockers Log

Started: 2026-04-07 evening session
Scope: Tasks 2B.2, 2B.3, 2B.4
Rule: If a task blocks on a contradiction with the architecture docs
that I cannot resolve safely, log it here with full context and move
on. Jason will review in the morning.

## How to read an entry

Each entry has:
- **Task / file** — where the issue arose
- **What I hit** — the contradiction or missing information
- **What I did** — skipped / partial / worked around
- **What I need from you** — the decision you need to make
- **Context** — links to the relevant docs or code

---

## 2026-04-07 — 2B.2 SimpleAtmosphere `L_path` (single-scatter)

- **Task / file**: Task 2B.2; [src/radiant/atmosphere/simple.py](src/radiant/atmosphere/simple.py)
- **What I hit**: RADIANT_Atmosphere.md §3.1 specifies the simple-model
  upwelling path radiance as
  `L_path(λ) = L_sun(λ) · cos(θ_sun) · ω₀(λ) · P(θ_scatter) · (1 − τ_atm(λ))`.
  This needs a top-of-atmosphere solar spectrum `L_sun(λ)`. The
  ReflectedSolarSource (which would own that spectrum) is not
  implemented yet, and even if it were, CLAUDE.md Rule 11 forbids
  `radiant.atmosphere` from importing `radiant.source`.
- **What I did**: Set `L_path(λ) ≡ 0` in `SimpleAtmosphere.build_state`.
  The `AtmosphericState` invariant ("always populated, prefer numerical
  zero over None") is satisfied. The 2B.2 numerical truth anchors only
  validate transmittance, so the validation requirements are still met.
  `derivation_chain` records the stub. `SpectralData.source` reads
  `"SimpleAtmosphere stub (pending solar source)"`.
- **What I need from you**: Decide where the canonical TOA solar
  spectrum lives. Two options I can see:
  1. Add a `solar.py` to `radiant.core` with a hard-coded 5778 K
     blackbody scaled to 1361 W/m² TOA (one-time, ~30 lines). Then
     `SimpleAtmosphere` can call it directly.
  2. Defer `L_path` until the `ReflectedSolarSource` task in Phase 2C
     and pass the solar spectrum into `SimpleAtmosphere.build_state`
     as an optional argument (would change the `Atmosphere` protocol).
- **Context**:
  - [docs/RADIANT_Atmosphere.md](docs/RADIANT_Atmosphere.md) §3.1 for the
    formula.
  - [docs/RADIANT_Source_Target_System.md](docs/RADIANT_Source_Target_System.md)
    for ReflectedSolarSource design.
  - [CLAUDE.md](CLAUDE.md) Rule 11 for the cross-stage import ban.

## 2026-04-07 — 2B.2 SimpleAtmosphere `L_atm_down` (graybody)

- **Task / file**: Task 2B.2; [src/radiant/atmosphere/simple.py](src/radiant/atmosphere/simple.py)
- **What I hit**: RADIANT_Atmosphere.md §3.1 specifies
  `L_atm_down(λ) = (1 − τ_atm(λ)) · B(λ, T_atm_eff)`. This needs the
  Planck function. Today `planck_spectral_radiance` lives in
  [src/radiant/source/blackbody.py](src/radiant/source/blackbody.py),
  which `radiant.atmosphere` cannot import (CLAUDE.md Rule 11 +
  `import-linter` "no cross-stage physics imports" contract).
- **What I did**: Set `L_atm_down(λ) ≡ 0` in `SimpleAtmosphere.build_state`.
  Same justification as the `L_path` stub above — invariant satisfied,
  derivation_chain documents the deferral.
- **What I need from you**: Decide whether to move
  `planck_spectral_radiance` from `radiant.source.blackbody` into
  `radiant.core` (e.g., `radiant.core.blackbody`). Planck is a pure
  physical formula with no chain dependencies and no sensor knowledge,
  so it sits cleanly in `core/` per the layout rules. If you agree
  I can do it as a small refactor at the start of 2B.5 — it would
  unblock `L_atm_down` here AND the thermal optics emission in 2B.3,
  and `radiant.source.emitted` would re-export from core.
- **Context**:
  - [src/radiant/source/blackbody.py](src/radiant/source/blackbody.py)
  - [pyproject.toml](pyproject.toml) — `[tool.importlinter]` "physics
    stages import only core" and "no cross-stage physics imports"
    contracts.

## 2026-04-08 — 2B.4 `DetectorStage` / `Stage` protocol missing

- **Task / file**: Task 2B.4; the prompt calls for
  `src/radiant/detector/stage.py` implementing "the Stage protocol".
- **What I hit**: The Stage protocol, `ChainState`, `ChainRunner`, and
  `RadiometricFrame` containers described in
  [docs/RADIANT_Signal_Chain_Architecture.md](docs/RADIANT_Signal_Chain_Architecture.md)
  are not yet implemented in `radiant.core`. `src/radiant/core/` has
  `constants.py`, `geometry.py`, `parameters.py`, `spectral.py`, and
  `units.py` — no `chain.py`. Without that, a `DetectorStage` has no
  protocol to implement and nothing to hand its outputs to.
- **What I did**: Skipped `detector/stage.py` for this overnight cut.
  Shipped the physics primitives (`qe.py`, `pixel.py`, `shot_noise.py`,
  `dark_current.py`, `readout/read_noise.py`, `readout/adc.py`) as
  standalone, fully tested classes that the future `DetectorStage`
  will assemble. All cross-stage coupling (ChainState wiring, regime
  finalisation, mtf_terms registration) is deferred until the core
  chain scaffolding exists.
- **What I need from you**: Confirm that the intended order is
  (1) ship `radiant.core.chain` in a separate Phase 2A task, then
  (2) wire `SourceStage`, `AtmosphereStage`, `OpticsStage`,
  `DetectorStage`, `ReadoutStage` on top of it in Phase 2C. The
  2B.1–2B.4 work so far is all primitives with no stage wrapper, which
  I believe is the right incremental path — I want a green light before
  writing half a dozen stage wrappers on a chain that doesn't exist.
- **Context**:
  - [docs/RADIANT_Signal_Chain_Architecture.md](docs/RADIANT_Signal_Chain_Architecture.md)
    §2 for the Stage protocol signature.
  - [src/radiant/core/](src/radiant/core/) — current core surface.

## 2026-04-08 — 2B.4 QE library tables not yet shipped

- **Task / file**: Task 2B.4; [src/radiant/detector/qe.py](src/radiant/detector/qe.py)
- **What I hit**: RADIANT_Detector_Complete.md §3.1 specifies a
  built-in QE library under `data/detectors/` (Si CCD, Si CMOS, InGaAs,
  HgCdTe MWIR/LWIR, InSb, T2SL), accessed through
  `detector.qe_input = "library"`. The directory does not exist yet.
- **What I did**: Implemented `CUSTOM` (parametric Fermi edge) and
  `FILE` (wrap an existing `SpectralData`) modes in `qe.py`. The
  `LIBRARY` mode and its `qe_cutoff_um` warping function are deferred.
- **What I need from you**: Either point me at the source for the
  canonical curves (published datasheets? existing hand-fit code in
  another repo?) or authorise me to generate Fermi-edge fits per
  material with the standard cutoff / peak values from the table in
  §3.1 — the latter would be a half-day task and would unblock the
  LIBRARY path for trade studies.
- **Context**:
  - [docs/RADIANT_Detector_Complete.md](docs/RADIANT_Detector_Complete.md) §3.1
