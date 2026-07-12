# Correction: MODTRAN Re-audit (supersedes the PROVISIONAL markers in Findings.md)

**Status:** Complete (2026-07-11)
**Context:** `Findings.md` F-19 and related items were marked 🔶 PROVISIONAL because the
atmosphere/MODTRAN area was under concurrent rework during the audit sweep. That rework
landed the same day (`4f624dc`, `dc348f7`, `2e707c7`, `ccad583`, `d56fd9c`); this correction
records the re-audit (CU-086), each claim grep-verified against `d56fd9c`.

## Resolved by the rework

- **Two-leg transmittance collapse (file flavor)** — resolved by
  `atmosphere.modtran.tape7_sun_path` (dc348f7, CU-011 file flavor); the collapse warning
  now fires only when no sun-leg file is supplied. The tape7 import is now a first-class
  schema parameter (`tape7_path`, 4f624dc), and the new sun-leg path deliberately does not
  clip out-of-range values (loud failure per Rule 17, citing CU-071).
- **`visibility_km`** — now wired through `loaders._build_modtran` from
  `atmosphere.visibility_km`.
- **CU-065 (Card 3 ANGLE)** — narrowed by the rework itself: deck-side at-H1 conversion
  implemented (2e707c7); residual manual-verification still gated on MODTRAN access.

## Surviving the rework (now firm, filed individually)

- **Downwelling thermal hard-zeroed** (`atm_emission_down` = zeros; `E_sky_thermal` = 0)
  and **`E_sky_scattered` = 0** → **Gap 81** (Tier 2: `tape7_down_path` mirroring the
  sun-leg pattern).
- **Parsed tape7 columns dropped** (`ground_reflected` cached but `_build_state_from_arrays`
  takes no such argument) + **remaining ModtranConfig knobs unwired** (`itype`, `iemsct`,
  `v1_cm1`, `v2_cm1`, `extra_cards`) → **CU-087** (deferred with the CU-011 binary-flavor
  gate).
- **No cloud/rain/fog capability** in any model → **Gap 82**.
- **LWIR aerosol Ångström clamp unimplemented** (doc's own stated plan) → **CU-088**.
- **CU-071 silent clamp** — unchanged by the rework; stays open as filed.
- **Uplooking geometry rejection** — Declined (owner-ratified 2026-07-11; out of current
  mission scope).

`Pre_GUI_Hardening_Plan.md` updated: Gap 81 and CU-088 join Phase 2; Gap 82 and CU-087
remain outside the plan (GUI-phase / MODTRAN-access-gated respectively).
