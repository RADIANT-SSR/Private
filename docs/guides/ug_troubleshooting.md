# Troubleshooting

RADIANT refuses things. It refuses them a lot, and the refusals are the point: a model that
accepts an impossible input and returns a plausible number is worse than one that stops. This
chapter is about reading those refusals, knowing which surface each one appears on, and getting
back to a working configuration.

## 1. The shape of every error

Every error RADIANT raises about your inputs carries three fields, and they answer three
different questions:

| Field | Question |
|---|---|
| **what** | what did you do that was refused |
| **why** | what physics or model constraint makes it wrong |
| **action** | what to type instead |

Some carry a fourth, **context** — the parameter, the value, the bounds — so the message is
machine-readable as well as human-readable.

Here is a whole one, produced by typing a detector temperature of 5000 K:

```text
What:    Parameter 'detector.detector_temperature_K' = 5000.0 out of bounds [1.0, 500.0] (K)
Why:     'detector.detector_temperature_K' must lie within its declared valid domain
         [1.0, 500.0] K
Action:  Set 'detector.detector_temperature_K' to a value in [1.0, 500.0] K
context.param:  detector.detector_temperature_K
context.value:  5000.0
context.bounds: (1.0, 500.0)
context.unit:   K
```

Three consequences of this design worth knowing as an operator.

**The message is never paraphrased by the GUI.** The dialog and the Messages row render the
fields the framework produced, verbatim.

**A rejected value never reaches your model.** Every edit is validated on a throwaway copy of
the configuration first, by one rule shared by the in-place editor, the Parameter Editor and
Reset to Default: only a failure *your change introduces* is a rejection. When a value is
refused, the row keeps the value it had, and nothing downstream saw the bad one. On a
configuration that is still incomplete, a legal value is accepted — the missing parameters
are Evaluate's advisory to report, not your value's fault — but a value that is wrong on its
own terms (out of bounds, a disagreeing member of a consistency group) is refused however
incomplete the configuration is.

**A rejection is not a failure of the run.** The last result stays on screen, marked stale.

## 2. Where errors appear

Four surfaces, and which one you get is decided structurally — by the *type* of the error and
its context, never by matching words in its message.

| Surface | Carries |
|---|---|
| **Inline where you typed** — the row's tint, banner and tooltip for an in-place edit; the error area inside the Parameter Editor for a dialog edit | a rejected *edit*: the value you just typed is wrong on its own terms |
| The **Parameter Rejected** dialog | a refused **Reset to Default** (headed `Cannot reset "<dot-path>"`), and the rejection of an edit made outside the dock — a stage form or the YAML editor |
| **The Messages panel** | everything a completed run had to say — warnings, advisories, and failures |
| **The status bar** | a one-line summary of the last action, and the specific thing to fix when a failure is attributable |
| **The stage strip** | which stage is implicated, when that can be known |

The **Parameter Rejected** dialog is headed `Cannot set "<dot-path>"` (or `Cannot reset …`)
and lists What / Why / Action / context, each selectable so you can copy it into a bug report. A failure that is *not*
a RADIANT error — a genuine bug rather than a bad input — gets a different dialog instead, with
the message up front and the full traceback behind a **Show details** fold. Nothing is
swallowed either way.

## 3. The common rejection families

### 3.1 Out of bounds

The most common one, and the easiest to fix, because the message contains the answer.

```text
Parameter 'detector.fill_factor' = 1.5 out of bounds [0.0, 1.0] (dimensionless)
  Why: 'detector.fill_factor' must lie within its declared valid domain [0.0, 1.0]
       dimensionless
  Action: Set 'detector.fill_factor' to a value in [0.0, 1.0] dimensionless
```

```text
Parameter 'optics.aperture_diameter_m' = -0.5 out of bounds [0.0001, 20.0] (m)
```

**Bounds are stated in the parameter's own unit**, and if you typed in a different display unit
the conversion has already happened — you are being told the bounds in the unit the schema
declares, which the Parameter Editor also shows you before you commit.

### 3.2 Not a valid choice

An enumeration lists its whole closed set:

```text
Parameter 'atmosphere.model' = 'bogus'; must be one of ['simple', 'exo', 'tabulated',
'modtran', 'interpolated']
  Why: 'atmosphere.model' is a fixed-choice parameter with a closed set of valid values
  Action: Set 'atmosphere.model' to one of ['simple', 'exo', 'tabulated', 'modtran',
          'interpolated']
```

In the GUI you will rarely see this one, because an enumerated parameter edits through a combo
box built from that same list. It is what you get from the YAML editor, a script, or the CLI.

### 3.3 A parameter that does not exist

Typos are caught with a suggestion:

```text
Unknown parameter: 'optics.apeture_diameter_m'. Did you mean:
'optics.aperture_diameter_m', 'optics.spider_width_m', 'optics.focal_length_m'?
```

### 3.4 Over-constrained consistency groups

The family that confuses people most, because every individual value is legal. Aperture
diameter, focal length and f-number form a group: give any two, the third is derived. Give all
three and they must agree.

Setting `f_number = 8.0` on a configuration that already states a 0.30 m aperture and a 1.20 m
focal length:

```text
Consistency group 'fnumber' is over-constrained:
  Constraint: f_number = focal_length_m / aperture_diameter_m
  User-specified 'optics.aperture_diameter_m' = 0.3
  Computed 'optics.aperture_diameter_m' from other parameters = 0.15
  Relative discrepancy: 1.500e-01 (tolerance: 1.000e-03)
  Fix: either remove 'optics.aperture_diameter_m' from inputs and let it be derived, or
       correct the inconsistent value.
```

Read it as: *these three numbers cannot all be true*. The tolerance is 0.1 %, so a value that
agrees to rounding is accepted. The fix is in the message: drop one of the three — in the GUI,
right-click the row and **Reset to Default**, which clears your input so the parameter reverts
to being derived — or make the third value consistent.

**Geometry has its own version, and it is the one you are most likely to hit.** Each geometry
family accepts exactly one mode, and setting a second door of the same family is
over-specification:

```text
What:   Over-specified viewing geometry: 2 inputs imply disagreeing values —
        geometry.path_zenith_rad ⇒ 0.3 rad (17.189°); geometry.ground_range_m ⇒
        1.41616 rad (81.140°)
Why:    Multiple input modes were set for the same canonical quantity and they disagree
        by more than 1%. RADIANT cannot know which one describes the intended scene.
Action: Set exactly one of these parameters (the others derive from it), or make the
        redundant values consistent.
```

This one comes with a **locator**: the application tints the offending family's card and jumps
you to the Geometry workspace, so you do not have to work out which of four family cards the
dot-paths belong to. The tint is navigation only — the actionable text is in the dialog and the
Messages panel, as always.

### 3.5 A required parameter with no value

```text
Required parameter 'detector.pixel_pitch_x_um' is not set.
  Description: Pixel pitch along the cross-track (x) axis.
  Expected type: float in um
  Action: set 'detector.pixel_pitch_x_um' — it has no default
```

This is the family that has **no modal**, on purpose — see §4.

### 3.6 Kirchhoff and the element train

Kirchhoff's law is enforced by making the over-specification unrepresentable rather than by
refusing it after the fact. There is no emissivity input for an optical element
anywhere in the GUI, the YAML, or the API: a mirror row takes a reflectance, a refractive row
takes a transmittance, and ε is derived and shown read-only.

The document parser reinforces that: a row's transfer mode decides which single value is read —
`reflectance` for `REFLECTIVE`, `transmittance` for `REFRACTIVE` — so a train you author in the
GUI, in YAML, or through the API cannot state an $R$ and a $T$ for the same surface, and cannot
state an ε at all.

What you *can* get wrong is the value:

```text
OpticalElement 'M1': reflectance values must be in [0, 1], got range [1.4, 1.4].
```

and a malformed row says which field is missing and what the row actually carried:

```text
Element 'M1': missing required field 'transfer_mode'. Available fields:
['name', 'kind', 'reflectance', 'temperature_K'].
```

The deeper energy-conservation checks — `T + R = 1.2 > 1 at some wavelengths`, or a mirror with
non-zero transmittance — live on the element object itself and guard the programmatic
construction path; they are not reachable from a config document, for the reason above.

Element errors from the table render **inline beneath the table**, not as a modal per keystroke,
and the row stays as a visible pending draft until it validates (chapter 7, §1.3).

## 4. Advisories — the failures that are not your fault

Some evaluations fail for reasons that are not a bad input at all: you are half-way through
building something, or your scene is perfectly legal and the bundled data simply does not cover
it. Rendering those as **Parameter Rejected** miscategorizes them, and because they fire one
gate at a time, it turns a normal working session into a wall of modals.

So these are **advisories**: no dialog, the implicated stage's chip red and the rest gray, the
specific fix named in the status bar, and the full what / why / action in the Messages panel.

| Situation | Status bar says |
|---|---|
| a required parameter is unset (e.g. after removing an FPA preset that supplied it) | `Config incomplete — set detector.pixel_pitch_x_um (see Messages; the previous result is shown, stale)` |
| a calibration scheme is active without its cal point | `The calibration scheme needs its cal temperature(s) — set them on the Calibration panel (see Messages; the previous result is shown, stale)` |
| digital counting is selected without a charge packet | `Digital counting needs a charge packet — set readout.count_packet_e on the Readout panel (see Messages; the previous result is shown, stale)` |
| the interpolated atmosphere library has no column for this scene | `The atmosphere library does not cover this scene — see Messages (the previous result is shown, stale)` |

![The right rail after a failed evaluation — the pinned cards flipped to their stale marker and
the Messages panel carrying the error.](figures/gui/ug_messages_error.png)

The figure is the calibration case, reached by switching `calibration.scheme` to `two_point` and
not yet typing a cal temperature. The rail shows the whole story at once: five pinned cards with
no value, the Evaluate button flipped to amber **Re-evaluate F5**, the Messages header reading
`1 error`, and the message itself:

```text
✕ calibration.scheme = 'two_point' needs a cal point, but calibration.cal_temp_low_K is unset.
    Why: an active NUC scheme corrects at known cal-source temperatures; without them there
    is nothing to correct at.
    Action: set calibration.cal_temp_low_K (and cal_temp_high_K for two_point), or set
    calibration.scheme = 'none'.
```

Type the cal temperature and the next debounced run clears it. Nothing was lost.

The atmosphere case deserves its own sentence, because it is the one that reads like an error
and is not. Your scene is legal and your inputs are legal; the bundled measured library simply
holds no column for that geometry. The remedy is a different family or
`atmosphere.model: simple`, and the family picker names the single closest miss rather than
producing a warning per failed gate. Chapter 6, §3 has the coverage guidance.

## 5. Where the logs are

**The GUI does not configure logging.** There is no log file, no log window, and no verbosity
setting. The library writes to the standard Python `logging` module under module-named loggers,
and with no handler installed, Python's last-resort handler prints records of `WARNING` and
above to **stderr** — the terminal you launched `radiant gui` from.

What that means in practice:

- **Launch from a terminal when you are chasing something.** `radiant gui config.yaml` from a
  shell gives you the stderr stream; launching from a desktop icon discards it.
- **Two classes of message go there and nowhere else.** The dual-path spatial consistency check
  logs a warning when the PSF path and the MTF product disagree — that means a degradation
  reached one path and not the other, which is a defect worth reporting. And the window logs a
  warning if an evaluation worker outlives a close by more than five seconds.
- **Everything an operator needs is in the window.** Warnings from the run are in the Messages
  panel verbatim; failures are in the rail and, where appropriate, in a dialog. The stderr stream
  is developer diagnostics, not a second copy of the user-facing messages.
- **To capture it**, redirect: `radiant gui config.yaml 2> radiant-gui.log`.

If you want a machine-readable record of a *run* rather than of the application, that is
**File ▸ Export JSON Result…** — the provenance record of the last evaluation.

## 6. Getting back to a working state

### 6.1 Per parameter

**Right-click ▸ Reset to Default** clears your input for that parameter, so it reverts to its
schema default or is re-derived. This is the correct fix for an over-constrained consistency
group: you are not setting a value, you are withdrawing one.

**Right-click ▸ Explain** prints the derivation trace — value, provenance, and where it came
from. When a number is not what you expect, this answers "who set this" in one step.

**`Ctrl+Z`** undoes parameter edits and element-train edits, twenty steps deep. A whole-document
swap — File ▸ Open, or an Apply in the YAML editor — clears the history, because it is not a
reversible edit.

### 6.2 Per document

**Edit ▸ Reset to Defaults** clears the whole input set.

**Edit Config (YAML) ▸ Revert** restores the editor text to the current document. If you have
already applied something you did not mean to, **Ctrl+Z** is gone (the undo stack resets on an
Apply), so the recovery is File ▸ Open on the last saved file.

**The title bar tells you whether you can afford that.** A leading `*` means unsaved edits, and
any action that would discard them — New, Open, a recent file, Quit — passes through the
unsaved-edits guard first, which offers Save, Discard or Cancel. A Save that you then cancel
cancels the whole action; you cannot lose work by accident.

### 6.3 From nothing

**File ▸ New** — or launching with no file — puts the welcome screen in the center column
instead of dead space, and it is a recovery surface as much as an onboarding one:

- a grid of **mission-template cards**, each with a name, a one-line description and a
  specification line — a known-good starting configuration for a class of mission;
- a **Blank config** card, for building from scratch;
- a **Worked examples** group of bundled studies;
- an **Open recent** list.

Activating any card is an ordinary file open with a known path, so when a session has become
tangled, starting from a template and re-applying the handful of parameters you care about is
often faster than unpicking it — especially with **Changed only** ticked on the old file to
list exactly what you had set.

*In a wheel install with no templates on disk the grid section is absent and the screen degrades
to Blank config plus Recent.*

## 7. Diagnosing a number rather than an error

Not every problem announces itself. A run that completes and returns a number you do not
believe has its own short checklist.

1. **Is the strip green?** Yellow means there is something in Messages you have not read.
2. **Is the banner up?** A saturated well hard-clips the signal, and SNR, NEDT and NIIRS all
   reflect the clipped value (chapter 9, §1.2).
3. **Which mode did the chain actually use?** The Geometry workspace's resolution outputs state,
   in words, which door each family walked through: `viewing_mode = path_zenith (default)`,
   `kinematics_mode = direct`. A geometry that resolved through the mode you did not intend is
   the single most common cause of a surprising range or GSD.
4. **What regime is it in?** The Optics workspace's `Regime` output is the final classification,
   and it decides whether ensquared energy is applied, whether the background term exists, and
   which SNR definition is in force.
5. **Is a metric missing because it was switched off?** A card reading
   `n/a — not computed for this run` is a metric group you deselected (chapter 9, §2), not a
   failure.
6. **Has something aged out?** A gray strip and an amber **Re-evaluate** button mean the numbers
   predate your last edit.
7. **Open the Inspector** (`Ctrl+I`) and walk the intermediates. The stage that first looks
   wrong is nearly always upstream of the stage whose metric looked wrong.
