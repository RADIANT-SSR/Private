# Digital-Pixel ROIC (DROIC) Readout Capability — Development and Test Plan

**Status:** Active — §8 decisions ratified by the owner 2026-09-02 (D2 amended in discussion: DN follows the residue flag).

**Date:** 2026-09-02
**Gap:** 117 (`docs/tracking/gaps.md`)
**Category:** C overall (physics implementation); Phase 0 is Category B (schema/abstraction), Phase 3 is Category D (integration + GUI).

**Read first:**
`docs/architecture/RADIANT_Master_Architecture.md`,
`docs/architecture/RADIANT_Signal_Chain_Architecture.md`,
`docs/architecture/RADIANT_Parameter_System.md`,
`docs/architecture/RADIANT_Detector_Complete.md`,
`docs/architecture/RADIANT_Metrics.md`,
`docs/architecture/RADIANT_Testing_Validation.md`,
`docs/architecture/RADIANT_GUI_Architecture.md` (Phase 3 only).

---

## 1. Objective

Add a **digital-pixel ROIC** (DROIC / digital focal-plane-array) readout architecture to
the readout stage: an in-pixel comparator + $N$-bit counter with charge-subtraction
reset, optionally with analog residue readout. This is the architecture of the MIT
Lincoln Laboratory DFPA lineage and Senseeker-class commercial parts, and it is how
modern high-dynamic-range focal planes reach effective well depths of
$10^8$–$10^9\ \mathrm{e^-}$ in a tactical pixel pitch.

The governing insight: **everything upstream of the readout stage is unchanged.** Photon
collection, QE, dark current, and detector-side noise are identical; what changes is the
charge-to-number conversion — saturation mechanism, quantization noise, and the TDI
mechanism. The new physics is confined to `src/radiant/readout/`, dispatched by a new
architecture parameter, with the existing analog path untouched and remaining the
default (zero golden-result change).

**In scope (v1):**
- Counting-well model: effective full well $Q_\mathrm{eff} = 2^{N} \cdot Q_\mathrm{pkt}$,
  saturation at counter rollover.
- Quantization-noise branch: $\sigma_q = Q_\mathrm{pkt}/\sqrt{12}$ without residue
  readout; with residue readout, the residue passes through the **existing** analog ADC
  quantization model (bits + gain apply to the residue signal, full scale
  $= Q_\mathrm{pkt}$).
- Comparator dead-time flux ceiling: max count rate $f_\mathrm{max}$ gives a second
  saturation bound $f_\mathrm{max} \cdot t_\mathrm{int} \cdot Q_\mathrm{pkt}$.
- Count-domain TDI: `readout.n_tdi` scaling unchanged; TDI mis-registration MTF retained
  (it is a sampling-timing effect, not a charge-transfer effect — §4, decision D4).
- DN output semantics: DN is the digitization of the total signal
  $Q_\mathrm{pkt} \cdot n_\mathrm{counts} + Q_\mathrm{res}$, following the residue flag —
  residue read on: combined word
  ($\mathrm{DN} = n_\mathrm{counts} \cdot 2^{M} + \mathrm{DN}_\mathrm{res}$, $M$ =
  `readout.adc_bits`, gain $Q_\mathrm{pkt}/2^{M}$ e-/DN); residue off: bare counter
  (gain $Q_\mathrm{pkt}$ e-/DN). DN and the noise budget are self-consistent in both
  configurations — §8 D2.
- GUI surface for the new parameters (Phase 3).

**Out of scope (v1)** — each becomes a Findings-Log line or Gap at Phase 0 close if the
owner wants it tracked: up/down counting and in-pixel background subtraction (modulo
arithmetic as a feature); in-pixel filtering / count-shift orthogonal-transfer TDI MTF
modeling beyond the retained mis-registration term; comparator threshold non-uniformity
as a residual-NU noise term (v1 assumes NUC-calibrated, §6 assumptions); ROIC
self-emission / glow as a background term; per-pixel packet-size dispersion.

---

## 2. Physics model

### 2.1 Count process

Integrated charge $Q_\mathrm{int}$ (e-, from the existing spectral-integration →
detector chain) converts as:

$$n_\mathrm{counts} = \left\lfloor Q_\mathrm{int} / Q_\mathrm{pkt} \right\rfloor,
\qquad Q_\mathrm{res} = Q_\mathrm{int} \bmod Q_\mathrm{pkt}$$

- $Q_\mathrm{pkt}$ — charge packet per count (`readout.count_packet_e`, e-/count).
- Counter saturates at $2^{N}-1$ counts ($N$ = `readout.counter_bits`); v1 treats
  rollover as saturation (clip + the existing saturation warning path), not modulo (§8 D1).

### 2.2 Noise terms

| Term | Analog path (existing) | Digital-counting path (new) |
|------|------------------------|------------------------------|
| Shot, dark, detector terms | unchanged | unchanged (act on $Q_\mathrm{int}$) |
| Read noise | `readout.read_noise_e_rms` | applies to residue read only when `residue_readout = true`; comparator/counter chain contributes `readout.read_noise_e_rms` interpreted as the per-frame counting-chain noise (§8 D3) |
| kTC reset | CDS-gated as today | per-packet reset noise $\sqrt{n_\mathrm{counts}} \cdot \sigma_{kTC}$ enters **only** if CDS is off — same `readout.cds_enabled` gate |
| ADC quantization | $\sigma_q = (g_{e/DN})/\sqrt{12}$ on full signal | **without residue read:** $\sigma_q = Q_\mathrm{pkt}/\sqrt{12}$; **with residue read:** existing ADC model applied to the residue (full scale $Q_\mathrm{pkt}$) |

Noise enters the budget through the existing `NoiseTerm` machinery — no new noise-summation
path. Each new term is a named budget entry (`counting_quantization`,
`packet_reset`), inspectable via `result.inspect()` like every existing term.

### 2.3 Saturation

$$Q_\mathrm{sat} = \min\!\left(2^{N} \cdot Q_\mathrm{pkt},\;
f_\mathrm{max} \cdot t_\mathrm{int} \cdot Q_\mathrm{pkt}\right)$$

with $f_\mathrm{max}$ = `readout.max_count_rate_hz` (None ⇒ no dead-time ceiling, first
term governs). Both bounds clip through the existing well-saturation warning path
(`check_well_saturation`) so downstream metrics see one consistent saturation signal.
`adc_well_match_ratio` and the ADC/well mismatch warning are meaningless under counting
and are suppressed for this architecture (the counter *is* the ADC).

### 2.4 What is deliberately unchanged

- The MTF product path: detector aperture, diffusion, IPC, jitter, smear MTFs are
  upstream/parallel and untouched. TDI mis-registration MTF is retained (D4). **No new
  spatial term ⇒ no Rule 4 dual-path work.**
- Spectral integration, EE_box application, regime logic: untouched (counting happens
  after spectral collapse, per Rule 8).

---

## 3. Parameter schema (`readout/_schema.py`)

| Name | dtype | Unit | Default | Notes |
|------|-------|------|---------|-------|
| `readout.architecture` | enum | — | `"analog_well"` | `analog_well` \| `digital_counting`; mode as data |
| `readout.counter_bits` | int | — | 16 | bounds [1, 32] |
| `readout.count_packet_e` | float | e-/count | None (required when counting) | bounds (0, 1e7] |
| `readout.residue_readout` | bool | — | True | residue ADC uses existing `adc_bits`/`gain_e_per_dn` semantics scoped to $Q_\mathrm{pkt}$ full scale |
| `readout.max_count_rate_hz` | float | Hz | None | None ⇒ no dead-time ceiling |

Validation (Rule 16): counting-only parameters set while `architecture = "analog_well"`
raise an actionable `ParameterEnumError`-family error (over-specification, same posture as
Rule 5); `count_packet_e` required when counting; `full_well_capacity_e` is **ignored
with a logged warning** under counting is *not* acceptable (Rule 17) — it is rejected if
explicitly set (schema default passes silently).

---

## 4. Module layout (Rule 19)

| File | Computation |
|------|-------------|
| `readout/counting_well.py` | effective well + dead-time ceiling → $Q_\mathrm{sat}$, count conversion |
| `readout/counting_quantization.py` | quantization noise branch (packet vs residue-ADC) |
| `readout/stage.py` | dispatch on `readout.architecture` (modified; analog path code untouched) |

`saturation.py` and `adc.py` are not modified — the counting branch calls its own modules
and reuses `check_well_saturation` with the counting-derived bound. Stage outputs gain
`counts`, `count_packet_e`, `effective_well_e`, `saturation_mechanism`
(`"rollover"` \| `"dead_time"` \| `"none"`).

---

## 5. Phases and gates

Each phase is one task, one branch, one merge, full gate battery (schema change in
Phase 0 ⇒ **full GUI suite runs on every phase** per the `_schema.py` rule).

- **Phase 0 — Schema + dispatch skeleton (Category B).** Parameters, validation,
  architecture dispatch with `digital_counting` raising `NotImplementedError`-style
  actionable error until Phase 1 lands. Lock-step doc updates (Rule 20):
  `RADIANT_Parameter_System.md`, `RADIANT_Detector_Complete.md` readout sections.
  Serialization round-trip + failure-mode tests.
- **Phase 1 — Core physics (Category C).** `counting_well.py`,
  `counting_quantization.py`, Level-0 tests written first (Rule 18). Truth anchors §7.
- **Phase 2 — Chain integration (Category C/D).** Stage dispatch live, noise budget
  entries, saturation signal, integration tests, golden regression (analog default ⇒
  zero golden drift, asserted explicitly). CHANGELOG entry (Rule 29 b/c) + gap 117 →
  DELIVERED.
- **Phase 3 — GUI (Category D).** Readout panel: architecture selector, counting
  parameter group shown only under `digital_counting` (contextual-relevance convention),
  display units per the GUI display-units rule. GUI live-review loop applies: **no merge
  before the owner has seen the running branch.** `gui_workflow.md` addendum for the
  first DROIC scenario.

A validation scenario (Senseeker-class MWIR DROIC vs the same FPA on an analog ROIC —
DR, SNR-vs-flux, NEDT comparison) rides with Phase 2 as the workflow-visible test.

---

## 6. Assumptions (v1)

- **Comparator threshold uniformity:** packet size is one global value; per-pixel
  dispersion assumed NUC-calibrated. *Breaks:* residual spatial noise at high flux;
  *detected:* documented limitation, out-of-scope note.
- **Counter is noiseless:** digital state carries no noise; all electronic noise is in
  the packet-reset and residue-read terms. *Breaks:* never at this modeling level.
- **Poisson charge, deterministic thresholding:** count statistics inherit shot noise on
  $Q_\mathrm{int}$; no comparator metastability model. Valid for
  $Q_\mathrm{pkt} \gg$ comparator noise.
- **Uniform in-pixel flux over $t_\mathrm{int}$** for the dead-time bound (worst-case DC
  comparison, not pulse-shaped).

---

## 7. Numerical truth anchors (Phase 1 exit criteria)

1. **Hand calculation** — effective well: $2^{16} \times 5000\ \mathrm{e^-/count} =
   327.68\ \mathrm{Me^-}$; saturation flux with $f_\mathrm{max}$; exact expected values.
2. **Analytic vs Monte Carlo** — quantization noise: uniform-residue $\sigma_q =
   Q_\mathrm{pkt}/\sqrt{12}$ against a numeric floor-model simulation over a flux sweep
   (`rel=1e-2`), including the low-flux regime where the uniform-residue assumption
   degrades (regime notes required).
3. **Literature** — MIT Lincoln Laboratory DFPA publications (Tyrrell et al., IEEE 2009;
   Kelly et al., Lincoln Laboratory Journal 2013): published counter depth / packet size /
   dynamic-range figures reproduced within the paper's stated precision.

Plus the Category C dimensional audit (e- → counts → DN chain) and cross-model
consistency: `digital_counting` with $Q_\mathrm{pkt} \to$ full-well-equivalent, residue
on, must converge to the analog path's SNR within stated tolerance in the shot-limited
regime.

---

## 8. Owner decisions — ratified 2026-09-02

| # | Question | Ruling |
|---|----------|--------|
| D1 | Counter rollover: clip-as-saturation vs modulo (up/down counting is the real part's feature) | **Clip in v1**; modulo/up-down counting deferred as its own gap, filed at Phase 0 |
| D2 | DN semantics under counting | **DN follows the residue flag**: DN = digitized total ($Q_\mathrm{pkt} \cdot n + Q_\mathrm{res}$). Residue on → combined word ($n \cdot 2^{M} + \mathrm{DN}_\mathrm{res}$, gain $Q_\mathrm{pkt}/2^{M}$ e-/DN); residue off → bare counter (gain $Q_\mathrm{pkt}$ e-/DN). *Amended from the original counter-only proposal: counter-only DN is quantized in packet steps, contradicting the noise budget whenever the residue is read. The owner's framing — total = well depth × counter + final well reading — is this model.* |
| D3 | `read_noise_e_rms` meaning under counting: reuse as counting-chain per-frame noise vs new parameter | **Reuse** — one fewer parameter; documented reinterpretation |
| D4 | TDI mis-registration MTF under count-domain TDI: retain or zero | **Retain** — timing mis-registration exists regardless of charge vs count transfer; it stays the one MTF-only term |
| D5 | Phase 3 GUI in this plan vs folded into the next GUI expansion plan | **In this plan** — small surface, one panel group |
