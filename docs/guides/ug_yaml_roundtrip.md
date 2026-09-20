# YAML Round-Trip

RADIANT's document is a YAML file, and the application is one editor of it. The other editors are your
text editor, the scripting window, and the CLI. This chapter is about moving between them
without losing anything — which values travel, which do not, and why.

The full file-format reference — every section, every reserved key, the dot-path convention,
the template and MODTRAN sections — is Volume III's Configuration chapter. This chapter does
not repeat those tables. It covers the
round trip as an operator experiences it.

## 1. What the document holds

A config file is **the inputs you specified**, not the resolved model. Open the minimal MWIR
example, change the QE, save it, and this is the whole file:

```yaml
# RADIANT config — written by Sensor.save()
_radiant:
  format: 1
  wavelength_points: 500
atmosphere:
  standard_atmosphere: midlat_summer
detector:
  dark_rate_e_per_s: 100.0
  pixel_pitch_x_um: 18.0
  pixel_pitch_y_um: 18.0
  qe_value: 0.62
geometry:
  sensor_altitude_m: 8000.0
optics:
  aperture_diameter_m: 0.3
  focal_length_m: 1.2
  transmission_scalar: 0.7
readout:
  adc_bits: 16
  full_well_capacity_e: 2000000.0
  gain_e_per_dn: 32.0
  read_noise_e_rms: 5.0
source:
  target:
    emissivity: 0.95
    temperature: 300.0
spectral_integration:
  filter_max_um: 5.0
  filter_min_um: 3.5
  integration_time_s: 0.005
```

Eighteen values. The schema holds 218 parameters; the other two hundred are defaults and
derived values, and writing them would turn every schema default into a frozen input that
silently stops tracking the model. **`f_number` is not in that file** even though the
GUI shows it, because it is derived from the aperture and the focal length, and a document that
stated it would be over-specifying the group.

`_radiant` is the meta block: the format version, and the wavelength-point count for the
evaluation grid. Structured sections — `optical_elements:` (chapter 7, §1.3) and
`configurations:` (chapter 8, §6) — ride alongside the parameter body when the session has them.

## 2. Edit Config (YAML)

The **Edit Config (YAML)** button in the right rail opens a roomy modal on the session
document, preloaded with exactly the text above, with **Apply / Revert / Cancel** and a caption
stating the contract:

```text
Apply re-parses and resolves through the framework; invalid YAML or a value the framework
refuses leaves the config unchanged.
```

In a study the caption instead says:

```text
This is the whole study — the shared parameters plus the configurations: section.
Apply re-parses and resolves through the framework; invalid YAML or a value the framework
refuses leaves the study unchanged.
```

That distinction is the one to remember about this editor: **it edits the document, not the
displayed configuration.** A study's text is the whole study.

### 2.1 What Apply does

Apply loads the edited text into a **fresh** document through the ordinary loader — the same
one File ▸ Open uses — then **resolves** that fresh document, and only hands it back to the
window on success. Two outcomes:

- **It parses and resolves.** The window adopts the new document, rebinds the parameter tree,
  the stage forms and the scripting console, and re-evaluates. The result is marked unsaved,
  keeps the current file path, and **the undo stack is reset** — a whole-document replacement
  is not a reversible edit, and pretending otherwise would let `Ctrl+Z` walk you into a state
  that never existed.
- **It does not.** The live document is untouched, the dialog stays open with your text still
  in it, and the real error renders **inline beneath the text**, as what / why / action: a
  `RadiantError` — bad YAML, a schema violation, a section violation naming the configuration
  and the parameter, or a value the framework refuses (out of bounds, a bad enum, an
  over-constrained consistency group). Anything else shows its traceback. Nothing is
  swallowed, and no dialog appears over the editor.

The resolve check has the same posture as every other edit: a document that is merely
**incomplete** — a required parameter deleted — is admitted, the window says `Configuration
incomplete`, and Evaluate's advisory names what is missing. A document that is **wrong** is
refused. Before this check, an out-of-bounds value typed here reached the live configuration,
was reported as "incomplete", and left the editor unable to reopen; the editor now opens on
any document, resolvable or not, so you can always repair one here.

**Revert** restores the editor to the current document's text. **Cancel** closes without
applying.

### 2.2 Editing the shape of the document

Because Apply goes through the ordinary loader, the *kind* of document is decided by the text.
Adding a `configurations:` section turns a plain session into a study and the configuration bar
appears; deleting the section collapses the study back to a plain session and the bar
disappears. Neither is a special case in the GUI — it is the parse result being adopted.

The same is true of `optical_elements:`. Adding the section opens the Optics Transmission tab in
element-train mode; removing it returns to scalar mode.

That makes the YAML editor the general escape hatch: anything the forms can express is
expressible here, and a few things the forms cannot reach are only expressible here.

*This chapter has no screenshot of the editor. It is a modal dialog, and the manual's figures
are generated by driving the GUI offscreen, where a modal cannot be captured without holding
the event loop open. The text above quotes the dialog's own strings verbatim instead.*

## 3. Open, Save, and what survives

| Action | Writes | Adopts the destination as the current file? |
|---|---|---|
| **Save** (`Ctrl+S`) | the document, to the current path (or Save As if there is none) | — |
| **Save As…** | the document, to a chosen path | yes; the title's `*` clears and the file joins the recent list |
| **Export YAML…** | the same document, to a chosen path | **no** — a snapshot, not a rebind; the dirty marker stays |
| **Export Resolved YAML…** | *every* resolved parameter, defaults and derived values included | no |

Save and Export YAML write the same bytes; they differ only in whether the session adopts the
destination. A study saves as a study, never as just the displayed configuration.

### 3.1 Provenance survives, and changes name

Values round-trip exactly. Their **provenance** changes, and it should:

| Before saving | After reopening |
|---|---|
| `user-set` (you typed it) | `config` (it came from the file) |
| `config` (it came from the file) | `config` |
| `default` (the schema supplied it) | `default` — it was not written, so it is still a default |
| `derived` (a consistency group produced it) | `derived` — it was not written either |
| `preset` (an FPA part supplied it) | `config` if the preset was applied and saved as values |

A parameter you set to `0.62` in the GUI reads:

```text
detector.qe_value = 0.62  (canonical: 0.62 )
  Provenance: user_set
  Source: Sensor.set
```

and after a save and reopen:

```text
detector.qe_value = 0.62  (canonical: 0.62 )
  Provenance: config_file
  Source: /path/to/rt.yaml
```

Same value, honest new story about where it came from. In the Parameters dock those show as the
`user-set` and `config` badges; `default` and `derived` rows are unaffected by a round trip
because they were never written.

**The `Changed only` checkbox above the parameter tree is the direct view of this.** It shows
exactly the rows whose provenance is `user-set` or `config` — your configuration, as a short
list — so after a round trip it shows the file's contents. Note the one row it does *not* show:
a value an FPA preset supplied carries the `preset` badge until the document is saved, so it is
hidden by `Changed only` in the session where the preset was applied and shown in every session
after.

### 3.2 Two things that do not survive a save

**Held element rows.** If you switched the Transmission tab to scalar mode while an element
train was in the table, those rows are held in the session only. Saving writes no
`optical_elements:` section, and the save confirmation adds a note saying how many rows were not
written. That is deliberate — a file with an element list means element mode, with no hidden
inactive state — but it is the one case where what you can see is not what gets written, so the
application tells you at the moment it happens.

**The undo stack.** It is session state, not document state.

## 4. Export Resolved YAML

`Export Resolved YAML…` writes the fully specified configuration: every parameter, including
every default and every derived value. It is a *documentation* export — a complete statement of
the model that produced a result, suitable for an appendix, a review package, or a diff against
another run.

It is not the file you should keep working in. Because every default is now an explicit input,
a resolved export stops tracking schema defaults, and a derived value written as an input will
over-specify its consistency group the next time you change one of its partners.

## 5. Result exports

The other File ▸ Export actions write results rather than configuration, and enable only once a
run exists:

| Action | Contents |
|---|---|
| Export JSON Result… | the provenance record of the last run |
| Export Metrics CSV… | the metric surface with units |
| Export Sweep CSV… | the retained sweep (enabled once a sweep has run — chapter 10) |
| Export XLSX Workbook… | configuration, metrics, and any retained sweep, in one workbook |

The XLSX export is the one to reach for when a result is going to someone who will open it in a
spreadsheet: it carries the configuration that produced the numbers in the same file as the
numbers, which a bare CSV does not.

## 6. Working across the GUI, scripts and the CLI

One document, three drivers, and no format differences between them.

**GUI → script.** The scripting window (`Ctrl+Shift+P`) is bound to the displayed sensor
already; `sensor` is in its namespace. The sweep dialog's **Copy as script** emits a
reproduction block for the trade you just configured (chapter 10, §1.3).

**Script → GUI.** `Sensor.save(path)` writes the same format the GUI opens. A configuration set
built programmatically saves as a study and opens with its selector.

**CLI.** `radiant run config.yaml` evaluates the same file; `radiant validate config.yaml`
resolves it without running the physics and reports every configuration of a study, one line
each. A study file requires `--configuration <name>` for `run`, because the `active`
designation in the file is GUI display state and must never become a silent batch default.

**One caution when moving between machines.** File-valued parameters — a QE curve CSV, a
coating file, a Zernike export, a tape7 — are stored relative to the file's own directory when
they can be, so a config plus its `data/` folder is portable. A path typed as an absolute path
stays absolute, and the parameter dock shows file parameters resolved to absolute paths, so
what you see in the tree is not necessarily what is written in the file. Keep referenced data
beside the config and the round trip is portable; reach outside that directory and it is not.
