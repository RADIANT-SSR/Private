# 9.4 GUI Workflow — OLI-2 multi-configuration study with per-element optics

1. **File → Open** → `oli2_30m_bands_study.yaml`. The file is a configuration set: a
   configuration tab strip (B1_CA … B9_Cirrus) appears above the signal-chain strip;
   the active tab opens on B4_Red.
2. **Optics stage** — the differentiator of this scenario. The element editor lists the
   full train (M1–M4, fpa_window, filter_butcher_block) with per-element R/T sources
   and Kirchhoff-derived ε (read-only, Rule 5). Open the
   **"Coating spectra — R / T / ε per element"** plot tab: one curve per optic — this
   is the per-optic model view (mirrors show R + ε; refractives show T). The
   **system transmission** plot shows the product; in Python,
   `plots.coating_spectra()` / `plots.system_transmission()`.
3. **Switch configuration tabs** and watch the spectral span follow each band's edges
   while the element document stays fixed — the composite butcher-block strip for the
   active band is visible in the coating plot at that band's wavelengths.
4. **Performance surface** — all eight configurations side by side; SNR per
   configuration against the walkthrough table (units: SNR [-], signal [e-]). Deltas
   are shown against the B4_Red baseline.
5. **Pan band**: File → Open → `oli2_b08_snr_ltyp.yaml` (standalone — Gap 103; the pan
   filter overlaps green/red and cannot join the shared composite). Its Optics view
   carries `filter_b08` instead of the composite.
6. Editing any **shared** value (e.g. `optics.aperture_diameter_m` [m]) moves all eight
   configurations at once; editing a **configured** value (e.g. `detector.qe_value` [-])
   in a stage form edits the displayed configuration only (ADR-0010 D-8).

GUI requirements exercised: configuration tab strip, element editor with spectral-CSV
sources, per-element coating plot, per-configuration Performance columns, study-file
open/refuse-as-plain-config behavior.
