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
