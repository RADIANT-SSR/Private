# RADIANT

First-principles electro-optical (EO) sensor performance modeling framework.

Predicts SNR, NEDT, NIIRS, MTF, and detection range for space-based and airborne EO sensors.

## Quick Start

```bash
pip install -e ".[dev]"
radiant --help
```

## Documentation

See `docs/` for architecture documents and `DEVELOPMENT.md` for developer setup.

## Signal Chain

source → atmosphere → optics → platform → spectral_integration → detector → readout → performance
