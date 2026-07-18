# Scenario 6.2 — Gaps and Friction

Issues encountered building/running the atmospheric model
intercomparison. Registry items mirrored into `docs/tracking/gaps.md`.

---

## RESOLVED before this scenario

### MODTRAN tape7 parser (was one of two primary gaps)
`radiant.atmosphere.modtran.Tape7Reader`, header-name-based column
mapping fixed by CU-066 (2026-07-10). This scenario is a real consumer
across all six profiles.

### Synthetic-data caveat (RESOLVED 2026-07-17)
The scenario originally ran on the synthetic A-block ("pipeline
demonstration, not a validated benchmark"). The real MODTRAN 6 run set
(2026-07-17, `modtran/real_runs/`) replaced it: the script auto-detects
the staged real data (synthetic remains the loud fallback for bare
clones), the walkthrough's results table and figures are regenerated
from the real runs, and the residuals are now a validated
SimpleAtmosphere-vs-MODTRAN measure. Headline finding: SimpleAtmosphere
over-responds to profile PWV (in-band τ spans 0.16–0.81 vs real
MODTRAN's 0.42–0.57; nearly exact at us_standard, ±40–60% at the
climate extremes). The "band-averaging divergence worth a follow-up"
below is thereby confirmed and quantified.

---

## OPEN

### No libRadtran parser or implementation at all
**Severity:** Medium (scenario-defining — the catalog wanted a 3-way
comparison, this delivers 2-way)
**Description:** no libRadtran output format parser exists anywhere in
this repo, and no real libRadtran run has ever been made against
RADIANT's outputs.
**Why not faked:** per the same policy established for MODTRAN
(`modtran/synthetic/README.md`) — hand-authoring plausible libRadtran
numbers would present a fabricated "independent" reference as if it
were real, defeating the entire point of a 3-way model intercomparison.
**Workaround:** none — this scenario is a 2-way comparison
(SimpleAtmosphere vs. MODTRAN-synthetic) until real libRadtran access
or a real parser + real run exists.

### No spectral residual / per-band error-analysis tool
**Severity:** Low-Medium
**Description:** the catalog wants "spectral residuals: RADIANT minus
MODTRAN" and "band-by-band error analysis: where does the simple model
break down?" This scenario computes in-band mean residuals only (the
table in walkthrough.md); no reusable residual/per-band tool exists.
**Workaround:** the script's own `np.interp`-based comparison is
ad-hoc, not a reusable RADIANT capability.

### Geometry deviates from the catalog's stated case
**Severity:** Low (deliberate, documented adaptation, not a defect)
**Description:** catalog specifies "10° off-nadir, 500 km path, midlat
summer" for a single profile; this scenario uses the run matrix's
A-block instead (nadir, 100 km sensor altitude, all six profiles) since
that data already existed and gives a broader profile sweep. A
10°-off-nadir/500 km A-block run does not exist in the current matrix.
**Workaround:** none needed — this is a legitimate reframing, not a
missing capability; noted for whoever revisits this scenario with real
MODTRAN data and might want the original geometry too.

---

## Friction / lessons

- **Full-well saturation silently erased the atmosphere signal on the
  first run.** `full_well_capacity_e=2e6` at 5 ms integration
  saturated (`well_status: clipped`) for every profile, at both
  atmosphere sources, producing *bit-identical* SNR (1414.029270461127
  to 12 significant figures) regardless of profile or atmosphere model
  — a strong tell that something was clipped, not that the atmosphere
  genuinely had zero effect. Fixed by reducing integration time to
  0.5 ms. Same lesson scenario 6.1 already logged
  ("LWIR staring FPAs are integration-time-limited") — worth promoting
  from a per-scenario lesson to a standing scenario-authoring checklist
  item: **always check `well_status` before trusting a "no effect"
  result.** (Recurred a third time in scenario 8.2 — escalated to
  Gap 65 in `docs/tracking/gaps.md`.)
- **SNR residuals do not track transmittance residuals.** Initially
  expected the two to move together; the extended-scene contrast
  term's target/background cancellation means they don't. Worth
  remembering when a stakeholder asks for "the atmosphere accuracy"
  without specifying which downstream metric they actually care about.
