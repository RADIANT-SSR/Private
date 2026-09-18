# Configuration Sets

Every real trade is a *family* of closely related models: one telescope in MWIR and in LWIR,
one sensor at four slant ranges, nominal against as-built. In every case two models differ in
a handful of parameters and agree on the other two hundred.

A **configuration set** is how RADIANT holds that family: one shared base, plus the parameters
you have explicitly said should differ. One file, one session, one evaluation pass.

The vocabulary matters and this manual keeps it straight throughout: a **config file** (or
*YAML config*) is the artifact on disk; a **configuration** is one member of a set inside it.

## 1. Shared by default, configured on purpose

The model is borrowed from optical-design software's zoom configurations, and it has exactly
one rule:

> A parameter is **shared** — one value across every configuration — until you explicitly mark
> it as **configured**. A configured parameter then carries one value per configuration, in
> every configuration, always.

Two consequences follow, and they are the whole reason for the design.

**Nothing differs unless someone said it should.** The failure mode this removes is the one
that N parallel YAML files always produce: two models that diverge in a parameter nobody
noticed, because a shared edit was applied to three files out of four.

**There is no resolution order to learn.** A configured parameter is *dense* — it has a value
in every configuration, not an overlay that may or may not be present — so there is no
inheritance chain, no precedence rule, no "which layer won". Configuring a parameter **moves**
it out of the shared base and seeds every configuration from its current shared value;
un-configuring collapses it back to one shared value again.

Everything you do not configure stays shared: tolerances, stage-output injections, and the
*structure* of the optical element train.

A set holds between 1 and 12 configurations. The cap is a product decision rather than a
technical limit — it bounds the always-on background pass and keeps the side-by-side metric
surface narrow enough to read honestly — and a thirteenth is refused in as many words:

```text
cannot add configuration 'C13': the set already holds 12 of at most 12
  Why: a set is capped at 12 configurations so the always-on evaluate-all pass and the
       side-by-side comparison stay bounded (ADR-0010 D-E)
  Action: Remove a configuration you no longer need, or split the study into two sets.
```

**A single-configuration session is not a degenerate study — it is exactly the ordinary
session.** One configuration with an empty configured table behaves, saves, and renders
identically to a session that has never heard of configurations. The configuration band is not
shown empty; it is absent.

## 2. The configuration bar

![The configuration selector on the nine-band OLI-2 study — the CONFIGURATIONS label, the
Manage… button, and one accent-chipped tab per
configuration.](figures/gui/ug_configuration_bar.png)

A study adds one band between the menu bar and the stage strip. Reading it left to right: the
**CONFIGURATIONS** label, a **⚙ Manage…** button, and one tab per configuration in set order,
each carrying a small colored chip. The chip's color is assigned by position and is stable —
the same configuration keeps the same hue in the selector, in the per-parameter value editor,
and in the Performance columns, so a color means one thing everywhere in the window.

Clicking a tab is **display state only**. It changes which configuration stages 1–9 are showing
and nothing else; it computes nothing, because every configuration has already been evaluated
(§5).

The Manage button sits at the *left*, right after the label, rather than at the far end of the
tab row. On a wide study it was invisible there. On a long study the tab row scrolls
horizontally inside its own strip — with the active tab always scrolled into view — rather than
forcing the window wider.

## 3. The Manage dialog

**⚙ Manage…**, or **Edit ▸ Configurations…**, opens the manager. It is also the door an
ordinary single-model session walks through to *become* a study: pressing **Add** on a
one-configuration session is what makes the selector appear.

Above the rows sits the study's **shared grid points** — the number of wavelength samples every
configuration uses unless its own row overrides it. RADIANT's default is 500. The field's
tooltip says precisely what it is, because "points" is ambiguous:

> Number of wavelength samples in each configuration's spectral evaluation grid. The grid
> spans that configuration's own `filter_min_um` → `filter_max_um`, so the same point count
> means a finer grid over a narrower band.

Then one row per configuration:

| Column | What it does |
|---|---|
| chip + name | the configuration's stable accent color and its name, editable in place; the **baseline** is marked |
| Grid points | an integer override, or blank to inherit the shared default — a blank box shows `shared: 500 pts` in gray, so "blank" is never an unexplained gap |
| Status | `OK`, or the failing configuration's *what*-line with the full what/why/action on hover |

The status column is resolve-only: **opening this dialog never runs physics.** It tells you
whether each configuration's inputs resolve, which is the cheap question, and it answers it for
all of them at once.

The buttons are Add, Duplicate, Rename, Remove, Reorder, and *set as baseline*.

**The dialog edits a private copy.** Cancel is exactly "throw the copy away" — nothing
partially applied, no half-entry on the undo stack. Accept applies the whole reshape as one
undoable step.

**Every guard you meet here is the framework's own, not a second implementation.** A
thirteenth configuration, a duplicate or empty name, removing the last one — each is refused by
the real API call on the private copy and rendered here in what/why/action form:

```text
a configuration named 'LWIR' already exists
```

**Removing the displayed configuration is allowed**, and the policy is printed in the dialog
before you do it: *removing the displayed configuration moves the display to the first
remaining one.* That is the model's own behavior, stated rather than reinvented, and it is why
the removal is confirmed instead of silent.

## 4. Configuring a parameter

![The Parameters dock on the nine-band OLI-2 study — the configured parameters carry the red C
badge; everything unmarked is shared.](figures/gui/ug_configured_parameters.png)

A configured parameter carries a small red **C** after its name, in the Parameters dock and in
every per-stage form. In the figure, seven parameters are configured — the two filter edges and
the integration time on Spectral Integration, the two pixel pitches, the QE and the dark rate
on Detector — and everything without a badge is shared by all nine bands. Hovering the badge
lists every configuration's value for that parameter, with units.

There are two ways to change a configured value, and they do different things on purpose.

**Edit it in place** — in the dock, or in a stage form — and you change **the displayed
configuration only**. That is the behavior the model is named for: you are looking at
configuration *X*, so you are editing *X*. Editing an unmarked (shared) parameter changes the
one shared value, as always. There is no hidden scope mode and no modifier key: what you are
looking at is what you are editing.

**Open the Parameter Editor** on a configured parameter and you get the all-*N* table instead:
one value box per configuration, each with its chip, its name, its unit, and the editor its
schema calls for. That is where you set every configuration's value in one pass.

The same dialog is how a *shared* parameter becomes configured. Right-click the row and choose
**Configure across configurations…**; the editor expands into the same table, pre-seeded with
the parameter's current shared value in every row, so nothing changes until you edit one. This
is one API call and one undo step.

**Un-configure** collapses the column back to a single shared value, and **the first
configuration's value is the one that survives.** The confirmation states that outright,
because it is a physics change in every other configuration and must never be silent.

## 5. Evaluation and the Performance surface

**Every configuration evaluates in the background, always.** The displayed one runs first, so
the visible views refresh at single-model latency, and the rest follow on the same worker pass.
Switching tabs shows a result that already exists; it does not queue a run.

A configuration that **fails** is named and kept, never dropped. If the failing one is not the
one you are looking at, it does not interrupt you with a modal — it appears in the Messages
panel prefixed with its name, and the study carries on with the configurations that worked.

![Performance workspace on the nine-configuration OLI-2 study — one metric column per
configuration.](figures/gui/compare_configurations.png)

On the Performance screen a study renders each metric group card as a **metric × configuration
matrix**: the group card is still the unit, and each metric row grows one column per
configuration, in set order — set order, not evaluation order, so the columns do not reshuffle
when you change the displayed configuration. Cards lay out one-up rather than two-up in a
study, because a card carrying nine columns needs the full pane width.

Three rules govern the cells, and each one is a decision rather than an accident:

- **Plain values only.** A cell carries a value and its unit. No delta, no best-mark, no
  color scale. Cross-configuration deltas and best-per-metric live on the scripting
  `compare` surface, where the baseline designation is used and the result is a table you can
  export — not a visual encoding that invites conclusions the numbers may not support.
- **Absent is absent.** A metric a configuration did not compute renders as an em dash. Never
  a zero, never a blank.
- **A failed configuration keeps its column.** Its cells read as not evaluated and its header
  carries a ✕ with the error's *what*-line on hover, so you see *which* configuration failed
  rather than a silently narrower table. A header ⚠ points at that configuration's entries in
  the Messages panel.

The **baseline** designation stays in the model whether or not the GUI paints anything with
it: it is the reference the scripting comparison measures deltas against.

## 6. What a study looks like on disk

One study is one file. The shared parameters sit where they always sat, and a
`configurations:` section carries the rest:

```yaml
configurations:
  active: Configuration 1
  baseline: Configuration 1
  names:
  - Configuration 1
  - LWIR
  parameters:
    spectral_integration.filter_min_um:
    - 3.5
    - 8.0
spectral_integration:
  filter_max_um: 5.0
  integration_time_s: 0.005
```

Reading it: `names` is the set order, `active` is which configuration the GUI reopens on,
`baseline` is the comparison reference, and every list under `parameters` is exactly as long as
`names` — dense, by construction. A length mismatch is a load error, never padded. A dot-path
may not appear both in the shared body and under `parameters`; that is checked at load.

An optional `wavelength_points:` map carries per-configuration grid-point overrides for the
configurations that have one.

**A file with no `configurations:` section is byte-for-byte the format RADIANT has always
written**, which is why an old config opens as a one-configuration session with nothing to
explain.

Two things follow for anyone moving between the GUI and scripts. A study must be opened with
the configuration-set reader; opening one with the plain single-sensor loader raises an
actionable error naming the reader to use instead — it does not quietly load the shared half.
And per-configuration optical **prescriptions** are supported per *row*, not per document: a
row of the shared train configures like a parameter (chapter 7, §1.3), while the number and
order of rows stay shared.

Configurations are not file composition. The reserved `_extends` / `_imports` keys remain
unimplemented and the loader still refuses them; configurations compose *within* one document
at the parameter level, which is a different question and stays one.
