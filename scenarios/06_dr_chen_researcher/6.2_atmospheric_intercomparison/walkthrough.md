# Scenario 6.2 — Atmospheric Model Intercomparison

**Persona:** Dr. Chen, researcher comparing RADIANT's parametric
atmosphere against an external radiative-transfer reference.
**Question:** How much does RADIANT's `SimpleAtmosphere` (Beer-Lambert,
tuned band fits) diverge from MODTRAN across the six named standard
atmosphere profiles, for the same nadir/100 km-sensor geometry — and
what does that divergence do to SNR?

**Status: pipeline demonstration, not a validated benchmark.** The
"MODTRAN" data is *synthetic* (HITRAN-line-by-line, not a real MODTRAN
run — see below). The comparison methodology and figures are real and
reusable; the specific residual numbers should not be treated as
validated until real MODTRAN data replaces A1–A6. **libRadtran is not
included at all** — no implementation or real output exists (see
gaps.md); fabricating plausible libRadtran numbers would defeat the
purpose of an intercomparison the same way a fake MODTRAN would.

**Deviation from the catalog:** the original entry specifies "10° off-
nadir, 500 km path, midlat summer" for one profile. The run matrix's
A-block instead gives all six profiles at a fixed nadir/100 km-sensor
geometry — a broader profile sweep using data that already existed
rather than re-deriving one path's data six ways. See gaps.md.

---

## Inputs (non-RADIANT)

| File | Represents |
|------|-----------|
| `modtran/synthetic/A1–A6.synthetic.tp7` | The "MODTRAN" transmittance datasets, one per profile — **synthetic**, not real MODTRAN. |

No Excel workbook — the six tape7 paths and their profile mapping are
the entire "vendor input" here, kept as script constants (matching
scenario 6.1's pattern for a self-contained, reproducible run).

---

## How RADIANT solves this

1. For each profile, `Tape7Reader(...).to_radiant_units()` converts
   the tape7 to a wavelength-domain transmittance + path-radiance CSV
   pair, fed to `atmosphere.model="tabulated"`.
2. The identical sensor config runs twice per profile — once with
   `atmosphere.model="simple"` at that profile, once with the
   tabulated MODTRAN-synthetic data — isolating the atmosphere term.
3. In-band mean transmittance and full-chain SNR are compared,
   profile by profile.

---

## Results

| Profile | τ SimpleAtmosphere | τ MODTRAN (synthetic) | τ residual | SNR SimpleAtmosphere | SNR MODTRAN | SNR residual |
|---------|---------------------|-------------------------|------------|------------------------|--------------|----------------|
| us_standard | 0.524 | 0.678 | +22.7% | 685.1 | 655.5 | −4.5% |
| tropical | 0.161 | 0.615 | +73.8% | 608.5 | 659.0 | +7.7% |
| midlat_summer | 0.269 | 0.639 | +57.9% | 629.7 | 651.0 | +3.3% |
| midlat_winter | 0.670 | 0.705 | +4.9% | 718.2 | 651.0 | −10.3% |
| subarctic_summer | 0.388 | 0.662 | +41.4% | 654.9 | 645.2 | −1.5% |
| subarctic_winter | 0.814 | 0.729 | −11.6% | 751.3 | 660.0 | −13.8% |

(residual = (MODTRAN − Simple) / MODTRAN, %)

- **Transmittance residuals are large and profile-dependent** (5% to
  74%), but **SNR residuals are much smaller and don't track them**
  (e.g. tropical has the *largest* τ residual, 74%, but only a 7.7%
  SNR residual). SNR depends on the *difference* between target and
  background path radiance in the extended-scene contrast term, and
  both terms are attenuated by the same τ — much of the transmittance
  discrepancy cancels in the signal ratio that actually drives SNR.
- **RADIANT's SimpleAtmosphere spans a much wider profile-to-profile
  transmittance range (0.16–0.81, 5×) than the synthetic MODTRAN data
  does (0.61–0.73, <20%)** — see `fig2`. The MWIR band's transmittance
  is dominated by the CO2 4.3 µm band, which is essentially saturated
  (opaque) in *every* profile (CO2 is well-mixed and doesn't vary by
  climate) — see `fig1`'s notch at 4.2–4.4 µm, identical across all
  six panels. That saturated core should dilute the profile-to-profile
  spread once it's folded into a band average; RADIANT's SimpleAtmosphere
  appears to weight the H2O-sensitive windows more heavily than the
  saturated CO2 core does in the synthetic data. This is a genuine,
  interesting divergence in band-averaging behavior — worth a follow-up
  investigation, not something this scenario resolves.

---

## Physics / modeling notes (house rule: explain the non-obvious)

- **The CO2 4.3 µm notch is identical across every profile** (`fig1`) —
  CO2 is well-mixed at ~415 ppm regardless of climate, so this is
  exactly the expected physical signature, and a good sanity check
  that the synthetic HITRAN-based generator is behaving correctly
  (see `modtran/synthetic/README.md` — `TOT TRANS` is the genuinely
  independent-physics column).
- **SNR is far less sensitive to atmosphere-model choice than raw
  transmittance is**, for an extended-scene contrast measurement. A
  scenario asking "how much does my *transmittance estimate* change"
  and one asking "how much does my *SNR prediction* change" have
  different answers here — worth remembering when scoping which metric
  actually matters for a given decision.
- **Full-well saturation silently erased the atmosphere signal on the
  first attempt** — see gaps.md's "Friction" section; the fix (shorter
  integration time) is the same lesson scenario 6.1 already logged
  ("LWIR staring FPAs are integration-time-limited").

---

## Gaps Identified

See `gaps.md`: libRadtran comparison, the geometry deviation from the
catalog's exact "10°/500 km" framing, and the SimpleAtmosphere
band-averaging divergence noted above.
