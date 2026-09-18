# The Main Window

The application has one window, and that window has one idea: **you are always looking at
exactly one stage of the signal chain, with every parameter on the left and every result on
the right.** Navigation is choosing a stage; nothing is buried two levels down.

![The main window, at its default proportions, on the minimal MWIR example after the
load-time evaluation.](figures/gui/ug_window_anatomy.png)

Reading that figure from the top: the menu bar (with the **◈ Inspector** button in its
right-hand corner), the **stage strip**, and then three columns — the **Parameters** dock,
the **stage workspace**, and the **right rail** — over a status bar.

A study adds one more band, a configuration selector between the menu bar and the stage
strip. A single-configuration session does not show an empty one; the band is absent
entirely.

## 1. Title bar and status bar

The title reads `[*] <file> [(N configurations)] — RADIANT <version> <commit>`. Three things
are being told to you at once: which file is on screen, whether it carries unsaved edits (the
leading `*`), and which build you are running. The build label exists because "the numbers
changed" is nearly always answered by "you are on a different commit".

The status bar carries the outcome of the last action. After a successful run it reads:

```text
Evaluated — 500 wavelength points
```

In a study it names the displayed configuration and the size of the pass, for example
`B4_Red — Evaluated — 500 wavelength points (9 configurations evaluated)`. On a
configuration that cannot yet resolve — a blank start with required parameters unset — it
says so and tells you what to do:

```text
Configuration incomplete — set required parameters, then Evaluate (F5) to see what is still missing
```

## 2. The stage strip

![The stage strip: ten chips in chain order, each with its health dot; Performance is
selected.](figures/gui/ug_stage_strip.png)

Ten chips, in the order the chain runs, each showing its number, name and a one-line physics
caption (`PSF · MTF`, `∫ dλ`, `TDI · ADC`). Clicking one is **navigation only** — it computes
nothing. It swaps the center to that stage's workspace and scrolls the Parameters dock to
that stage's namespace.

The dot on each chip is a **health indicator**, and it reports the whole run rather than that
stage alone:

| Dot | Meaning |
|---|---|
| green | the last evaluation finished with no warnings |
| yellow | the last evaluation finished and carried at least one warning |
| red | the last evaluation raised an error |
| gray | stale — no result yet, or a parameter has been edited since the last run |

The dots move together on purpose. Captured warnings are free text that cannot be reliably
attributed to a single stage, and a raised error does not reliably carry the stage it came
from, so the strip marks every chip rather than guessing which one is at fault. A yellow
strip means *this run has something to read in Messages*, not *this stage is unhealthy*. Gray
appearing the instant you type is the other half of the same honesty: the numbers on screen
no longer describe the model you have now, and they say so until the pending re-evaluation
lands.

The strip scrolls horizontally on a narrow window rather than forcing the window wider.

## 3. The Parameters dock

Every parameter in the model, grouped by namespace in chain order, in three columns
(chapter 4's provenance figure shows the dock widened, with the full dot-paths legible):

- **Parameter** — the leaf name (the full dot-path is in the parameter editor and in the
  right-click *Copy dot-path*).
- **Value** — the value with its unit, in your chosen display unit, prefixed with ⚡ when it
  is derived.
- **Source** — the provenance badge (chapter 4, §4).

Above the tree, a **filter box** narrows by substring across dot-paths, and **Changed only**
hides every row still at its schema default — your configuration, as a short list.

**Editing.** Double-clicking the *Value* cell of a non-derived row opens the editor its type
calls for: a combo box for an enumeration (with the choices read from the schema), a
checkbox for a boolean, a spin box for an integer, a text field for a float or string.
Double-clicking the *Parameter* or *Source* cell instead opens the full **Parameter Editor**
dialog, which shows the complete dot-path, the schema description, the current value with
unit and provenance, the bounds in those units, and — for a dimensional parameter — a unit
selector with a live canonical preview.

Both paths commit the same way: the value is validated on a throwaway copy of the model
first, so a rejected value never reaches the live one. A rejection is rendered inline on the
row *and* as a dialog, in *what / why / action* form, and the row keeps its previous value.

Right-clicking a row offers **Edit…**, **Copy dot-path**, **Explain** (the same derivation
trace `radiant explain` prints, in a dialog), and **Reset to Default**, which clears your
input so the parameter reverts to its default or is re-derived.

A derived row opens read-only. That is not a restriction to work around: the value is a
consequence, and its inputs are what you change.

The dock hides and shows with **F6**.

## 4. The stage workspace

The center column shows the selected stage and nothing else. Every workspace is built from
the same three sections, in order: **Inputs** (this stage's editable parameters, each with
its unit), **Outputs** (what the stage computed, read-only, each with its unit and symbol,
read verbatim from the stage's own outputs), and **Plots** (that stage's figures).

Stages with substantial separable content are tabbed — Geometry is *Inputs | Schematic*,
Source has five tabs, Optics four, Platform and Detector two or three; the rest are a single
pane. Chapter 4, §1 has the full map.

Three behaviors belong to the center column rather than to any one stage:

**Derived fields are inert.** They show a lightning bolt and a `derived` badge, and they are
not editable, exactly as in the dock.

**Irrelevant fields are shown disabled, not hidden.** Where a stage accepts one mode out of
several — one geometry mode per family, one transmission definition, one readout
architecture — the alternatives stay visible and grayed. You can see what you did not choose,
which is the difference between a tool that has no such feature and one where you took the
other door.

**The saturation banner lives here.** When the pixel is clipping, a persistent,
non-dismissible banner appears at the top of the center column with the well fill and the
accumulated-versus-capacity charge in electrons. It is deliberately not folded into the
Messages panel: silent clipping invalidates every downstream number, so it gets its own
strip.

With no configuration loaded, the center shows the **welcome screen** instead of dead space:
a grid of mission-template cards (name, one-line blurb, specification line), a **Blank
config** card, a **Worked examples** group of bundled studies, and an **Open recent** list.
Activating any card is an ordinary file open with a known path.

## 5. The right rail

![The right rail: pinned metric cards, the Edit Config (YAML) button, the Messages panel, and
the Evaluate footer.](figures/gui/ug_right_rail.png)

Always visible, whatever stage you are on. Top to bottom:

**Pinned.** Value cards that survive navigation. Five are pinned by default — SNR, NEDT,
NIIRS, GSD, MTF @ Nyq — and `+ Pin…` adds any metric on the result surface. Any stage
output's row carries a pin affordance too, so a card can track an intermediate (a
transmittance, an electron count) as well as a headline metric. Each card shows the label,
the value with its unit, and the stage it came from; a metric that failed shows its reason
rather than a blank. The pinned set is per session.

**Edit Config (YAML).** Opens a roomy modal editor on the document — the whole study when
the session is one. **Apply** re-parses the edited text through the framework, on a throwaway
first, so invalid YAML produces an actionable error and leaves the live document untouched.
The text is the *inputs* scope: what you specified, not the resolved two hundred.

**Messages.** Warnings and errors from the last run, one row each, verbatim and never
deduplicated. The header reads `⚠ N warnings` with the first inline; clicking opens the full
list. Errors render their *what / why / action*. In a study each message is prefixed with the
configuration that raised it, so a per-band effect never reads as a property of the whole
study. The panel also carries advisory notes that are not failures — an atmosphere family
that cannot serve your scene, a half-finished architecture switch — because those belong
beside the inputs, not in a modal headed "Parameter Rejected".

**Evaluate (F5).** The accent button is pinned to the bottom of the rail, below the stretchy
Messages panel, so it never scrolls away.

The rail hides and shows with **F7**.

## 6. The evaluate loop

RADIANT re-evaluates on its own, and understanding when is worth a paragraph.

Three things start a run and nothing else does: **loading a file**, **editing anything**
(on a 200 ms debounce, so edits coalesce), and **Evaluate** on demand — `F5`, or
`Ctrl+Return` (`⌘Return` on macOS, provided because a bare `F5` needs the `Fn` modifier on
stock macOS keyboards). Chapter 9, §1 is the full treatment: what counts as an edit, why
the whole chain re-runs every time, and what the worker thread does and does not let you
interrupt.

**A failed evaluation leaves the previous result on screen**, marked stale, with the failure
in Messages. It never shows a blank, and it never shows a mixture of old and new numbers.

**Run ▸ Validate Only** (`Ctrl+R`) is present but not wired in this build. The resolve-only
check runs from the command line as `radiant validate <config>`, and the configuration
manager's Status column applies it per configuration (chapter 8, §3).

## 7. Menus

Every action lives in the menu bar, and actions a build does not implement are present but
disabled, so the menus read as the full surface rather than shifting shape between
versions. **Appendix A is the menu reference** — every entry of File, Edit, View, Run,
Tools and Help, with its shortcut, what it does, and whether it is wired in this build.
It also catalogues the affordances that are not in a menu at all: the right rail's **Edit
Config (YAML)** button, the Parameters dock's context menu, the per-row configuration
scope, and the import dialogs that hang off the Optics and Detector workspaces.

Three menu entries are worth knowing before you get there, because they are the ones an
operator reaches for first: **Run ▸ Evaluate** (`F5`), **Edit ▸ Configurations…** (the
configuration manager of chapter 8), and **Tools ▸ Scripting Window** (`Ctrl+Shift+P`).

## 8. Shortcut summary

| Key | Action |
|---|---|
| `F5` / `Ctrl+Return` | Evaluate |
| `Ctrl+R` | Validate only — present, not wired in this build |
| `F6` / `F7` | Show or hide the Parameters dock / right rail |
| `Ctrl+1`…`Ctrl+9`, `Ctrl+0` | Jump to stage 1…10 |
| `Ctrl+O` / `Ctrl+S` | Open / Save |
| `Ctrl+Z` / `Ctrl+Shift+Z` (`Ctrl+Y` on Windows) | Undo / Redo |
| `Ctrl+I` | Inspector |
| `Ctrl+Shift+P` | Scripting window |
| `Ctrl+Q` | Quit |

On macOS, `Ctrl` in this table is the `⌘` key, as Qt maps the portable modifier to the
platform's own.
