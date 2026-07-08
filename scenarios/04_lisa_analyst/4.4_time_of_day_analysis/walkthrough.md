# Scenario 4.4 — Time-of-Day (Diurnal) Thermal Detectability

**Persona:** Lisa, image analyst assessing when a target is collectable.
**Question:** Over a 24-hour cycle, when is a painted-metal vehicle
detectable against its soil background in the LWIR, and when does it wash
out?

The physics is **thermal crossover**: twice a day the target and
background reach equal apparent radiance, the thermal contrast collapses,
and the target vanishes — regardless of how sensitive (low-NEDT) the
detector is. This scenario is data-driven: the diurnal temperature profile
is input data, and the chain is run over it. **No new framework model** —
the signal chain already computes the in-band signal for any surface
temperature and emissivity.

---

## Inputs (field-campaign / vendor formats — non-RADIANT)

| File | Format | Represents |
|------|--------|-----------|
| `inputs/diurnal_thermal_profile.csv` | 3-column CSV (`hour_local,T_target_K,T_background_K`) | 24-hour measured surface temperatures: target (painted-metal vehicle, low thermal inertia → large early swing) and background (soil, higher inertia → smaller lagged swing) |
| `inputs/lisa_lwir_sensor.xlsx` | Excel workbook (`SensorConfig`) | LWIR sensor optical/detector configuration |

`inputs/create_spreadsheet.py` regenerates both. The profile is two offset
sinusoids (a standard first-order diurnal surface model); the thermal-
inertia difference is encoded as different amplitude and phase, producing
two temperature crossings per day.

---

## Contrast construction (why it is built, not read)

The chain's own `contrast_e` differential (`signal_e − background_e`) is
only populated in the **sub-pixel** regime; for an **extended** target
pixel next to an extended background pixel the background-reference frame
is not built, so `contrast_e` collapses to the whole-scene signal and
never nulls. The transparent construction — the same one scenario 4.3 uses
— is to run the two pixels separately and difference them:

```
contrast SNR = (S_target − S_background) / √(N_target² + N_background²)
```

This nulls exactly at the **radiance** crossover
`ε_t · B(λ, T_t) = ε_b · B(λ, T_b)`. Because the emissivities differ
(0.92 vs 0.95), that radiance crossover is **offset** from the physical
temperature crossover `T_t = T_b` — the interesting physics of this
scenario. (Filed as Gap 52: no first-class extended target-vs-background
differential.)

---

## What the run produces

`scripts/run_diurnal_analysis.py` (run from the repo root):

1. **Diurnal sweep table** — target/background temperature, ΔT, and
   contrast SNR every 3 h (computed every 0.5 h), with a detectability
   flag.
2. **Crossover & washout report** — the physical-temperature crossovers,
   the offset radiance crossovers, and the detectability washout windows.
3. **Two figures** — diurnal temperatures + ΔT with temperature-crossover
   markers (`fig1`), and |contrast SNR| vs time with the detectability
   threshold and shaded washout windows (`fig2`).

---

## Results (LWIR 8–12 µm, 3 km AGL)

| Local time | T_target | T_background | ΔT | Contrast SNR | Detectable? |
|-----------|----------|--------------|-----|--------------|-------------|
| 00:00 | 285.0 K | 289.1 K | −4.06 K | −105 | yes (cold target) |
| 06:00 | 292.0 K | 289.1 K | +2.97 K | +20 | yes |
| 12:00 | 309.0 K | 298.9 K | +10.06 K | +148 | yes (hot target) |
| 18:00 | 302.0 K | 298.9 K | +3.03 K | +19 | yes |
| 21:00 | 292.0 K | 294.0 K | −1.98 K | −70 | yes |

- **Physical-temperature crossovers (ΔT = 0):** 04:12 and 19:48.
- **Radiance crossovers (contrast = 0):** 05:12 and 18:48 — **offset ~1 h**
  from the temperature crossovers.
- **Detectability washout windows (|contrast SNR| < 10):** ≈05:30–06:00
  and ≈18:30–19:00 (~30 min each, limited by the 0.5 h profile grid).
- **Median NEDT across the day: 39 mK, nearly constant.** The washout is
  *not* a sensor-sensitivity effect — the detector is just as sensitive at
  crossover as at noon. It is a **scene-contrast** effect: there is simply
  no signal to detect when the two surfaces radiate equally.

### The emissivity offset (the key insight)

The target is *less* emissive than the background (0.92 vs 0.95). To match
the background's apparent radiance, the target must be a few kelvin
**warmer** than the background — so the contrast crosses zero *after* the
physical temperature crossover in the morning (05:12 vs 04:12) and *before*
it in the evening (18:48 vs 19:48). An analyst who plans collections around
the *temperature* crossover would mis-time the washout by ~1 hour; the
*radiance* crossover is what governs detectability.

---

## Physics / modeling notes (house rule: explain the non-obvious)

- **Regime = EXTENDED** for each pixel run; the differential is built at
  the scenario level (see "Contrast construction"). Point-source and
  sub-pixel machinery is unused.
- **Integration time is short (0.1 ms).** LWIR self-emission from a ~300 K
  scene is intense; at the sensor's 8 ms nominal the well saturates
  (>99%), which clips the signal and destroys the contrast. 0.1 ms keeps
  the well ~40 % full so the contrast is linear. (This is itself a design
  lesson: LWIR staring sensors on warm scenes are integration-time-limited,
  not photon-starved.)
- **Contrast sign flips** between day (target hotter → positive) and night
  (target colder → negative). Detection works on |contrast|; the sign
  tells the analyst whether the target appears hot or cold.
- **Thermal inertia** drives the whole effect: the metal target swings
  more and peaks earlier than the soil, so it is hotter by day and colder
  by night, crossing the background twice.

---

## Assumptions & fragility

- The diurnal profile is a smooth two-sinusoid model; real surfaces show
  weather-driven excursions (cloud shadow, rain) that create additional
  transient crossovers not captured here.
- Emissivity is treated as spectrally flat (graybody) per surface; a
  spectrally structured ε(λ) would shift the radiance crossover further
  (see Gap 47, spectral emissivity).
- The atmosphere is the `simple` model at a fixed 3 km slant path; a
  MODTRAN LWIR path would change absolute signals but not the crossover
  structure.
