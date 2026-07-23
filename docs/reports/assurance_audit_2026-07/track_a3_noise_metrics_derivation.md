# Track A3 — Blind Re-Derivation: Noise & Sensitivity Metrics

Status: Complete (derivation phase)
Produced by: blind-derivation agent (no access to src/ or docs/), 2026-07-22.
Comparison against implementation: see findings.md.

---

# Blind Physics Re-Derivation — RADIANT Detector/Readout Noise & Performance Metrics Audit

**Method statement:** Derived entirely from first principles and standard literature (Holst; Dereniak & Boreman; Vincent). No file under `src/` or `docs/` was read. All numerics computed with Python (CODATA: h = 6.62607015e-34 J·s, c = 2.99792458e8 m/s, k_B = 1.380649e-23 J/K, q = 1.602176634e-19 C).

Conventions: noise in e- RMS, signal in e-, wavelength in µm, radiance in W/m²/sr/µm, temperature K.

---

## 1. Photon (Shot) Noise

**(a)** Poisson: σ_shot = √N_e [e- RMS]. Independent Poisson populations add in variance:
σ_shot,total² = N_target + N_background + N_dark [e-²]; σ_shot,total = √(N_target + N_background + N_dark).
N_background includes scene background, path radiance, and instrument self-emission; dark shot is the same physics applied to thermally generated carriers.

**(b)** Poisson valid for thermal/incoherent light (photon degeneracy ≪ 1); QE < 1 preserves Poisson statistics (binomial thinning), so apply √ to *electrons*, not photons; no avalanche gain (which adds excess-noise factor F > 1).

**(c) Pitfalls.** √S with S in DN (√g error — properly σ_DN = √(S_DN/g)); adding σ's instead of variances; assuming dark-frame subtraction removes dark *shot* noise (it removes only the mean; single-shot dark subtraction doubles dark shot variance).

**(d) Spot checks.** N_e = 16000 e- (10000+5000+1000): σ = **126.491106 e-**; component RSS identical. N_e = 100: σ = 10, SNR = 10.

## 2. Dark Current

**(a)** N_d = I_dark·t_int/q [e-] (I_dark in A/pixel); or N_d = r_dark·t_int for e-/s input. σ_dark = √N_d.
Temperature scaling: diffusion-limited I_dark ∝ T³·exp(−E_g/(k_B T)); G-R-limited ∝ T^(3/2)·exp(−E_g/(2 k_B T)). Rule-07-style laws are this form recast as J₀·exp(−C·hc/(λ_c·k_B·T)).

**(b)** Stationary Poisson generation (excludes RTS/hot pixels); single-mechanism Arrhenius; tunneling terms nearly T-independent (set the cooling floor).

**(c) Pitfalls.** nA/cm² without pixel-area multiply; dark subtraction ≠ dark noise removal; E_g where E_g/2 applies (over-predicts cooling benefit); silicon "doubles every 6–8 K" rule misapplied to cryogenic HgCdTe.

**(d) Spot checks.** 1 fA, 10 ms: N_d = **62.4150907 e-**, σ = **7.90032219 e-**. 0.1 pA, 5 ms: N_d = **3120.75454 e-**, σ = **55.8637141 e-**. Diffusion E_g = 0.1 eV, 77→84 K: ratio **4.55823**; G-R 77→85 K: **2.35722**.

## 3. Read Noise and Total Noise (RSS)

**(a)** σ_tot = √(σ_shot² + σ_dark_shot² + σ_read² + σ_ADC² + σ_FPN²) [e- RMS], all input-referred to electrons.

**(b)** Independence is the load-bearing assumption; violated for FPN across frames of the same pixel (fixed spatial pattern — enters a single-frame spatial budget but does not average down temporally).

**(c) Pitfalls.** Linear σ summing; unit mixing (DN with e-); double-counting dark shot; counting quantization twice when measured "read noise" already includes the ADC.

**(d) Anchor.** N_t = 10000, N_bg = 5000, N_dark = 1000, σ_read = 50 e-, PRNU k = 0.1% → σ_PRNU = 10 e-:
σ_tot = √(16000 + 2500 + 100) = √18600 = **136.381817 e- RMS**. Read-only limit: 50 e- exactly.

## 4. ADC Quantization Noise

**(a)** σ_ADC = g/√12 ≈ 0.288675·g [e- RMS], g = N_fullwell/2ⁿ [e-/DN] for n-bit full-scale mapping.

**(b)** Valid when input noise ≳ 1 LSB (dithered); fails sub-LSB (contouring); ideal DNL/INL.

**(c) Pitfalls.** √12 vs 12 (3.46× understate); σ in DN not referred through g; double-count with measured read noise.

**(d) Anchor.** 14-bit, 100 ke- full well: g = **6.10351562 e-/DN**; σ_ADC = **1.76193316 e- RMS**. Wrong divisor g/12 = 0.508626 e- (3.4641× low). 12-bit variant: σ_ADC = **7.04773265 e-**.

## 5. Fixed-Pattern Noise (PRNU/DSNU)

**(a)** σ_PRNU = k_PRNU·N_e (photo-signal; LINEAR in signal, not √N); σ_DSNU = k_DSNU·N_dark. PRNU/shot crossover at N_cross = 1/k².

**(b)** k is residual post-NUC non-uniformity, signal-independent over the linear range; FPN averages down spatially, not temporally.

**(c) Pitfalls.** √ applied to PRNU; claiming temporal co-adding reduces PRNU; k applied to signal+dark (dark non-uniformity is DSNU); conflating 1/f drift with static FPN.

**(d) Spot checks.** k = 0.1%: N_cross = **1.0e6 e-**. N = 1e4: σ_shot = 100 vs σ_PRNU = 10 (shot-dominated). N = 5e6: σ_shot = 2236.07 vs σ_PRNU = 5000 (FPN-dominated).

## 6. SNR — Extended Scene and Contrast SNR

**(a)** SNR_abs = S_target/σ_tot; SNR_contrast = (S_target − S_background)/σ_tot. **The denominator always contains background (and dark) shot noise** — subtracting the background estimate in the numerator does not remove its Poisson fluctuations.

**(b)** Extended-source regime (no EE factor); σ_tot at actual operating flux.

**(c) Pitfalls.** σ = √(S_t − S_b) in the denominator (huge overstatement when S_b ≫ ΔS — the thermal-IR regime); DN-domain √; EE factors applied to extended scenes.

**(d) Spot checks** (§3 anchor): SNR_abs = **73.3235578**; SNR_contrast = **36.6617789**. Wrong-denominator √(S_t−S_b) = 70.71 → 1.93× overstatement.

## 7. NEDT

**(a)** NEDT = σ_tot/(dS/dT) [K].
dS/dT = t_int·G·∫(λ/hc)·QE(λ)·τ_opt(λ)·τ_atm(λ)·(∂L_λ/∂T)|_T dλ [e-/K], photon-domain weighting.
Étendue G = A_optics·Ω_pixel = A_pixel·Ω_optics; exact circular-pupil on-axis form G = A_d·π/(4F#²+1); paraxial limit A_d·π/(4F#²).
∂L_λ/∂T = L_λ(T)·(x/T)·eˣ/(eˣ−1), x = hc/(λ k_B T).

**(b)** Small-signal linearization about T_scene; extended blackbody scene; unobscured circular pupil for the exact étendue.

**(c) Pitfalls.** Paraxial 4F#² vs exact 4F#²+1 (6.25% at f/2, 25% at f/1 — understates NEDT); finite-ΔT differencing instead of analytic derivative; energy radiance without λ/hc conversion; σ_tot not evaluated at background flux.

**(d) Spot checks.** Anchor: dS/dT = 5000 e-/K, σ_tot = 60 e- → NEDT = **12.0000 mK**.
Full example: LWIR 8–12 µm, T = 300 K, QE = 0.7, τ = 0.8, F# = 2, 20 µm pixel, t_int = 1 ms:
∫₈¹²(∂L_λ/∂T)dλ = **0.629704 W/m²/sr/K** (matches literature ~0.63);
G_exact = **7.391983e-11 m²·sr** (paraxial/exact ratio = 1.0625);
dS/dT = **1.294177e6 e-/K** (exact) vs 1.375063e6 (paraxial).
Well-fill consistency flag: same integral gives S ≈ 8.01e7 e- in 1 ms — 801× a 100 ke- well; at half-well fill (t_int ≈ 0.62 µs) dS/dT = 807.454 e-/K, photon-limited NEDT = **276.9 mK** per sample — millikelvin claims must be checkable against implied well fill.

## 8. NEI (at aperture)

**(a)** NEI_photon = σ_tot/(η_sys·EE·A_ap·t_int) [photons/m²/s]; NEI_power = NEI_photon·(hc/λ̄) [W/m²] (quasi-monochromatic; else band-integrate). η_sys = QE·τ_opt; EE = ensquared-energy fraction (point-source regime).

**(b)** Point-source regime; σ_tot with background flux present; wide-band NEI needs a declared source spectrum.

**(c) Pitfalls.** Photon/energy domain mixing (λ/hc lost or doubled); EE omitted (optimistic by 1/EE); reference plane not declared; σ_read alone instead of σ_tot.

**(d) Spot checks.** σ_tot = 136.381817 e-, A_ap = 7.853982e-3 m² (10 cm dia), η_sys = 0.56, EE = 1, t_int = 1 ms, λ = 10 µm:
NEI_photon = **3.100834e7 photons/m²/s**; NEI_power = **6.159640e-13 W/m²**. EE = 0.5 doubles both.

## 9. D* (Specific Detectivity)

**(a)** D* = √(A_d·Δf)/NEP [cm·√Hz/W] (A_d in cm²!). Δf = 1/(2·t_int) for boxcar integration.
BLIP PV: D* = (λ/hc)·√(η/(2Q_b)); PC lower by √2 (generation AND recombination noise): (λ/hc)·√(η/(4Q_b)).

**(b)** Presumes areal white noise (fails for read-noise-limited FPAs — D* is a material metric, not a camera metric).

**(c) Pitfalls.** Δf = 1/t_int vs 1/(2t_int) (√2 error, same magnitude as PV/PC — easily conflated); m² instead of cm² (100×); PV formula on PC detector; Q_b hemispheric instead of cold-shield-limited.

**(d) Anchor.** NEP = 1e-14 W, A_d = 4.0e-6 cm², Δf = 1000 Hz: D* = **6.324555e12 cm·√Hz/W**. t_int = 0.5 ms ⇒ Δf = 1000 Hz ✓. BLIP λ = 10 µm, η = 0.7, Q_b = 1e17: PV **9.417970e10**, PC **6.659510e10 cm·√Hz/W**.

## 10. TDI and Co-Adding

**(a)** S_N = N·S₁; σ_N = √N·σ₁ (uncorrelated); SNR ×√N. Read noise: once for charge-domain TDI (single read), ×√N for off-chip digital co-add. Well-fill constraint: N·(S₁+N_d1) ≤ N_fullwell.
FPN correlation: staring frame co-add of the same pixels → FPN adds coherently (σ = k·N·S₁, no improvement); true cross-scan TDI over N different pixels → effective PRNU k/√N.

**(b)** Perfect scan sync (mis-registration is an MTF effect, not noise); equal per-stage illumination.

**(c) Pitfalls.** SNR ×N claim; read-noise ×√N applied to charge-domain TDI (√N pessimistic) or single-read assumed for digital co-add (√N optimistic); well ceiling ignored; FPN correlation model mismatched to architecture.

**(d) Spot checks.** S₁ = 10000 e-, N = 32: σ₃₂ = **565.685425 e-**, SNR gain **√32** exact. Well: 320 ke- > 100 ke- well → max charge-domain N = 10. FPN k = 0.1%: correlated **320 e-** vs TDI-averaged **56.5685 e-** (√32 apart).

## 11. Dynamic Range

**(a)** DR = N_fullwell/σ_floor; DR_dB = 20·log₁₀(·); DR_bits = log₂(·). σ_floor = dark-scene floor (read + dark shot + ADC), NOT photon shot.

**(b)** 20·log (amplitude convention, e-/e-); linear response; single gain/exposure; σ_floor at operating t_int.

**(c) Pitfalls.** 10·log vs 20·log (halves dB); ADC full scale vs true full well; shot-inflated denominator at full well; DR_bits vs ADC bits without the LSB/√12 subtlety.

**(d) Spot checks.** 100 ke-/50 e-: DR = 2000 = **66.0206 dB** = 10.97 bits. 100 ke-/5 e-: **86.0206 dB** = 14.29 bits (exceeds 14-bit ADC). 30 ke-/20 e-: **63.5218 dB**.

## 12. BLIP Condition

**(a)** BLIP: N_bg > σ_dark² + σ_read² + σ_ADC² + σ_FPN² (background shot exceeds all else RSS'd).
f_BLIP = σ_bg,shot/σ_tot = √(N_bg/(N_bg + Σother_variances)); threshold f > 1/√2. Equivalently D*_actual/D*_BLIP.

**(b)** "Background" = unavoidable in-band flux through the cold shield; target shot excluded; Poisson background; FPN calibrated below shot floor.

**(c) Pitfalls.** Target shot counted as background; BLIP quoted at one t_int as if general (N_bg ∝ t_int, σ_read fixed); FPN ignored (σ_FPN = k·N_bg grows faster than √N_bg — a system can exit BLIP from above); comparing against sources individually instead of their RSS.

**(d) Spot checks.** N_bg = 5000, N_dark = 1000, σ_read = 50, σ_FPN = 10: σ_bg = **70.7107 e-** vs other-RSS **60.0000 e-** → marginally BLIP; f_BLIP = **0.762493**. N_bg = 1e6: f_BLIP = 0.998205, but 0.1% PRNU on that background gives σ_FPN = 1000 e- = σ_bg exactly (the §5 crossover) — FPN-limited, not BLIP.

---

## Cross-Cutting Audit Checklist

1. Shot noise in **electrons** (post-QE); single Poisson variance = N_t + N_bg + N_d.
2. Dark shot present after offset subtraction; E_g (diffusion) vs E_g/2 (G-R) not conflated.
3. RSS in variance space, all input-referred to e-; no double counts.
4. σ_ADC = g/**√12**; not double-counted inside measured read noise.
5. σ_PRNU = k·N_photo (linear, photo-signal only); no temporal averaging of FPN.
6. Contrast SNR denominator contains background + dark shot; numerator is the difference.
7. NEDT: analytic Planck derivative, photon-domain λ/hc weighting, étendue variant declared (4F#²+1 exact vs 4F#² paraxial, 6.25% at f/2); implied well fill physically consistent.
8. NEI declares reference plane, regime (EE), photon-vs-power domain.
9. D* in cm·√Hz/W, A_d in cm²; Δf = 1/(2t_int); PV/PC √2 once, right direction.
10. TDI: SNR ×√N; read noise once (charge) vs ×√N (digital); well cap; FPN correlation matches architecture.
11. DR = full well / dark-scene floor, 20·log₁₀.
12. BLIP excludes target shot, RSS's competitors, evaluated at operating t_int.
