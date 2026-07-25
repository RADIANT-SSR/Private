# 9.3 GUI Workflow

1. **File → Open** `modis_b20_nedt_300k.yaml` (the band without the well artifact).
2. **Source stage**: 300 K blackbody; open the spectral table and compare the band
   radiance against the published L_typ (0.45 W/m²/sr/µm for B20) — the Part-1 anchor
   check, visible directly in the GUI.
3. **Run**; read NEDT (~10 mK) from Performance outputs; well fill ~35%.
4. Open a B31 config to see the **Gap 101 artifact deliberately preserved**: the
   saturation banner + 100% well fill are the representational gap discussed in
   gaps.md — useful as a teaching case for the detector-class limitation.
5. Optional: pin `ds_dt_e_per_K` (Spectral Integration outputs) and verify
   NEdT ≈ sigma_total_e / ds_dt_e_per_K.
