# 9.4 GUI Workflow — the per-configuration Elements showcase (OLI-2, nine bands, one file)

This is the acceptance walk for **configured element rows** (Gap 103 v1.1): nine Landsat 9
OLI-2 bands in one study, each mounting its own interference filter. Ten minutes, one file.

1. **Open the study.** From this folder:
   `radiant gui oli2_all_bands_study.yaml` (or File → Open on it). A study file loads as a
   configuration set — the CLI and File → Open use the same reader, so there is no
   "open it as a study" mode to choose.

2. **Read the selector band.** Across the top: nine tabs — `B1_CA`, `B2_Blue`, `B3_Green`,
   `B4_Red`, `B5_NIR`, `B6_SWIR1`, `B7_SWIR2`, `B8_Pan`, `B9_Cirrus` — each carrying its own
   accent hue (the same hue identifies that configuration everywhere, in both themes). The
   file opens with **B4_Red** active (it is also the baseline). At the right of the band
   sits **⚙ Manage…**.

3. **Evaluate.** Press **Evaluate (F5)**. All nine configurations run in one pass, active
   configuration first. Expect nine SNR values from ~139 [-] (B9 Cirrus) to ~496 [-]
   (B2 Blue) — the walkthrough table.

4. **Go to the Elements tab.** Stage strip → **Optics** → **Elements**. The table shows
   **B4_Red's** train: rows `M1`, `M2`, `M3`, `M4`, `fpa_window`, `filter_b04`, with each
   row's R or T source and its Kirchhoff-derived ε read-only (Rule 5). The note above the
   table says whose train you are looking at.

5. **Spot the configured row.** Row 5's name reads **`filter_b04` C** — a red **C** after
   the name, the same configured badge the parameter surfaces use. Hover it: *"configured —
   one entry per configuration; editing edits B4_Red only."* Rows 0–4 have no C: the four
   mirrors and the window are shared by all nine bands and are stated once in the file.

6. **Select row 5 and watch the coating detail.** The **Coating detail — R / T / ε on the
   coating's own grid** pane draws `filter_b04`'s transmittance over the curve's full stored
   extent: a super-Gaussian passband with 50% points at 0.636 / 0.673 µm [µm].

7. **March the filter across the spectrum.** Click through the configuration tabs —
   `B1_CA` → `B2_Blue` → … → `B9_Cirrus` — with row 5 still selected. The Elements table
   re-renders each band's *effective* train, so row 5's name steps `filter_b01` →
   `filter_b02` → … → `filter_b09`, and the coating-detail passband marches from 0.435 µm
   (coastal aerosol) out to 2.294 µm (SWIR 2) — nine strips spanning 0.43–2.3 µm. Rows 0–4
   never move: same mirrors, same window, every band.

8. **Stop at `B8_Pan`.** The pan band is an ordinary member of this study, not a special
   case: row 5 is `filter_b08` (0.503–0.676 µm, overlapping green and red — the overlap that
   made a single shared filter element impossible), and on the **Detector** and **Spectral
   integration** stages its pixel pitch reads **18 µm** and its integration time **1.8 ms**,
   each carrying the configured C badge. Ordinary configured scalars, no second file.

9. **Edit one band's entry (commit-on-edit, D-8).** Still on `B8_Pan`, row 5, change
   `temperature_K` from 210 to 215 and press Enter. The edit commits immediately — no Apply
   button — and the evaluation follows. Switch to `B7_SWIR2`: its row 5 still reads 210 K.
   You edited **one configuration's entry**, which is the whole point of a configured row.
   Type 210 back in before saving — an element edit is not a scalar parameter, so it
   records no undo step (documented GUI limitation).

10. **Configure / un-configure a row.** Select row 4 (`fpa_window`) and press
    **Configure across configurations…** (also on the right-click menu). The row gains its
    C and nine identical entries seeded from the shared one — nothing changes until you edit
    one, so the SNR column does not move. Right-click → *Un-configure row (keep B1_CA's
    entry)…* collapses it back to one shared entry and states which entries are discarded.
    Do that now: the study ships with exactly one configured row (row 5).

11. **Manage the set.** Press **⚙ Manage…** to add, rename, reorder, or remove
    configurations. The cap is 12; with nine bands there are three slots left, and the
    add-row refuses at 12 with the cap quoted.

12. **Read the Performance matrix.** Stage strip → **Performance**. Nine columns, one per
    configuration, in file order and in the selector's accent hues, with the grouped metric
    rows down the side (SNR [-], signal [e-], noise [e- RMS], …), each cell carrying its
    unit from the metric registry. The row labels stay frozen while the columns scroll.
    Cells are plain values — delta-vs-baseline and best-per-metric live on the scripting
    `compare` surface, not here. Check the SNR row against the walkthrough table.

13. **Cross-check against the standalones.** Each band's number must equal its
    `oli2_b0N_snr_ltyp.yaml` standalone exactly; `python scripts/check_all_bands_parity.py`
    asserts `rel < 1e-9` for all nine (measured: 0.00e+00 [-] every band).

**GUI requirements exercised**: study-file open from CLI and File → Open; 9-tab selector
band with per-configuration accents; **Elements tab with a configured element row (red C),
per-configuration effective-train rendering, and commit-on-edit D-8 editing**;
configure/un-configure from button and context menu; coating-detail pane following the
active configuration; configured scalars on Detector and Spectral-integration stages;
configuration-manager dialog with the 12-cap; 9-column Performance matrix with frozen
labels and baseline deltas.
