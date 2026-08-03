# Scenario 6.1 — Published-Datasheet Benchmark (D*/NETD)

**Persona:** Dr. Chen, researcher validating RADIANT against the literature.
**Question:** Does RADIANT's electron-domain noise model reproduce a
published cooled-LWIR detector's specific detectivity (D*) and NETD when
configured to the datasheet's reference conditions?

This scenario is the first consumer of the new D*/NEP/NETD converter set
(`radiant.performance.detectivity`, `.nep_electrons`, `.nep_netd`), which
bridges the chain's electron-domain noise to the datasheet's optical-power
figures of merit.

---

## Inputs (published datasheet — non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/chen_lwir_datasheet.xlsx` | Excel workbook (`Datasheet` sheet) | Published cooled-LWIR HgCdTe FPA: D*, NETD, band, pixel, reference f/#, scene temperature, and the as-built detector components |

`inputs/create_spreadsheet.py` regenerates it; values are transcribed into
the run script as constants for a self-contained, reproducible run.

---

## The converter bridge

The datasheet quotes **optical-power** figures (D* in Jones, NETD in K);
the chain computes **electron-domain** noise. The converters link them:

```
NEP = σ_e · h·c / (η · λ · t_int)     electrons → optical power [W]
D*  = √(A_d · Δf) / NEP               NEP → detectivity [Jones]
Δf  = 1 / (2 · t_int)                 integrating-detector noise bandwidth
```

Dr. Chen runs the chain, reads its total noise `σ_e = signal_e / SNR`, and
converts to `D*(chain)` and reads `NETD(chain)` (the exact band-integrated
value from Gap 43). Both are compared to the datasheet.

---

## Results (cooled LWIR, f/2, 300 K, 8–12 µm, 30 µm pixel)

| Metric | Datasheet | Chain | Residual | Verdict (±15%) |
|--------|-----------|-------|----------|----------------|
| D* [Jones] | 2.00 × 10¹¹ | 1.74 × 10¹¹ | **−13.0 %** | PASS |
| NETD [mK] | 25.0 | 24.6 | **−1.6 %** | PASS |

*Numbers refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-07-08). Dominant mover: CU-224 — down-looking path radiance now carries
`(1−τ)·B(λ,T_eff)`, which raises the in-band signal of this 8–12 µm
`simple`-atmosphere nadir scene (6.0 × 10⁶ → 6.35 × 10⁶ e⁻) and with it the
BLIP shot noise. CU-267's gas-region blend contributes a further −0.27 % on
τ over 8–12 µm.*

- **RADIANT reproduces the published performance within tolerance** — the
  noise model, propagated from components (dark, read) plus scene photon
  shot noise, lands within ~13 % of the datasheet D* and ~2 % of the NETD.
- **The chain is photon-shot- (BLIP-) limited**: total noise σ_e = 2520 e⁻
  ≈ √signal (2519 e⁻). So the *system* D* reflects the background-limited
  detectivity at these conditions, which is below the peak D* the
  datasheet quotes — hence the −13 % (honest, and the expected direction).
- **The datasheet D* implies 2193 e⁻ of total noise** at the reference
  bandwidth (via D* → NEP → σ_e); the chain's 2520 e⁻ is 15 % higher,
  consistent with the D* residual.

---

## Physics / modeling notes (house rule: explain the non-obvious)

- **D* is background-dependent at the system level.** The datasheet peak D*
  is a near-intrinsic figure; a real system operating against a 300 K scene
  is photon-shot-limited, so its effective D* is lower. The −13 % residual
  is this effect, not a model error — and it widened (from −10 %) precisely
  because CU-224 added the atmosphere's own `(1−τ)·B` emission to the
  down-looking background, deepening the BLIP floor this system sits on.
- **Noise bandwidth vs integration time.** `Δf = 1/(2·t_int)` is the
  equivalent noise bandwidth of an integrating detector — the convention
  linking a per-frame electron count to the per-√Hz D* definition. The
  datasheet's stated integration time (30 µs) sets Δf = 16.7 kHz.
- **NETD uses the exact dS/dT** (Gap 43), so the NETD comparison is against
  RADIANT's best thermal-sensitivity estimate, not the single-λ
  approximation.
- **Regime = EXTENDED** (the 300 K scene fills the pixel), well 63 % (the
  30 µs integration is chosen to stay unsaturated on the intense LWIR flux
  — itself a lesson: LWIR staring FPAs are integration-time-limited).

---

## Truth anchors for the converters

Verified in `src/radiant/performance/tests/test_noise_spec_converters.py`
(13 Level-0 tests) before this scenario consumed them:

1. D*: A_d = 1e-4 cm², Δf = 1 Hz, D* = 1e10 → NEP = 1e-12 W (hand calc).
2. NEP ↔ σ_e round-trip exact; NEP = σ_e·hc/(η·λ·t_int).
3. NEP ↔ NETD: NEP 1e-12 W, dP/dT 1e-11 W/K → NETD = 0.1 K.
4. Full D* → NEP → NETD → NEP → D* round-trip closes.
