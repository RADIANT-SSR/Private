# 9.1 Gaps / Known Issues

- **B11 INCONCLUSIVE** — implied QE·τ = 0.091 is implausible for MCT SWIR; points at an
  unpublished, much-shorter SWIR integration time (~0.5 ms vs the 3.0 ms 20 m line
  time). Needs an ESA/Airbus source for the SWIR t_int to close.
- **B2 tension is an assumption artifact** — resolved by the implied-QE inversion
  (QE ≈ 0.20 at 493 nm, plausible front-illuminated CMOS + dichroic losses); a published
  MSI QE curve would convert this from hypothesis to closure.
- Full well is an analysis-mode value (500 ke-, never clips); the real MSI manages
  saturation per band via CTIA/CVF sizing — per-band effective wells are unpublished.
