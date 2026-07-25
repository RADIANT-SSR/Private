# 9.1 Sentinel-2 MSI — SNR at Reference Radiance

**Mission**: Copernicus Sentinel-2 MSI, 786 km SSO, 150 mm TMA pushbroom imager.
**Claim validated**: RADIANT's aperture-to-electrons radiometry predicts ESA's per-band
SNR at the reference radiance L_ref the requirement is defined at.

## Design

Each band drives the chain with a flat user-radiance spectrum equal to the published
L_ref through a vacuum path (`atmosphere.model: exo`) — atmosphere and scene models are
deliberately out of the loop, because the published requirement and the on-orbit
measurement are both stated *at* an at-sensor radiance. Extended scene (EE_box = 1),
2-line TDI charge sum, line time GSD/v_g ≈ 1.50 ms (10 m bands).

## Run

`radiant run s2_msi_b04_snr_lref.yaml` (from this folder), or open in the GUI. The
5 configs differ only in band edges, L_ref spectrum (data/*.csv), pitch (B11: 15 µm),
and per-band QE assumption.

## Expected results (chain central values vs published)

| Band | RADIANT SNR [-] | ESA required [-] | S2C measured [-] |
|---|---|---|---|
| B2 | 253 | ≥154 | 162 |
| B3 | 208 | ≥168 | — |
| B4 | 193 | ≥142 | 175 |
| B8 | 337 | ≥174 | — |
| B11 | 331 | ≥100 | 133 |

Central predictions sit above measured because the QE·τ assumptions are generous; the
dossier's envelope + implied-throughput inversion (Findings §1) shows every gap
corresponds to a plausible value of an unpublished parameter (B2: blue-end QE ≈ 0.20;
B11: a much shorter SWIR integration time). Physics verdict: CONSISTENT (B11
INCONCLUSIVE pending a sourced SWIR t_int).

Non-RADIANT inputs: `data/s2_msi_*_lref.csv` — flat 2-point spectra at the published
L_ref values ([S2-SW] Table 3), regenerable trivially from those constants.
