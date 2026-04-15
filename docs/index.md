# RADIANT

**First-principles EO sensor performance modeling.**

RADIANT predicts SNR, NEDT, NIIRS, MTF, and detection range for space-based
and airborne electro-optical sensors. It models the complete signal chain
from source emission through atmospheric propagation, optical collection,
spectral integration, detector response, and readout electronics to
performance metrics.

---

## Get Started in 5 Minutes

Follow the [Quickstart Guide](guides/quickstart.md) to install RADIANT, run
your first evaluation, and perform a parameter sweep.

---

## Features

- **7-stage signal chain** --- source, atmosphere, optics, platform, spectral
  integration, detector, readout, with full physics at each stage
- **Parametric sweeps** --- 1D and 2D parameter sweeps via CLI or Python API
- **Monte Carlo tolerance analysis** --- assign statistical distributions to
  parameters and propagate uncertainty through the signal chain
- **CLI and Python API** --- `radiant run`, `radiant sweep`, `radiant explain`,
  or script with the `Sensor` class
- **Sensitivity analysis** --- identify which parameters have the largest
  impact on performance metrics
- **Data library** --- bundled material emissivity spectra, detector QE
  curves, solar irradiance, and 12 sensor templates

---

## Documentation

### User Guides

- [Quickstart](guides/quickstart.md) --- install and first evaluation
- [Configuration](guides/configuration.md) --- YAML structure, defaults, overrides
- [Scripting](guides/scripting.md) --- Python API for sweeps, Monte Carlo, sensitivity
- [Parameter Reference](guides/parameter_reference.md) --- all 91 parameters
- [Regime Selection](guides/regime_selection.md) --- extended, sub-pixel, point-source
- [Trade Studies](guides/trade_studies.md) --- worked examples of common workflows

### Theory

- [Radiometric Chain](theory/radiometric_chain.md) --- governing equations for all 7 stages
- [Noise Model](theory/noise_model.md) --- 16 noise sources, scaling rules, regimes
- [Spatial Model](theory/spatial_model.md) --- PSF, MTF, EE, RER, NIIRS/GIQE-5

### Developer

- [Architecture](RADIANT_Master_Architecture.md) --- non-negotiable design rules
- [Signal Chain](RADIANT_Signal_Chain_Architecture.md) --- stage protocol, ChainState
- [Conventions](RADIANT_Conventions.md) --- units, coordinates, spectral variable
- [Parameters](RADIANT_Parameter_System.md) --- parameter naming and resolution
- [Testing](RADIANT_Testing_Validation.md) --- test levels and validation framework
