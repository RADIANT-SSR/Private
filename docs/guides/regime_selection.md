# Regime Selection Guide

*Persona: Sarah (systems engineer), Raj (mission planner)*

How RADIANT classifies targets into radiometric regimes and why it matters.

---

## What Is a Radiometric Regime?

The radiometric regime determines how signal couples from the target through
the optical system to the detector. RADIANT supports three regimes:

| Regime          | Physical meaning                              | EE_box applied? |
|-----------------|-----------------------------------------------|-----------------|
| **Extended**    | Target fills the pixel completely              | No              |
| **Sub-pixel**   | Target smaller than pixel but larger than PSF | Yes (target only) |
| **Point-source** | Target smaller than the diffraction limit    | Yes (target only) |

The regime affects SNR because a smaller target puts less energy into the
pixel. EE_box (ensquared energy) accounts for how much of the PSF falls
within the pixel footprint.

---

## How RADIANT Classifies Regime

Classification is a two-step process (Rule 10):

### Step 1: SourceStage (tentative)

The source stage computes the target's angular extent:

$$\theta = \sqrt{A_{\text{target}}} \;/\; R$$

where $A_{\text{target}}$ is `source.target.projected_area_m2` and $R$ is
the slant range. It compares $\theta$ to the pixel IFOV:

$$\text{IFOV} = p_{\text{pitch}} \;/\; f$$

Decision logic:

```
if fill_fraction < 1.0:
    regime = SUB_PIXEL
elif regime_override != "auto":
    regime = regime_override
elif theta >= 2 * IFOV:
    regime = EXTENDED
elif theta <= 0.25 * IFOV:
    regime = POINT_SOURCE
else:
    regime = SUB_PIXEL
```

### Step 2: OpticsStage (final)

The optics stage confirms or refines the classification, accounting for the
actual PSF size. All downstream stages read the **final** regime from:

`result.stage_outputs["optics"]["regime"]`

Never re-classify after OpticsStage.

---

## Decision Flowchart

```
                    Is fill_fraction < 1.0?
                           |
                    Yes ---|--- No
                    |            |
               SUB_PIXEL    Is regime_override set?
                                 |
                          Yes ---|--- No
                          |            |
                     Use override    Compute angular extent theta
                                         |
                              theta >= 2*IFOV?
                                   |
                            Yes ---|--- No
                            |            |
                       EXTENDED    theta <= 0.25*IFOV?
                                         |
                                  Yes ---|--- No
                                  |            |
                            POINT_SOURCE   SUB_PIXEL
```

---

## When to Use Each Regime

### Extended Scene (default for most Earth observation)

The target fills the pixel or is much larger than the IFOV. Signal per pixel
depends on radiance (W/m^2/sr/um) only --- the pixel sees a uniform field.

Typical targets: terrain, water, buildings, forest canopy, cloud tops.

```bash
radiant run examples/templates/mwir_leo_pushbroom.yaml
```

No `projected_area_m2` or `range_m` needed --- extended is the default when
`fill_fraction = 1.0` and no area/range are given.

### Sub-Pixel

The target is smaller than the pixel but larger than the diffraction limit.
The pixel sees a mix of target and background, weighted by fill fraction.
EE_box is applied to the target signal but not to the background.

Typical targets: small vehicles, people, small boats from high altitude.

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/templates/mwir_leo_pushbroom.yaml")
sensor.set("source.target.projected_area_m2", 10.0)  # 10 m^2 vehicle
sensor.set("source.target.range_m", 8000.0)
sensor.set("source.target.fill_fraction", 0.3)
sub_result = sensor.evaluate()
regime = sub_result.stage_outputs["optics"]["regime"]
```

### Point Source

The target is much smaller than the diffraction limit. Most of the PSF
energy may fall outside the pixel. EE_box captures how much lands in the
central pixel.

Typical targets: stars, distant missiles, satellites, laser glints.

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/templates/mwir_leo_pushbroom.yaml")
sensor.set("source.target.projected_area_m2", 0.01)   # tiny
sensor.set("source.target.range_m", 100000.0)          # 100 km
result = sensor.evaluate()
```

---

## Where EE_box Is Applied (Rule 9)

EE_box is applied **exactly once**, in `SpectralIntegrationStage`:

- **Extended**: EE_box = 1.0 (not applied --- pixel is filled)
- **Sub-pixel**: EE_box applied to the target signal only, **not** to
  the background term
- **Point-source**: EE_box applied to the target signal

This ensures that sub-pixel and point-source SNR correctly accounts for
aperture loss without double-counting.

---

## Manual Override

If the automatic classification is wrong for your scenario, override it:

```yaml
source:
  regime_override: point_source   # or: extended, sub_pixel, auto
```

Or in Python:

```python
from radiant.api import Sensor

sensor = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
sensor.set("source.regime_override", "point_source")
```

---

## Common Pitfall

**Symptom**: SNR is unexpectedly low or high.

**Cause**: Wrong regime. An extended target treated as point-source will have
EE_box < 1, reducing signal. A point source treated as extended will
overestimate signal because it assumes the pixel is uniformly filled.

**Fix**: Check `result.stage_outputs["optics"]["regime"]` and verify it
matches your target geometry. If it doesn't, set `regime_override` or
adjust `projected_area_m2` and `range_m`.
