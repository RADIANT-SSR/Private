# Scenario 4.3 Gaps: Camouflage Effectiveness Analysis

Executed 2026-07-08 (Phase T3). Registry mirror: `docs/tracking/gaps.md`
(ASTER importer closed by f50253a; new Gap 47 for spectral target
emissivity).

## Summary
Hot vehicle (380 K, oxidized steel ε≈0.80) vs three nets (draped, 310 K)
against 305 K scrub (ε 0.96), LWIR FLIR 8–12 µm at 3 km. Camouflage is
radiance MATCHING: net C (ε≈0.93, near the 0.96 scrub) cuts the signature
95.5% (SCNR 1285.9→57.5); the intuitive low-ε net A over-corrects to a cold
signature (72.4% reduction, residual −512k e⁻). Detection range edge-
limited for all (sensitive FLIR at 3 km) — camo reduces signature, not
detectability.

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-08-02, pre-CU-321). Dominant mover: **CU-321** — the down-looking path
emission is now emitted at a height-resolved `T_eff(λ)`, so the scrub
background's shot noise falls and every SCNR rises ~1.2 %. The contrast
electrons are bit-identical (common-mode radiance cancels in a difference) and
the 95.5 % / 72.4 % reduction figures are unchanged.*

## Gap Closure Status (catalog "Gaps revealed" list)

| # | Catalog gap | Status | Evidence |
|---|-------------|--------|----------|
| 1 | No ΔL (spectral contrast) output | Not filed — hand-Planck scene analysis | ΔL(λ) = ε_t·B(T_t) − ε_bg·B(T_bg) computed and plotted script-side; it is scene analysis, not a chain output |
| 2 | No optimal band finder | Not filed — sub-band sweep | Two half-band runs per option rank the detection band; a "find best sub-band" helper would compose `Sensor` runs, no new physics |
| 3 | No detection range reduction analysis | Not filed — bisection, shared with 4.1 | Range-vs-zenith bisection at SCNR ≥ 5 (spherical Earth); edge-limited here |
| 4 | No sparse spectral data interpolation | Documented assumption, not a framework gap | Net C's 3 points are linearly interpolated; the ASSUMPTION is stated in output and walkthrough — a framework helper would just wrap `np.interp` |
| 5 | Limited spectral emissivity input (scalar only) | Open — **registry Gap 47** | The source surface takes a scalar ε; spectral ε(λ) reaches the chain only by composing L_t = ε(λ)·B(λ,T) and injecting via the S8 `user_radiance_path` |

## New Gap Found by This Execution

### Registry Gap 47 — spectral target emissivity has no chain input
`source.target.emissivity` is a scalar; there is no `emissivity_path` for a
tabulated ε(λ) the way `reflectance_path`/`albedo_path` exist for
reflective targets. Spectral thermal-emission targets must be pre-composed
to radiance and fed through S8 (`user_radiance_path` → `T6TabulatedAtSource`,
"no physical model applied"), which means the USER supplies the Planck
integral and the assumed surface temperature — the chain does not apply the
atmosphere-coupled thermal emission model to a spectral-ε target. Worked
around cleanly here; a first-class `source.target.emissivity_path` (routing
to a spectral T1Thermal descriptor) would let the chain own the physics.

## Sub-Pixel / S8 Composition Note (design finding)

The first execution used the sub-pixel path (as scenarios 4.1/1.3 do) and
got an INVERTED electron contrast: the S8 tabulated-source radiance is
correct (target 88 vs background 40 W/m²/sr band-integrated), but composed
with the in-pixel background fraction the target pixel read *dimmer* in
electrons than a pure-background pixel. A draped net is genuinely
pixel-filling, so the scenario uses the extended regime with an explicit
differential against a scrub pixel (the resolved-target construction) — both
cleaner and physically right. The sub-pixel/S8 composition itself is worth a
closer look but is orthogonal to this scenario; not filed pending a
minimal reproducer.

## Non-Gap Observations

- **Camouflage = matching, not minimizing.** The lowest-ε net (A) is NOT
  the best camo against a warm background — it over-corrects into a cold
  signature. Net C (high ε near the background value) wins. A `|contrast|`
  detector sees cold and hot equally.
- **Per-band emissivity matters** (net B's 8–10 vs 10–12 split): a scalar ε
  would erase the spectral-shaping trade the whole scenario is about.
- **Detection range is the wrong metric at 3 km** — every option is
  detectable across the swath. Signature reduction (SCNR) is the
  operationally meaningful figure; the walkthrough leads with it.
