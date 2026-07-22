# Assurance Audit Remediation Plan

Status: Draft (awaiting owner ratification of dispositions)
Source audit: `docs/reports/assurance_audit_2026-07/` (chartered 2026-07-22)
Author: Claude (Fable 5), 2026-07-22

## What the audit found, in one paragraph

The physics itself held up well everywhere the audit could see: every named test anchor the
Track B agents checked against literature was genuine, and the Track C agents confirmed the
load-bearing code contracts (ChainState immutability, frame registry, regime thresholds,
provenance record, import rules) are real and test-enforced. The debt is concentrated in three
places: (1) a handful of physics quantities whose tests cannot catch a wrong constant or unit
slip (GIQE-5 coefficients, band-integrated responsivity, `integrate_planck_over_band`, EE_box,
NEP↔electrons); (2) invariants that are true today but have no tripwire (dual-path consistency
is warn-only, no lint for unit conversions/constants/approx-tolerances in physics modules);
(3) doc drift — 14 drifted claims in the physics docs, ~12 in the core docs, and one doc
(`RADIANT_Testing_Validation.md` §5–§9) describing a golden/provenance/CI toolchain that
largely does not exist. One item is unfinished: the Track A code-vs-derivation comparison wave
was killed by the session usage limit; R1 below completes it in a way that is also the durable
fix.

## Remediation waves (each item = one PR-sized task, per Agent Task Discipline)

### R1 — Anchor-test hardening (Category C tasks, HIGHEST VALUE)

Convert the Track A blind-derivation anchors (already committed in
`track_a1..a4_*_derivation.md`, computed independently of the codebase) into Level-0 anchor
tests. **Running these tests IS the unfinished comparison wave** — any formula mismatch
surfaces as a test failure — and it permanently fixes the self-referential-anchor findings.

- R1.1 (S): Planck-family anchors — pin `planck_spectral_radiance(10, 300) = 9.92403333`,
  `(4, 300) = 0.721976423` W/m²/sr/µm, dL/dT(10, 300) = 0.159971567 W/m²/sr/µm/K,
  `integrate_planck_over_band(8–12, 300 K) = 38.5004239 W/m²/sr` (rel=1e-3 for the band
  integral, rel=1e-6 monochromatic). Closes findings B2-3, B1-4 (band_planck_radiance rides
  the same anchor).
- R1.2 (S): Responsivity anchors — closed-form band-integrated R for flat τ·QE
  (R_band = A·Ω·τ·QE·(λ_max²−λ_min²)/(2hc)) and a real electrons→radiance round-trip
  assertion. Closes B2-1, B2-2 (both High).
- R1.3 (S): GIQE-5 — pin all six coefficients to literature values and one hand-computed
  NIIRS with numeric literals. Closes B1-1 (High).
- R1.4 (S): NEP↔electrons hand anchor (σ=100 e-, η=0.7, λ=10 µm, t=0.01 s →
  NEP ≈ 2.84e-16 W). Closes B1-2.
- R1.5 (M): EE_box quantitative anchor — unaberrated Airy at Q=2 ensquared in a 1-pixel box
  = 0.177327 (Track A2 §8), tolerance sized to the pupil-grid discretization floor.
  Closes B1-3.
- R1.6 (M): Spatial/MTF anchors — diffraction MTF(0.5ν_c) = 0.391002, detector MTF at
  Nyquist = 2/π, jitter σ=0.25 px at Nyquist = 0.734603, smear d=0.5 px = 0.900316,
  Maréchal S(λ/14) = 0.817569. Most may already be covered (Track B found the spatial suites
  strong) — add only the missing ones; this doubles as the A2 comparison.
- R1.7 (M): Geometry anchors — viewing triangle (h=500 km, η=30° → Λ=2.628951°,
  R_s=585,101.608 m eq.-radius), v/v_g/period, off-nadir GSD along=2.925508 / cross=3.473732 m
  (the cos θ_i-vs-cos η discriminator), solar zenith 17.425559°. **Match the code's Earth
  radius before asserting** (mean-radius variants in track_a4). This is the A4 comparison.
- R1.8 (M): Noise anchors — RSS 136.381817 e- case, ADC 14-bit/100 ke- → 1.76193 e-,
  D* = 6.324555e12 cm·√Hz/W case, TDI √32 gain; verify the derivation's checklist items
  (PRNU linear in signal, contrast-SNR denominator, Δf = 1/(2t_int), étendue variant declared).
  This is the A3 comparison.
- R1.9 (S): Small test fixes — tight ε·B assert (B2-4), revisit-interval anchor (B2-5),
  emissivity-resample values (B2-6), delete tautology (B1-7), `>=`→`>` (B1-8), solar-geometry
  anchor comment (B2-8), Rule-9 positive-path stage test (B1-5).
- R1.10 (S): Sweep the 29 `pytest.approx` calls lacking explicit tolerances (B1-6, B2-7).

Any R1 test that FAILS on first run is a Track A physics mismatch → stop, file a CU with the
failure evidence, and treat per Rule 15/17 severity before "fixing" the test.

### R2 — Enforcement tripwires (Category A/D)

- R2.1 (M): Dual-path consistency CI gate — assert `passed_x/passed_y` across the 34
  GUI-scenario baselines (extends the CU-179 gate). Kills the #1 unenforced risk (warn-only
  invariant).
- R2.2 (S): Physics-module lint — CI grep/ruff rule for `pi / 180`, `* 1e4`-style conversions
  and hardcoded constants (6.62e-34, 1.38e-23, 3e8…) inside the nine physics packages.
- R2.3 (S): `pytest.approx`-without-tolerance lint (simple AST or grep check in CI).
- R2.4 (M, owner decision): architecture-doc parameter-table freshness — either extend
  `gen_param_reference.py --check` to the architecture-doc tables, or delete the duplicated
  tables and point at the generated reference (recommended: delete — one canonical version,
  Rule 27).

### R3 — Doc repairs (Category A, Rule 20 lock-step; one PR per doc)

- R3.1 (S): Signal_Chain — fix turbulence-MTF stage attribution (D6, highest-severity doc fix:
  it is the map implementers read first), platform/readout term ownership (D7), `"electrons"`
  frame examples (D8), §8 phantom frames (D9).
- R3.2 (L): Testing_Validation §5–§9 rewrite against the real toolchain
  (`scripts/update_golden.py`, real golden JSON shape, real C13 provenance record, real ci.yml;
  delete or de-aspirationalize freeze-golden/reproduce/config-hash/Hypothesis/coverage-matrix
  claims — or banner them DESIGN-TARGET). Covers D10–D18 + the two minor snippet errors.
- R3.3 (S): Master — C11 wording (collect-all is CLI-only today), C12 geometry exception
  naming, §7.6 import table (+data/, gui/ rows), archive link (D3–D5).
- R3.4 (S): Conventions — §4 frame-rate contract (see R4.1) and §5 angle-naming claim
  reconciled to reality (D1, D2).
- R3.5 (S): Spatial_Complete — CU-003 stale paragraphs (S1, S2), RER geometric-mean wording
  (S3), "unconditional" → Gap-96-gated wording in §0/§1.4/§5/§11 (S4), WFE default 0.633 (S5),
  h_sensor alias row (S6), 11-vs-12 count note.
- R3.6 (S): Optics — transmission_scalar default row (pending R4.2), remove `f_number` from
  stage-output banner (O2), fix §9 Ω-names/type-system claim to describe the real structural
  separation (O3).
- R3.7 (S): Metrics — trim EE variants to ee_1x1/ee_3x3 (M1), `detector.clutter_sigma` (M2).
- R3.8 (S): Parameter_System — spectral-grid paragraph rewritten to the real
  filter_min/max + wl_points mechanism (P1), delete stale CU-090 paragraph (P2), banner or
  rewrite the unimplemented explain/sweep/sensitivity examples (P3), cds_enabled literal,
  required_unless prose, alias-list completeness.

### R4 — Owner decisions needed (blocking the corresponding R3 items)

- R4.1: Conventions §4 frame-rate/duty-cycle contract — implement it (new parameters +
  derivation + warning) or delete the claim? (Recommend: delete until a scan-timing task needs
  it; it is currently pure fiction.)
- R4.2: `optics.transmission_scalar` — keep silent default 0.7 (document it) or make it
  required-unless-elements (doc currently promises None)? Radiometric results change for
  configs that omitted it if you choose required.
- R4.3: Ratify Declined-vs-CU'd for the low-severity Track B style items if not worth PRs.
- R4.4: Re-run or drop the four wave-2 comparison agents (killed by the session usage limit,
  resets 11:40 MT). Recommendation: **drop them** — R1 subsumes the comparison at near-zero
  marginal cost and leaves a permanent regression net instead of a one-shot report.

## Disposition register (Rule 28)

| Finding(s) | Disposition |
|---|---|
| B1-1..B1-5, B1-6..B1-9, B2-1..B2-8 | Planned → R1 (CU entries to be filed per item when this plan is ratified) |
| Track C drifted: D1–D18, O1–O3, S1–S6, M1–M2, P1–P3 | Planned → R3 (+R4 decisions) |
| Unenforced risks 1–3 (consistency gate, conversion lint, approx lint) | Planned → R2 |
| Unenforced: pupil_npix/psf_oversample literals; Ω typing; stage-output key schema; convolution-order test; stage purity; coverage thresholds | Proposed **Declined** (documented residual risk — revisit if a regression ever implicates them) |
| Track A wave-2 comparison incompletion | Planned → R1 (subsumed) / R4.4 |

Sequencing: R1 first (it is both the highest-value hardening and the missing audit wave), R2
second, R3 in any order after (R3.1 early — it misleads implementers today). Waves are
independent PR-sized tasks suitable for the per-CU overnight workflow.

On completion: move this plan to `docs/archive/` (Rule 24), close the audit folder as immutable
(Rule 28), file/close CUs per Rules 21–22.
