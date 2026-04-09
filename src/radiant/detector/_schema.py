"""Parameter definitions for the detector stage (2B.4 minimum subset).

Only the parameters needed by :mod:`radiant.detector.qe`,
:mod:`radiant.detector.pixel`, :mod:`radiant.detector.dark_current`,
and :mod:`radiant.detector.shot_noise` are defined here. The full
RADIANT_Detector_Complete.md §4 noise inventory (16 terms) and the
QE library selector will be added by later tasks.
"""

from __future__ import annotations

from radiant.core.parameters import ParameterDef

# ---------------------------------------------------------------------------
# Pixel geometry
# ---------------------------------------------------------------------------

PIXEL_PITCH_X = ParameterDef(
    name="detector.pixel_pitch_x_um",
    description="Pixel pitch along the cross-track (x) axis.",
    dtype=float,
    canonical_unit="m",
    input_unit="um",
    default=None,
    bounds=(0.1, 1000.0),
    tags=frozenset({"detector", "pixel"}),
)

PIXEL_PITCH_Y = ParameterDef(
    name="detector.pixel_pitch_y_um",
    description="Pixel pitch along the along-track (y) axis. Defaults to x pitch.",
    dtype=float,
    canonical_unit="m",
    input_unit="um",
    default=None,
    bounds=(0.1, 1000.0),
    tags=frozenset({"detector", "pixel"}),
)

FILL_FACTOR = ParameterDef(
    name="detector.fill_factor",
    description="Photosensitive fraction of the pixel cell.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=1.0,
    bounds=(0.0, 1.0),
    tags=frozenset({"detector", "pixel"}),
    default_justification="Most modern EO sensors have near-unity fill factor.",
)

# ---------------------------------------------------------------------------
# Quantum efficiency (parametric mode)
# ---------------------------------------------------------------------------

QE_PEAK = ParameterDef(
    name="detector.qe_peak",
    description="Peak quantum efficiency for the parametric QE model.",
    dtype=float,
    canonical_unit="",
    input_unit="",
    default=0.8,
    bounds=(0.0, 1.0),
    tags=frozenset({"detector", "qe"}),
    default_justification="0.8 is representative of a backside-illuminated Si CCD.",
)

QE_CUTON_UM = ParameterDef(
    name="detector.qe_cuton_um",
    description="Short-wavelength cut-on for the parametric QE model.",
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=0.4,
    bounds=(0.01, 30.0),
    tags=frozenset({"detector", "qe"}),
)

QE_CUTOFF_UM = ParameterDef(
    name="detector.qe_cutoff_um",
    description="Long-wavelength cutoff for the parametric QE model.",
    dtype=float,
    canonical_unit="um",
    input_unit="um",
    default=1.1,
    bounds=(0.01, 30.0),
    tags=frozenset({"detector", "qe"}),
)

# ---------------------------------------------------------------------------
# Dark current
# ---------------------------------------------------------------------------

DARK_RATE_E_PER_S = ParameterDef(
    name="detector.dark_rate_e_per_s",
    description="Dark current generation rate per pixel [e-/s].",
    dtype=float,
    canonical_unit="1/s",
    input_unit="1/s",
    default=100.0,
    bounds=(0.0, 1e9),
    tags=frozenset({"detector", "noise", "dark"}),
    default_justification="Order-of-magnitude room-temperature Si CCD reference.",
)

DARK_REFERENCE_TEMP = ParameterDef(
    name="detector.dark_reference_temperature_K",
    description="Temperature at which dark_rate_e_per_s is specified [K].",
    dtype=float,
    canonical_unit="K",
    input_unit="K",
    default=300.0,
    bounds=(1.0, 500.0),
    tags=frozenset({"detector", "dark"}),
)

DARK_ACTIVATION_EV = ParameterDef(
    name="detector.dark_activation_energy_eV",
    description=(
        "Arrhenius activation energy for dark-rate temperature scaling. Zero disables scaling."
    ),
    dtype=float,
    canonical_unit="eV",
    input_unit="eV",
    default=0.0,
    bounds=(0.0, 5.0),
    tags=frozenset({"detector", "dark"}),
)


ALL_PARAMETERS: tuple[ParameterDef, ...] = (
    PIXEL_PITCH_X,
    PIXEL_PITCH_Y,
    FILL_FACTOR,
    QE_PEAK,
    QE_CUTON_UM,
    QE_CUTOFF_UM,
    DARK_RATE_E_PER_S,
    DARK_REFERENCE_TEMP,
    DARK_ACTIVATION_EV,
)
