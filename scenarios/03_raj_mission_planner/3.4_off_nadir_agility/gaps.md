# Scenario 3.4: Gaps — Off-Nadir Performance Degradation

## Gap Closure Summary

*Statuses reconciled 2026-09-07 (CU-340 PR): all four gaps were ruled CLOSED in
`docs/tracking/gaps.md` and `walkthrough.md` on 2026-09-01, but this file still
carried them OPEN.*

| Gap # | Description | Status | Notes |
|-------|-------------|--------|-------|
| 33    | GSD not adjusted for off-nadir angle | **CLOSED** | `gsd_cross_track_m` reads `path_zenith_rad` and tracks the scenario's independent spherical-Earth cross-track GSD to round-off at every swept angle (closed by `65720f0d`, ADR-0006 Phase 2; owner-ruled retired 2026-09-01) |
| 34    | NIIRS not recomputed with off-nadir GSD | **CLOSED** | `result.metrics["niirs"]` consumes the two-axis off-nadir GSD (GIQE-5 takes the geometric mean internally); the script's residual rescale was retired by CU-340 (2026-09-07) as a double-count |
| 35    | No along-track vs cross-track GSD at off-nadir | **CLOSED** | The chain reports `gsd_cross_track_m` and `gsd_along_track_m` separately (1.86 / 2.63 m at 45°) plus `gsd_geometric_mean_m`; the script's own projection agrees to round-off since the CU-340 fix |
| 36    | No swath width / access geometry calculator | **CLOSED** | `performance/{ground_range,swath_width,access_rate}.py` shipped; this config exercises `ground_range_m` (527.2 km at 45°). Swath/access-rate need `detector.n_pixels_cross` / `geometry.ground_speed_m_s`, unset here, so the script still computes those locally |

## Newly Available Metrics

These metrics are now returned by `result.metrics` and were not available when
the scenario was first written:

| Metric | API Key | Value (nadir) | Notes |
|--------|---------|---------------|-------|
*(Values refreshed 2026-09-07 from the CU-340 runner — this table had been
carrying the 2026-08-02 vintage, missing CU-335/CU-336. See the walkthrough's
sweep-table vintage notes for the movers.)*

| NEDT | `result.metrics["nedt_K"]` | 64.0 [mK] | Noise-equivalent delta temperature |
| NIIRS | `result.metrics["niirs"]` | 5.35 [--] | GIQE-5, extrapolated (see walkthrough banner) |
| GSD (cross) | `result.metrics["gsd_cross_track_m"]` | 1.37 [m] | Nadir GSD |
| GSD (along) | `result.metrics["gsd_along_track_m"]` | 1.37 [m] | Nadir GSD |
| GSD (GM) | `result.metrics["gsd_geometric_mean_m"]` | 1.37 [m] | Geometric mean |
| Q (center) | `result.metrics["q_center"]` | 0.844 [--] | Sampling parameter |
| Q (min/max) | `result.metrics["q_min"]`, `["q_max"]` | 0.562 / 1.125 [--] | Over band |
| Strehl | `result.metrics["strehl"]` | 0.9065 [--] | From EffectivePSF |
| RER | `result.metrics["rer"]` | 0.5372 [--] | Relative edge response |
| Well margin | `result.metrics["well_margin_dB"]` | 26.9 [dB] | |
| Dynamic range | `result.metrics["dynamic_range_dB"]` | 62.4 [dB] | |
| MTF budget | `result.stage_outputs["performance"]["mtf_budget"]` | See table | Per-component MTF at Nyquist |
| Folded MTF | `result.metrics["mtf_folded_at_nyquist"]` | 0.4544 [--] | ≈ 2× pre-sampling MTF at Nyquist; alias fraction 0.5000 (CU-209) |
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
| Signal shot | 60.14 |
| Dark shot | 0.12 |
| Read noise | 6.00 |
| Quantization | 1.44 |
| Nearfield shot | 0.00 |

Note: there is no separate background_shot term — an extended scene is one
radiance field, so its shot noise is `signal_shot` alone (ADR-0002 Decision #13;
the old 121.40/121.40 pair predates that landing). Nearfield = 0 because the
optics use scalar transmission mode (lumped refractive element has emissivity = 0
by Kirchhoff's law: epsilon = 1 - T - R, and for a transmission-only model T is
the total throughput with R = 0).

## Remaining Open Gaps

None. Gaps 33–36 are all CLOSED (see the closure summary above and
`docs/tracking/gaps.md`); the workaround column of the old table is retired —
the chain publishes off-nadir cross/along GSD, NIIRS on the geometric mean,
and `ground_range_m` directly. The script's own geometry survives only as the
two-axis cross-check in `walkthrough.md`.

-------|-------------|--------|------------|
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
