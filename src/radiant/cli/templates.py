"""``radiant template`` subcommand — sensor templates.

Ships 4 canonical sensor configurations as starting points.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import click
import yaml

# ------------------------------------------------------------------
# Template definitions
# ------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, Any]] = {
    "mwir_leo_pushbroom": {
        "description": "Baseline MWIR LEO pushbroom — 0.30m aperture, 3.5–5.0 µm",
        "config": {
            "source": {
                "target": {"temperature": 300.0, "emissivity": 0.95},
            },
            "atmosphere": {"standard_atmosphere": "midlat_summer"},
            "geometry": {"sensor_altitude_m": 8000.0},
            "optics": {
                "aperture_diameter_m": 0.30,
                "focal_length_m": 1.20,
                "transmission_scalar": 0.70,
            },
            "detector": {
                "pixel_pitch_x_um": 18.0,
                "pixel_pitch_y_um": 18.0,
                "qe_value": 0.70,
                "dark_rate_e_per_s": 100.0,
            },
            "spectral_integration": {
                "filter_min_um": 3.5,
                "filter_max_um": 5.0,
                "integration_time_s": 0.005,
            },
            "readout": {
                "read_noise_e_rms": 5.0,
                "gain_e_per_dn": 1.0,
                "adc_bits": 16,
            },
        },
    },
    "vnir_aerial": {
        "description": "Visible/NIR aerial sensor — 0.15m aperture, 0.4–0.9 µm",
        "config": {
            "source": {
                "target": {"temperature": 5800.0, "emissivity": 0.10},
            },
            "atmosphere": {"standard_atmosphere": "midlat_summer"},
            "geometry": {"sensor_altitude_m": 3000.0},
            "optics": {
                "aperture_diameter_m": 0.15,
                "focal_length_m": 0.60,
                "transmission_scalar": 0.80,
            },
            "detector": {
                "pixel_pitch_x_um": 5.5,
                "pixel_pitch_y_um": 5.5,
                "qe_value": 0.85,
                "dark_rate_e_per_s": 10.0,
            },
            "spectral_integration": {
                "filter_min_um": 0.4,
                "filter_max_um": 0.9,
                "integration_time_s": 0.001,
            },
            "readout": {
                "read_noise_e_rms": 3.0,
                "gain_e_per_dn": 1.0,
                "adc_bits": 14,
            },
        },
    },
    "lwir_geo": {
        "description": "LWIR geostationary — 0.50m aperture, 8–12 µm",
        "config": {
            "source": {
                "target": {"temperature": 290.0, "emissivity": 0.97},
            },
            "atmosphere": {"standard_atmosphere": "midlat_summer"},
            "geometry": {"sensor_altitude_m": 35786000.0},
            "optics": {
                "aperture_diameter_m": 0.50,
                "focal_length_m": 2.00,
                "transmission_scalar": 0.65,
            },
            "detector": {
                "pixel_pitch_x_um": 25.0,
                "pixel_pitch_y_um": 25.0,
                "qe_value": 0.60,
                "dark_rate_e_per_s": 500.0,
            },
            "spectral_integration": {
                "filter_min_um": 8.0,
                "filter_max_um": 12.0,
                "integration_time_s": 0.020,
            },
            "readout": {
                "read_noise_e_rms": 15.0,
                "gain_e_per_dn": 2.0,
                "adc_bits": 14,
            },
        },
    },
    "swir_leo": {
        "description": "SWIR LEO mapper — 0.25m aperture, 1.0–2.5 µm",
        "config": {
            "source": {
                "target": {"temperature": 300.0, "emissivity": 0.90},
            },
            "atmosphere": {"standard_atmosphere": "midlat_summer"},
            "geometry": {"sensor_altitude_m": 500000.0},
            "optics": {
                "aperture_diameter_m": 0.25,
                "focal_length_m": 1.00,
                "transmission_scalar": 0.75,
            },
            "detector": {
                "pixel_pitch_x_um": 15.0,
                "pixel_pitch_y_um": 15.0,
                "qe_value": 0.75,
                "dark_rate_e_per_s": 50.0,
            },
            "spectral_integration": {
                "filter_min_um": 1.0,
                "filter_max_um": 2.5,
                "integration_time_s": 0.010,
            },
            "readout": {
                "read_noise_e_rms": 8.0,
                "gain_e_per_dn": 1.0,
                "adc_bits": 14,
            },
        },
    },
}


# ------------------------------------------------------------------
# Click commands
# ------------------------------------------------------------------


@click.group()
def template() -> None:
    """Manage sensor configuration templates."""


@template.command("list")
def template_list() -> None:
    """List available sensor templates."""
    click.echo(f"{'Name':<25s}  Description")
    click.echo("-" * 70)
    for name, tmpl in sorted(TEMPLATES.items()):
        click.echo(f"{name:<25s}  {tmpl['description']}")


@template.command("show")
@click.argument("name")
def template_show(name: str) -> None:
    """Print a template configuration as YAML."""
    if name not in TEMPLATES:
        click.echo(f"Error: unknown template '{name}'.", err=True)
        click.echo(f"Available: {', '.join(sorted(TEMPLATES))}", err=True)
        sys.exit(1)
    header = f"# RADIANT template: {name}\n# {TEMPLATES[name]['description']}\n"
    click.echo(
        header
        + yaml.dump(
            TEMPLATES[name]["config"],
            default_flow_style=False,
            sort_keys=True,
        )
    )


@template.command("create")
@click.argument("name")
@click.option(
    "--output",
    "output_path",
    type=click.Path(),
    default=None,
    help="Output file path (default: <name>.yaml in current directory).",
)
def template_create(name: str, output_path: str | None) -> None:
    """Write a template YAML to a file as a starting point."""
    if name not in TEMPLATES:
        click.echo(f"Error: unknown template '{name}'.", err=True)
        click.echo(f"Available: {', '.join(sorted(TEMPLATES))}", err=True)
        sys.exit(1)

    if output_path is None:
        output_path = f"{name}.yaml"
    dest = Path(output_path)

    header = f"# RADIANT config — {name}\n# {TEMPLATES[name]['description']}\n"
    text = header + yaml.dump(
        TEMPLATES[name]["config"],
        default_flow_style=False,
        sort_keys=True,
    )
    dest.write_text(text, encoding="utf-8")
    click.echo(f"Template written to {dest}")
