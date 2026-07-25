# 9.2 Gaps / Known Issues

- QWIP in-band spectral response shape unpublished — the reason a CE bracket (raw
  band-average vs saturation-inverted) is carried instead of a single value.
- Electronics noise is a spec ceiling (<1000 e-), not a measured value; configs use the
  ROIC-typical 260 e- (optimistic edge of the Findings bracket).
- 'PSF undersampled' log on evaluation is physically true (Q ≈ 0.3 fast-optics design),
  not a config error; spatial metrics for TIRS need a finer psf_oversample if ever used.
