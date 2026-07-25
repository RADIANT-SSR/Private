# External Validation Plan

Status: Active
Owner ask: 2026-07-24 ("move out on" the validation dossier). Multi-PR effort per
OPERATING_MODEL §3 sizing rule; this plan is the epic, findings will be CU'd/Gap'd.

## Goal

Evidence that RADIANT's equations match the world, not just the code: configure RADIANT
to real, well-documented sensors and compare predicted performance against **published,
cited** specified and measured values. Complement to the 2026-07 assurance audit (which
proved internal consistency).

## Method

1. **Data** — per instrument, a `docs/validation/<sensor>_source_data.md` file: every
   parameter with value, units, source (author/year/URL), and confidence class
   (published / derived / **assumption**). No uncited numbers; assumptions carry
   recommended values and a sensitivity range.
2. **Model** — `scripts/run_external_validation.py` builds each band's RADIANT config
   (user-radiance mode at the published reference radiance, `atmosphere.model = exo`, so
   the comparison isolates instrument radiometry — the published SNR figures are defined
   *at* an at-sensor radiance) and runs the public `RadiantSession` API.
3. **Compare** — predicted vs required vs measured, with the assumption envelope
   propagated (min/max plausible predicted SNR), dispositioned per band: CONSISTENT /
   TENSION (explain) / CANNOT-VALIDATE (missing data).
4. **Report** — point-in-time dossier in `docs/reports/external_validation_2026-07/`
   when the campaign closes (Rule 24: this plan then archives).

## Targets

| # | Instrument | Validates | Status |
|---|---|---|---|
| 1 | Sentinel-2 MSI (B2/B3/B4/B8 VNIR, B11 SWIR) | Reflective-band SNR @ L_ref vs ESA requirement + S2C measured | Data banked (SentiWiki + eoPortal, 2026-07-24); modeling in progress |
| 2 | Landsat 8/9 TIRS (bands 10/11) | LWIR NEDT @ 300 K vs spec + measured | Research incomplete (session-limit casualty); relaunch single agent |
| 3 | MODIS TEB (bands 20/29/31/32) | MWIR/LWIR NEdT vs spec + Xiong measured | Research incomplete; relaunch after #2 |

## Ground rules

- The published number is never adjusted to fit; discrepancies are explained by named
  assumptions or filed as findings.
- Every value in every output carries units (owner hard rule).
- Instrument-parameter gaps that RADIANT *should* accept but cannot express become Gap
  entries; RADIANT physics discrepancies become CUs.
