# Running and Reading Results

The application evaluates on its own and shows you the result. This chapter is about the loop
that produces it, the control you have over *how much* it computes, and how to read what comes
back — including the parts that are warnings, refusals, or absences rather than numbers.

## 1. The evaluate loop

Three things start a run, and nothing else does:

| Trigger | When |
|---|---|
| **On load** | once, automatically, as soon as a file opens. A file you opened is a file you have already evaluated. |
| **After an edit** | on a 200 ms debounce. Edits inside the window coalesce, so dragging through five fields costs one run, not five. |
| **On demand** | **Evaluate** — `F5`, or `Ctrl+Return` (`⌘Return` on macOS, because a bare `F5` needs the `Fn` modifier on stock Apple keyboards). |

An "edit" here is any committed change: a parameter field, a combo, an element-train cell, a
metric-group checkbox, an FPA preset applied or removed. Each of them marks the run stale and
restarts the debounce.

**The whole chain re-runs every time.** There is no partial or incremental re-evaluation, and
none is planned: a stale sub-graph is a class of bug that silent partial updates make
invisible, and the full pass is cheap enough — roughly 0.8 s for one configuration — that
buying speed with that risk would be a bad trade.

**Runs happen on a worker thread.** The window stays responsive, and the status bar grows an
indeterminate progress strip on the right while a pass is in flight, reading `Evaluating…`. A
study evaluates every configuration in one pass on that worker: the displayed configuration
first, so the visible views refresh at single-model latency, then the rest.

**Cancel** appears beside Evaluate in the rail footer while a run is in flight. It stops the
pass at the next configuration boundary — the configuration being evaluated finishes first,
because the chain has no interior cancellation point — and leaves the results on screen as
they were, marked stale. The sweep dialog has its own Cancel (chapter 10). A long study is
still cheaper to reduce than to interrupt: fewer configurations, fewer wavelength points, or
fewer metric groups (§2).

### 1.1 Staleness — the trust signal

The instant you edit anything, three things change before any new number arrives:

- every stage chip's dot goes **gray**;
- the **Evaluate** button turns amber and relabels itself **Re-evaluate F5**;
- the center column gains a stale notice, and each pinned card appends a `→?` marker to its
  value.

All of that says one thing: *the numbers on screen no longer describe the model you have now*.
They stay honest until the pending run lands.

**A failed evaluation leaves the previous result on screen, marked stale.** It never shows a
blank and it never shows a mixture of old and new numbers. That is the other half of the same
contract: the last thing you saw was true of *some* configuration, and you will not be shown a
hybrid that was true of none.

### 1.2 The saturation banner

One condition gets its own strip rather than a message row. When the detector well clips, a
persistent, non-dismissible banner appears at the top of the center column:

```text
⚠ Detector well saturated — well fill 1.16× (462,700 e- accumulated vs 400,000 e-
capacity). The signal is hard-clipped; SNR / NEDT / NIIRS reflect the clipped value.
```

It is not folded into Messages because silent clipping invalidates every downstream number, and
a row in a list is too easy to scroll past. It clears by itself on the next unsaturated result.

## 2. Choosing what to compute

![Performance workspace with the Spatial / MTF and Interpretability groups deselected — the
Compute row's state and the card sections that survive
it.](figures/gui/ug_performance_selection.png)

The Performance workspace leads with a single row of five checkboxes:

```text
Compute:  ☑ Sampling / geometry   ☐ Spatial / MTF   ☑ Radiometric
          ☐ Interpretability      ☑ Saturation
```

Their order matches the card sections below them, by construction — the checkbox row and the
readout read from the same table, so they cannot drift apart.

| Group | Metrics it owns |
|---|---|
| Sampling / geometry | GSD (cross-track, along-track, geometric mean), target-plane sample distances, ground range, swath width, access rate, Q at band center / min / max, sampling regime, diffraction limits, maximum integration time |
| Spatial / MTF | FWHM x and y, RER, ensquared energy 1×1 and 3×3, straddle factor, MTF at Nyquist, Strehl (PSF-derived and Maréchal), system MTF at Nyquist x/y, folded MTF, alias fraction |
| Radiometric | SNR, contrast SNR, SCNR, NEDT, detection range, radiometric accuracy (% and K) |
| Interpretability | NIIRS, extrapolated NIIRS, MRT at Nyquist |
| Saturation | well margin, ADC margin, dynamic range |

**Unchecking a group stops the computation, not just the display.** That is the distinction
worth internalizing: this is not a view filter. The stage computes only what the enabled groups
need — plus any hidden prerequisites their dependency closure requires — and any warning a
disabled metric would have raised is not raised either.

Two visible consequences in the figure. The Spatial / MTF and Interpretability card sections
are gone from the readout entirely. And the pinned **MTF @ Nyq** card reads

```text
n/a
not computed — the Interpretability metric group is off
```

The second line is the reason, and it says which of three things happened: the metric's
group is switched off (as above); the scene-class relevance map turned it off by default —
`not computed — off by default for this scene class; select the Sampling / geometry group
to compute it` — and selecting the group overrides that; or the group ran and the metric is
simply not defined here — `not computed — not defined for this regime` (detection range on
an extended scene, say). A metric the run *declined* keeps its own reason instead, such as
the GIQE-5 calibration range.

— not a blank, not a zero, not a stale value. A metric you switched off says so. The text
is not exclusive to that case: it is what any metric the run did not produce shows,
switched off or declined (chapter 4, section 7).

**The spatial path itself is skipped** when the Spatial / MTF group is off *and* no enabled
metric needs a spatial input. That is the case where the saving is real rather than cosmetic:
the PSF convolution stack and the MTF product are the expensive part of a run. When it happens,
the dual-path consistency check that normally runs on every evaluation is skipped too — there
is no spatial computation left to check.

**Scene class can switch a group off by default, and only by default.** A ground-target scene
turns the three target-plane sample distances off, because they mean nothing there; the
Geometry workspace's scene-class card previews exactly which metrics its class defaults off
(chapter 6, §1.1). A group *you* select is always computed, whatever the scene class.

## 3. Reading the Performance workspace

The cards are grouped exactly as the checkboxes are, two-up on a single-configuration session
and one-up in a study. Each row is a metric's **human label** — `GSD (cross-track)`, not
`gsd_cross_track_m` — followed by its value **with its registry unit**.

Two conventions to know:

**A failed metric names its reason.** The performance layer is allowed to return a typed
failure instead of raising, so a metric that could not be computed renders as
`n/a (<reason>)` — for example a detection range below the threshold you set, which reads
`n/a (Target not detectable at minimum range 5000 m: SNR = 5.80 < 6.0)` in its own row of the
Radiometric card: the pass/fail and the threshold, together. What it never renders as is a
bare `nan`, and what it never does is propagate silently into a metric that depends on it.

**Absence is shown, not filled.** A metric the run did not produce is an em dash.

Hovering a row reveals a **pin** affordance on its right. Pin glyphs are hover-revealed rather
than always on because thirty-six permanent pins were visual noise; the affordance is there on
every row.

## 4. The right rail

### 4.1 Pinned cards

Five metrics are pinned by default — SNR, NEDT, NIIRS, GSD, MTF @ Nyq — and **+ Pin…** adds any
metric on the result surface. Any *stage output* row carries a pin affordance too, so a card
can track an intermediate (a transmittance, an electron count, a jitter σ) rather than only a
headline metric.

Each card shows the label, the value with its unit, and the stage it came from. A card whose
metric failed shows the reason; a card whose metric was not computed says so; a card showing a
value that predates the last edit carries the `→?` marker. The pinned set is per session.

### 4.2 Messages

![The right rail after a failed evaluation — pinned cards flipped to their stale marker and the
Messages panel carrying the error.](figures/gui/ug_messages_error.png)

Everything the last run had to say, one row each, **verbatim and never deduplicated**. The
panel clears and repopulates on every evaluation. Its header states the count — `1 error`,
`⚠ 3 warnings`, or `clean` — and the empty state says so in words rather than showing an empty
box:

```text
No messages — the last run was clean.
```

Three kinds of row land here.

**Warnings** are the chain's own `UserWarning`s, captured for the run: a saturation clip, a
NIIRS extrapolation, a model used outside its calibration band. Clicking any warning opens the
verbatim full list.

**Errors** render their *what* line, with the full what / why / action on click. The figure
shows one:

```text
✕ calibration.scheme = 'two_point' needs a cal point, but calibration.cal_temp_low_K is unset.
    Why: an active NUC scheme corrects at known cal-source temperatures; without them
    there is nothing to correct at.
    Action: set calibration.cal_temp_low_K (and cal_temp_high_K for two_point), or set
    calibration.scheme = 'none'.
```

**Advisory notes** are the third kind, and the reason the panel exists as more than an error
log. Some outcomes are neither a failure of your inputs nor a clean run: an atmosphere family
that has no measured column for your scene, an architecture switch you are half-way through, a
calibration scheme whose cal point you have not typed yet. Those belong *beside the inputs*,
not in a modal headed "Parameter Rejected", so they are routed here — with the failing stage's
chip marked and the status bar naming what is missing — and the application does not interrupt
you with a dialog for each parameter you have not got to yet. Chapter 12, §4 goes through the
routing rules.

**In a study every message is prefixed with the configuration that raised it**, so a per-band
effect never reads as a property of the whole study. A configuration that failed while it was
not the displayed one appears here as a named error row and nothing more.

## 5. The warnings taxonomy, as an operator sees it

The stage strip's dots report the **run**, not the individual stage, and move together —
chapter 5, §2 has the color table and the reason they move as one.

**A yellow strip means "there is something to read in Messages", not "this stage is
unhealthy".** The advisory routes of §4.2 are the deliberate exception: where the failure *can*
be attributed structurally — a calibration scheme without its cal point, a counting
architecture without its charge packet, a required parameter with no value — only that stage's
chip goes red and the rest go gray, because nine red chips read as "the run is broken" instead
of "fix this one thing".

The bar to hold yourself to: **a valid scenario evaluates warning-free.** A warning that fires
on every run of a correct configuration is a defect in the model or the scenario, not
background noise to be trained out of.

## 6. Looking deeper than the metrics

Three surfaces go past the Performance cards, and all three are non-destructive.

**Tools ▸ Inspector** (`Ctrl+I`, or the **◈ Inspector** button in the menu bar's right corner)
dumps every intermediate value of the last run as a tree. It is non-modal — leave it open
beside the window and it follows each run. It is disabled until the first evaluation, because
there is nothing to dump.

**The stage workspaces themselves.** Every stage's Outputs block is read verbatim from that
stage's own outputs, each value with its unit and symbol. When a metric surprises you, the
stage that produced its inputs is one click away in the strip, and the answer is usually a
derived value you did not expect rather than a metric that is wrong.

**Right-click ▸ Explain** on any parameter row prints the derivation trace — the same thing
`radiant explain` prints — showing the value, its provenance, and where it came from.

## 7. Exporting a result

Once a run exists, the File menu's export actions enable:

| Action | What it writes |
|---|---|
| Export JSON Result… | the provenance record of the last run |
| Export Metrics CSV… | the metric surface as CSV |
| Export XLSX Workbook… | config, metrics, and any retained sweep in one workbook; in a study, the `Config` and `Metrics` sheets carry one value column per configuration, named as on screen |

Export Sweep CSV… joins them once a sweep has been run (chapter 10). The two YAML exports
write configuration rather than results, and are chapter 11's subject.

**Every result export carries a run stamp.** The CSVs open with `# key: value` comment lines
and the workbook carries a `Run` sheet:

```text
# run_id: 3f9c…
# evaluated_at: 2026-09-20T14:02:11+00:00
# radiant: v1.4.0 (+bf8a2118)
# config: /…/mwir_leo_minimal.yaml
# stale: no
```

`stale` is the line to read. It says `yes — the configuration was edited after this run` when
the numbers on screen predate your last edit (the gray strip, the amber **Re-evaluate**), and
`yes — the last re-evaluation failed; this is the previous result` when the window is showing
the result it kept after a failed run. A sweep's stamp says when it ran and whether the
configuration was edited after it. The status bar repeats the stale note when it applies, so a
file cannot leave the tool looking current when it is not.
