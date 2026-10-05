# Reference — Every Way to Define Optical Transmission

**Example**: `transmission_doors` · ships in the wheel as
`radiant/data/examples/transmission_doors.yaml` · modality: config-led, GUI-readable

---

## What this example is

A syntax reference that happens to run. The other six bundled examples are curated
snapshots of real scenarios; this one is a deliberately unrealistic six-element train
whose only job is to use **every way of defining optical transmission at once**, so you
can read the forms side by side and diff your own config against it.

Open it, copy the element whose shape matches the datasheet in front of you, and delete
the rest.

It evaluates to SNR 1181.00 [-] with a band-mean system throughput of 0.80595 [-]. Those
numbers are not a result anyone should cite; they exist so the file stays honest.

## The first fork: scalar τ, or an element train

RADIANT accepts optical transmission in exactly two mutually exclusive forms.

| | How you say it | When it is right |
|---|---|---|
| **Scalar** | `optics.transmission_scalar: 0.70` | You know the net throughput and nothing else — a vendor's single number, an early trade. |
| **Element train** | an `optical_elements:` list | You have a prescription: surfaces, coatings, temperatures. |

A config carrying both is refused — there is no rule for which should win. This example
uses the train, so it has **no** `transmission_scalar` line at all.

The choice is not only bookkeeping. A scalar τ is a lumped number with no surfaces, so
it has **no Kirchhoff emissivity** and contributes no warm-optics self-emission. In a
thermal band that omission is not small: declaring the same net τ as a real train of
290 K surfaces is what puts the optics' own glow into the background. If you are working
in the MWIR or LWIR and you care about the noise floor, the train is not a refinement —
it is the model.

## The second fork: three forms, per quantity

Every optical quantity — a mirror's reflectance, a lens surface's coating, a bulk
absorption coefficient — takes any of three forms, independently of every other quantity
in the file.

**Scalar.** One number, flat across the band.

```yaml
reflectance: 0.980
```

**Spectral CSV.** A path, resolved relative to *the config file*, not the working
directory. Two columns, `wavelength_um` then value. Lines starting with `#` are
comments, and a single column-header row is accepted — which is what Excel and pandas
write, so you do not have to strip it.

```yaml
reflectance: transmission/protected_silver_R.csv
```

**Inline λ-table.** The same meaning as a CSV, carried in the config itself. Right for a
handful of points you do not want to manage as a separate file.

```yaml
reflectance:
  wavelength_um: [3.0, 4.0, 5.0]
  values: [0.975, 0.978, 0.974]
```

`NaN` and `inf` are refused in a CSV rather than read as data: one of them interpolates
across the whole grid, and a silently-NaN emissivity is worse than a stopped run.

## The third fork: three element models

| Model | What it is | ε |
|---|---|---|
| **Reflective** | A mirror: one surface, one reflectance. | 1 − R, derived |
| **Simple refractive** | One net transmittance and nothing else. | **0, by construction** |
| **Cavity** | Two coated surfaces around an absorbing bulk. | derived from α·d and the coatings |

The middle row is the one that surprises people. A simple refractive element takes the
remaining 1 − τ to be **reflection, not absorption**, so its emissivity is zero and it
emits nothing at any temperature. That is the correct model for a cold window whose
losses you only know in aggregate — and the wrong one if you need its thermal emission.
In this example `dewar_window` sits at 80 K where it does not matter; put the same
element at 290 K and you would be silently omitting its glow.

Use the cavity model when you need an element's emission. It is also the only model a
substrate can act on, which is why naming one on a mirror or on a simple refractive row
is refused rather than quietly ignored.

## The fourth fork: where the bulk absorption comes from

A cavity element needs the bulk absorption coefficient α. There are two doors, and they
reach the identical physics.

**Named substrate** — the bundled material library supplies α(λ):

```yaml
substrate: germanium
thickness_m: 0.008
R1: 0.010
R2: 0.010
```

**Explicit α** — the custom-material path, for a measured coupon or a material the
library does not carry. It takes all three forms, and a measured coupon is a spectrum:

```yaml
alpha: transmission/chalcogenide_alpha.csv
thickness_m: 0.006
```

Naming a substrate **and** giving α over-specifies the element and is refused: a
substrate supplies exactly that quantity, so there is no rule for which should win.
`thickness_m` is required either way — thickness belongs to the lens, never to the
material.

The library carries six materials in two confidence tiers. ZnSe, CaF₂ and multispectral
ZnS are built from five or six published laser-line α anchors; Ge, Si and BaF₂ are
flagged as class-typical, because an analyst cannot avoid germanium and silicon whatever
the data density. The tier is shown wherever you pick a material, and a substrate used
outside its published window is refused rather than extrapolated — past an absorption
edge, an extrapolated α is not an approximation, it is a different material.

There is no refractive index input. It entered no formula.

## The fifth fork: the two surfaces are independent

A cavity's faces may differ in **value and in form**, which is what a real lens looks
like — a measured coating on one face and a nominal number on the other. `imager_custom`
in this example does exactly that:

```yaml
R1: transmission/ar_coating_ge_R.csv   # measured curve
T2: 0.988                               # nominal scalar
```

Note also that surface 1 is given as **R** and surface 2 as **T**. Either is accepted
per surface, and the other is derived: coatings are lossless by model rule, so
R + T = 1. Give whichever the datasheet quotes.

## What each element in the file demonstrates

| # | Element | Door | Through-value [-] | ε [-] |
|---|---|---|---|---|
| 1 | `primary` | REFLECTIVE, scalar | 0.98000 | 0.02000 |
| 2 | `secondary` | REFLECTIVE, spectral CSV | 0.98000 | 0.02000 |
| 3 | `fold` | REFLECTIVE, inline λ-table | 0.97567 | 0.02433 |
| 4 | `dewar_window` | simple REFRACTIVE, scalar τ | 0.92000 | 0.00000 |
| 5 | `collimator_ge` | cavity, named substrate | 0.96600 | 0.01438 |
| 6 | `imager_custom` | cavity, explicit α from CSV, mixed-form surfaces | 0.96781 | 0.01066 |

Row 4's zero emissivity is the simple-refractive model doing what it says. Rows 5 and 6
differ in where α came from and in nothing else.

## Reading it in the GUI

Open the example and go to **Optics ▸ Transmission**. The train table is the overview;
selecting a row opens that element in the detail editor beside its figure.

- **Model** names which of the three models the element uses, and switches between them.
  A switch states what it will cost before it applies — converting a simple element to a
  cavity has to *seed* coatings, because one net transmittance cannot determine two
  coatings plus a bulk.
- **Definition** shows the two surfaces independently, each with its own R-or-T choice
  and its own scalar / table / CSV source.
- **Bulk** offers the named substrate or the explicit α as one choice, never two fields
  you can both fill — so the over-specification above cannot be constructed. On rows 1–4
  the same tab explains why there is no bulk.
- **View α(λ)…** draws the chosen material's absorption on a log axis across its whole
  published window with the run band shaded. α spans orders of magnitude inside a
  transparency window — CaF₂'s rises 645× across its own — so a linear axis would
  collapse the transparent region onto zero.

## See also

- `docs/guides/examples_running.md` — running a bundled example
- `docs/architecture/RADIANT_Optics.md` §6 — the cavity model and the first-order
  one-interaction-per-surface rule
- `docs/guides/parameter_reference.md` — every parameter, generated from the schema
