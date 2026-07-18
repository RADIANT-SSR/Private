"""MODTRAN atmosphere interface — tape7 import, card deck builder, parser, cache.

Two ways in, per ``docs/architecture/RADIANT_Atmosphere.md`` section 5:

1. **Tape7 file import (primary)** — ``atmosphere.modtran.tape7_path``
   names a tape7 file produced elsewhere.  The loader layer parses it
   pre-chain (Rule 6) into a :class:`Tape7Import`; the binary, the
   cache, and the fallback are never consulted.
2. **Binary invocation (secondary, never yet exercised)** — RADIANT
   builds a tape5 input deck, invokes a locally-installed MODTRAN
   executable, parses the tape7 output, converts to RADIANT canonical
   units, and caches the result keyed by an SHA-256 hash of the
   rendered deck.

Unit conversions (exactly once, in :meth:`Tape7Reader.to_radiant_units`):

- Wavenumber ``cm-1`` -> wavelength ``um``: ``lam = 10000 / nu``
- Radiance ``W/cm2/sr/cm-1`` -> ``W/m2/sr/um``:
  ``L(lam) = L(nu) * nu**2 / 1e4``
  (factor 1e4 from cm-2 -> m-2; the nu**2 / 1e4 is the Jacobian
  |d nu / d lam| = 1e4 / lam**2 = nu**2 / 1e4)
- Transmittance is dimensionless and unchanged.
- Arrays reversed from descending wavenumber to ascending wavelength.

If the MODTRAN binary is unavailable:

- Cache hit: use cached result.
- ``allow_fallback=True``: translate params to SimpleAtmosphere and warn.
- ``allow_fallback=False``: raise ``ModtranUnavailableError``.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.errors import AtmosphereStateError, AtmosphereValidationError
from radiant.atmosphere.protocol import (
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.core.exceptions import RadiantError
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData, SpectralGrid

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ModtranUnavailableError(RadiantError, RuntimeError):
    """MODTRAN binary is not available and no fallback is enabled.

    Co-inherits from :class:`RuntimeError` for back-compat with existing
    ``except RuntimeError`` patterns; :class:`RadiantError` is the
    canonical base.
    """

    def __init__(self, binary_path: str | Path, detail: str = "") -> None:
        msg = (
            f"MODTRAN binary not found at '{binary_path}'. "
            "Install MODTRAN and set atmosphere.modtran.binary_path, "
            "or set atmosphere.modtran.allow_fallback=True to use the "
            "simple parametric model as a fallback."
        )
        if detail:
            msg += f" Detail: {detail}"
        super().__init__(msg)
        self.binary_path = binary_path


class Tape7ParseError(RadiantError, ValueError):
    """Error parsing MODTRAN tape7 output.

    Co-inherits from :class:`ValueError` for back-compat with existing
    ``pytest.raises(ValueError, ...)`` patterns; :class:`RadiantError`
    is the canonical base.
    """


# ---------------------------------------------------------------------------
# MODTRAN configuration
# ---------------------------------------------------------------------------

# Map RADIANT atmosphere profile names -> MODTRAN MODEL card values.
_PROFILE_MAP: dict[str, int] = {
    "tropical": 1,
    "midlat_summer": 2,
    "midlat_winter": 3,
    "subarctic_summer": 4,
    "subarctic_winter": 5,
    "us_standard": 6,
}

# Map RADIANT aerosol type -> MODTRAN IHAZE values.
_IHAZE_MAP: dict[str, int] = {
    "none": 0,
    "rural": 1,
    "maritime": 3,
    "urban": 4,
    "tropospheric": 5,
}

# Default cache location.
_DEFAULT_CACHE_DIR = Path.home() / ".radiant" / "modtran_cache"


@dataclass
class ModtranConfig:
    """Configuration for the MODTRAN atmosphere model.

    Parameters
    ----------
    binary_path:
        Path to the MODTRAN executable.
    cache_dir:
        Directory for caching tape7 results. Created on first use.
    allow_fallback:
        If True and the binary is unavailable, fall back to
        SimpleAtmosphere with translated parameters.
    atmosphere_profile:
        Standard atmosphere profile (maps to MODTRAN MODEL card).
    aerosol_model:
        Aerosol type (maps to MODTRAN IHAZE card).
    h2o_scale:
        Water vapor column scaling factor.
    o3_scale:
        Ozone column scaling factor.
    visibility_km:
        Meteorological visibility [km] (Card 2 VIS, CU-063). ``None``
        (default) leaves VIS at ``0.000``, which tells MODTRAN to use
        the IHAZE-default visibility; set explicitly to express a
        degraded-visibility run independent of the aerosol type.
    itype:
        MODTRAN Card 1 ITYPE path geometry (CU-069): ``2`` (default) =
        slant path between two altitudes (H1, H2, ANGLE), the mode
        this deck builder was designed around; ``1`` = horizontal
        (constant-altitude) path; ``3`` = slant path to space — used
        by the ground-level solar-irradiance runs (Block E of
        ``docs/plans/modtran_run_matrix.csv``, which look from H1=0
        up through the full atmosphere).
    iemsct:
        MODTRAN Card 1 IEMSCT mode (CU-064): ``2`` (default) = thermal
        + solar/lunar path radiance with scattering, the mode this
        deck builder was designed around; ``3`` = solar/lunar
        irradiance at H2 (no path-radiance decomposition — used for
        sky-irradiance / E_sky reference runs, e.g. Block E of
        ``docs/plans/modtran_run_matrix.csv``); ``0``/``1`` are the
        remaining MODTRAN-defined values (no emission; thermal-only).
        See the CU-067 caveat on ``render_tape5`` for how this token's
        position was identified.
    spectral_resolution_cm1:
        Spectral resolution in cm-1 for the MODTRAN run.
    v1_cm1:
        Start wavenumber [cm-1] for the computation.
    v2_cm1:
        End wavenumber [cm-1] for the computation.
    extra_cards:
        Additional card overrides as {card_name: content} dict.
        Not exposed as a ParameterDef (dict type not supported).
    """

    binary_path: Path = Path("/usr/local/bin/modtran")
    cache_dir: Path = _DEFAULT_CACHE_DIR
    allow_fallback: bool = False
    atmosphere_profile: str = "us_standard"
    aerosol_model: str = "rural"
    h2o_scale: float = 1.0
    o3_scale: float = 1.0
    visibility_km: float | None = None
    itype: int = 2
    iemsct: int = 2
    spectral_resolution_cm1: float = 1.0
    v1_cm1: float = 700.0  # ~14.3 um
    v2_cm1: float = 25000.0  # ~0.4 um
    extra_cards: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.binary_path = Path(self.binary_path)
        self.cache_dir = Path(self.cache_dir)

        if self.atmosphere_profile not in _PROFILE_MAP:
            raise AtmosphereValidationError(
                f"ModtranConfig: atmosphere_profile='{self.atmosphere_profile}' "
                f"not recognised. Choose one of {sorted(_PROFILE_MAP)}."
            )
        if self.aerosol_model not in _IHAZE_MAP:
            raise AtmosphereValidationError(
                f"ModtranConfig: aerosol_model='{self.aerosol_model}' "
                f"not recognised. Choose one of {sorted(_IHAZE_MAP)}."
            )
        if self.h2o_scale <= 0.0:
            raise AtmosphereValidationError(
                f"ModtranConfig: h2o_scale={self.h2o_scale} must be positive."
            )
        if self.o3_scale <= 0.0:
            raise AtmosphereValidationError(
                f"ModtranConfig: o3_scale={self.o3_scale} must be positive."
            )
        if self.visibility_km is not None and self.visibility_km <= 0.0:
            raise AtmosphereValidationError(
                f"ModtranConfig: visibility_km={self.visibility_km} must be "
                "positive, or None to use the IHAZE default."
            )
        if self.itype not in (1, 2, 3):
            raise AtmosphereValidationError(
                f"ModtranConfig: itype={self.itype} not recognised. "
                "MODTRAN defines ITYPE in {1, 2, 3}."
            )
        if self.iemsct not in (0, 1, 2, 3):
            raise AtmosphereValidationError(
                f"ModtranConfig: iemsct={self.iemsct} not recognised. "
                "MODTRAN defines IEMSCT in {0, 1, 2, 3}."
            )
        if self.spectral_resolution_cm1 <= 0.0:
            raise AtmosphereValidationError(
                f"ModtranConfig: spectral_resolution_cm1="
                f"{self.spectral_resolution_cm1} must be positive."
            )
        if self.v1_cm1 >= self.v2_cm1:
            raise AtmosphereValidationError(
                f"ModtranConfig: v1_cm1={self.v1_cm1} must be < v2_cm1={self.v2_cm1}."
            )


# ---------------------------------------------------------------------------
# MODTRAN native output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModtranNativeOutput:
    """Raw tape7 output in MODTRAN native units.

    All arrays are in MODTRAN's native descending-wavenumber order.

    Attributes
    ----------
    wavenumber_cm1:
        Wavenumber grid [cm-1], descending.
    total_transmittance:
        Total path transmittance, dimensionless.
    path_thermal_radiance:
        Thermal path radiance [W/cm2/sr/cm-1].
    path_scattered_radiance:
        Scattered (solar) path radiance [W/cm2/sr/cm-1].
    ground_reflected_radiance:
        Ground-reflected radiance reaching the sensor [W/cm2/sr/cm-1].
    header:
        Raw header metadata parsed from the tape7 file.
    """

    wavenumber_cm1: np.ndarray
    total_transmittance: np.ndarray
    path_thermal_radiance: np.ndarray
    path_scattered_radiance: np.ndarray
    ground_reflected_radiance: np.ndarray
    header: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Card deck builder
# ---------------------------------------------------------------------------


def render_tape5(
    config: ModtranConfig,
    geometry: AtmosphericGeometry,
) -> str:
    """Render a MODTRAN tape5 input deck from RADIANT parameters.

    This builds a minimal MODTRAN 5/6 compatible card deck for a
    single line-of-sight radiance/transmittance calculation.

    Returns
    -------
    str
        The complete tape5 content as a string.
    """
    import math

    model_code = _PROFILE_MAP[config.atmosphere_profile]
    ihaze = _IHAZE_MAP[config.aerosol_model]

    # Geometry: convert to MODTRAN convention.
    # H1 = sensor altitude [km], H2 = target altitude [km].
    h1_km = geometry.sensor_altitude_m / 1000.0
    h2_km = geometry.target_altitude_m / 1000.0
    zenith_deg = math.degrees(geometry.path_zenith_rad)
    solar_zen_deg = math.degrees(geometry.solar_zenith_rad)
    solar_az_deg = math.degrees(geometry.solar_azimuth_rad)

    # CU-065: MODTRAN measures Card 3 ANGLE from zenith AT H1 (the
    # sensor), while RADIANT's path_zenith_rad is measured at the LOWER
    # endpoint of the path (RADIANT_Atmosphere.md §4.1). Downlooking
    # (H1 above H2) the sensor is the UPPER endpoint, so in the
    # plane-parallel limit ANGLE = 180° − zenith — a nadir-looking
    # space sensor renders ANGLE = 180, not 0. Uplooking (H1 at or
    # below H2) the sensor IS the lower endpoint and ANGLE = zenith
    # unchanged. This reproduces the hand-worked
    # `modtran_angle_at_h1_deg` column of
    # docs/plans/modtran_run_matrix.csv for every ITYPE=2 row.
    # Residual CU-065 caveat: confirm the convention against the
    # MODTRAN user manual when access arrives.
    angle_deg = 180.0 - zenith_deg if h1_km > h2_km else zenith_deg

    # Card 1 — whitespace-split token positions (CU-067, verified against
    # the real 2026-07-17 MODTRAN 6 run set):
    #   [0] 'T'   MODTRN band-model flag
    #   [1] '5'   fixed literal default
    #   [2] '0'   fixed literal default
    #   [3] MODEL         atmosphere profile 1–6  ← confirmed: A1–A6 vary
    #                     this token and produced the matching standard
    #                     profile (US Standard, tropical, …) in each tape7.
    #   [4] '0'   fixed literal default
    #   [5] ITYPE         path geometry (2 = slant H1→H2, 3 = slant-to-space)
    #   [6] IEMSCT        radiance/irradiance mode (2 = thermal+solar path
    #                     radiance, 3 = irradiance) — confirmed: the E-block
    #                     runs set [5]=[6]=3 and produced the flux/irradiance
    #                     output, every other run set 2/2 and produced tape7
    #                     radiance. ITYPE precedes IEMSCT (MODTRAN canonical
    #                     order); the deck writes them in that order.
    #   [7] IMULT '1'     multiple scattering (DISORT) — confirmed: the
    #                     MULT_SCAT/SING_SCAT columns are populated.
    #   [8..13] fixed literal defaults ('0 0 0 1 0 0.000'). These are
    #   unchanged for every run; their individual MODTRAN field identities
    #   are not independently asserted here, but an error in any of them
    #   would have broken all 39 runs, which it did not.
    # Superseded the pre-2026-07-17 stale name-list comment that did not
    # line up index-for-index with these tokens (the original CU-067
    # defect). RADIANT only controls [3] MODEL, [5] ITYPE, [6] IEMSCT.
    itype = config.itype
    iemsct = config.iemsct
    imult = 1
    card1 = (
        f"T    5    0    {model_code}    0    {itype}    {iemsct}    {imult}"
        "    0    0    0    1    0  0.000"
    )

    # Card 1A: DIS, NSTR, LSUN
    card1a = "T    4 F F F F    0 0.00000  0.00000  0.00000  0.00000"

    # Card 2: IHAZE, ISEASN, IVULCN, ICSTL, ICLD, IVSA, VIS, WSS, WHH, RAINRT
    # VIS (CU-063): 0.000 tells MODTRAN to use the IHAZE-default
    # visibility; a positive value overrides it independent of IHAZE.
    vis_field = f"{config.visibility_km:7.3f}" if config.visibility_km is not None else "  0.000"
    card2 = f"    {ihaze}    0    0    0    0    0{vis_field}  0.000  0.000  0.000  0.000"

    # Card 2C (water vapor scaling): H2OSTR
    h2o_str = f"{config.h2o_scale:.3f}g"
    o3_str = f"{config.o3_scale:.3f}g"
    card2c = f"  {h2o_str}  {o3_str}"

    # Card 3: H1, H2, ANGLE, RANGE, BETA, RO, LENN, PHI
    card3 = (
        f"  {h1_km:10.3f}{h2_km:10.3f}{angle_deg:10.3f}"
        f"     0.000     0.000     0.000    0     0.000"
    )

    # Card 3A1: IPARM, IPH, IDAY, ISOURC, PARM1 (solar zen), PARM2 (solar az)
    card3a1 = f"    2    0    0    0{solar_zen_deg:10.3f}{solar_az_deg:10.3f}     0.000     0.000"

    # Card 4: V1, V2, DV, FWHM, YFLAG, XFLAG, FLAGS
    card4 = (
        f"  {config.v1_cm1:10.1f}{config.v2_cm1:10.1f}"
        f"  {config.spectral_resolution_cm1:10.4f}"
        f"  {config.spectral_resolution_cm1:10.4f}"
        f" T F   1"
    )

    # Card 5: termination (IRPT=0)
    card5 = "    0"

    lines = [card1, card1a, card2, card2c, card3, card3a1, card4, card5]

    # Apply any extra card overrides.
    for card_name, content in config.extra_cards.items():
        logger.info("ModtranCardDeck: applying extra_cards override for %s", card_name)
        # Find and replace the matching card line.
        for idx, line in enumerate(lines):
            if line.startswith(card_name):
                lines[idx] = content
                break

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Tape7 reader
# ---------------------------------------------------------------------------


# Canonical MODTRAN tape7 (IEMSCT=2, "full" radiance-mode output)
# column labels, MODTRAN 4/5 User's Manual, in their standard
# left-to-right order. Header lines are fixed-width FORTRAN output
# with two-word labels ("TOT TRANS", "PTH THRML", ...); naive
# whitespace splitting cannot recover a 1:1 token-to-column mapping
# from that, so CU-066 identifies each label's COLUMN ORDER by the
# position its text starts at in the header line (left to right),
# not by a literal token index.
# Tape7 column vocabulary across MODTRAN output-format variants.
#
# MODTRAN writes its spectral columns under one of two label
# conventions. Classic MODTRAN 4/5 tape7 uses space-delimited two-word
# names ("TOT TRANS", "PTH THRML"); MODTRAN 6 uses single-token
# underscore names ("TOT_TRANS", "THRML_EM") and splits the classic
# combined solar-scatter column ("SOL SCAT") into separate multiple-
# and single-scatter columns ("MULT_SCAT", "SING_SCAT"). Both
# vocabularies are recognised so one reader serves either binary
# (CU-154 — the 2026-07-17 run set is MODTRAN 6). The two label sets are
# disjoint as substrings (space vs underscore), so a header is matched
# by exactly one vocabulary.
#
# Every recognised raw header label maps to a canonical internal key.
# THRML_SCT / SURF_EMIS / DRCT_RFLT / TOTAL_RAD are real tape7 columns
# with no ModtranNativeOutput field yet: they are located (and their
# labels preserved in ``header`` for future use) but not consumed.
_TAPE7_LABEL_ALIASES: dict[str, str] = {
    "FREQ": "FREQ",
    "TOT TRANS": "TOT_TRANS", "TOT_TRANS": "TOT_TRANS",
    "PTH THRML": "THRML_EM", "THRML_EM": "THRML_EM",
    "THRML SCT": "THRML_SCT", "THRML_SCT": "THRML_SCT",
    "SURF EMIS": "SURF_EMIS", "SURF_EMIS": "SURF_EMIS",
    # Classic combined solar scatter; MODTRAN 6 splits it in two.
    "SOL SCAT": "SOL_SCAT",
    "MULT_SCAT": "MULT_SCAT",
    "SNGL SCAT": "SING_SCAT", "SING_SCAT": "SING_SCAT",
    "GRND RFLT": "GRND_RFLT", "GRND_RFLT": "GRND_RFLT",
    "DRCT RFLT": "DRCT_RFLT", "DRCT_RFLT": "DRCT_RFLT",
    "TOTAL RAD": "TOTAL_RAD", "TOTAL_RAD": "TOTAL_RAD",
}

# Canonical keys that must be present to build a ModtranNativeOutput.
# The solar path-scatter term is required too but has variant-dependent
# sourcing (SOL_SCAT, or MULT_SCAT + SING_SCAT) — checked separately.
_REQUIRED_TAPE7_KEYS: tuple[str, ...] = (
    "FREQ",
    "TOT_TRANS",
    "THRML_EM",
    "GRND_RFLT",
)

# Positional fallback (pre-CU-066 behavior) used only when no named
# column header is found — e.g. headerless/synthetic input. CU-066:
# cols 3/4 are wrong against the real IEMSCT=2 layout (THRML_SCT and
# SURF_EMIS, not SOL_SCAT and GRND_RFLT); kept only as a best-effort
# degraded mode, always paired with a UserWarning.
_POSITIONAL_FALLBACK_COLUMNS: dict[str, int] = {
    "FREQ": 0,
    "TOT_TRANS": 1,
    "THRML_EM": 2,
    "SOL_SCAT": 3,
    "GRND_RFLT": 4,
}


def _locate_tape7_columns(header_line: str) -> dict[str, int] | None:
    """Map tape7 columns found in ``header_line`` to their indices.

    Returns ``None`` if the line has no "FREQ" label (i.e. is not a
    real column-header line). Otherwise returns ``{canonical_key:
    column_index}`` for every recognised label present — in either the
    classic space-delimited or the MODTRAN 6 underscore vocabulary —
    ordered by where the label starts in the whitespace-normalised
    line. This recovers column ORDER without depending on exact
    character widths, which vary by MODTRAN version.

    The index is the rank among recognised columns, which equals the
    true column index as long as the recognised leading columns are
    contiguous from FREQ — true for both real MODTRAN layouts (any
    unrecognised columns trail the consumed ones).
    """
    normalized = " ".join(header_line.split())
    if "FREQ" not in normalized:
        return None

    found = [
        (normalized.find(raw_label), canonical)
        for raw_label, canonical in _TAPE7_LABEL_ALIASES.items()
        if normalized.find(raw_label) >= 0
    ]
    found.sort(key=lambda pair: pair[0])
    return {canonical: idx for idx, (_, canonical) in enumerate(found)}


class Tape7Reader:
    """Parse MODTRAN tape7 fixed-column output.

    The tape7 format is a fixed-width text file with a header section
    (including, on real MODTRAN output, a numeric card-echo of the
    input deck) followed by a column-labeled spectral data table. The
    exact column layout depends on the MODTRAN version and card-deck
    options; this reader locates columns by their header LABELS
    (CU-066), falling back to the historical positional assumption
    with a ``UserWarning`` only when no labeled header is found.

    Parameters
    ----------
    tape7_path:
        Path to the tape7 output file.
    """

    def __init__(self, tape7_path: str | Path) -> None:
        self._path = Path(tape7_path)
        if not self._path.exists():
            raise FileNotFoundError(
                f"MODTRAN tape7 file not found: {self._path}. "
                "Check that MODTRAN completed successfully."
            )
        self._native: ModtranNativeOutput | None = None

    def parse(self) -> ModtranNativeOutput:
        """Parse the tape7 file into native MODTRAN units.

        Returns
        -------
        ModtranNativeOutput
            Raw data in MODTRAN convention (descending wavenumber,
            W/cm2/sr/cm-1 for radiance).

        Raises
        ------
        Tape7ParseError
            If the file cannot be parsed.
        """
        if self._native is not None:
            return self._native

        text = self._path.read_text()
        lines = text.strip().splitlines()

        # Pass 1: look for a named column-header line ("FREQ..."),
        # recording preceding/surrounding non-numeric text as header
        # metadata (card echoes on real tape7 output, decorative
        # banners on synthetic fixtures) regardless of the outcome.
        header_info: dict[str, Any] = {}
        column_index: dict[str, int] | None = None
        header_line_no: int | None = None
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if column_index is None:
                candidate = _locate_tape7_columns(stripped)
                if candidate is not None:
                    column_index = candidate
                    header_line_no = i
            if i < 20:
                header_info[f"header_line_{i}"] = stripped

        if column_index is not None:
            missing = [k for k in _REQUIRED_TAPE7_KEYS if k not in column_index]
            # Solar path scatter: classic single SOL_SCAT column, or the
            # MODTRAN 6 MULT_SCAT + SING_SCAT pair that replaces it.
            has_scatter = "SOL_SCAT" in column_index or (
                "MULT_SCAT" in column_index and "SING_SCAT" in column_index
            )
            if missing or not has_scatter:
                detail = list(missing)
                if not has_scatter:
                    detail.append("solar-scatter (SOL_SCAT, or MULT_SCAT + SING_SCAT)")
                raise Tape7ParseError(
                    f"MODTRAN tape7 {self._path}: column header found but "
                    f"missing required column(s) {detail}. Recognised "
                    f"columns: {sorted(column_index)}. This tape7 variant "
                    "is not supported."
                )
            # Data starts on the first numeric-leading line strictly
            # after the header — never before it, so numeric card
            # echoes preceding the header cannot be mistaken for
            # spectral data (the pre-CU-066 defect).
            data_start = None
            for i in range(header_line_no + 1, len(lines)):
                stripped = lines[i].strip()
                if not stripped:
                    continue
                try:
                    float(stripped.split()[0])
                    data_start = i
                    break
                except ValueError:
                    continue
            if data_start is None:
                raise Tape7ParseError(
                    f"MODTRAN tape7 {self._path}: found a column header "
                    "but no numeric data followed it. The file may be "
                    "truncated."
                )
        else:
            # No labeled header: locate the first numeric-leading line
            # (if any) BEFORE warning — a file with no data at all
            # (empty, header-only) is a parse error, not a degraded
            # fallback, and must not also claim to be "falling back".
            data_start = None
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    float(stripped.split()[0])
                    data_start = i
                    break
                except ValueError:
                    continue
            if data_start is None:
                raise Tape7ParseError(
                    f"MODTRAN tape7 {self._path}: no numeric data found. "
                    "The file may be empty or corrupted."
                )
            # Rule 17: a degraded-confidence fallback must not be silent.
            warnings.warn(
                f"MODTRAN tape7 {self._path}: no 'FREQ' column-header "
                "line found; falling back to the version-dependent "
                "positional column assumption (CU-066). This may "
                "misassign columns on real MODTRAN output — verify "
                "against the tape7 header.",
                UserWarning,
                stacklevel=2,
            )
            column_index = _POSITIONAL_FALLBACK_COLUMNS

        # Parse spectral data.
        rows: list[list[float]] = []
        n_expected: int | None = None
        for line in lines[data_start:]:
            stripped = line.strip()
            if not stripped:
                continue
            # Some tape7 formats have summary/footer lines; stop if we
            # encounter a non-numeric line after data has started.
            parts = stripped.split()
            try:
                row = [float(p) for p in parts]
            except ValueError:
                break
            # A row whose column count differs from the established
            # width is a footer/sentinel, not spectral data — MODTRAN
            # terminates the block with a lone numeric marker (e.g.
            # "-9999."), which is float-parseable and would otherwise
            # corrupt the array. Stop at the first such row.
            if n_expected is None:
                n_expected = len(row)
            elif len(row) != n_expected:
                break
            rows.append(row)

        if len(rows) < 2:
            raise Tape7ParseError(
                f"MODTRAN tape7 {self._path}: fewer than 2 spectral data "
                f"rows parsed. The output may be incomplete."
            )

        data = np.array(rows, dtype=np.float64)
        n_cols = data.shape[1]

        if n_cols < 3:
            raise Tape7ParseError(
                f"MODTRAN tape7 {self._path}: expected at least 3 columns "
                f"(wavenumber, transmittance, radiance), got {n_cols}."
            )

        def _column(label: str) -> np.ndarray:
            idx = column_index.get(label)
            if idx is None or idx >= n_cols:
                return np.zeros(data.shape[0], dtype=np.float64)
            return data[:, idx]

        wavenumber = _column("FREQ")
        total_trans = _column("TOT_TRANS")
        path_thermal = _column("THRML_EM")
        # Solar path scatter. The classic format's combined SOL_SCAT
        # column is the full solar scatter and takes priority (classic
        # tape7 also carries a separate SNGL_SCAT column that must NOT be
        # double-counted); MODTRAN 6 has no SOL_SCAT and instead splits
        # the term into MULT_SCAT + SING_SCAT, whose sum is the classic
        # value. Thermal scatter (THRML_SCT) is intentionally excluded —
        # the path-radiance contract is thermal emission + solar scatter.
        if "SOL_SCAT" in column_index:
            path_scattered = _column("SOL_SCAT")
        else:
            path_scattered = _column("MULT_SCAT") + _column("SING_SCAT")
        ground_reflected = _column("GRND_RFLT")

        self._native = ModtranNativeOutput(
            wavenumber_cm1=wavenumber,
            total_transmittance=total_trans,
            path_thermal_radiance=path_thermal,
            path_scattered_radiance=path_scattered,
            ground_reflected_radiance=ground_reflected,
            header=header_info,
        )
        return self._native

    def to_radiant_units(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Convert parsed tape7 data to RADIANT canonical units.

        Returns
        -------
        wavelength_um:
            Wavelength grid in um, strictly ascending.
        transmittance:
            Total path transmittance, dimensionless [0, 1].
        path_radiance:
            Total upwelling path radiance (thermal + scattered)
            [W/m2/sr/um].
        ground_reflected:
            Ground-reflected radiance reaching sensor [W/m2/sr/um].

        Notes
        -----
        The unit conversion is performed exactly once here. The
        Jacobian for the spectral axis conversion is::

            L(lambda) = L(nu) * |d nu / d lambda|
                      = L(nu) * nu**2 / 1e4

        where the 1e4 accounts for 10000 cm-1/um. The radiance values
        also need a factor of 1e4 to convert from W/cm2 to W/m2, and
        these two factors combine to::

            L_radiant(lambda) = L_modtran(nu) * nu**2
        """
        native = self.parse()
        nu = native.wavenumber_cm1

        # Filter out zero-wavenumber entries (sometimes present as padding).
        mask = nu > 0.0
        nu = nu[mask]
        trans = native.total_transmittance[mask]
        l_thermal = native.path_thermal_radiance[mask]
        l_scattered = native.path_scattered_radiance[mask]
        l_ground = native.ground_reflected_radiance[mask]

        # Wavelength conversion: lambda [um] = 10000 / nu [cm-1].
        wavelength_um = 10000.0 / nu

        # Jacobian: L(lambda) [W/m2/sr/um] = L(nu) [W/cm2/sr/cm-1] * nu^2
        # The nu^2 absorbs both the cm-2 -> m-2 (1e4) and the
        # |d nu/d lambda| = 1e4/lambda^2 = nu^2/1e4 factors.
        jacobian = nu * nu

        l_path_radiant = (l_thermal + l_scattered) * jacobian
        l_ground_radiant = l_ground * jacobian

        # Sort to ascending wavelength (MODTRAN output order varies).
        sort_idx = np.argsort(wavelength_um)
        wavelength_um = wavelength_um[sort_idx]
        trans = trans[sort_idx]
        l_path_radiant = l_path_radiant[sort_idx]
        l_ground_radiant = l_ground_radiant[sort_idx]

        return wavelength_um, trans, l_path_radiant, l_ground_radiant


# ---------------------------------------------------------------------------
# Flux table reader (MODTRAN spectral flux CSV — Block E irradiance runs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModtranFluxOutput:
    """Raw MODTRAN spectral flux table in native units.

    MODTRAN's flux export (the ``*_flux.csv`` sidecar of a run-matrix
    Block E irradiance run) reports, at each atmospheric level, three
    spectral irradiances: upward diffuse (UP), downward diffuse (DOWN —
    thermal emission + scattered solar), and the direct solar beam
    (SOLAR). Arrays are in MODTRAN-native descending wavenumber and
    native spectral-flux units W/cm²/cm⁻¹.

    Attributes
    ----------
    wavenumber_cm1:
        Wavenumber grid [cm⁻¹], descending. Shape ``(N,)``.
    altitude_km:
        Atmospheric level altitudes [km], ascending. Shape ``(M,)``.
    flux_up, flux_down, flux_direct_solar:
        Upward-diffuse, downward-diffuse, and direct-solar spectral
        flux [W/cm²/cm⁻¹]. Shape ``(N, M)`` — wavenumber × level.
    header:
        Parsed file metadata (``num_freq``, ``num_column``, column names).
    """

    wavenumber_cm1: np.ndarray
    altitude_km: np.ndarray
    flux_up: np.ndarray
    flux_down: np.ndarray
    flux_direct_solar: np.ndarray
    header: dict[str, Any] = field(default_factory=dict)


class ModtranFluxReader:
    """Parse a MODTRAN spectral flux CSV into a :class:`ModtranFluxOutput`.

    File format (MODTRAN 6 flux export)::

        case index 0 = {
        num freq, 25976
        num column, 108
        Freq,   UP,   DOWN,  SOLAR,   UP,   DOWN,  SOLAR, ...   <- 3 per level
        [cm-1], 0 KM, 0 KM,  0 KM,  1 KM,  1 KM,  1 KM,   ...   <- level per column
        695, <108 flux values>
        ...
        }

    The data columns are 3 × n_levels, ordered (UP, DOWN, SOLAR) per
    ascending level. Brace, ``num …``, and label lines are metadata;
    data rows are the numeric-leading lines. The trailing ``}`` closes
    the block.
    """

    def __init__(self, flux_path: str | Path) -> None:
        self._path = Path(flux_path)
        self._native: ModtranFluxOutput | None = None

    def parse(self) -> ModtranFluxOutput:
        """Parse the flux CSV into native MODTRAN units (W/cm²/cm⁻¹).

        Raises
        ------
        Tape7ParseError
            If the file has no level-label header or no data rows, or a
            column count that is not a multiple of 3.
        """
        if self._native is not None:
            return self._native

        lines = self._path.read_text(encoding="utf-8").splitlines()

        header: dict[str, Any] = {}
        level_labels: list[str] | None = None
        data_start: int | None = None
        for i, raw in enumerate(lines):
            s = raw.strip()
            if not s or s == "}" or s.endswith("{"):
                continue
            low = s.lower()
            if low.startswith("num freq"):
                header["num_freq"] = int(s.split(",")[1])
                continue
            if low.startswith("num column"):
                header["num_column"] = int(s.split(",")[1])
                continue
            toks = [t.strip() for t in s.split(",")]
            if toks[0].lower() == "freq":
                header["column_names"] = toks
                continue
            if toks[0].lower().startswith("[cm"):
                level_labels = toks
                continue
            try:
                float(toks[0])
            except (ValueError, IndexError):
                continue
            data_start = i
            break

        if data_start is None or level_labels is None:
            raise Tape7ParseError(
                f"MODTRAN flux file {self._path}: no data rows or no "
                "level-label ('[cm-1], 0 KM, ...') header found. The file "
                "may be truncated or not a MODTRAN flux CSV."
            )

        # Level axis: labels after the Freq column, one triple per level.
        labels = level_labels[1:]
        n_cols = len(labels)
        if n_cols == 0 or n_cols % 3 != 0:
            raise Tape7ParseError(
                f"MODTRAN flux file {self._path}: {n_cols} data columns is "
                "not a positive multiple of 3 (UP, DOWN, SOLAR per level)."
            )
        n_levels = n_cols // 3
        altitude_km = np.array(
            [
                float(labels[3 * j].lower().replace("km", "").strip())
                for j in range(n_levels)
            ],
            dtype=np.float64,
        )

        # Data rows: numeric, 1 + 3·n_levels wide; stop at the closing
        # brace or any width/parse mismatch (footer).
        rows: list[list[float]] = []
        expected = 1 + n_cols
        for raw in lines[data_start:]:
            s = raw.strip()
            if not s or s == "}":
                break
            parts = [p for p in (t.strip() for t in s.split(",")) if p != ""]
            try:
                row = [float(p) for p in parts]
            except ValueError:
                break
            if len(row) != expected:
                break
            rows.append(row)

        if len(rows) < 2:
            raise Tape7ParseError(
                f"MODTRAN flux file {self._path}: fewer than 2 spectral data "
                "rows parsed. The output may be incomplete."
            )

        data = np.array(rows, dtype=np.float64)
        wavenumber = data[:, 0]
        # Columns run (UP, DOWN, SOLAR) per level, level-major.
        flux = data[:, 1:].reshape(data.shape[0], n_levels, 3)

        self._native = ModtranFluxOutput(
            wavenumber_cm1=wavenumber,
            altitude_km=altitude_km,
            flux_up=flux[:, :, 0],
            flux_down=flux[:, :, 1],
            flux_direct_solar=flux[:, :, 2],
            header=header,
        )
        return self._native

    def to_radiant_units(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Ground-level direct and diffuse-downwelling irradiance in
        RADIANT canonical units.

        Returns
        -------
        wavelength_um:
            Wavelength grid [µm], strictly ascending.
        e_direct:
            Direct solar beam spectral irradiance at the ground
            (MODTRAN SOLAR column) [W/m²/µm].
        e_diffuse_down:
            Downward diffuse spectral irradiance at the ground (MODTRAN
            DOWN column — thermal emission + scattered solar) [W/m²/µm].

        Notes
        -----
        The spectral-flux Jacobian is identical to the radiance case
        (there is no per-steradian factor to alter it)::

            E(λ) [W/m²/µm] = E(ν) [W/cm²/cm⁻¹] · ν²

        where ν² absorbs both cm⁻² → m⁻² (1e4) and |dν/dλ| = ν²/1e4.
        """
        native = self.parse()
        ground = int(np.argmin(native.altitude_km))  # lowest level (0 km)

        nu = native.wavenumber_cm1
        mask = nu > 0.0
        nu = nu[mask]
        e_direct = native.flux_direct_solar[mask, ground]
        e_diffuse = native.flux_down[mask, ground]

        wavelength_um = 10000.0 / nu
        jacobian = nu * nu
        e_direct_r = e_direct * jacobian
        e_diffuse_r = e_diffuse * jacobian

        sort_idx = np.argsort(wavelength_um)
        return (
            wavelength_um[sort_idx],
            e_direct_r[sort_idx],
            e_diffuse_r[sort_idx],
        )


# ---------------------------------------------------------------------------
# Tape7 file import
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Tape7Import:
    """A tape7 file parsed to RADIANT canonical units before chain execution.

    Built by the loader layer (``radiant.atmosphere.loaders._build_modtran``)
    when ``atmosphere.modtran.tape7_path`` is set — Rule 6 keeps the file
    read out of ``AtmosphereStage.run``.  Wraps the four ascending-wavelength
    arrays from :meth:`Tape7Reader.to_radiant_units` plus provenance.

    Like tabulated files, an imported tape7 is geometry-agnostic: the
    arrays are served as-is for any query geometry.

    Attributes
    ----------
    wavelength_um:
        Wavelength grid [µm], strictly ascending.
    transmittance:
        Total path transmittance, dimensionless [0, 1].
    path_radiance:
        Total upwelling path radiance (thermal + scattered) [W/m²/sr/µm].
    ground_reflected:
        Ground-reflected radiance reaching the sensor [W/m²/sr/µm].
    source_path:
        Path the file was read from.
    content_key:
        First 16 hex chars of the SHA-256 of the file bytes — the
        provenance analogue of the binary path's tape5 cache key.
    """

    wavelength_um: np.ndarray
    transmittance: np.ndarray
    path_radiance: np.ndarray
    ground_reflected: np.ndarray
    source_path: str
    content_key: str

    @classmethod
    def from_file(cls, tape7_path: str | Path) -> Tape7Import:
        """Parse *tape7_path* via :class:`Tape7Reader` and convert units.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        Tape7ParseError
            If the file cannot be parsed as a tape7.
        """
        path = Path(tape7_path)
        reader = Tape7Reader(path)
        wavelength_um, transmittance, path_radiance, ground_reflected = reader.to_radiant_units()
        content_key = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        return cls(
            wavelength_um=wavelength_um,
            transmittance=transmittance,
            path_radiance=path_radiance,
            ground_reflected=ground_reflected,
            source_path=str(path),
            content_key=content_key,
        )


# ---------------------------------------------------------------------------
# Cache utilities
# ---------------------------------------------------------------------------


def _cache_key(tape5: str) -> str:
    """Compute a deterministic cache key for a tape5 deck.

    Returns the first 16 hex characters of the SHA-256 hash.
    """
    return hashlib.sha256(tape5.encode("utf-8")).hexdigest()[:16]


def _cache_path(cache_dir: Path, key: str) -> Path:
    """Return the path where a cached result is stored."""
    return cache_dir / f"{key}.npz"


def _save_cache(
    cache_dir: Path,
    key: str,
    wavelength_um: np.ndarray,
    transmittance: np.ndarray,
    path_radiance: np.ndarray,
    ground_reflected: np.ndarray,
) -> None:
    """Save a MODTRAN result to the cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.savez(
        _cache_path(cache_dir, key),
        wavelength_um=wavelength_um,
        transmittance=transmittance,
        path_radiance=path_radiance,
        ground_reflected=ground_reflected,
    )
    logger.info("MODTRAN result cached: %s", key)


def _load_cache(
    cache_dir: Path,
    key: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    """Load a cached MODTRAN result, or return None if not found."""
    path = _cache_path(cache_dir, key)
    if not path.exists():
        return None
    data = np.load(path)
    return (
        np.asarray(data["wavelength_um"], dtype=np.float64),
        np.asarray(data["transmittance"], dtype=np.float64),
        np.asarray(data["path_radiance"], dtype=np.float64),
        np.asarray(data["ground_reflected"], dtype=np.float64),
    )


# ---------------------------------------------------------------------------
# ModtranAtmosphere
# ---------------------------------------------------------------------------


class ModtranAtmosphere:
    """Atmosphere model backed by MODTRAN — a tape7 file import or the binary.

    Implements the :class:`~radiant.atmosphere.protocol.Atmosphere`
    structural protocol.

    Precedence: when *tape7_import* is provided (the loader builds it from
    ``atmosphere.modtran.tape7_path``), the atmospheric state comes from
    the file — the binary, the cache, and the SimpleAtmosphere fallback
    are never consulted.  Without it, the legacy render-deck → cache →
    binary → fallback sequence is unchanged.

    Parameters
    ----------
    config:
        MODTRAN configuration including binary path, cache location,
        and model parameters.  With a *tape7_import*, only ``config``
        fields unrelated to deck rendering matter (the deck is never
        rendered); the import's own provenance supersedes the profile /
        aerosol knobs.
    tape7_import:
        Pre-parsed tape7 file (:class:`Tape7Import`), or ``None`` for
        the binary/cache path.
    tape7_sun_import:
        Optional pre-parsed sun-leg tape7 (CU-011, file flavor).  Only
        meaningful together with *tape7_import*; its transmittance
        column supplies ``tau_sun`` in :meth:`evaluate` instead of
        aliasing the up-leg value.
    """

    def __init__(
        self,
        config: ModtranConfig,
        tape7_import: Tape7Import | None = None,
        tape7_sun_import: Tape7Import | None = None,
    ) -> None:
        self._config = config
        self._tape7_import = tape7_import
        self._tape7_sun_import = tape7_sun_import
        self._name = "modtran_atmosphere"

    @property
    def name(self) -> str:
        return self._name

    def _run_modtran(self, tape5: str, work_dir: Path) -> Path:
        """Write tape5 and invoke the MODTRAN binary.

        Returns the path to the tape7 output file.

        Raises
        ------
        ModtranUnavailableError
            If the binary is not found.
        RuntimeError
            If MODTRAN returns a non-zero exit code.
        """
        binary = self._config.binary_path
        if not binary.exists():
            raise ModtranUnavailableError(binary)

        work_dir.mkdir(parents=True, exist_ok=True)
        tape5_path = work_dir / "tape5"
        tape5_path.write_text(tape5)

        result = subprocess.run(
            [str(binary)],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise AtmosphereStateError(
                f"MODTRAN exited with code {result.returncode}. stderr: {result.stderr[:500]}"
            )

        tape7_path = work_dir / "tape7"
        if not tape7_path.exists():
            raise AtmosphereStateError(
                f"MODTRAN completed but tape7 not found in {work_dir}. "
                f"stdout: {result.stdout[:500]}"
            )
        return tape7_path

    def build_state(
        self,
        wavelength_um: np.ndarray,
        geometry: AtmosphericGeometry,
    ) -> AtmosphericState:
        """Compute the atmospheric state via MODTRAN.

        With a tape7 import: resample the imported arrays to the query
        grid and return — no deck, no cache, no binary.

        Binary path: render tape5 -> check cache -> run MODTRAN (or use
        cache / fallback) -> parse tape7 -> convert units -> resample
        to query grid -> return AtmosphericState.
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        if lam.ndim != 1:
            raise AtmosphereValidationError(
                f"ModtranAtmosphere: wavelength_um must be 1-D, got shape {lam.shape}."
            )
        if lam.size < 2:
            raise AtmosphereValidationError(
                "ModtranAtmosphere: wavelength_um needs at least two samples."
            )
        if not np.all(np.diff(lam) > 0):
            raise AtmosphereValidationError(
                "ModtranAtmosphere: wavelength_um must be strictly ascending."
            )
        if np.any(lam <= 0.0):
            raise AtmosphereValidationError(
                "ModtranAtmosphere: wavelength_um must be strictly positive."
            )

        # Tape7 file import: the file wins unconditionally (precedence
        # documented in RADIANT_Atmosphere.md §5). Geometry-agnostic —
        # the imported arrays are served as-is, like tabulated files.
        if self._tape7_import is not None:
            imp = self._tape7_import
            return self._build_state_from_arrays(
                lam,
                geometry,
                imp.wavelength_um,
                imp.transmittance,
                imp.path_radiance,
                f"tape7-file:{imp.content_key}",
            )

        tape5 = render_tape5(self._config, geometry)
        key = _cache_key(tape5)

        # Try cache first.
        cached = _load_cache(self._config.cache_dir, key)
        if cached is not None:
            logger.info("MODTRAN cache hit: %s", key)
            wl_cached, tau_cached, lp_cached, gr_cached = cached
            return self._build_state_from_arrays(
                lam,
                geometry,
                wl_cached,
                tau_cached,
                lp_cached,
                key,
            )

        # Try running MODTRAN.
        try:
            import tempfile

            with tempfile.TemporaryDirectory(prefix="radiant_modtran_") as tmpdir:
                tape7_path = self._run_modtran(tape5, Path(tmpdir))
                reader = Tape7Reader(tape7_path)
                wl_mod, tau_mod, lp_mod, gr_mod = reader.to_radiant_units()

            # Cache the result.
            _save_cache(
                self._config.cache_dir,
                key,
                wl_mod,
                tau_mod,
                lp_mod,
                gr_mod,
            )

            return self._build_state_from_arrays(
                lam,
                geometry,
                wl_mod,
                tau_mod,
                lp_mod,
                key,
            )

        except ModtranUnavailableError:
            if self._config.allow_fallback:
                logger.warning(
                    "MODTRAN binary not available at '%s'. "
                    "Falling back to SimpleAtmosphere with translated parameters.",
                    self._config.binary_path,
                )
                return self._fallback(lam, geometry)
            raise

    def evaluate(
        self,
        wavelength_um: np.ndarray,
        los: LineOfSightGeometry,
        params: ParameterSet,
    ) -> AtmosphericQuantities:
        """Option C thin adapter over the legacy MODTRAN ``build_state``.

        A single tape7 (import or binary run) pre-dates the two-leg
        split, so this adapter collapses the legs the same way
        :class:`TabulatedAtmosphere` does:

        - ``tau_sun == tau_up == tau_full_up`` — the single MODTRAN
          transmittance, re-evaluated at the cached up-leg geometry —
          with a ``UserWarning``.  **Exception (CU-011, file flavor)**:
          with a sun-leg import (``atmosphere.modtran.tape7_sun_path``),
          ``tau_sun`` comes from that file's transmittance column
          resampled to the chain grid, and the collapse warning is not
          emitted (``tau_up == tau_full_up`` still alias — the up-leg
          pair is exact for the surface targets this path permits).
        - ``L_path_up == L_path_full``.
        - ``E_sky_thermal == π · L_atm_down``.
        - ``E_sky_scattered == 0`` (Stage 6 deliverable).
        - ``E_TOA`` from the core solar irradiance so the direct-solar
          branch still works in the assembly.

        Airborne targets (``h_tgt > 0``) are supported on the binary path
        by setting MODTRAN's H2 to ``los.h_tgt``; the tape5 content
        participates in the SHA-256 cache key via :func:`_cache_key`, so
        distinct h_tgt values produce distinct cache entries
        automatically.  On the tape7-import path a single file cannot
        carry both the target-leg and the full-column transmittance, so
        ``h_tgt > 0`` raises ``NotImplementedError`` — the same
        surface-target restriction as :class:`TabulatedAtmosphere`.
        """
        import warnings

        from radiant.core.solar import toa_solar_spectral_irradiance

        if self._tape7_import is not None and float(los.h_tgt) > 0.0:
            raise NotImplementedError(
                f"ModtranAtmosphere.evaluate: h_tgt = {los.h_tgt} m > 0 is "
                "not supported on the tape7 file-import path — a single "
                "imported tape7 records one column and cannot supply both "
                "the target→sensor leg (tau_up) and the ground→sensor full "
                "column (tau_full_up) the background branch needs.  "
                "Workaround: use the binary path (unset "
                "atmosphere.modtran.tape7_path), SimpleAtmosphere, or a "
                "surface-level target."
            )

        # Reconstruct an AtmosphericGeometry from params; MODTRAN consumes it
        # via build_state below.  h_tgt flows through to MODTRAN H2.
        geometry = AtmosphericGeometry(
            sensor_altitude_m=float(params.get("geometry.sensor_altitude_m")),
            target_altitude_m=float(los.h_tgt),
            path_zenith_rad=float(los.theta_o),
            solar_zenith_rad=(
                float(los.theta_s)
                if los.theta_s is not None
                else float(params.get("geometry.solar_zenith_rad"))
            ),
            solar_azimuth_rad=(
                float(los.delta_phi)
                if los.delta_phi is not None
                else float(params.get("geometry.solar_azimuth_rad"))
            ),
        )

        legacy_state = self.build_state(wavelength_um, geometry)
        tau = np.asarray(legacy_state.transmittance.values, dtype=np.float64)
        lpath = np.asarray(legacy_state.path_radiance.values, dtype=np.float64)
        ldown = np.asarray(legacy_state.atm_emission_down.values, dtype=np.float64)

        if self._tape7_sun_import is not None:
            # CU-011 (file flavor): tau_sun from the sun-leg file's
            # transmittance, resampled to the chain grid.  Deliberately
            # NOT clipped — an out-of-range file fails loud in
            # AtmosphericQuantities.__post_init__ (Rule 17; cf. CU-071
            # on the up-leg builder's legacy clamp).
            sun = self._tape7_sun_import
            sun_sd = SpectralData(
                name="atm.transmittance.modtran_sun",
                wavelength_um=sun.wavelength_um,
                values=sun.transmittance,
                unit="",
                source=f"MODTRAN tape7 sun-leg import: {sun.source_path}",
                source_parameters={
                    "model": "modtran",
                    "cache_key": f"tape7-file:{sun.content_key}",
                },
            )
            target_grid = SpectralGrid(wavelengths_um=np.asarray(wavelength_um, dtype=np.float64))
            tau_sun = np.asarray(sun_sd.resample(target_grid).values, dtype=np.float64)
        else:
            tau_sun = tau
            warnings.warn(
                (
                    "ModtranAtmosphere.evaluate: the MODTRAN-tape7 backend does not "
                    "carry the Option C two-leg split — collapsing "
                    "τ_sun=τ_up=τ_full_up and L_path_up=L_path_full to the single "
                    "MODTRAN transmittance.  Provide a sun-leg file via "
                    "atmosphere.modtran.tape7_sun_path (file-import flavor), or "
                    "wait for the binary two-run flavor (CU-011)."
                ),
                UserWarning,
                stacklevel=2,
            )

        E_TOA = np.asarray(toa_solar_spectral_irradiance(wavelength_um), dtype=np.float64)
        E_sky_thermal = np.maximum(np.pi * ldown, 0.0)
        E_sky_scattered = np.zeros_like(wavelength_um, dtype=np.float64)

        return AtmosphericQuantities(
            wavelength_um=np.asarray(wavelength_um, dtype=np.float64),
            tau_sun=tau_sun,
            tau_up=tau.copy(),
            tau_full_up=tau.copy(),
            E_TOA=E_TOA,
            E_sky_scattered=E_sky_scattered,
            E_sky_thermal=E_sky_thermal,
            L_path_up=lpath,
            L_path_full=lpath.copy(),
        )

    def _build_state_from_arrays(
        self,
        query_wavelength_um: np.ndarray,
        geometry: AtmosphericGeometry,
        source_wavelength_um: np.ndarray,
        source_transmittance: np.ndarray,
        source_path_radiance: np.ndarray,
        cache_key: str,
    ) -> AtmosphericState:
        """Build an AtmosphericState by resampling MODTRAN output."""
        target_grid = SpectralGrid(wavelengths_um=query_wavelength_um)

        tau_sd = SpectralData(
            name="atm.transmittance.modtran",
            wavelength_um=source_wavelength_um,
            values=np.clip(source_transmittance, 0.0, 1.0),
            unit="",
            source=f"MODTRAN (cache_key={cache_key})",
            source_parameters={"model": "modtran", "cache_key": cache_key},
        )
        lp_sd = SpectralData(
            name="atm.path_radiance.modtran",
            wavelength_um=source_wavelength_um,
            values=np.maximum(source_path_radiance, 0.0),
            unit="W/m²/sr/µm",
            source=f"MODTRAN (cache_key={cache_key})",
            source_parameters={"model": "modtran", "cache_key": cache_key},
        )

        tau_resampled = tau_sd.resample(target_grid)
        lp_resampled = lp_sd.resample(target_grid)

        # MODTRAN tape7 does not provide a separate downwelling column
        # in the standard IEMSCT=2 output.  Set to zeros; the user can
        # supply a separate downwelling run or use the simple-model
        # approximation for L_atm_down.
        #
        # Gap 81: this is a real physics reduction — the reflected-downwelling
        # and sky-scatter background terms disappear, so a MODTRAN-backed run
        # is *lower* fidelity than SimpleAtmosphere for the background in
        # thermal bands. Warn loudly rather than let switching model= silently
        # drop the terms. The full fix (ingest a separate downwelling run via
        # atmosphere.modtran.tape7_down_path, mirroring tape7_sun_path) is
        # gated on MODTRAN access, alongside CU-011/065/070.
        warnings.warn(
            "ModtranAtmosphere: downwelling sky emission (atm_emission_down / "
            "E_sky_thermal) and scattered-solar sky radiance are set to ZERO — "
            "the standard IEMSCT=2 tape7 carries no downwelling column. Any "
            "reflected-downwelling or sky-scatter background term is dropped, so "
            "in thermal bands this MODTRAN state is lower-fidelity than "
            "SimpleAtmosphere for the background. Use atmosphere.model='simple' "
            "where downwelling matters, or supply a separate downwelling run "
            "(atmosphere.modtran.tape7_down_path — not yet implemented; Gap 81).",
            UserWarning,
            stacklevel=2,
        )
        zeros = np.zeros_like(query_wavelength_um)

        return AtmosphericState(
            transmittance=SpectralData(
                name="atm.transmittance.modtran",
                wavelength_um=query_wavelength_um,
                values=tau_resampled.values,
                unit="",
                source=tau_sd.source,
                source_parameters=tau_sd.source_parameters,
            ),
            path_radiance=SpectralData(
                name="atm.path_radiance.modtran",
                wavelength_um=query_wavelength_um,
                values=lp_resampled.values,
                unit="W/m²/sr/µm",
                source=lp_sd.source,
                source_parameters=lp_sd.source_parameters,
            ),
            atm_emission_down=SpectralData(
                name="atm.emission_down.modtran",
                wavelength_um=query_wavelength_um,
                values=zeros,
                unit="W/m²/sr/µm",
                source="ModtranAtmosphere default (zeros — use separate downwelling run)",
                source_parameters={"model": "modtran", "cache_key": cache_key},
            ),
            geometry=geometry,
            derivation_chain=(
                (
                    f"ModtranAtmosphere(tape7 import: {self._tape7_import.source_path})",
                    f"content_key={self._tape7_import.content_key}",
                    "Geometry-agnostic: imported arrays not rescaled with viewing geometry",
                )
                if self._tape7_import is not None
                else (
                    f"ModtranAtmosphere(profile={self._config.atmosphere_profile}, "
                    f"aerosol={self._config.aerosol_model})",
                    f"cache_key={cache_key}",
                )
            ),
        )

    def _fallback(
        self,
        wavelength_um: np.ndarray,
        geometry: AtmosphericGeometry,
    ) -> AtmosphericState:
        """Fall back to SimpleAtmosphere with translated parameters."""
        from radiant.atmosphere.simple import SimpleAtmosphere

        # Map MODTRAN aerosol model -> SimpleAtmosphere aerosol type.
        aerosol_map: dict[str, str] = {
            "none": "rural",
            "rural": "rural",
            "urban": "urban",
            "maritime": "maritime",
            "tropospheric": "rural",
        }
        simple_aerosol = aerosol_map.get(self._config.aerosol_model, "rural")

        # Map MODTRAN atmosphere profile -> SimpleAtmosphere standard_atmosphere.
        simple_profile = self._config.atmosphere_profile

        model = SimpleAtmosphere(
            aerosol_type=simple_aerosol,
            standard_atmosphere=simple_profile,
            precipitable_water_cm=1.4 * self._config.h2o_scale,
        )
        return model.build_state(wavelength_um, geometry)
