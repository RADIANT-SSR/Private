# Menu and Shortcut Reference

Every action in the RADIANT desktop application, in menu order, with its shortcut, when it
becomes available, and what it does.

**Modifier convention.** Shortcuts are written with the portable `Ctrl` modifier, which Qt maps
to the platform's own: on macOS every `Ctrl` in this appendix is the `⌘` key.

**Present but unwired.** The menus are built as the full surface, so actions a build does not
implement are present and disabled rather than absent — the menus do not change shape between
versions. Eight such actions are marked **not wired** below, and that is the complete list
for this build.

**Availability.** Four gates recur:

| Gate | Meaning |
|---|---|
| *always* | available from launch |
| *config* | available once a configuration is loaded |
| *result* | available once an evaluation has completed |
| *sweep* | available once a sweep has been run |

## A.1 File

| Action | Shortcut | Available | Notes |
|---|---|---|---|
| New | | always | blank session — shows the welcome screen; passes the unsaved-edits guard first |
| Open YAML… | `Ctrl+O` | always | a plain config or a study; one reader handles both |
| Open Recent ▸ | | always | persisted between launches; the submenu is disabled while the list is empty |
| Save | `Ctrl+S` | config | writes the inputs scope to the current file; falls back to Save As when there is none |
| Save As… | | config | writes and **adopts** the destination as the current file |
| Export YAML… | | config | writes the same document to a chosen path without adopting it |
| Export JSON Result… | | result | the provenance record of the last run |
| Export Resolved YAML… | | config | every resolved parameter — defaults and derived values included |
| Export Metrics CSV… | | result | the metric surface with units |
| Export Sweep CSV… | | sweep | the retained sweep result |
| Export XLSX Workbook… | | result | config + metrics + any retained sweep in one workbook |
| Quit | `Ctrl+Q` | always | passes the unsaved-edits guard |

## A.2 Edit

| Action | Shortcut | Available | Notes |
|---|---|---|---|
| Undo | `Ctrl+Z` | config | parameter edits and element-train edits, 20 steps; a whole-document swap clears the history |
| Redo | the platform's redo (`Ctrl+Shift+Z`; `Ctrl+Y` on Windows) | config | |
| Reset to Defaults | | config | clears the whole input set |
| Configurations… | | config | the configuration manager (chapter 8, §3) — also the door a single-model session becomes a study through |
| Find Parameter | `Ctrl+F` | — | **not wired** in this build; use the Parameters dock's filter box |

## A.3 View

| Action | Shortcut | Available | Notes |
|---|---|---|---|
| Show/Hide Parameter Panel | `F6` | always | checkable; the state persists between launches |
| Dark/Light Theme | | always | checkable; persists, and re-themes figures and custom-drawn views too |
| Font Size + | | — | **not wired** in this build |
| Font Size − | | — | **not wired** in this build |
| Show/Hide Right Rail | `F7` | always | checkable; the state persists |
| Angles in Degrees | | always | checkable; **on by default**, persists. Display only — canonical storage is unchanged, and entry and display stay symmetric on toggle |
| Go to Stage ▸ | `Ctrl+1`…`Ctrl+9`, `Ctrl+0` | config | the ten signal-chain stages in order; the tenth wraps to `Ctrl+0`, because `Ctrl+10` is not a key |

The stage-jump submenu lists the namespaces in chain order:

| Key | Stage | Key | Stage |
|---|---|---|---|
| `Ctrl+1` | geometry | `Ctrl+6` | spectral_integration |
| `Ctrl+2` | source | `Ctrl+7` | detector |
| `Ctrl+3` | atmosphere | `Ctrl+8` | readout |
| `Ctrl+4` | optics | `Ctrl+9` | calibration |
| `Ctrl+5` | platform | `Ctrl+0` | performance |

## A.4 Run

| Action | Shortcut | Available | Notes |
|---|---|---|---|
| Evaluate | `F5`, `Ctrl+Return` | config | runs the whole chain on a worker thread. The `Ctrl+Return` alternate exists because a bare `F5` needs the `Fn` modifier on stock macOS keyboards |
| Validate Only | `Ctrl+R` | — | **not wired** in this build. The resolve-only check is available from the command line as `radiant validate <config>`, and the configuration manager's Status column runs it per configuration |
| Run Sweep… | | config | the 1-D / 2-D sweep dialog, on a clone, with progress and cancel (chapter 10, §1) |
| Monte Carlo… | | config | opens a prefilled Monte-Carlo **script scaffold** in the scripting window, seeded with the tolerances you have set |
| Batch Run… | | config | opens a prefilled `BatchRunner` **script scaffold** |

## A.5 Tools

| Action | Shortcut | Available | Notes |
|---|---|---|---|
| Inspector | `Ctrl+I` | result | every intermediate value of the last run, as a tree; non-modal, so it can stay open beside the window |
| Scripting Window | `Ctrl+Shift+P` | config | a separate top-level window — command line and workspace — bound to the displayed sensor |
| Parameter Schema Browser | | config | the read-only schema tree: every parameter, its type, unit, bounds and description |
| Compare Config Files… | | config | evaluates this configuration against other config **files** and tables the metrics (chapter 10, §3) |
| Compare Measured MTF… | | result | overlays measured MTF data on the predicted curve |
| Solve for Parameter… | | config | inverse solve: what value of X gives metric Y (chapter 10, §2) |
| Explain Parameter… | | config | pick a dot-path, read its derivation trace |
| Preferences… | | — | **not wired** in this build |

`Ctrl+Shift+P` is deliberately not the more conventional control-backtick chord: Qt maps the
portable `Ctrl` to macOS's `⌘`, and command-backtick is an OS-reserved shortcut that never
reaches the application.

## A.6 Help

| Action | Shortcut | Available | Notes |
|---|---|---|---|
| Documentation | | — | **not wired** in this build |
| Example Configs | | — | **not wired** in this build |
| About RADIANT | | — | **not wired** in this build |

## A.7 The menu-bar corner

The menu bar's right-hand corner carries a **◈ Inspector** button. It triggers the same action
as Tools ▸ Inspector and shares its enabled state, so it greys out before the first evaluation
too.

## A.8 Shortcut summary

| Key | Action |
|---|---|
| `F5` / `Ctrl+Return` | Evaluate |
| `F6` | Show or hide the Parameters dock |
| `F7` | Show or hide the right rail |
| `Ctrl+1`…`Ctrl+9`, `Ctrl+0` | Jump to stage 1…10 |
| `Ctrl+O` | Open |
| `Ctrl+S` | Save |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` (`Ctrl+Y` on Windows) | Redo |
| `Ctrl+I` | Inspector |
| `Ctrl+Shift+P` | Scripting window |
| `Ctrl+Q` | Quit |
| `Ctrl+F` | Find Parameter — **not wired** |
| `Ctrl+R` | Validate Only — **not wired** |

## A.9 Affordances that are not in a menu

Several actions have no menu entry at all, and are listed here so the appendix is a complete
map of the surface.

| Affordance | Where | What it does |
|---|---|---|
| **Evaluate / Re-evaluate** button | bottom of the right rail | the same action as Run ▸ Evaluate; turns amber and relabels itself when the result is stale |
| **Edit Config (YAML)** button | right rail | the document editor (chapter 11, §2) |
| **+ Pin…** | right rail | add any metric to the pinned cards |
| per-row **pin** | metric rows and stage-output rows | pin that value to the rail (hover-revealed) |
| **⚙ Manage…** | configuration bar (studies only) | the same dialog as Edit ▸ Configurations… |
| configuration tabs | configuration bar (studies only) | choose the displayed configuration — display state only |
| stage chips | stage strip | navigation only; computes nothing |
| **Filter parameters…** / **Changed only** | above the Parameters dock tree | narrow by substring; show only explicitly set rows |
| row right-click ▸ Edit… / Copy dot-path / Explain / Reset to Default | Parameters dock | per-parameter actions (chapter 5, §3) |
| row right-click ▸ Configure across configurations… / Un-configure… | Parameters dock and stage forms, studies only | configuration scope (chapter 8, §4) |
| row right-click ▸ Configure / Un-configure row… | Optics element table, studies only | per-row configuration (chapter 7, §1.3) |
| **Choose part & apply… / Details… / Remove / Open datasheet/paper** | Detector ▸ Inputs | the FPA part library (chapter 7, §3.1) |
| **Import Zemax Zernike…** | Optics ▸ Inputs | wavefront import (chapter 7, §1.1) |
| **Define QE(λ) table… / Import QE curve (preview)…** | Detector ▸ Inputs | QE authoring and import (chapter 7, §3.2) |
| **Compute:** checkboxes | Performance workspace | metric-group selection (chapter 9, §2) |
| **TRANSMISSION DEFINED BY:** selector | Optics ▸ Transmission | scalar versus element train (chapter 7, §1.2) |
