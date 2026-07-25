# 9.2 Landsat 8 TIRS — Thermal NEdT

**Mission**: Landsat 8/9 TIRS, 705 km SSO, f/1.64 refractive LWIR pushbroom, 43 K QWIP
FPA — the canonical spaceborne LWIR NEdT benchmark.
**Claim validated**: RADIANT's photon/dark/read noise floor predicts the flight-measured
NEdT (Montanaro et al. 2014, on-orbit blackbody method).

## Design

300 K unit-emissivity blackbody through a vacuum path — the same view the published
NEdT is measured against (the onboard calibrator). Configs carry the published optics
(f/1.64, 178 mm, τ 0.49), detector (25 µm QWIP, 3.49 ms as-flown, dark 4×10⁷ e-/s,
read 260 e-), and the effective conversion efficiency inverted from the published
saturation temperatures (well full at 400 K B10 / 370 K B11); the raw published CE
(8.0e-3) is the other bracket bound — see Findings §2.

## Run

`radiant run tirs_b10_nedt_300k.yaml`; read NEdT from the Performance outputs.

## Expected results

| Band | RADIANT NEdT (this config) | Bracket (Findings §2) | Spec | Measured |
|---|---|---|---|---|
| B10 | 58 mK | 58–124 mK | ≤400 mK | 49 mK |
| B11 | 52 mK | 52–89 mK | ≤400 mK | 52 mK |

B11's prediction lands exactly on the flight value. Cross-check: RADIANT's raw signal
model agrees with the instrument team's own published budget (Jhabvala 2011) within
~25%. The published budget's dominant terms are calibration-*stability* terms
(blackbody/optics temperature knowledge), which are not detector noise and are
correctly absent here. Verdict: CONSISTENT.
