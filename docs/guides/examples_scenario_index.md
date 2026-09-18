# Scenario Index

Fifty-one scenario folders live under `scenarios/` in the RADIANT repository. This
appendix indexes every one of them, in catalog order, with the place in this volume
where it is covered.

**Coverage is total, at tiered depth**: eight scenarios
are walked at full depth as case studies, four are the subject of the
flagship-validation chapter, and the remaining thirty-nine appear as digests in the
compendium. Nothing in the repository is unrepresented here.

## How to read the table

- **Scenario** — the folder name's numeric identifier. Two folders share the
  identifier 2.7; they are distinguished in the Title column and in the digest
  compendium, and the identifier collision is a property of the tree, not a typo.
- **Persona** — the catalog persona the folder belongs to. Folders 8, 9 and 10 are not
  personas: 8 is a set of tool demonstrations, 9 is the external-validation suite, and
  10 is the direction-general acceptance suite for the geometry work.
- **GUI** — *yes* when the folder ships a GUI-openable baseline. For personas 1–8 and 10
  that is an `inputs/<slug>.gui.yaml` opened through **File → Open YAML**; for the
  flagship folders it is the per-band config files at the folder root, which open the
  same way (marked *configs*).
- **Runner** — *yes* when the folder ships an executable program under `scripts/`
  (`PYTHONPATH=src python scenarios/<...>/scripts/<name>.py`). A folder without one is
  driven from the GUI or from `radiant run`.
- **Covered in** — where in this volume to read about it. *Case study* names the
  full-depth chapter; *Validation* names the mission's section of the flagship-mission
  validation chapter; *Digest* is the entry in the scenario digest compendium, filed under the
  same identifier.

Every folder, without exception, carries a `walkthrough.md` (the narrative and the
committed results), a `gui_workflow.md` (the GUI route and its requirements), and a
`gaps.md` (what the scenario could not do, and why). Those three files are the
authority for their scenario; this volume's chapters quote them.

| Scenario | Title | Persona | GUI | Runner | Covered in |
|---|---|---|:--:|:--:|---|
| 1.1 | MWIR Maritime Surveillance Trade Study | Sarah, systems engineer | yes | yes | Case study — MWIR Maritime Surveillance |
| 1.2 | VNIR Pan Imager: GSD vs Aperture vs Altitude | Sarah, systems engineer | yes | yes | Digest 1.2 |
| 1.3 | Dual-Band MWIR/LWIR Wildfire Detection | Sarah, systems engineer | yes | yes | Digest 1.3 |
| 1.4 | TDI Pushbroom Optimization: Line Rate vs SNR | Sarah, systems engineer | yes | yes | Digest 1.4 |
| 1.5 | Obscured Aperture and Spider Vanes | Sarah, systems engineer | yes | yes | Digest 1.5 |
| 1.6 | MWIR Point-Source Space Domain Awareness | Sarah, systems engineer | no | yes | Digest 1.6 |
| 2.1 | InSb vs HgCdTe Noise Budget Shootout at 77 K | Mike, detector engineer | yes | yes | Case study — InSb versus HgCdTe on One Bench |
| 2.2 | 1/f Noise Corner Frequency, LWIR Staring Array | Mike, detector engineer | yes | yes | Digest 2.2 |
| 2.3 | IPC Impact on MTF | Mike, detector engineer | yes | yes | Digest 2.3 |
| 2.4 | Persistence Characterization: Bright-Source Recovery | Mike, detector engineer | no | yes | Digest 2.4 |
| 2.5 | Well Capacity Optimization: Integration Time vs Dynamic Range | Mike, detector engineer | yes | yes | Digest 2.5 |
| 2.6 | DROIC vs Analog ROIC: Single-Frame HDR | Mike, detector engineer | no | yes | Digest 2.6 |
| 2.7 | Calibration-Limited NEDT: Two-Point NUC Floor | Mike, detector engineer | no | yes | Digest 2.7 (calibration-limited NEDT) |
| 2.7 | Up/Down Counting: In-Pixel Background Subtraction | Mike, detector engineer | no | yes | Digest 2.7 (up/down background subtraction) |
| 2.8 | Real-Part Quick Start: GeoSnap-18 by Name | Mike, detector engineer | no | yes | Digest 2.8 |
| 3.1 | ISR Orbit Geometry and Pass Planning | Raj, mission planner | yes | yes | Case study — ISR Pass Planning |
| 3.2 | Weather Sensitivity: How Bad Can It Get? | Raj, mission planner | yes | yes | Digest 3.2 |
| 3.3 | Multi-Sensor Comparison for Procurement | Raj, mission planner | yes | yes | Digest 3.3 |
| 3.4 | Off-Nadir Performance Degradation | Raj, mission planner | yes | yes | Digest 3.4 |
| 3.5 | Nighttime MWIR Imaging Feasibility | Raj, mission planner | yes | yes | Digest 3.5 |
| 4.1 | Target Detection Matrix | Lisa, detection/targeting analyst | yes | yes | Case study — A Target Detection Matrix |
| 4.2 | Maritime Ship Classification (Johnson DRI) | Lisa, detection/targeting analyst | no | yes | Digest 4.2 |
| 4.3 | Camouflage Effectiveness Analysis | Lisa, detection/targeting analyst | yes | yes | Digest 4.3 |
| 4.4 | Time-of-Day (Diurnal) Thermal Detectability | Lisa, detection/targeting analyst | yes | yes | Digest 4.4 |
| 4.5 | Microbolometer UAV Altitude Trade (NETD-Specified) | Lisa, detection/targeting analyst | yes | yes | Digest 4.5 |
| 5.1 | WFE Budget Allocation | Tom, optical designer | yes | yes | Case study — Allocating a Wavefront-Error Budget |
| 5.2 | Pixel Pitch and the Sampling Parameter Q | Tom, optical designer | yes | yes | Digest 5.2 |
| 5.3 | Monochromatic vs Polychromatic PSF | Tom, optical designer | yes | yes | Digest 5.3 |
| 5.4 | Jitter Tolerance: Line-of-Sight Stability Requirements | Tom, optical designer | yes | yes | Digest 5.4 |
| 5.5 | Stray Light and Veiling Glare | Tom, optical designer | yes | yes | Digest 5.5 |
| 6.1 | Published-Datasheet Benchmark (D*/NETD) | Dr. Chen, researcher | yes | yes | Case study — Benchmarking Against a Published Datasheet |
| 6.2 | Atmospheric Model Intercomparison | Dr. Chen, researcher | yes | yes | Digest 6.2 |
| 6.3 | Noise Model Verification Against Hand Calculation | Dr. Chen, researcher | yes | yes | Digest 6.3 |
| 6.4 | Synthetic Scene Generation for Algorithm Testing | Dr. Chen, researcher | yes | yes | Digest 6.4 |
| 6.5 | Emissivity Sensitivity for Temperature Retrieval | Dr. Chen, researcher | no | yes | Digest 6.5 |
| 7.1 | Predicted vs Measured NEDT Reconciliation | Karen, test engineer | yes | yes | Case study — Reconciling Predicted and Measured NEDT |
| 7.2 | Radiometric Calibration Verification | Karen, test engineer | yes | yes | Digest 7.2 |
| 7.3 | MTF Measurement vs Prediction | Karen, test engineer | yes | yes | Digest 7.3 |
| 7.4 | Cold-Stop Undersizing Sweep | Karen, test engineer | yes | yes | Digest 7.4 |
| 7.5 | Performance at Temperature Extremes | Karen, test engineer | yes | yes | Digest 7.5 |
| 8.1 | Off-Nadir Angle Interpolation | Tool demonstration | yes | yes | Digest 8.1 |
| 8.2 | Target-Altitude Interpolation | Tool demonstration | yes | yes | Digest 8.2 |
| 8.3 | Boost-Phase Target-Altitude Sweep (skeleton) | Tool demonstration | no | yes | Digest 8.3 |
| 9.1 | Sentinel-2 MSI — SNR at Reference Radiance | Flagship validation | yes, *configs* | no | Validation — Sentinel-2 MSI |
| 9.2 | Landsat 8 TIRS — Thermal NEdT | Flagship validation | yes, *configs* | no | Validation — Landsat 8 TIRS |
| 9.3 | MODIS (Aqua) Thermal Emissive Bands | Flagship validation | yes, *configs* | no | Validation — Aqua MODIS |
| 9.4 | Landsat 9 OLI-2 — Nine-Band SNR, Per-Element Coated Optics | Flagship validation | yes, *configs* | yes | Validation — Landsat 9 OLI-2 |
| 10.1 | Ground-to-Air MWIR Detection | Direction-general | yes | yes | Digest 10.1 |
| 10.2 | Air-to-Air Level-Arm MWIR IRST | Direction-general | yes | yes | Case study — Air-to-Air IRST on a Level Arm |
| 10.3 | Ground-to-Space SST, Visible Band | Direction-general | yes | yes | Digest 10.3 |
| 10.4 | LEO-to-GEO Up-Looking Space-to-Space SDA | Direction-general | yes | yes | Digest 10.4 |

## Counts

| Folder | Scenarios | Case studies | Validation | Digests |
|---|---:|---:|---:|---:|
| 1 — Sarah, systems engineer | 6 | 1 | 0 | 5 |
| 2 — Mike, detector engineer | 9 | 1 | 0 | 8 |
| 3 — Raj, mission planner | 5 | 1 | 0 | 4 |
| 4 — Lisa, detection/targeting analyst | 5 | 1 | 0 | 4 |
| 5 — Tom, optical designer | 5 | 1 | 0 | 4 |
| 6 — Dr. Chen, researcher | 5 | 1 | 0 | 4 |
| 7 — Karen, test engineer | 5 | 1 | 0 | 4 |
| 8 — Tool demonstrations | 3 | 0 | 0 | 3 |
| 9 — Flagship missions | 4 | 0 | 4 | 0 |
| 10 — Direction-general | 4 | 1 | 0 | 3 |
| **Total** | **51** | **8** | **4** | **39** |

Thirty-eight of the fifty-one ship an `inputs/*.gui.yaml` baseline and the four
flagship folders ship GUI-openable per-band configs — forty-two GUI entry points in
all. Forty-eight ship an executable runner; the three without one — the
three flagship folders that are pure configuration comparisons — are driven by
`radiant run <config>` or by the repository-level
`scripts/run_external_validation.py`, which is the canonical executable form of the
external-validation dossier.

The catalog itself — one paragraph per scenario, with the persona's motivating question
— is the repository's scenario catalog. It is the front door for
"which scenario is closest to my problem"; this appendix is the front door for "where
does this volume discuss it".
