# Capability Audit — Findings

**Status:** Complete (2026-07-11)
**Charter:** `Audit_Plan.md` (this folder). Method: 21-agent parallel sweep (11 package areas,
8 persona/scenario audits, registry triage, latency probe) followed by manual adversarial
verification of every high-severity claim by the orchestrating auditor (grep/read/execute).
**Verification legend:** ✅ = independently re-verified by auditor; ⚠ = agent evidence cited
but not independently re-verified; 🔶 PROVISIONAL = touches the atmosphere/MODTRAN area under
concurrent rework — must be re-checked after that work lands (CU-086).
**Disposition legend (Rule 28):** every finding carries CU'd (registry ID), Planned
(`docs/plans/Pre_GUI_Hardening_Plan.md`), or Declined (rationale). The three
Proposed-Declined items were ratified Declined by the owner on 2026-07-11.

---

## Headline conclusions

1. **The physics engine is mature; the product surface around it is not.** The signal chain,
   noise budget (16 terms), dual-path spatial architecture, and parameter system are
   disciplined and well-tested. What is missing is almost entirely *reachability and
   packaging*: implemented physics that config/YAML/Sensor cannot express, computed metrics
   never surfaced, and zero persistence.
2. **Scenario evidence is complete — and the status table lies about it.** All 35 persona
   scenarios plus both interpolation demos are implemented and executed (2026-07-08/09), yet
   `scenarios/README.md` still marks 21 of them "stub" (CU-075). Persona coverage is
   strong: Tom/Karen/Chen ~85-90 % of stated workflow demonstrated, Sarah/Mike ~80-90 %,
   Raj ~70-75 %, Lisa strong-with-caveats.
3. **The chain is GUI-fast.** Measured on `examples/mwir_leo_minimal.yaml`: import 0.41 s,
   full chain evaluate median **0.22 s** (n=3). Interactive parameter editing is viable
   without an incremental-re-evaluation engine; sweeps/MC need progress hooks, not a rewrite.
4. **Five load-bearing GUI-blockers exist**, all verified: no persistence (F-01), non-scalar
   inputs unreachable from `Sensor` (F-02), no schema introspection (F-03), no
   progress/cancel hooks (F-05), no metric units metadata (F-04).
5. **Doc-vs-code drift is the systemic risk.** Four "Authoritative" architecture docs
   describe systems with zero or partial implementation (F-20). Anyone speccing the GUI from
   the docs would design against phantom surfaces.

---

## Theme A — GUI binding surface (the blockers)

**F-01 (high, ✅) No session/run persistence anywhere.** No `Sensor.save/load`, no
`ChainResult.to_json/to_csv` or reload; only metrics+noise JSON and provenance JSON exist.
The accepted `RADIANT_GUI_Architecture.md` binds File-Open/Save directly to these missing
methods. Verified: zero `def save|to_json|load` in `api/sensor.py`, `io/results.py`.
→ **CU'd: Gap 67**; sequenced in Pre_GUI_Hardening_Plan.

**F-02 (high, ✅) Non-scalar chain inputs unreachable from the Sensor/YAML surface.** Optical
element lists, Zernike/OPD wavefronts, pupil masks, spectral injections require
`RadiantSession.run(extra_stage_outputs=...)`; `Sensor.evaluate/sweep/monte_carlo` never
passes it (verified: 0 references in `sensor.py`). Compounding: schema-advertised modes that
always raise — optics transmission modes `spectral_file`/`telescope_plus_filters`/
`key_elements` (verified: `optics/stage.py:740-749` passes only scalar+elements), stray-light
`spectral_file`/`pst_file`, WFE `opd_map` (NotImplementedError). → **CU'd: Gap 68**.

**F-03 (high, ✅) No public parameter-schema introspection.** GUI/CLI form generation must
read `ParameterSet._defs`/`._groups` privates (verified: `cli/schema_cmd.py:37`,
`api/sensitivity.py:133`). → **CU'd: Gap 70**.

**F-04 (high, ⚠) `result.metrics` is a bare name→float mapping** — no units, descriptions, or
types; units live in some key suffixes only. Conflicts with the owner's units-on-everything
hard rule. The doc-promised uniform `MetricResult` contract does not exist; the metric
registry (`performance/registry.py`) has zero production consumers and declares four metrics
the stage never computes. → **CU'd: Gap 71** (contract) + **CU-078** (registry drift).

**F-05 (high, ⚠) No progress or cancellation hooks** on `evaluate/sweep/sweep_2d/
monte_carlo/sensitivity/BatchRunner`; `ChainRunner.run` has no per-stage callback seam.
At 0.22 s/point a 30×30 sweep is ~3 min of frozen UI. → **CU'd: Gap 72**.

**F-06 (high, ✅) Parallel sweep crashes.** `n_workers>1` dies with unhandled
`_pickle.PicklingError`: the fallback catches only `(TypeError, AttributeError)` at submit
time but ProcessPoolExecutor pickles asynchronously (verified `api/sweep.py:225-232`).
→ **CU'd: CU-072**.

**F-07 (medium, ⚠) Unknown-parameter errors are bare `KeyError`, not `RadiantError`** —
the documented single GUI error boundary (`except RadiantError`) misses the most common user
mistake (typo'd parameter name). Rule 15 drift. → **CU'd: CU-073**.

**F-08 (medium, ⚠) Bundled reference libraries not selectable from config.** 6-material
detector QE library has no `detector.qe_material` parameter (verified: zero grep hits);
19-material emissivity library binds to `source.background.material` but there is no
`source.target.material`. → **CU'd: Gap 69**.

**F-09 (medium, ⚠) Expandability seams missing in core:** unit registry is a private pair
table (no `register_unit()`, no per-dimension enumeration, error text tells users to edit
core source; missing ft/nmi/°C/mK); consistency-group machinery has exactly one registered
group (f/#) though the resolver supports chains (IFOV/GSD/Q triples unwired); `radiant.io`
exposes no public namespace; `BatchRunner` not exported and doc contradicts itself on its
existence. → **CU'd: Gap 70 (introspection), CU-085 (sweep items)**; unit-registry and
consistency-group expansion folded into Pre_GUI_Hardening_Plan (Planned).

## Theme B — physics and metrics gaps (fix before they embarrass a demo)

**F-10 (high, ✅) Point-source regime silently zeroes background and path photon noise**
(`spectral_integration/stage.py:342-364`, `background_e = 0.0`): point-target SNR/detection
range against daytime sky or sunlit clouds is optimistic; noise budget is discontinuous at
the sub-pixel→point-source boundary. → **CU'd: Gap 73**.

**F-11 (high, ✅) fill_factor diverges the two Rule-4 paths:** the optics PSF pixel kernel
applies pitch×fill_factor (`optics/pixel_kernel.py:57-58`) but the detector MTF sinc and the
radiometric A_pixel ignore fill_factor (verified: zero hits in `detector/stage.py`,
`spectral_integration/stage.py`). Any fill_factor<1 trips the consistency check and collects
unphysically high signal. → **CU'd: CU-074**.

**F-12 (high, ✅) The scan/timing subsystem does not exist** despite an "Authoritative"
`RADIANT_Scan_Timing.md`: no ScanMode, no t_int derivation from line rate/dwell, no
t_int ≤ line_period × n_tdi feasibility constraint (unphysical TDI configs accepted
silently); two of three documented smear sources (cross-track scan, target motion) have no
parameters or kernels (verified: zero grep hits for ScanMode/TimingState/cross_track_velocity
in src). → **CU'd: Gap 74** (capability) + **CU-079** (doc banner).

**F-13 (medium, ⚠) Orbit/coverage library is unwired:** `core/orbit.py` and
`core/repeat_ground_track.py` (period, ground-track speed, sun-sync inclination, revisit) are
imported by nothing outside their tests; ground velocity is never derived from altitude; and
duplicate parameters (`platform.ground_velocity_m_s` vs `geometry.ground_speed_m_s`;
`platform.h_sensor` vs `geometry.sensor_altitude_m`) can silently disagree. → **CU'd: Gap 75**.

**F-14 (medium, ⚠) Solar spectrum is a 5778 K blackbody everywhere** — `core/solar.py`
raises on any other model; the bundled "AM0" CSV is itself a Planck fit (no Fraunhofer
structure), validated only to ±5 % integrated TSI; no day-of-year/Earth-Sun distance
variation though `core/solar_geometry.py` has the math. 5-20 % band-dependent error in
narrow VNIR bands. Previously untracked. → **CU'd: Gap 76**.

**F-15 (high-value, ⚠) The decision-grade metrics personas brief are script-side, not
in-chain.** Detection range (headline metric, doc §4.12) never computed in-chain; SCNR
(clutter-inclusive SNR — Lisa's and Sarah's core detection number) assembled by hand in every
scenario; Pd/ROC, Johnson DRI, NEDL/NEDR→MRC, D*/NEP/NEI converters all library-only.
→ **CU'd: Gap 77 (SCNR + detection-range solver), Gap 78 (acquisition-metric surfacing)**.

**F-16 (medium, ⚠) No multi-band concept:** one filter_min/max pair per run; dual-band
comparison (scenario 1.3) and band trades require externally orchestrated runs. → **CU'd:
Gap 80**.

**F-17 (medium, ⚠) Trade-study ergonomics are per-script boilerplate:** no multi-config
compare/compliance-matrix primitive (demanded by Sarah 1.3, Raj 3.3, Lisa 4.1, Chen 6.1);
no sweep-level warning dedup (~25 identical warnings across a 13×11 grid); constrained 2-axis
sweeps (aperture×altitude at fixed GSD) hand-rolled each time. → **CU'd: Gap 79**.

**F-18 (medium, ⚠) Detector model traps:** dark current is temperature-inert by default
(`dark_activation_energy_eV=0` — a GUI temperature slider does nothing, demo-embarrassing)
→ **CU-081**; QE(T) is a single linear scalar with no cutoff-wavelength shift (dominant
HgCdTe/T2SL effect; registry Gap 48 closed the scalar path only) → noted, Declined
for pre-GUI (owner-ratified 2026-07-11; physics upgrade, not surface work — revisit post-GUI); IPC kernel applied at PSF
sample spacing instead of pixel pitch, making the PSF-path IPC effect orders of magnitude too
small (scenario 2.3 evidence; Gap 1 closed without covering spacing) → **CU-083**.

**F-19 (medium, 🔶 PROVISIONAL) Atmosphere findings under concurrent rework:** MODTRAN-backed
chain zeroes downwelling sky irradiance (E_sky_thermal=0, E_sky_scattered=0 — lower fidelity
than SimpleAtmosphere for background terms); binary-invocation path never executed against
real MODTRAN (CU-065/067 already track); six ModtranConfig knobs schema-unreachable; parsed
tape7 columns (ground-reflected et al.) dropped; no cloud/rain capability in any model;
uplooking geometry rejected; LWIR aerosol Ångström extrapolation acknowledged-wrong with
unimplemented clamp. → **CU'd: CU-086** (re-audit after MODTRAN work lands; do not act now).

## Theme C — documentation drift (the systemic risk)

**F-20 (high, ✅/⚠) Four "Authoritative" docs describe unimplemented systems:**
`RADIANT_Source_Target_System.md` (ResolvedTarget contract + 70-parameter surface vs the
actual 38-parameter descriptor implementation); `RADIANT_Scan_Timing.md` (zero code, ✅);
`RADIANT_Spatial_Complete.md` (smear sources, ✅); `RADIANT_Metrics.md` (MetricResult/plugin
contract). Plus `RADIANT_GUI_Architecture.md` uses wrong parameter dot-paths throughout and
promises an unbacked <100 ms incremental-DAG contract, and `RADIANT_Optics.md` promises
aperture shapes/apodization/PupilDescription with no backend. → **CU'd: CU-079**
(re-banner as DEFERRED-design or reconcile, per doc).

**F-21 (medium, ✅) `scenarios/README.md` status table stale** (21 implemented scenarios
marked "stub") — it misled this audit's own charter. → **CU'd: CU-075**.

**F-22 (medium, ⚠) A shadow legacy source system** (CombinedSource, five resolvers,
ResolvedTarget...) is publicly exported from `radiant.source` but unwired to the chain —
notably its CombinedSource applies no atmospheric attenuation to solar, so binding the wrong
system produces wrong physics. Rule 27 violation. → **CU'd: CU-084**.

**F-23 (low, ⚠) Reference-data provenance:** detector QE and solar CSVs have no
manifest/citations; all 19 emissivity curves share one identical synthetic 84-point grid with
no committed generator; `data/atmospheres/README.md` names a nonexistent parameter and
module. → **CU'd: CU-080**.

**F-24 (medium, ⚠) Persona-cited complaints that registry marks FIXED** (Gap 37 nearfield,
Gap 42 lab mode, Gap 65 saturation, Gap 66 qe_table_path): scenario `gaps.md` files predate
the fixes — the registry's own "rerun after fix" discipline is the remedy; several reruns
are pending. → Planned (rerun list in Pre_GUI_Hardening_Plan).

## Theme D — validation soft spots (grouped sweep)

**F-25 (medium, ⚠, grouped).** Tolerance objects unvalidated at construction (empty gaussian
params silently sample std=0 — MC studies with fake zero-spread "uncertainty");
ConsistencyGroup over-spec check silently passes when the first parameter lacks a derivation
rule; `SpectralDataStore.add()` constant-extrapolates at DEBUG level; platform smear silently
degrades to zero when altitude/t_int missing (user explicitly set a velocity);
`readout.tdi_mode` and `detector.noise_regime` are free strings with no enum validation
(typo → silently wrong physics); digital-TDI branch has zero test coverage; IPC y-axis MTF
uses x pitch; `pixel_pitch_y_um` description promises a fallback that doesn't exist; CLI
provenance hardcodes version "0.1.0"; `read_noise_is_post_cds` is a dead parameter and
`cds_1f_suppression` is doc-only. → **CU'd: CU-076, CU-077, CU-085** (hardening sweep).

## Theme E — GUI groundwork assessment

**F-26 (informational).** PySide6 decision is Accepted; geometry_gui_v2 prototype is polished
(386 tests) and its Qt-free scene library lifts cleanly — but it exercises **zero**
signal-chain functionality (✅ verified: no `radiant.api` imports), so the production GUI's
core loop (param tree → evaluate → badges → plots) is unprototyped. The MATLAB-like script
window — the standing requirement in ~all 35 `gui_workflow.md` files — has no spike. The
prototype's own records are stale (slider panel claimed deferred but shipped; phase-2+
goldens missing vs C8 claim). → **CU'd: CU-082**; script-window spike sequenced in
Pre_GUI_Hardening_Plan. Latency result (0.22 s/run) means the GUI arch doc's incremental-DAG
machinery is **not** needed for v1 — simple full re-runs suffice (Declined,
owner-ratified 2026-07-11: incremental re-evaluation engine).

**F-27 (informational).** Persona GUI demands converge on six patterns: unit-aware
spreadsheet import with conversion preview; script/command window with unit-labeled echo;
importers with visual preview + loud fallback flags; matrix/batch builder with live progress
grid; saturation/well-status surfaced un-missably; coverage indicators for interpolated
atmosphere queries. Recorded as GUI-requirements input, no disposition needed.

---

## Disposition summary

| Disposition | Items |
|---|---|
| CU'd — new gaps | Gap 67–80 (14) |
| CU'd — new CUs | CU-072–086 (15) |
| CU'd — already tracked | F-19 partials (CU-011/065/067/070), Gap 21/38/39/58/60–64 triage confirmed |
| Planned | Pre_GUI_Hardening_Plan sequencing; scenario reruns (F-24); unit-registry + consistency-group expansion (F-09) |
| Declined (owner-ratified 2026-07-11) | Incremental re-evaluation engine for GUI v1 (F-26 — 0.22 s runs make it unnecessary); QE(T) cutoff-shift model pre-GUI (F-18); uplooking geometry support (out of current mission scope) |

Registry triage of pre-existing items (22 triaged: 1 gui_blocking, 6 fix_before_gui,
15 fine_after_gui) is preserved in the workflow bundle; the fix_before_gui set is folded
into the plan. Latency probe and persona coverage matrices: full agent returns archived in
the session workflow journal (`wf_a5ff4a64-721`).
