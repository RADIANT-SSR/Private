# Scenario 6.4 — Gaps and Friction

## RESOLVED during this scenario

### ROC / detection-probability generator (was the primary gap)
The catalog flagged "no ROC curve generator." **Built as
`radiant.performance.roc`** (committed c1ad64e): `roc_curve`,
`detection_probability` (`P_d = Q(Q⁻¹(P_fa) − SNR)`), and `roc_auc`
(`Φ(SNR/√2)`) under the equal-variance Gaussian signal-detection model.
11 Level-0 tests with analytic truth anchors.

### Per-pixel signal/noise + simulated noisy image
The catalog's "no per-pixel signal/noise simulation" and "no simulated
image output with realistic noise" are met at the scenario level: the chain
supplies `S_bg`, `S_tgt`, and σ; the script assembles a 1-D strip and adds
Poisson shot + Gaussian read noise (fixed seed). This is scenario scripting
on top of existing chain outputs, **not** a new framework capability — see
below.

## Gaps NOT closed (framework-level, filed for later)

### Multi-target spatial scene model — DEFERRED (Large)
The catalog lists "no multi-target scene model" and "no spatial scene
layout." RADIANT remains a **single-pixel / single-target radiometry
engine**; this scenario fakes a scene by running the chain per target and
laying pixels out in the script. A true 2-D scene renderer (target masks,
sub-pixel placement, PSF-convolved scene, per-pixel mixed radiance) is a
large capability that belongs in a dedicated `scene/` module, not a
scenario script. **Recorded in `docs/tracking/gaps.md`** as the multi-target
scene gap (already tracked, priority "Large"); this scenario is a
stopgap consumer, not a closure.

### Sub-pixel patch via the chain — friction, not a gap
The chain's point-source/sub-pixel path requires a projected area + range
from `SourceStage`; a uniform-radiance patch has no discrete "source
object," so the extended run + analytic fill-fraction dilution is the
correct route. No new gap: this is the intended use of the extended regime
plus geometry, not a missing feature.

## Friction / lessons

- **The nominal scene is "too easy."** All five targets are hot and
  resolved (or barely diluted), so every contrast SNR is 49–476 and every
  P_d ≈ 1 — a ROC of just those five is uninformative. This is physically
  correct, not a bug. The scenario reports it honestly and adds a
  **detection-range sweep** (analytic, range-independent extended signal) to
  reach the informative band (P_d 0.9 at ≈ 533 km, 50/50 at ≈ 687 km).
- **AUC ≠ operating-point P_d.** At 800 km AUC is still 0.985 but P_d at
  P_fa = 1e-4 is 0.26 — separation is good, but a strict false-alarm
  budget costs detections. The scenario surfaces both so the distinction
  isn't lost.
- **Shot-noise-limited background** (σ = 738 e- on 5.34×10⁵ e-): read noise
  (100 e-) and dark (500 e-) are negligible here; detectability is set by
  photon statistics, so the only lever on the floor is collecting-area ×
  integration-time (i.e. range dilution).

*Figures refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-09). Mover: CU-224's down-looking `(1−τ)·B(λ,T_eff)` path-radiance
term raised the background pixel and hence the shot-noise floor; see the
walkthrough's results tables for the sign discussion.*

## Catalog status

Priority 33 (Scenario 6.4) — **DONE** as a scenario deliverable: the ROC
generator gap is closed in the framework; the multi-target *scene* gap
remains open in `docs/tracking/gaps.md` (Large), consumed here by a
scripted stopgap.
