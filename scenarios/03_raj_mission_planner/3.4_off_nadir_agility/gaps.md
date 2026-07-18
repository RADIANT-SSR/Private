# Scenario 3.4: Gaps — Off-Nadir Performance Degradation

## Gap Closure Summary

| Gap # | Description | Status | Notes |
|-------|-------------|--------|-------|
| 33    | GSD not adjusted for off-nadir angle | OPEN | RADIANT reports nadir GSD even with path_zenith_rad > 0. Script computes true off-nadir GSD externally. However, RADIANT now does provide nadir GSD via `result.metrics["gsd_cross_track_m"]` (was previously unavailable). |
| 34    | NIIRS not recomputed with off-nadir GSD | OPEN | GIQE-5 uses nadir GSD internally. Script applies GSD scaling correction. However, RADIANT now provides nadir NIIRS via `result.metrics["niirs"]`. |
| 35    | No along-track vs cross-track GSD at off-nadir | OPEN | Both GSD axes equal in RADIANT; no projection correction for look angle |
| 36    | No swath width / access geometry calculator | OPEN | Must compute externally in script |

## Newly Available Metrics

These metrics are now returned by `result.metrics` and were not available when
the scenario was first written:

| Metric | API Key | Value (nadir) | Notes |
|--------|---------|---------------|-------|
| NEDT | `result.metrics["nedt_K"]` | 49.2 [mK] | Noise-equivalent delta temperature |
| NIIRS | `result.metrics["niirs"]` | 5.65 [--] | GIQE-5 rating (nadir only) |
| GSD (cross) | `result.metrics["gsd_cross_track_m"]` | 1.37 [m] | Nadir GSD |
| GSD (along) | `result.metrics["gsd_along_track_m"]` | 1.37 [m] | Nadir GSD |
| GSD (GM) | `result.metrics["gsd_geometric_mean_m"]` | 1.37 [m] | Geometric mean |
| Q (center) | `result.metrics["q_center"]` | 0.844 [--] | Sampling parameter |
| Q (min/max) | `result.metrics["q_min"]`, `["q_max"]` | 0.562 / 1.125 [--] | Over band |
| Strehl | `result.metrics["strehl"]` | 0.9169 [--] | From EffectivePSF |
| RER | `result.metrics["rer"]` | 0.5592 [--] | Relative edge response |
| Well margin | `result.metrics["well_margin_dB"]` | 14.7 [dB] | |
| Dynamic range | `result.metrics["dynamic_range_dB"]` | 53.4 [dB] | |
| MTF budget | `result.stage_outputs["performance"]["mtf_budget"]` | See table | Per-component MTF at Nyquist |
| Folded MTF | `result.metrics["mtf_folded_at_nyquist"]` | 1.5114 [--] | Indicates aliasing |
| Noise terms | `result.noise_terms` | See breakdown | Per-source noise in e- |

## RADIANT MTF Budget at Nyquist (nadir)

| Component | MTF@Ny_x | MTF@Ny_y |
|-----------|----------|----------|
| Optics (diffraction + WFE + obscuration) | 0.3815 | 0.3812 |
| Pixel Aperture | 0.6366 | 0.6366 |
| IPC | 0.9400 | 0.9400 |
| Jitter | 1.0000 | 1.0000 |
| Smear | 1.0000 | 1.0000 |
| Charge Diffusion | 1.0000 | 1.0000 |
| TDI | 1.0000 | 1.0000 |
| **System (product)** | **0.2283** | **0.2281** |

## Noise Breakdown (nadir)

| Source | Value [e-] |
|--------|-----------|
| Signal shot | 121.40 |
| Background shot | 121.40 |
| Dark shot | 0.12 |
| Read noise | 6.00 |
| Quantization | 1.44 |
| Nearfield shot | 0.00 |

Note: Nearfield = 0 because the optics use scalar transmission mode (lumped
refractive element has emissivity = 0 by Kirchhoff's law: epsilon = 1 - T - R,
and for a transmission-only model T is the total throughput with R = 0).

## Remaining Open Gaps

| Gap # | Description | Impact | Workaround |
|-------|-------------|--------|------------|
| 33    | GSD not adjusted for off-nadir angle | At 45 deg, RADIANT GSD is +9.6% vs true cross-track GSD | Script computes slant-range GSD externally |
| 34    | NIIRS not recomputed with off-nadir GSD | NIIRS overpredicted at off-nadir | Script applies -3.32*log10(GSD_ratio) correction |
| 35    | No along-track vs cross-track GSD at off-nadir | Along-track GSD diverges from cross-track at high angles | Script computes both with ground projection |
| 36    | No swath width / access geometry calculator | Must compute externally | Script uses n_pixels * GSD_cross |

---

## Real-data validation (2026-07-17)

The real MODTRAN 6 B-fan validated the angular physics and quantified a
model bias: real VNIR transmittance follows Beer–airmass scaling to
<0.2%, but SimpleAtmosphere's absolute pan-band optical depth is ~1.9×
too high, overstating the off-nadir τ penalty by ~10% (45°) to ~18%
(60°) in ratio terms. Geometry conclusions unaffected. See the
walkthrough's "Real-MODTRAN validation note".
