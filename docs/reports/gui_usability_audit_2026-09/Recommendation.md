# GUI Usability Audit — Recommendation

**Status:** Complete (point-in-time record — immutable per Rule 24/28; corrections are new documents)
**Date:** 2026-09-19
**Phase:** 6 of `Audit_Plan.md` §8 — closes the charter. Every finding below carries one of the three Rule 28 dispositions: **CU'd**, **Planned**, or **Declined**.
**Baseline:** `main` at `ecd8ef51`.

---

## 1. Answer to the charter question

> Can each persona get from an empty window to their deliverable, pivot mid-session, make ordinary mistakes, and recover — without a wedge, a misleading message, or leaving the GUI?

**Not yet.** Every persona reached a result, but none without at least one of the three. The two owner-reported symptoms have single, named mechanisms:

- **"Errors on every edit from a blank scenario"** is the resolver's cycle detector firing before the required-parameter check on an unresolved configuration, routed to a modal on every debounced re-evaluation until the aperture exists. Order-dependent: zero modals optics-first, twelve detector-first. (F-13, CU-373.)
- **"A conflict you cannot fix one edit at a time"** is two things. Consistency-group and door conflicts are admitted on incomplete configurations and surface late, blaming the wrong parameter (F-06); and mode selectors are display-only, so the field that must be withdrawn is the one the card greys out (F-05). The exit is a dock right-click the message does not name. (CU-372, CU-377.)

Underneath both sits one design seam: the GUI has three edit paths (in-place, dialog, YAML) and one withdrawal path (Reset), and they validate differently. The dialog has a differential guard, the in-place editor does not, the YAML editor validates nothing until the next open, and Reset validates after applying. CU-372 is that seam.

## 2. Findings by severity

| Severity | Count | Findings |
|---|---|---|
| S1 | 4 | F-01, F-02/F-46, F-03, F-32 |
| S2 | 11 | F-04, F-05, F-06, F-08, F-17, F-20, F-22, F-24, F-45, F-46, F-47 |
| S3 | 27 | F-07, F-09–F-15, F-18, F-19, F-21, F-23, F-25–F-28, F-34, F-35, F-37–F-39, F-41–F-44, F-48, F-51, F-55 |
| S4 / observation | 13 | F-16, F-29–F-31, F-33, F-36, F-40, F-49, F-50, F-52–F-54 |

Nine findings were confirmed natively in live session 1 (`Findings_Live_Session_1.md` §1); the rest stand on two independent headless reproductions each.

## 3. Dispositions

### CU'd (six family CUs, one per mechanism)

| CU | Mechanism | Findings |
|---|---|---|
| **CU-372** | edit-discipline seam: clone-validate, differential guard, reset, document apply, undo provenance | F-01, F-02, F-03, F-04, F-06, F-20, F-32, F-37 |
| **CU-373** | evaluation-failure routing and the strings it uses; advisory targeting; launch path | F-09, F-10, F-12, F-13, F-21, F-28 (routing half), F-44, F-47, F-51 |
| **CU-374** | export formats: units, labels, per-configuration columns, run stamps, provenance | F-17, F-22, F-31, F-34, F-35, F-42 |
| **CU-375** | trade surfaces need the result's own flags; scaffolds and compare | F-18, F-19, F-23, F-24, F-27, F-41 |
| **CU-376** | Parameters dock ergonomics and small-window layout | F-14, F-38, F-45, F-46, F-49 |
| **CU-377** (owner-gated, with Gap 85) | mode and door switching; inactive-door display; lab door | F-05, F-07, F-15, F-25, F-26, F-43, F-48 |
| **CU-371** (existing family) | process language in product strings | F-28 (wording half), F-30, F-52, F-53 |
| **CU-363** (existing) | form clipping at off-default widths | F-38 cross-reference only |

### Planned

- **F-08** (transmission-mode modals carrying Python API text, no pointer to the Transmission tab) and **F-39** (Zernike import leaves the WFE mode row on scalar): two one-line fixes that ride the first CU-373 or CU-371 live-review merge rather than their own CU.
- **F-55** (soak: memory grows ~2.9 MB per accepted edit for the first 200 and ~22 MB per sweep, never released; per-edit time flat at 0.55 s) — a measurement, not yet a mechanism. Planned as the first profiling task after CU-376 lands, since the tree rebuild is the obvious suspect; minted then, not now.
- **Live session 2** (T-H at real sizes, T-I keyboard-only, T-R template recovery, T-S scripting as escape hatch): held when the owner has an hour; the T-H grabs already in `Findings_Tracks.md` are the script.

### Declined (with rationale)

- **F-33** undo bottom reached silently — the greyed menu item is the standard cue; documented depth.
- **F-54** YAML round trip relabels user-set as config — documented in `ug_yaml_roundtrip.md` §3.1 and consistent with the file being the new source.
- **F-40** a default mirror saturates the from-scratch MWIR configuration — physics, not a GUI defect; the F-18 flags will make it visible.
- **F-16, F-36, F-50** — Findings-Log lines (2026-09-19), below CU grade.
- **F-29** — a quantification of F-13, no separate action.

## 4. Order of work (recommendation, not a ruling)

1. **CU-372** first. It is the S1 set, it is where both owner symptoms live, and every other family assumes edits and resets tell the truth.
2. **CU-373** second, and small: the required-before-cycle ordering alone removes the blank-config modal spray; the advisory-routing items are a pattern already in the code.
3. **CU-376** third: the tree rebuild is the single most-felt irritation in a real session, and it likely explains F-55.
4. **CU-374 and CU-375** together: they are what leaves the tool on a slide.
5. **CU-377** waits for the Gap 85 ruling; nothing in it should be built ahead of that decision.

## 5. What the audit did not do

No source was changed. No physics was judged. Windows was not exercised (§10 ruling 3). Live session 2 was not held. Journeys started from Blank config only; the mission-template path (T-R) is untested. The headless driver is scratch and not committed; the committed record is the numbered steps and the six figures in `figures/`, regenerable from those steps.
