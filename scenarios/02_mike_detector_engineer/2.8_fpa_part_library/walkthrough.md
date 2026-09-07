# Scenario 2.8 Walkthrough: Real-Part Quick Start — GeoSnap-18 by Name

## Persona
Mike, detector engineer. Every prior scenario began with him transcribing
datasheet values by hand — pitch here, well there, a QE he half-remembers.
For the new MWIR airborne study he wants the sensor he is actually being
offered, a **Teledyne GeoSnap-18**, modeled from the library that ships with
RADIANT (Gap 119): one `fpa:` line, every value carrying its datasheet
citation, and the datasheet itself one click away.

## What the config says (inputs/geosnap18_mwir_leo.yaml)
| Input | Value | Unit | Who supplies it |
|---|---|---|---|
| FPA part | `geosnap-18` | — | library preset (11 parameters) |
| Target temperature | 300 | K | Mike |
| Sensor altitude | 8000 | m | Mike |
| Aperture / focal length | 0.30 / 1.20 (f/4) | m | Mike |
| Band | 3.5–5.0 | µm | Mike |
| Integration time | 5 | ms | Mike |
| Dark rate | 5.0×10⁴ | e⁻/s | Mike (explicit — see below) |

The preset supplies: 18 µm pitch (both axes), 2048 cross-track pixels, 100 %
fill factor, QE 85 %, T_det 110 K, `analog_well` architecture, 2.6 Me⁻ well,
400 e⁻ RMS ROIC noise, 14-bit ADC, and the 85 Hz frame period — each entry in
`src/radiant/data/tables/fpa/geosnap-18.yaml` naming the exact datasheet line
it came from.

**The dark rate is Mike's on purpose.** The GeoSnap-18 preset deliberately
ships no dark current: it is a custom-cutoff part and dark is a function of
cutoff wavelength and temperature (the datasheet only says so in nA/cm²).
The preset notes call this out; Mike sets his programme estimate for a
5.3 µm cutoff at 110 K.

## Result (scripts/run_scenario.py, 2026-09-06)
| Metric | Value | Unit |
|---|---|---|
| Radiometric regime | extended | — |
| Readout architecture | analog_well | — |
| **SNR** | **1178.6** | — |

Physics worth knowing (also printed by the script):

- The 400 e⁻ RMS entry is the vendor's **ROIC-only** noise for the large
  (2.6 Me⁻) well. The measured 13.2 µm science device shows 360 e⁻ RMS
  *system* read noise (Bowens et al. 2024) — the preset value is honest to
  within 10 %, and the preset notes say which to prefer for LWIR work.
- At 5 ms against a 300 K extended scene the chain is background-shot
  dominated; the binding capacity is the 2.6 Me⁻ charge well, not the 14-bit
  ADC.
- GeoSnap is a **digital-interface FPA, not a digital-pixel counter**: CTIA
  well + on-chip column ADC (`analog_well`). The counting-architecture
  exemplar in the library is `dfpa-generic` (scenario 2.6/2.7 territory).

## Where the trust comes from
Every preset value traces `fpa:geosnap-18/<source>` in the run's provenance
record, the cited PDFs live at `docs/validation/fpa_datasheets/` with SHA-256
rows in that folder's manifest, and `radiant.data.FPALibrary` refuses any
preset whose attribution is incomplete. Overriding any value is one ordinary
`sensor.set` — explicit always wins.
