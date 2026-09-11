> **HISTORICAL — archived 2026-09-11 (completed by the coding agent; W1–W5 all landed 2026-09-09 on branch `gap127/element-only-emission`, merged as `e0cd1d13`; Gap 127 closed in `docs/tracking/gaps.md` 2026-09-11).** Declared-emissivity path deleted end-to-end (`optics.scalar_emissivity`, `make_lumped_element(emissivity=…)`, `OpticalElement.declared_emissivity` and the Rule-5 carve-out); cavity per-surface T + R = 1 enforced with one-of R/T derivation in the factory and YAML reader; both shipped templates corrected; `tests/integration/test_element_only_nearfield.py` plus the weak-absorption ε_eff → α·t anchor; RADIANT_Optics.md §5/§6/§7, parameter reference, and CHANGELOG in lock-step. The §6 out-of-scope items became CU-350 (closed) and CU-352 (closed); CU-351 remains open, owner-gated. Successor model: `docs/archive/Nearfield_Etendue_Model.md` (Gap 128).

# Optics Emission Model Rules — Element-Only Near-Field (Gap 127)

**Status:** Complete — owner ratified the four model rules in conversation, 2026-09-09; W1–W5 delivered 2026-09-09.

**Date:** 2026-09-09
**Category:** C (physics model change; D-style regression section required because shipped
templates change results).
**Tracking:** Gap 127 (`docs/tracking/gaps.md`).

**Read first:**
`docs/architecture/RADIANT_Master_Architecture.md`,
`docs/architecture/RADIANT_Optics.md` (§5 transmission modes, §6 elements, §7 nearfield),
`docs/architecture/RADIANT_Parameter_System.md`.

---

## 1. Objective

Remove the conceptually unfounded declared-emissivity path from the optics train and make
near-field (warm-optics) emission derivable **only from defined elements**. Kirchhoff
equates emissivity to *absorptance*; the removed path let a scalar lump claim an
emissivity with no absorbing surface behind it, inviting the ε = 1 − τ fallacy the shipped
SDA template committed (`scalar_emissivity: 0.4` labelled "Kirchhoff-consistent with
T=0.6").

## 2. Owner-Ratified Rules (2026-09-09)

1. **Scalar throughput ⇒ no near-field.** Mode 1 (scalar τ) computes no near-field
   emission, ever. `optics.scalar_emissivity` is removed. Mode 2 (spectral-file τ(λ)) is
   the same rule — a transmission curve is still not a surface.
2. **Mirrors:** ε = 1 − R per element (already shipped; unchanged).
3. **Simple refractive:** %T only — no absorption, no near-field, ε = 0 (already shipped;
   unchanged).
4. **Complex refractive:** per-surface %R / %T with Kirchhoff held at each surface and
   **no coating absorption** — per surface, T + R = 1 (specify one, derive the other;
   specifying both requires them to sum to 1 within tolerance). Bulk absorption α,
   thickness, and temperature then give the emissivity via the existing cavity
   expression (ε ≈ α·t in the weak-absorption limit — the sanity anchor, not the
   implementation).

**Scope boundary:** warm-*enclosure* emission (the uncooled-cavity limit, where
ε_eff = 1 − τ at uniform temperature is genuinely correct) is not an optical-train
property. Its home is the stray/thermal path (`optics.stray_includes_thermal`); this plan
only documents that boundary, it does not extend the stray model.

## 3. Current-State Map

| Rule | Today | Change |
|---|---|---|
| 1 | `_resolve_scalar` synthesizes a LUMPED element carrying `declared_emissivity` from `optics.scalar_emissivity` (default 0); `OpticalElement` has a LUMPED-only declared-ε carve-out ("the one sanctioned exception" to Rule 5) | Delete the parameter, the factory argument, the field, and the carve-out |
| 2 | `make_reflective_element`: ε = 1 − R | None |
| 3 | `make_refractive_element`: ε = 0 | None |
| 4 | `CavityModel` accepts per-surface T + R ≤ 1, but ε_eff counts only bulk absorption — coating absorption is silently non-emitting (internal inconsistency) | Require per-surface T + R = 1 (tol `_CAVITY_KIRCHHOFF_TOL`); factory + YAML config accept one of R/T per surface and derive the other |

## 4. Work Items

**W1 — Delete the declared-ε path (Rule 1).**
- `optics/_schema.py`: remove `SCALAR_EMISSIVITY`. Old YAMLs then fail loudly with
  `UnknownParameterError` naming the parameter (documented in CHANGELOG).
- `optics/transmission_modes.py`: drop `scalar_emissivity` from `resolve_transmission`
  and `_resolve_scalar`.
- `optics/element_factories.py`: drop the `emissivity` argument from
  `make_lumped_element`.
- `optics/element.py`: remove `declared_emissivity` field, its validation, and its
  branch in `emissivity`; Rule 5 becomes exception-free.
- `optics/stage.py`: remove the `scalar_emissivity` read, the ignored-in-non-scalar-mode
  warning, and rework the CU-265 warning to: `optics.optics_temperature_K` explicitly set
  while no defined element can emit (max ε = 0 over the resolved element list) ⇒ warn
  that the temperature contributes nothing and elements are required for emission.

**W2 — Per-surface no-coating-absorption constraint (Rule 4).**
- `optics/cavity_model.py`: tighten per-surface check from T + R ≤ 1 to T + R = 1
  (both directions, tolerance `_CAVITY_KIRCHHOFF_TOL`), with an actionable error naming
  the surface and the deficit.
- `optics/element_factories.py::make_refractive_cavity_element` and the element-config
  YAML reader (`io/element_config.py`): accept exactly one of R/T per surface and derive
  the other as 1 − x; both accepted only when they sum to 1 within tolerance.

**W3 — Templates.**
- `sda_space_to_space.yaml`: remove `scalar_emissivity` and the "Kirchhoff-consistent"
  comment; remove the now-inert `optics_temperature_K`. Header comment gains one line
  noting near-field requires defined elements (Gap 127).
- `ground_to_air_mwir_detection.yaml`: remove `scalar_emissivity`,
  `optics_temperature_K`, `nearfield_fraction` (all inert in scalar mode).

**W4 — Tests.**
- Rewrite `tests/integration/test_scalar_emissivity_nearfield.py` → scalar and
  spectral-file modes yield `nearfield_e == 0` exactly; element modes still emit.
- Update `optics/tests/` for the removed argument/field and the tightened cavity
  constraint (one-of derivation, both-given =1 acceptance, both-given <1 rejection).
- Level-0 anchor for Rule 4: thin-slab cavity ε_eff → α·t in the weak-absorption limit.

**W5 — Lock-step docs + CHANGELOG (Rules 20/29).**
- `RADIANT_Optics.md` §5 (mode 1/2 emit nothing), §6.1 (factories), §7 (near-field is
  element-only; enclosure emission belongs to stray/thermal — the scope boundary above).
- `RADIANT_Parameter_System.md` + `python scripts/gen_param_reference.py` regeneration.
- `CHANGELOG.md` under `[Unreleased]`: **Results-affecting** — scalar/spectral-file modes
  no longer emit near-field (SDA template at 6–11 µm: near-field 6.0×10⁷ e⁻ → 0);
  **Removed** — `optics.scalar_emissivity`.

## 5. Validation (Category C)

- **Truth anchors:** (1) mirror train ε = 1 − R per element vs. hand-summed
  Σ ε_i·τ_down,i; (2) cavity ε_eff ≈ α·t weak-absorption limit vs. analytic Beer–Lambert
  single pass; (3) scalar-mode near-field ≡ 0 vs. the removed-path 180 K SDA
  reproduction (6.0×10⁷ e⁻ → 0, physics: no absorbing surface is modelled).
- **Regression:** full battery. Shipped templates are loadable+evaluable-pinned, not
  value-pinned (Gap 126), so no golden update is expected; any golden that does move
  fails the merge and is investigated, not bumped.

## 6. Out of Scope (tracked separately)

- Well-fill/saturation omitting `nearfield_e`/`stray_e` (`readout/stage.py:467-470`) —
  from the same 2026-09-09 deployment review; still real in element modes. Files as its
  own CU when scheduled.
- Remaining 2026-09-09 Windows-deployment items (MTF overlay total curve, MTF x-axis
  limit, MTF table pixel-term version check, GUI exposure questions). The earlier idea of
  exposing `scalar_emissivity` in the GUI optics form is **mooted** by W1.
- Stray/thermal enclosure model extension (the warm-cavity limit's proper home).
