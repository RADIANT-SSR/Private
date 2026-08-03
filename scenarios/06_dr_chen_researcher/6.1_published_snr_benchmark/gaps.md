# Scenario 6.1 — Gaps and Friction

Issues encountered building/running the published-datasheet benchmark.
Registry items are mirrored into `docs/tracking/gaps.md`.

---

## RESOLVED during this scenario

### D*/NEP/NETD converters (was the primary gap)
The catalog flagged "no D*/NETD/NEP → component noise converters".
**Built as `radiant.performance.detectivity`, `.nep_electrons`, `.nep_netd`**
(committed ac59315): D* ⇄ NEP, NEP ⇄ noise electrons, NEP ⇄ NETD. 13
Level-0 tests, hand truth anchors + a full D*→NEP→NETD round-trip. This
scenario (and 4.5) are the first consumers.

---

## Friction / lessons

- **A datasheet D* implies TOTAL noise, not read noise.** The first
  attempt set the chain's read-noise parameter to the σ_e derived from D*
  (≈180 000 e⁻ at 8 ms) — which (a) blew the read-noise bound and (b) is
  physically wrong: the D*-implied σ_e is the *total* (BLIP-dominated)
  noise, not the electronic read noise. The correct benchmark configures
  the detector *components* (dark, read, QE) and compares the chain's
  *computed* total noise (converted to D*) against the datasheet. Noted so
  the next author doesn't repeat it.
- **LWIR staring FPAs are integration-time-limited.** At f/2 on a 300 K
  scene the well saturated in ~50 µs; the benchmark uses 30 µs (well 63 %).
  Same lesson as the T3/T4 thermal scenarios — size t_int to the flux.
- **System D* < datasheet peak D*** for a background-limited detector. The
  −13 % residual is physics (BLIP), not a model error; the scenario reports
  it honestly rather than tuning the datasheet to match.

*Figures refreshed 2026-08-02 from the unmodified runner (previous vintage
2026-08-02, pre-CU-321); the well fraction and D* residual moved by ~0.1 point
with CU-321's height-resolved emission temperature on the CU-224 path-radiance
term. Both verdicts (PASS/PASS) and the −13 % BLIP interpretation are
unchanged.*

---

## Framework observations (no new gap)

- The converters live in `performance/` as pure functions; a future
  `radiant.api` convenience (`benchmark_against_datasheet(...)` →
  residual report) would package the chain-run + convert + compare recipe,
  but the primitives are all present. Low priority; not filed as a gap
  (parallel to Gaps 45/46's ergonomics framing).
