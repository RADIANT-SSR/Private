# Assurance Audit — July 2026

Status: Complete (closed 2026-07-24 — see findings.md for the disposition register and verification)
Triggered by: project owner (2026-07-22, interactive session)
Auditor: Claude (Fable 5), multi-agent
Scope ratified: owner selected three tracks from a proposed menu; no `src/` modifications
are in scope — findings only, dispositioned per Rule 28 (CU'd / Planned / Declined).

## Charter

Verify that what is already built is correct. No backlog work, no new capabilities.

### Track A — Adversarial physics re-derivation
Independent agents re-derive the governing equations of the physics chain from
first principles and literature, **without reading the implementation**. A second
wave of agents then diffs each derivation against the code. Catches shared-mistake
bugs that truth-anchor tests cannot (anchors were chosen by the same process that
wrote the code).

Clusters:
- A1: Radiometry & sources — Planck, band radiance, brightness/radiance temperature,
  reflected solar, BRDF, fill fraction, point-source intensity.
- A2: Spatial — diffraction PSF, pupil-autocorrelation MTF, Zernike OPD, Strehl,
  detector/jitter/smear/turbulence MTF terms, EE_box.
- A3: Noise & sensitivity — shot/dark/read/fixed-pattern noise, TDI/co-add scaling,
  SNR, NEDT, NEI, D*, dynamic range, BLIP.
- A4: Geometry & sampling — spherical-Earth slant range/incidence, orbital velocity,
  GSD, ground range, swath, smear kinematics, Nyquist/Q.

### Track B — Test-quality audit
For the physics-stage test suites: which tests would still pass against a gutted
implementation; which `pytest.approx` tolerances are too loose to catch a sign,
factor-of-2, or unit error; which contracts have no test at all.

### Track C — Doc-vs-code drift sweep
For the most normative architecture docs, verify each enforceable claim is actually
enforced by a test, type check, or contract. Docs in scope: Conventions,
Signal_Chain_Architecture, Master_Architecture, Optics, Spatial_Complete, Metrics,
Parameter_System, Testing_Validation.

## Outputs
- `findings.md` — every finding with severity and disposition (CU'd / Planned / Declined)
- Track working notes (`track_a_*.md`, `track_b_*.md`, `track_c_*.md`)
- CU entries appended to `docs/tracking/Cleanup_Backlog.md` for confirmed defects

## Immutability
Per Rule 28 / OPERATING_MODEL §2, this folder is immutable once the audit closes.
