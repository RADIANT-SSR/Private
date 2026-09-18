# Manual Editorial Audit — Master Findings List

**Status:** Complete
**Date:** 2026-09-18
**Charter:** `Audit_Plan.md` (this folder). Owner-triggered 2026-09-17; scope defaults ratified ("go").
**Auditors:** one editorial-review pass per volume (full source read + full rendered-PDF page-by-page inspection), a cross-volume consistency analysis over the four style fingerprints, and orchestrator hand-verification of the physics-accuracy findings.
**Fix tracking:** CU-370 (family). This report is the checklist source; findings are cited below by ID.

---

## 1. Summary

**134 findings**: 21 High, 66 Medium, 47 Low — 13 cross-volume (X), 32 in Volume I,
26 in Volume II, 31 in Volume III, 32 in Volume IV.

The suite's fundamentals are strong: units discipline on reader-facing numbers is
near-perfect (the owner's hard rule held), the evaluate/run verb split and the
config-file/configuration/study glossary are applied consistently across all four
volumes, math and tables render cleanly in the large majority of pages, and the
build filters correctly strip the "In RADIANT." / "Record:" / persona anchor
paragraphs everywhere they were designed to reach.

The defects cluster into five themes:

1. **One build bug corrupts numbers in three volumes** — every degree sign inside a
   math span typesets as "ř" (X-01). Highest-value single fix in the report.
2. **Two printed physics recipes are wrong** while the code is right: the mixed-train
   appendix irradiance formula is dimensionally inconsistent (I-005) and the tape7
   conversion is printed a factor 10⁴ off (III-001). Both hand-verified.
3. **Repo-process language leaks past the strip filters** wherever it is embedded in
   ordinary prose rather than anchor paragraphs — CU/Gap/ADR/Rule numbers, commit
   SHAs, file paths, owner-ratification dates — in all four volumes (X-06 and its
   per-volume instances). The Theory intro's claim that "the typeset manual omits the
   pointers" is currently false (I-011).
4. **The typeset page is not yet print-safe at the edges**: wide generated tables
   truncate or collide (III-002/005), result matrices and one runner command overflow
   or clip at the margin (IV-020/021), and ~26 repo-relative `.md` hyperlinks ship as
   dead links (X-03).
5. **Suite-wide style splits** nobody legislated: `e-` vs `e⁻`, US vs UK dialect,
   heading capitalization, thousands separators (X-04/05/09/10) — each individually
   small, together they read as four books by four authors.

PDF page citations use each auditor's convention (physical page unless the volume
report states printed folio); source `file:line` cites are authoritative.

**Shipped-build note:** the audited PDFs (built 2026-09-17, post anchor-strip
filters) are 85 pp. (Theory) and 87 pp. (User's Guide) versus the 91/97 pp. recorded
at Gap 131 closure — those registry numbers are phase-merge snapshots, not defects;
recorded as a Findings-Log line, not a finding.

---

## 2. Cross-volume findings (X)

[X-01] High | RENDER | build (math Unicode mapping) — Degree signs inside `$...$`
typeset as "ř" (r-caron) throughout Volumes I, III, IV (I-001, III-003, IV-022);
° in prose renders correctly. Fix once in the build: map `°` in math (or preprocess
to `^\circ`); add a regression check alongside the existing missing-glyph guard.

[X-02] Medium | RENDER | build (title-page template) — Every title page prints the
version twice: "v0.1.0 (v0.1.0)" (I-008, III-018; same template feeds all four
volumes). Emit the parenthetical only when git-describe differs from the version.

[X-03] High | RENDER | suite-wide (26 instances) — Repo-relative `.md` hyperlinks in
bound sources ship as dead colored links: same-volume links that should be chapter
references, cross-volume links (`theory/noise_model.md:212`,
`theory/calibration_model.md:461` → `../guides/parameter_reference.md`), and links to
guides bound in **no** volume (`atmosphere_selection.md`, `trade_studies.md` — from
`guides/configuration.md:399,511,531`, `guides/ug_defining_scene.md:225`,
`guides/ug_sweeps_trades.md:191`, `guides/tech_data_libraries.md:218`). Mechanism
confirmed: the build filters drop anchor paragraphs but never rewrite links. Fix as
policy: name the owning volume/chapter in prose; optionally add a build check that
fails on `.md` link targets.

[X-04] Medium | FORMAT | suite-wide — Electron-unit glyph split against the canonical
table (`notation.md` declares `e-`): Vol I ch. 3 drifts to `e⁻` (I-032), Vol II once
(II-016), Vol III Part 1 tables (III-031), Vol IV mixes ~105 `e⁻` against ~80 `e-`,
sometimes within a paragraph (`examples_digests.md:121-123`). Normalize to `e-`
everywhere outside quoted program output.

[X-05] Medium | FORMAT | suite-wide — Dialect split: Vol I/III/IV write US English
("graybody", "-ize") while Vol II is dominantly UK ("grey", "-ise/-our") with -ize
intrusions (II-012), and Vol IV mixes grey/gray. Owner picks one dialect (US is the
majority and matches "graybody" as a term of art); sweep prose, exempting verbatim
GUI strings and data identifiers (`paint_grey`).

[X-06] High | EXTRANEOUS | suite-wide — Repo-internal process content embedded in
ordinary prose survives into every shipped volume: CU/Gap tags mid-sentence, commit
vintages, ADR cites, CLAUDE.md rule numbers, module/test paths, owner-ratification
language (instances: I-003/004/007/012/013/024, II-002/004/005/006, III-027/028,
IV-004/005/006/018). The strip filters work as designed — they remove marker
*paragraphs* only; the leakage is prose-embedded and needs source rewording (or a
ruled expansion of the filter conventions). The Theory intro's "the typeset manual
omits the pointers and keeps the physics" is false until this lands (I-011).

[X-07] Medium | RENDER | figure pipeline — Full-window GUI captures set at text width
render in-app text at ~3–5 pt (II-014, IV-027) — illegible in print — while
panel/region grabs in the same volumes read well. Adopt panel grabs where prose
discusses one pane; reserve full-window shots for anatomy figures at full-page size.

[X-08] Medium | ACCURACY | Vols I, IV — Hardcoded "§N" cross-references written
against source-file numbering break under the rendered `--number-sections` numbers
(I-010; IV-028: text cites "§2"/"§8" where the built chapter numbers run 13.2–13.9).
Reference by section name or resolve at build time.

[X-09] Medium | FORMAT | suite-wide — Heading-capitalization conventions differ by
volume: I uses sentence-case sections (except ch. 3's Title Case, I-022), II uses
sentence-case H2/H3, III sets H2 in Title Case with H3 drifting both ways within one
chapter, IV uses sentence-case H2. Legislate one convention (sentence-case sections
is the suite majority) and sweep.

[X-10] Low | FORMAT | suite-wide — Number-formatting drift: thousands separators
appear as thin-space groups, commas, and plain spaces across (and within) volumes
(I fingerprint, IV-012); percent spacing drifts "0.1 %" vs "0.4%" (Vol I) and
"11.1 %" (Vol IV); range dashes spaced in IV ("3.5 – 5.0 µm") vs unspaced elsewhere.
Pick one convention per class; quoted program output exempt.

[X-11] Low | RENDER | build — Straight double quotes throughout while apostrophes are
typographic (II-025; same Pandoc settings feed all volumes) — enable smart double
quotes, guarding verbatim blocks.

[X-12] Medium | RENDER | build — Markdown alt text is dropped: every figure renders
bare, unnumbered and uncaptioned, while prose leans on "the figure" (II-013; Vol IV
figures likewise bare). Enable implicit-figures so alt text becomes numbered captions.

[X-13] Low | FORMAT | `guides/configuration.md:461-462` — Prose writes "3.5--5.0 um"
/ "8.0--12.0 um": bare "um" in running text where the house unit is µm (CLI unit
tokens like `radiant convert 18 um m` are legitimately exempt), plus ASCII `--`
(see III-008 for the volume's `---` em-dash residue). Write "3.5–5.0 µm".

---

## 3. Volume I — Theory Manual (32 findings: 7 High, 19 Medium, 6 Low)

[I-001] High | RENDER | `geometry.md:46,50,77-78,102,106` + `atmosphere_models.md:347,364,371,615,623,648,823` (PDF pp. 16–19, 28, 39–44, 47, 49) — Every degree sign inside a math span (`$\eta = 30°$`, `$\sec 48.2°$`) prints as "ř"; dozens of numeric anchors visibly corrupted. Fix: `^\circ` in math or a build mapping (X-01).

[I-002] High | RENDER | `atmosphere_models.md:781-782` (PDF p. 46) — The L_sky display equation overflows the right margin; its trailing "≡ 0" is clipped at the page edge. Fix: break the equation or set the `L_beyond ≡ 0` clause as prose.

[I-003] High | RENDER | `performance_metrics.md:6-9` (PDF p. 73) — Chapter intro ships repo-internal citations verbatim: "(`track_a3_noise_metrics_derivation.md`)" and "(CLAUDE.md Rule 17 carve-out / ADR-B)". Fix: reword to reader-neutral phrasing.

[I-004] High | EXTRANEOUS | `performance_metrics.md:240-249` (PDF p. 76) — The "Metric selection and the registry" section is repo machinery (`performance/_schema.py`, `registry.py`, test paths) serving no analyst. Fix: reduce to two sentences on metric groups and the spatial-path skip.

[I-005] High | ACCURACY | `radiometric_model_mixed_train.md:176-220` (PDF pp. 79–80) — **Hand-verified.** The upstream-element irradiance recipe `E_FP,i = L·G_i/A_FP·τ_i` with `G_i = A_stop·cosθ/z²` is dimensionally inconsistent (G_i is a solid angle, so the product yields W/m⁴/µm): the emitting element's area is missing. Fix: restate G_i as an étendue (A_elem·A_stop·cosθ/z²) or add A_elem,i explicitly.

[I-006] High | ACCURACY | `radiometric_chain.md:113,165,218,271,333,397,457,514-515,578,653,720,784,854` vs `references.md` (PDF p. 84) — Twelve citation keys used in ch. 3 have no References entry (Siegel & Howell; Kirchhoff 1860; Wolfe & Zissis; NIST ITS-90; Press et al.; Kopp & Lean 2011; ASTM E490; Wehrli 1985; Nicodemus 1977; Phong 1975; Lewis 1994; Janesick 2001). Fix: add the entries.

[I-007] High | EXTRANEOUS | `atmosphere_models.md:99-103,205-274,626-675,835-841,1081-1119` (PDF pp. 35–51) — Extensive change-history narrative ships in print (CU numbers, commit SHAs, the CU-335/336 re-fit archaeology, owner-approval dates, dev-deck provenance) despite the chapter's own "organized by model rather than by change history" promise. Fix: keep physics + current calibrated values; move history to the repo-side records the filters already strip.

[I-008] Medium | RENDER | PDF p. 1 — Title page prints "v0.1.0 (v0.1.0)" (X-02).

[I-009] Medium | RENDER | PDF pp. 5–10 — The running header across the whole Notation chapter reads "Contents" (front-matter chapter never sets its header mark). Fix in template.

[I-010] Medium | RENDER | `notation.md:12`, `atmosphere_models.md` passim, `geometry.md:239`, `spatial_model.md:341` — In-prose "§N" cross-references keep source numbering that mismatches the rendered numbers ("the table in §1" renders beside 0.1; "§2.7" renders as 4.2.7) and collide visually with external-document "§" pointers (X-08). Fix: chapter-qualified names or build-resolved refs.

[I-011] Medium | ACCURACY | `introduction.md:219-222` (PDF p. 15) — The intro claims "The typeset manual omits the pointers and keeps the physics," contradicted throughout the PDF (see X-06 instances). Fix: make it true (preferred) or soften the claim.

[I-012] Medium | EXTRANEOUS | `geometry.md:10,150-159,198-199`; `spatial_model.md:75-79,378-381`; `atmosphere_models.md:1121`; `performance_metrics.md:227-229` — Code/module paths embedded in prose ship in print (`core/constants.py::R_EARTH_M`, `core/solar_geometry.py::solar_declination_deg`, "nedl.py, nedr.py … Gap 78"). Fix: reword so the physics statement stands alone; paths belong in the stripped anchor paragraphs.

[I-013] Medium | EXTRANEOUS | `atmosphere_models.md:323,368,409,453,624,675,841,955,974,1056` — Eleven references to "the parity document §N," a repo validation record absent from the shipped suite. Fix: name it once in plain language or route through stripped provenance paragraphs.

[I-014] Medium | EXTRANEOUS | `noise_model.md:171,210-213`; `calibration_model.md:459-463` — Dangling suite pointers: heading "Frame timing (Conventions §4)" cites a repo doc; two "See Parameter Reference" sections point at a document not in this volume (stripped link left bare text). Fix: point at Volume III by name, or drop.

[I-015] Medium | ACCURACY | `notation.md:41` — The angular-spatial-frequency row is self-contradictory: canonical unit "cy/mrad" vs its own definition ν_ang = νf (which yields cy/rad) — a factor-10³ mismatch in the suite's canonical table. Fix: unit → cy/rad, or definition → νf/1000 with a mrad quoting note.

[I-016] Medium | ACCURACY | `performance_metrics.md:77-95` vs `notation.md:106` — §8.3 uses η_sys / η = 0.7 for efficiency and an undefined Q_b in BLIP detectivity; notation reserves η for the look angle and defines neither. Fix: define at point of use and note the reuse in notation §9.

[I-017] Medium | ACCURACY | `radiometric_chain.md:469,503-507` — T_sun declared 5778 K, then the numeric anchor computed "for a pure 5772 K blackbody Sun" with no reconciliation (code model named `blackbody_5778`). Fix: explain the IAU 5772 K anchor and quantify the offset, or recompute at 5778 K.

[I-018] Medium | FORMAT | `radiometric_chain.md:113,165,218,271,397,578,720,784` vs `references.md:3` — Ch. 3 cites bare "[Holst]" (~8×) where every other chapter writes "[Holst 2008]"; the References chapter's own example "[Holst §3.2]" matches neither. Fix: normalize to [Holst 2008].

[I-019] Medium | FORMAT | `atmosphere_models.md:1125-1141` vs `references.md:3-4` (PDF p. 52) — The atmosphere chapter carries its own full-citation References list (six entries), contradicting the back matter's "one list, chapters cite by key only"; its final bullet is a self-pointer to the References chapter. Fix: fold the six citations into `references.md` as keys.

[I-020] Medium | VOICE | `radiometric_model_mixed_train.md` (whole file; PDF pp. 77–83) — Appendix A breaks the volume's register: ASCII-art equations in unlabeled code fences, no derivations/pitfalls/anchors structure, spec-sheet bullets, sentence-case title. Fix: re-typeset equations as Pandoc math and align structure, or badge explicitly as an implementation recipe.

[I-021] Medium | ACCURACY | `radiometric_model_mixed_train.md:92-97` vs `notation.md:200-213` — The appendix re-enters truncated constants (h = 6.626e-34 …) against the front matter's exact CODATA values and its "never re-entered" rule; its Planck form omits the per-µm Jacobian ch. 3 calls the subject's biggest bug source. Fix: drop the constants line (cite notation §8); state λ units/Jacobian.

[I-022] Medium | FORMAT | `radiometric_chain.md:33,60,117,169,224,275,337,461,519,657,724,788,858` — Ch. 3 section headings are Title Case; every other chapter uses sentence case (X-09). Fix: convert.

[I-023] Medium | ACCURACY | `radiometric_chain.md:866-875` (PDF p. 32) — The "How the Foundations Feed the Chain" table's Detailed-in column says "atmosphere docs" / "performance docs" (vague repo pointers) where the intro's parallel table correctly says "Ch. 4"/"Ch. 8"; ADR tags ship in the same table. Fix: chapter cross-references.

[I-024] Medium | EXTRANEOUS | `spatial_model.md:161-163,178-183,296-299,338-347`; `performance_metrics.md:115-123,176-179` — CU/Gap tags ride mid-prose ("(CU-074)", "(cell-area-overlap, CU-188)", "Fit-envelope gating (CU-166)", "IIRS status (Gap 100)"). Fix: keep the physics statements; move IDs to stripped provenance paragraphs.

[I-025] Medium | GRAMMAR | `spatial_model.md:135` (PDF p. 55) — Typo "unbobscured" → "unobscured".

[I-026] Medium | VERBOSE | `atmosphere_models.md:626-675` (PDF pp. 43–44) — §2.11 spends ~700 words and a four-corner table narrating a *declined* alternative (layered downwelling temperature), burying the one-line shipped model (D = sec 48.2°). Fix: compress to 2–3 sentences + the decisive number.

[I-027] Low | FORMAT | `radiometric_model_mixed_train.md:35,101,142,237,251,280,357` — Internal "Part N" heading names are off-by-one against the rendered A-numbering (TOC: "A.3 Part 2 — …"). Fix: drop "Part N —" from headings.

[I-028] Low | FORMAT | `notation.md:144` vs `spatial_model.md:191-194` — Notation defines RMS angular jitter as σ_j; the spatial chapter writes σ_θ (and focal-plane σ) without referencing it. Fix: align.

[I-029] Low | ACCURACY | `notation.md:202-213` — Banner "All constants are the CODATA 2018 exact values" covers a table that includes the IUGG mean Earth radius (not CODATA). Fix: scope the banner.

[I-030] Low | ACCURACY | `notation.md:169` vs `calibration_model.md:183-186` — k defined as *post-NUC residual* PRNU fraction in notation but used as *pre-correction* PRNU fraction in the calibration one-point model. Fix: add the second sense or rename one.

[I-031] Low | RENDER | PDF p. 82 — Appendix Part-7 comparison table breaks after a single orphan row at the page bottom. Fix: nudge the break.

[I-032] Low | FORMAT | `notation.md:37-39` vs `radiometric_chain.md:794-844` — `e-` vs ch. 3's `e⁻` (X-04); percent-spacing drift "0.1 %" vs "0.4%" (X-10).

---

## 4. Volume II — User's Guide (26 findings: 3 High, 11 Medium, 12 Low)

PDF cites are physical pages of the 87-page shipped build.

[II-001] High | ACCURACY | `ug_defining_sensor.md:195,266` (PDF pp. 46–47) — Both pointers say "chapter 4, §6 covers the sampling-phase modes," but ch. 4 §6 is "Configurations," and the pixel-phase modes (`average`/`centered`/`worst_case`/`specified`) are documented nowhere in the volume. Fix: correct the reference or add the missing subsection.

[II-002] High | RENDER | `ug_troubleshooting.md:165,173` (PDF p. 78) — "The Kirchhoff constraint of Rule 5…" / "the over-specification Rule 5 forbids…" — repo rule numbers in the shipped PDF. Fix: state the physics constraint; drop the rule number.

[II-003] High | RENDER | `figures/gui/ug_platform_workspace.png` via `ug_defining_sensor.md:172` (PDF p. 45) — The shipped Platform screenshot shows an in-app advisory note containing "v1-minimal (owner ratified…)… (ADR-0006 §4 / CU-122)… post-v1 task". The GUI string itself leaks process language to every operator. Fix: reword the GUI advisory (live-review rule applies), then recapture.

[II-004] Medium | EXTRANEOUS | `ug_introduction.md:120` (PDF p. 7) — "Chapters 1–6 — this batch — take you…" leaks the authoring-batch process. Fix: delete "— this batch —".

[II-005] Medium | EXTRANEOUS | `ug_defining_scene.md:46` (PDF p. 33) — "This is the flexibility the personas need" — internal product-development vocabulary. Fix: "the flexibility different disciplines need".

[II-006] Medium | EXTRANEOUS | `ug_installation.md:8-9` (PDF p. 9) — Repo doc-path pointers ("The repository's `README.md`… `docs/guides/quickstart.md`…") in the shipped manual, line-breaking badly in print. Fix: volume-internal pointer (chapter 3).

[II-007] Medium | RENDER | `ug_defining_scene.md:225` (PDF p. 39), `ug_sweeps_trades.md:191` (p. 69), `ug_yaml_roundtrip.md:8` (p. 70) — Cross-references render as unresolvable pointers: literal "atmosphere_selection.md"/"trade_studies.md" filenames and a live-colored link targeting `configuration.md` (X-03). Fix: keep the Volume III/IV half of each sentence; drop the `.md` link.

[II-008] Medium | ACCURACY | `ug_quickstart_tour.md:83` (PDF p. 15) — "Everything above is also a two-line file and one command," followed by a ~15-line four-section file. Fix: "a short file".

[II-009] Medium | ACCURACY | `ug_quickstart_tour.md:49-51` (PDF p. 13) — Ch. 3 explains NIIRS's `n/a — not computed for this run` as declining out-of-range GIQE-5 extrapolation, but ch. 4 §7 (`ug_core_concepts.md:214-217`) and ch. 9 §2 (`ug_running_results.md:99-104`) define that exact string as the group-switched-off state with `n/a (<reason>)` as the out-of-range form. Fix: align the three (or fix the GUI string if the screenshot behavior is intended).

[II-010] Medium | ACCURACY | `ug_core_concepts.md:146` (PDF p. 22) — Target angular extent given as θ = √A_t/R, contradicting `notation.md:107,122` (θ = √A_t/R_s; R is the mean Earth radius). Fix: R_s.

[II-011] Medium | FORMAT | `ug_troubleshooting.md:54` et al. — One panel, three names: "Messages panel" (`ug_core_concepts.md:221`; `ug_main_window.md:140,166`; `ug_running_results.md:153`), "Messages rail" (`ug_troubleshooting.md:54,150,204`; `ug_defining_scene.md:68`; `ug_configuration_sets.md:181`; `ug_defining_sensor.md:385`), "Messages list" (`ug_main_window.md:130`); ch. 9 uses two forms. Fix: standardize on "Messages panel".

[II-012] Medium | GRAMMAR | `ug_defining_sensor.md:61,302` — -ise/-ize mix in an otherwise British-English volume ("finalized", "digitizes" vs "digitised"/"quantisation"/"internalising") (X-05). Fix: one convention; exempt verbatim GUI/CLI strings.

[II-013] Medium | RENDER | PDF, all 25 figures (e.g. pp. 13, 32, 63) — Figure captions (alt text) dropped at build; every figure bare and unnumbered while prose says "the figure"; one image reused twice (pp. 63, 79) (X-12). Fix: implicit-figures captions.

[II-014] Medium | RENDER | PDF pp. 13, 14, 22, 25, 32, 36–38, 41, 43, 45–48, 50, 56, 60 — Full-window captures at text width put in-app labels at ~4–5 pt (X-07). Fix: cropped-region captures or full-page anatomy shots.

[II-015] Low | EXTRANEOUS | `ug_configuration_sets.md:44` (PDF p. 52) — The quoted 13th-configuration refusal carries "(ADR-0010 D-E)" — verbatim GUI output, so the *manual* is accurate; the shipped product string cites an internal ADR. Fix in the GUI string; manual inherits on recapture.

[II-016] Low | FORMAT | `ug_defining_sensor.md:325-327` — "e⁻ RMS"/"e⁻/DN" against the volume's (and notation's) "e-" (X-04).

[II-017] Low | FORMAT | `ug_quickstart_tour.md:44` — Edit Config button set in code font where chs. 5/11/Appendix A set it bold. Fix: bold.

[II-018] Low | VOICE | `ug_sweeps_trades.md:1,6`; `ug_yaml_roundtrip.md:3` — Chapters 2–9 say "the application"; chapters 10–11 switch to "the GUI" (including a title). Fix: "the application".

[II-019] Low | ACCURACY | `ug_introduction.md:29` — Stage table credits "sixteen noise terms" to the Detector stage; ch. 4 §1 and the ch. 3 budget assign several to Readout/Calibration. Fix: "the noise-term budget" or "most of the sixteen".

[II-020] Low | VERBOSE | `ug_main_window.md:51-66,174-190,199-262` — Health-dot table + evaluate-loop rules repeated nearly verbatim in ch. 9 (`ug_running_results.md:9-35,196-207`); ch. 5 §7's menu map duplicates most of Appendix A. Fix: one authoritative copy per fact, cross-reference the other.

[II-021] Low | VERBOSE | `ug_troubleshooting.md:165-174` — §3.6 states "the over-specification is unrepresentable rather than refused" as both its opening and closing sentence. Fix: cut one.

[II-022] Low | RENDER | `figures/gui/ug_atmosphere_workspace.png` via `ug_defining_scene.md:200` (PDF p. 38) — Capture clips the "Background path" plot mid-axes; reads as broken. Fix: recapture scrolled or crop above.

[II-023] Low | RENDER | PDF p. 46 — FPA-strip verbatim block wraps, stranding a lone "]" on its own line. Fix: shorten the quoted strip line.

[II-024] Low | RENDER | PDF p. 87 — Appendix A affordances table breaks so its final row sits alone on the otherwise-blank last page. Fix: nudge the break.

[II-025] Low | RENDER | PDF volume-wide (pp. 13, 21, 25, 34, 53, 66) — Straight double quotes vs typographic apostrophes (X-11).

[II-026] Low | FORMAT | `ug_defining_sensor.md:63` (PDF p. 42) — Heading "Transmission — one home for τ_opt" carries the literal underscore form in display type; notation sets $\tau_{\mathrm{opt}}$. Fix: math form or "optical throughput"; `τ_opt` only when quoting GUI strings.

---

## 5. Volume III — Technical Reference (31 findings: 4 High, 16 Medium, 11 Low)

Bound-verbatim Part 3 specs and the generated parameter reference were audited for
outright errors and render only (charter boundary 2).

[III-001] High | ACCURACY | `tech_conventions.md:130-132` and `tech_external_data.md:46,50-51` (PDF pp. 13, 93–94) — **Hand-verified.** The tape7 conversion is printed $L(\lambda)=L(\nu)\,\nu^2/10^4$ with the claim that "the 10⁴ also carries the cm⁻² → m⁻² area conversion" — but the Jacobian ν²/10⁴ and the area factor 10⁴ cancel to a net ν², which is what `modtran.py` correctly implements (`jacobian = nu * nu`). As printed, the relation is a factor 10⁴ low. The same confusion sits in `src/radiant/atmosphere/modtran.py:17-21` (module docstring; the `to_radiant_units` docstring at lines 815–820 explains it correctly). Fix both chapters + the docstring.

[III-002] High | RENDER | `parameter_reference.md:17` (PDF p. 47) — `geometry.los_angular_rate_rad_s` description truncates at "…LOS direction rotates," — unescaped pipes in `|v_rel,perp|` split the table cell; both Gap-111 doors and the 1 % agreement rule are silently dropped. Fix: `gen_param_reference.py` escapes `|` in cells; regenerate.

[III-003] High | RENDER | `tech_conventions.md:57` (PDF p. 12) — `$0.1° = 1745$ µrad` renders "0.1ř" (X-01).

[III-004] High | RENDER | PDF pp. 81–85 (`tech_errors.md` §§3–6 sources fine) — Error-taxonomy tables let long class names overflow the Class column into Bases, mashing names ("ArchitectureOverSpecificaReadoutValidationError"). Fix: allow identifier breaks or widen the column style.

[III-005] Medium | RENDER | PDF pp. 46, 48, 50, 61, 66, 68–70, 73 — Parameter Reference Default column collides with Input Unit when the default is wide ("1.5707963rad", "**required**m", "1000000.0Hz"). Fix: widen/gap the generated-table style.

[III-006] Medium | RENDER | `parameter_reference.md:270` (PDF p. 78) — Unescaped `*` in the `performance.metrics.sampling` description italicizes mid-cell text and swallows the wildcards ("gsd_," "q_,"). Fix: escape `*` in generated cells (same generator family as III-002).

[III-007] Medium | RENDER | PDF pp. 57, 60, 63 — Long unbreakable tokens in generated cells overflow or hyphenate mid-identifier ("radi-ant.api…"). Fix: break at `_`/`.` without hyphens for code tokens.

[III-008] Medium | FORMAT | `configuration.md:408 (heading),201,417-532`; `scripting.md:784,820-826` (PDF pp. 2, 29, 39, 43–45) — Literal ASCII `---` prints as three hyphens in a heading, the TOC, prose, and a See-Also list; the rest of the volume uses true em dashes. Fix: `—` in source.

[III-009] Medium | ACCURACY | `configuration.md:34` (PDF p. 36) — Annotated YAML enumerates `# simple | exo | tabulated | modtran`, omitting `interpolated` — the bundled-library backend §5.13 of the same chapter recommends. Fix: add it.

[III-010] Medium | ACCURACY | `configuration.md:113-127` (PDF p. 38) — The "minimum required set" disagrees with the generated reference's **required** markers (lists five defaulted parameters as required; omits schema-required `optics.f_number`). Fix: align with the schema or retitle "recommended explicit set".

[III-011] Medium | UNITS | `tech_overview.md:33` (PDF p. 6) — Stage table says calibration publishes "bias budget [e⁻]"; `BiasTerm.value_frac` is a dimensionless fractional radiance bias, per notation §7. Fix: "[--] (fractional ΔL/L)".

[III-012] Medium | ACCURACY | `tech_overview.md:123,131`; `tech_conventions.md:32` (PDF pp. 7–8, 11) — MTF written as a function of $f$ where notation reserves $f$ for focal length and defines MTF(ν). Fix: ν in Parts 1–2.

[III-013] Medium | ACCURACY | `tech_errors.md:41-47` (PDF p. 79) — The `ParameterBoundsError` example raises on `sensor.detector.operating_temp` — a dot-path violating the volume's own "no `sensor.` root" convention and naming a nonexistent parameter — and the "rendered" message that follows shows a different parameter. Fix: a real dot-path, message matching.

[III-014] Medium | ACCURACY | `RADIANT_Parameter_System.md:270` (PDF p. 124) — Bound spec: "The **nine** parameter namespaces…" omits `calibration`, which the same document lists 60 lines earlier and `configuration.md` §5.1 counts as ten. Fix: lock-step spec correction to ten.

[III-015] Medium | ACCURACY | `RADIANT_Testing_Validation.md:615` (PDF p. 152) vs `tech_errors.md:92-116` (p. 80) — The bound spec asserts a single-tier `RadiantError` hierarchy; ch. 7's generated taxonomy documents a two-tier hierarchy plus ~20 classes the spec's tree lacks. Fix: refresh the spec's §8.5 (stale against the code it claims to match).

[III-016] Medium | RENDER | `RADIANT_Signal_Chain_Architecture.md:200` (PDF p. 105) — `**EE_box**` inside a code span prints the asterisks literally in the Point-regime signal equation. Fix: drop the asterisks.

[III-017] Medium | RENDER | PDF pp. 100–101, 121–123, 152 — Wide ASCII blocks in the bound specs hard-wrap with ↪ continuation marks, scrambling two-column alignment (stage annotations orphaned; exception tree split mid-bracket). Fix: smaller code size or pre-wrap at build.

[III-018] Medium | RENDER | PDF p. 1 — "v0.1.0 (v0.1.0)" (X-02).

[III-019] Medium | UNITS | `parameter_reference.md:180,182,197,223` (PDF pp. 69–72) — Input Unit prints "---" for parameters with physical units (`detector.dsnu_e_rms` [e- RMS], `detector.flicker_K` [e-²], `detector.prior_signal_e` [e-], `readout.full_well_capacity_e` [e-]); unit-string drift "m2" vs "m^2" between two area parameters. Fix: set `input_unit` in the owning `_schema.py` defs; regenerate.

[III-020] Medium | RENDER | PDF pp. 3–4 — TOC entries for two-digit ch. 12 subsections collide with their titles ("12.10Schema Introspection…"). Fix: widen the TOC number box.

[III-021] Low | ACCURACY | `parameter_reference.md:11` (PDF p. 46) — `geometry.circular_orbit` description says "mode V6 entry"; the published mode taxonomy has no V6. Fix: stale `_schema.py` description.

[III-022] Low | ACCURACY | `tech_overview.md:209-210` (PDF p. 9) — Lists three `__all__` names, then says "those two names carry stability guarantees". Fix: "Sensor and RadiantError carry stability guarantees".

[III-023] Low | ACCURACY | `tech_overview.md:105` (PDF p. 7) — EE_box called "Encircled energy"; the suite defines it as *ensquared* energy. Fix: "ensquared".

[III-024] Low | ACCURACY | `RADIANT_Signal_Chain_Architecture.md:384`; `RADIANT_Testing_Validation.md:544-546,591-607` (PDF pp. 110, 150–151) — Bound-spec examples use the retired `sensor.` super-prefix that the Parameter System spec in the same Part forbids. Fix: update example paths.

[III-025] Low | ACCURACY | `RADIANT_Parameter_System.md:199-200,875-882` (PDF pp. 122, 136) — `calibration.scheme` enum listed without `three_point`; "Loading precedence" shows a ladder that doesn't match the shipped 5-level precedence in `configuration.md` §5.7. Fix: refresh both passages.

[III-026] Low | ACCURACY | `RADIANT_Testing_Validation.md:31` vs `:45` (PDF pp. 138–139) — Prose says the Planck integral runs "0.01–100 µm"; the code four lines below integrates 0.1–200.0 µm. Fix: align prose.

[III-027] Low | EXTRANEOUS | `configuration.md:83,254,470-471` (PDF pp. 37, 40, 44) — "(Gap 119)", "(CU-349 — they arrive with pip install…)", "raised from 8 to 12 in 2026-09" in user-manual prose (X-06). Fix: strip or footnote.

[III-028] Low | EXTRANEOUS | `tech_overview.md:12`; `scripting.md:25`; `configuration.md:512` (PDF pp. 5, 16, 45) — Parts 1–2 cite repo paths before the Part-3 preface (p. 99) explains that convention. Fix: explain at first use or use document titles.

[III-029] Low | ACCURACY | `configuration.md:399,511,531`; `tech_data_libraries.md:218` (PDF pp. 42–43, 45, 92) — Links to the Atmosphere Selection and Trade Studies guides render as internal-style links with no target in this PDF (X-03). Fix: name the owning volume.

[III-030] Low | GRAMMAR | `tech_cli.md:132` (PDF p. 32) — Sample output "…(canonical: 4.0 )" — stray space from an empty unit string; verbatim CLI output, so the blemish is the CLI's (Findings-Log line filed). No manual edit needed unless the CLI string changes.

[III-031] Low | FORMAT | `tech_overview.md:26-33`; `tech_conventions.md:26-27` — Part-1 tables use "e⁻" and ASCII "[m^(-2/3)]" against notation's "e-" and $m^{-2/3}$ (X-04).

---

## 6. Volume IV — Worked Examples & Validation (32 findings: 4 High, 14 Medium, 14 Low)

[IV-001] High | ACCURACY | `examples_cookbook.md:473-474` (PDF p. 156) — **Hand-verified.** Recipe 6's "Seen in anger" describes the detection matrix as "six targets × three atmospheres × three sensors"; chapter 7 documents 12 × 4 × 3 = 144 cells. Fix: correct the counts.

[IV-002] Medium | ACCURACY | `examples_case_maritime_mwir.md:37,118-121` (PDF pp. 33, 36) — Inputs table says slant range is "Derived… — not entered" and step 2 says `target_range_m` is greyed/derived, yet the same step lists it among the five `config`-badged rows. Fix: reconcile.

[IV-003] Medium | ACCURACY | `examples_scripting.md:177-181` vs `examples_cookbook.md:88-90` (PDF pp. 25, 149) — Two different saturation-warning texts are both quoted as the same config's actual output; one vintage is stale. Fix: re-run one chapter and quote the current text in both.

[IV-004] Medium | EXTRANEOUS | `examples_digests.md:9`; `examples_scenario_index.md:7`; `examples_validation.md:440,481` (PDF pp. 101, 143–144, 158) — Owner-process language in print: "The owner's ruling (Q3, 2026-09-16)", "owner-run MODTRAN 6 run matrix", "the drift is recorded in the findings log". Fix: reader-neutral phrasing.

[IV-005] Medium | EXTRANEOUS | `examples_digests.md` (CU-062/160/161/166/178/188/355/362, Gap 42–128, ADR pass-throughs); `examples_case_detection_matrix.md:427`; `examples_case_irst_level_arm.md:210,285` (PDF pp. 67, 98, 104–134) — ~25 bare CU/Gap/ADR tracker identifiers in reader-facing prose with no shipped referent (X-06). Fix: self-contained phrases, or a one-line key in front matter.

[IV-006] Medium | EXTRANEOUS | `examples_validation.md:107,367,612`; `examples_digests.md:1470` (PDF pp. 137, 142, 146, 128) — Repo coding-rule numbers cited bare ("(Rule 9)", "(Rule 5)", "(Rule 4)"). Fix: spell out the invariant.

[IV-007] Medium | FORMAT | `examples_digests.md:662-666` (PDF p. 113) — Digest 3.3's Key inputs is a prose paragraph; all 38 other digests use the compact table the compendium legislates. Fix: recast as the standard table.

[IV-008] Low | FORMAT | `examples_digests.md:176-180,727-732,1095-1098` vs `1046-1048,1141-1144,1241-1243` — Walkthrough-contradiction notes appear as standalone italic paragraphs in three digests but inline parentheticals in six others; the spec says "one clause". Fix: inline form in 1.4, 3.4, 5.4.

[IV-009] Medium | FORMAT | `examples_gui.md:128,158,169`; `examples_cookbook.md:27,193,442`; `examples_validation.md` (PDF throughout) — NEDT/NEdT/NETD spelling drifts across the volume and within GUI walkthrough 2; notation canonicalizes NEDT. Fix: NEdT only in quoted mission literature, NETD only in the vendor-datasheet chapter, NEDT elsewhere.

[IV-010] Low | UNITS | `examples_gui.md:244`; `examples_case_detector_shootout.md:96` (PDF pp. 15, 45) — Dark rate quoted "50000 1/s" / "280 868 1/s", transcribing the GUI's ambiguous display unit where the canonical unit is e-/s. Fix: e-/s in prose; note the GUI display quirk once if intended.

[IV-011] Low | FORMAT | `examples_case_irst_level_arm.md:149,306`; `examples_case_pass_planning.md:34,188` — "deg" and "°" mixed within single chapters. Fix: one rule (e.g. "deg" for entered parameters, "°" for derived/tabulated), stated once.

[IV-012] Low | FORMAT | `examples_case_maritime_mwir.md:36` vs `examples_case_nedt_reconciliation.md:172` vs `examples_validation.md:131` — Thousands separators: thin-space, comma, and plain-space styles across chapters (X-10). Fix: one convention; program output exempt.

[IV-013] Low | ACCURACY | `examples_gui.md:162`; `examples_case_detector_shootout.md:182` (PDF pp. 13, 48) — "MRT" used as a headline metric, never expanded, absent from notation's acronym table. Fix: expand at first use; add to notation.

[IV-014] Low | VOICE | `examples_gui.md:162-164` — Walkthrough 2 reports NIIRS as "`yes — outside GIQE-5`" with no value, unlike every other chapter (value + flag); reads as if "yes" were the rating. Fix: state the numeric NIIRS or "no value displayed".

[IV-015] Low | VOICE | `examples_scenario_index.md:59-63` vs `examples_digests.md:789` — Persona role drift: "Lisa, analyst" vs "Lisa, Detection/Targeting Analyst". Fix: one title everywhere.

[IV-016] Low | GRAMMAR | `examples_digests.md:148` — "(The concept started MWIR; …)" — missing "as". Fix: "started as MWIR".

[IV-017] Medium | VERBOSE | `examples_validation.md:604-636` (PDF pp. 146–147) — The "What validation does not yet cover" caveat — the passage V&V readers most need — is one ~30-line blockquote with First…Fifth buried inline. Fix: numbered list.

[IV-018] Low | EXTRANEOUS | `examples_gui.md:457-459` (PDF p. 21) — Chapter close points at `scenarios/GUI_EXERCISE_INDEX.md` and "the three headless gates" — repo CI mechanics. Fix: "the repository's scenario exercise index".

[IV-019] Low | FORMAT | `examples_scripting.md:52,146` et al. — Program-output fences carry no language tag, against the house rule (`text` satisfies it). Fix: tag them.

[IV-020] High | RENDER | `examples_case_detection_matrix.md:248-311` (PDF pp. 63–65) — The three detection-range matrices — the chapter's centerpiece — overflow the code-block width and hard-wrap with ↳ marks: every row's arctic_clear cell drops to its own line; "not detectable" splits across lines. Fix: narrow the printed tables ("—" for not-detectable, shorter padding) or smaller mono size.

[IV-021] High | RENDER | `examples_case_maritime_mwir.md:308-309` (PDF p. 42) — The one-line runner command runs past the physical page edge; the ".py" tail is clipped, so a print reader copies a broken command. Fix: backslash continuation as other chapters do.

[IV-022] High | RENDER | `examples_case_irst_level_arm.md:149-151` (PDF p. 94) — "η = 89.7755ř", "φ = 0.44896ř" — degree-in-math mojibake (X-01); the bold text-mode "90.2245°" on the same line is correct.

[IV-023] Medium | RENDER | `examples_scripting.md:477-518` (PDF p. 30) — Configuration-set "Focus metrics" output exceeds the block width; the LWIR_long column lands on a ↳ continuation line for every metric. Fix: trim quoted output to ~92 columns.

[IV-024] Medium | RENDER | `examples_case_nedt_reconciliation.md:168-179,209-222` (PDF pp. 86–87) — NEDT comparison and gap-analysis tables wrap with ↳ marks ("Cannot ↳ explain alone" on every row). Fix: shorten rows or reduce mono size for these blocks.

[IV-025] Medium | RENDER | `examples_digests.md:1529-1530` (PDF p. 129) — A source-line wrap beginning "+ quantization." renders as a stray bullet item in digest 7.5's Regime. Fix: rewrap so no line begins with "+ ".

[IV-026] Medium | RENDER | PDF pp. 69, 77, 83 — Chapter display titles hyphenate mid-word ("Wavefront-Error Bud-get", "Pub-lished Datasheet", "Mea-sured NEDT"). Fix: disable hyphenation in the chapter-title style.

[IV-027] Medium | RENDER | `examples_gui.md` figures and all GUI-led case studies (PDF pp. 9–15, 20, 35–41, 45–48, 52–57, 93–97) — Full-window screenshots at text width leave in-window text at ~3 pt while the prose claims the dock is "widened so the full dot-path… is legible"; panel grabs (pp. 18, 56) show the workable alternative (X-07).

[IV-028] Medium | RENDER | `examples_validation.md:60,463-475,631`; `examples_scenario_index.md:28,82-85` (PDF pp. 136, 143–144, 146, 158, 160) — Hardcoded "§N" cites don't survive compilation: text cites "§§1-4"/"§2"/"§8" while the built chapter numbers run 13.2–13.9 (X-08). Fix: section names or build-resolved refs.

[IV-029] Low | RENDER | `examples_scenario_index.md:1` (PDF pp. 3, 158) — Heading doubles the word: "Appendix A. Appendix — Scenario Index". Fix: retitle the source "Scenario Index".

[IV-030] Low | RENDER | `examples_digests.md:100-101,188-189,1342-1343` (PDF pp. 103–104, 109, 125, 127) — Long "Where to go deeper" code paths break so the sentence period lands orphaned at line start (". A GUI baseline ships.") in five digests. Fix: keep path + following sentence on one source line.

[IV-031] Low | RENDER | `examples_case_irst_level_arm.md:128-129` (PDF pp. 94, 100) — The committed IRST schematic has the `h_s` pill's unit clipped at the viewport edge (narrated in prose instead of recaptured); the chapter's closing pointer sits orphaned alone on p. 100. Fix: regenerate the figure; nudge the break.

[IV-032] Low | RENDER | `figures/gui/case_maritime_atmosphere.png` (PDF p. 35) — Atmosphere panel grab crops the background-path plot mid-axes; target-path y-axis labels collide. Fix: recapture.

---

## 7. Cross-volume style comparison

Synthesized from the four per-volume fingerprints. "OK" = appropriate genre
difference, no action; flagged cells reference findings.

| Dimension | Vol I | Vol II | Vol III (Parts 1–2) | Vol IV | Verdict |
|---|---|---|---|---|---|
| Person & mood | Impersonal declarative | Second person, "the application" | Impersonal + imperative | Persona narration + imperative walkthroughs | OK — matches each genre |
| Dialect | US (graybody, -ize) | UK (-ise/-our, grey) w/ -ize intrusions | US | Mixed grey/gray | X-05: pick one |
| Section heading case | Sentence case (ch. 3 drifts Title) | Sentence case | **Title Case H2**, H3 drifts | Sentence case | X-09: Vol III is the outlier |
| Electron unit | e- (ch. 3 e⁻) | e- (one table e⁻) | e- (Part-1 tables e⁻) | Heavily mixed | X-04: normalize to e- |
| Em dashes | True — | True — | ASCII `---` residue in two files | True — | III-008 |
| Scientific notation | ×10ⁿ prose / e-notation output | same | same | same | OK — consistent |
| Thousands separators | Mixed (commas vs thin space) | GUI-precision quoting | Commas, rare | Thin-space / comma / space by chapter | X-10: pick one |
| Cross-reference form | "§N.M" + "Chapter N" | "chapter N, §M" | Quoted chapter names + md links | Names, no numbers | OK per volume; fix X-03/X-08 |
| Admonitions | Bold run-in labels, no boxes | Bold run-in, no boxes | Bold run-in, no boxes | Blockquote + bold run-in | OK — no boxes anywhere, consistent |
| evaluate / run | evaluate = compute; run = chain run | evaluate = chain pass; run = CLI/noun | evaluate canonical; run = CLI | evaluate = chain; run = scripts/sweeps | OK — genuinely consistent |
| config vocabulary | "configuration" only | Legislated glossary (ch. 8) | Legislated glossary (§5.14) | Follows the glossary | OK — consistent |
| FPA / detector | detector / focal plane | FPA + part/preset | FPA presets / detector stage | FPA + part; focal plane | OK |
| Tool name | RADIANT / "the model" | "the application" (chs 2–9), "the GUI" (10–11) | RADIANT / `radiant` | RADIANT / "the window" | II-018 only |
| Units on numbers | Complete | Complete (zero UNITS findings) | Two findings (III-011/019) | Two findings (IV-010) | Strong suite-wide |

---

## 8. Dispositions (Rule 28)

- **CU'd → CU-370 (family)**: all findings except the two below. Suggested working
  batches inside the family checklist:
  **B1 build/template** (one fix, four volumes): X-01, X-02, X-11, X-12, I-009,
  III-020, IV-026;
  **B2 generator + schema** (then regenerate): III-002, III-005, III-006, III-007,
  III-019, III-021;
  **B3 accuracy** (physics/consistency corrections): I-005, I-006, I-015, I-016,
  I-017, I-021, I-029, I-030, II-001, II-008, II-009, II-010, II-019, III-001,
  III-009, III-010, III-011, III-012, III-013, III-014, III-015, III-022, III-023,
  III-024, III-025, III-026, IV-001, IV-002, IV-003, IV-013;
  **B4 leakage/extraneous + link policy**: X-03, X-06, I-003, I-004, I-007, I-011,
  I-012, I-013, I-014, I-023, I-024, II-002, II-004, II-005, II-006, II-007, III-027,
  III-028, III-029, IV-004, IV-005, IV-006, IV-018;
  **B5 page-fit/overflow**: I-002, I-031, II-023, II-024, III-004, III-017, IV-020,
  IV-021, IV-023, IV-024, IV-025, IV-030, plus the §-ref repairs X-08 / I-010 /
  IV-028;
  **B6 style conventions — owner picks flagged**: X-04, X-05, X-09, X-10, X-13,
  I-018, I-019, I-020, I-022, I-026, I-027, I-028, I-032, II-011, II-012, II-016,
  II-017, II-018, II-020, II-021, II-026, III-008, III-031, IV-007, IV-008, IV-009,
  IV-011, IV-012, IV-014, IV-015, IV-016, IV-017, IV-019, IV-029, I-025;
  **B7 figures** (GUI strings first — live-review rule — then recapture): X-07,
  II-003, II-013, II-014, II-015, II-022, IV-027, IV-031, IV-032.
- **Findings Log** (lines appended in this PR): III-030 (CLI stray space — a CLI
  string blemish, not a manual edit); the Gap-131 page-count snapshots vs the
  post-filter rebuilds (85/87 pp. shipped vs 91/97 pp. recorded — historical
  snapshot, no registry edit).
- **Declined**: none.

## 9. Verification and method notes

- Each volume: every source file read in full; every rendered PDF page inspected
  (rendered to images; text layer swept in parallel). The anchor-strip filters were
  verified working as designed before leakage was flagged (only prose-embedded
  content survives — X-06).
- Hand-verified by the orchestrating auditor before publication: **I-005**
  (dimensional analysis of the mixed-train recipe), **III-001** (Jacobian × area
  algebra against `modtran.py`, which is correct in code), **IV-001** (12×4×3 = 144
  in the case study vs the cookbook's 6×3×3).
- Mechanism checks: `internal_anchors.lua` drops marker paragraphs only and rewrites
  no links (X-03 root cause); the builder's `\newunicodechar` preamble covers `e⁻`,
  so X-04 is consistency-only, not dropped glyphs; the builder fails the build on
  any unmapped missing glyph — the "ř" of X-01 is a wrong-glyph substitution, which
  that guard cannot see.
