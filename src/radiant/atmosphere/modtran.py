"""MODTRAN atmosphere interface — card deck builder, tape7 parser, and cache.

Wraps MODTRAN as an external binary tool per
``docs/RADIANT_Atmosphere.md`` section 5.  RADIANT builds a tape5 input
deck, invokes the MODTRAN executable, parses the tape7 output, converts
to RADIANT canonical units, and caches the result keyed by an SHA-256
hash of the rendered deck.

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from radiant.atmosphere._quantities import AtmosphericQuantities
from radiant.atmosphere.protocol import (
    AtmosphericGeometry,
    AtmosphericState,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterSet
from radiant.core.spectral import SpectralData, SpectralGrid

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ModtranUnavailableError(RuntimeError):
    """MODTRAN binary is not available and no fallback is enabled."""

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


class Tape7ParseError(ValueError):
    """Error parsing MODTRAN tape7 output."""


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
    spectral_resolution_cm1: float = 1.0
    v1_cm1: float = 700.0   # ~14.3 um
    v2_cm1: float = 25000.0  # ~0.4 um
    extra_cards: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.binary_path = Path(self.binary_path)
        self.cache_dir = Path(self.cache_dir)

        if self.atmosphere_profile not in _PROFILE_MAP:
            raise ValueError(
                f"ModtranConfig: atmosphere_profile='{self.atmosphere_profile}' "
                f"not recognised. Choose one of {sorted(_PROFILE_MAP)}."
            )
        if self.aerosol_model not in _IHAZE_MAP:
            raise ValueError(
                f"ModtranConfig: aerosol_model='{self.aerosol_model}' "
                f"not recognised. Choose one of {sorted(_IHAZE_MAP)}."
            )
        if self.h2o_scale <= 0.0:
            raise ValueError(
                f"ModtranConfig: h2o_scale={self.h2o_scale} must be positive."
            )
        if self.o3_scale <= 0.0:
            raise ValueError(
                f"ModtranConfig: o3_scale={self.o3_scale} must be positive."
            )
        if self.spectral_resolution_cm1 <= 0.0:
            raise ValueError(
                f"ModtranConfig: spectral_resolution_cm1="
                f"{self.spectral_resolution_cm1} must be positive."
            )
        if self.v1_cm1 >= self.v2_cm1:
            raise ValueError(
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
    angle_deg = math.degrees(geometry.path_zenith_rad)
    solar_zen_deg = math.degrees(geometry.solar_zenith_rad)
    solar_az_deg = math.degrees(geometry.solar_azimuth_rad)

    # Card 1: MODRAN, SPEED, BINARY, LYMOLC, MODEL, T_BEST, ITYPE, IEMSCT, IMULT
    # ITYPE=2 (slant path H1 to H2), IEMSCT=2 (thermal+solar radiance),
    # IMULT=1 (multiple scattering via DISORT)
    card1 = (
        f"T    5    0    {model_code}    0    2    2    1"
        f"    0    0    0    1    0  0.000"
    )

    # Card 1A: DIS, NSTR, LSUN
    card1a = "T    4 F F F F    0 0.00000  0.00000  0.00000  0.00000"

    # Card 2: IHAZE, ISEASN, IVULCN, ICSTL, ICLD, IVSA, VIS, WSS, WHH, RAINRT
    card2 = (
        f"    {ihaze}    0    0    0    0    0"
        f"  0.000  0.000  0.000  0.000  0.000"
    )

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
    card3a1 = (
        f"    2    0    0    0"
        f"{solar_zen_deg:10.3f}{solar_az_deg:10.3f}     0.000     0.000"
    )

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


class Tape7Reader:
    """Parse MODTRAN tape7 fixed-column output.

    The tape7 format is a fixed-width text file with a header section
    followed by spectral data columns.  The exact column layout depends
    on the MODTRAN version and card-deck options; this reader supports
    the standard transmittance/radiance output from IEMSCT=2 runs.

    Parameters
    ----------
    tape7_path:
        Path to the tape7 output file.
    """

    # Standard tape7 column positions for IEMSCT=2 output (0-indexed).
    # These are approximate and version-dependent; the header row names
    # provide the canonical mapping.
    _COL_WAVENUMBER = 0
    _COL_TOTAL_TRANS = 1
    _COL_PATH_THERMAL = 2
    _COL_PATH_SCATTERED = 3
    _COL_GROUND_REFLECTED = 4

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

        # Find the start of spectral data: skip header lines until we
        # find a line where the first field parses as a float.
        data_start = 0
        header_info: dict[str, Any] = {}
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            first_field = stripped.split()[0]
            try:
                float(first_field)
                data_start = i
                break
            except ValueError:
                # Accumulate header info.
                if i < 20:
                    header_info[f"header_line_{i}"] = stripped
        else:
            raise Tape7ParseError(
                f"MODTRAN tape7 {self._path}: no numeric data found. "
                "The file may be empty or corrupted."
            )

        # Parse spectral data.
        rows: list[list[float]] = []
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

        wavenumber = data[:, self._COL_WAVENUMBER]
        total_trans = data[:, self._COL_TOTAL_TRANS]
        path_thermal = data[:, self._COL_PATH_THERMAL] if n_cols > 2 else np.zeros_like(wavenumber)
        path_scattered = (
            data[:, self._COL_PATH_SCATTERED] if n_cols > 3 else np.zeros_like(wavenumber)
        )
        ground_reflected = (
            data[:, self._COL_GROUND_REFLECTED] if n_cols > 4 else np.zeros_like(wavenumber)
        )

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
    cache_dir: Path, key: str,
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
    """Atmosphere model wrapping the MODTRAN binary.

    Implements the :class:`~radiant.atmosphere.protocol.Atmosphere`
    structural protocol.

    Parameters
    ----------
    config:
        MODTRAN configuration including binary path, cache location,
        and model parameters.
    """

    def __init__(self, config: ModtranConfig) -> None:
        self._config = config
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
            raise RuntimeError(
                f"MODTRAN exited with code {result.returncode}. "
                f"stderr: {result.stderr[:500]}"
            )

        tape7_path = work_dir / "tape7"
        if not tape7_path.exists():
            raise RuntimeError(
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

        Sequence: render tape5 -> check cache -> run MODTRAN (or use
        cache / fallback) -> parse tape7 -> convert units -> resample
        to query grid -> return AtmosphericState.
        """
        lam = np.asarray(wavelength_um, dtype=np.float64)
        if lam.ndim != 1:
            raise ValueError(
                f"ModtranAtmosphere: wavelength_um must be 1-D, got shape {lam.shape}."
            )
        if lam.size < 2:
            raise ValueError(
                "ModtranAtmosphere: wavelength_um needs at least two samples."
            )
        if not np.all(np.diff(lam) > 0):
            raise ValueError("ModtranAtmosphere: wavelength_um must be strictly ascending.")
        if np.any(lam <= 0.0):
            raise ValueError("ModtranAtmosphere: wavelength_um must be strictly positive.")

        tape5 = render_tape5(self._config, geometry)
        key = _cache_key(tape5)

        # Try cache first.
        cached = _load_cache(self._config.cache_dir, key)
        if cached is not None:
            logger.info("MODTRAN cache hit: %s", key)
            wl_cached, tau_cached, lp_cached, gr_cached = cached
            return self._build_state_from_arrays(
                lam, geometry, wl_cached, tau_cached, lp_cached, key,
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
                self._config.cache_dir, key,
                wl_mod, tau_mod, lp_mod, gr_mod,
            )

            return self._build_state_from_arrays(
                lam, geometry, wl_mod, tau_mod, lp_mod, key,
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

        MODTRAN's tape7 output pre-dates the two-leg split, so this adapter
        collapses the legs the same way :class:`TabulatedAtmosphere` does:

        - ``tau_sun == tau_up == tau_full_up`` — the single MODTRAN
          transmittance, re-evaluated at the cached up-leg geometry.
        - ``L_path_up == L_path_full``.
        - ``E_sky_thermal == π · L_atm_down``.
        - ``E_sky_scattered == 0`` (Stage 6 deliverable).
        - ``E_TOA`` from the core solar irradiance so the direct-solar
          branch still works in the assembly.

        Surface targets (``h_tgt == 0``) only in v1; see Stage 5 for the
        airborne extension.
        """
        import warnings

        from radiant.core.solar import toa_solar_spectral_irradiance

        if los.h_tgt > 0.0:
            raise NotImplementedError(
                f"ModtranAtmosphere.evaluate: h_tgt = {los.h_tgt} m > 0 "
                "(airborne targets) is a Stage 5 deliverable; v1 MODTRAN "
                "runs are surface-target only."
            )

        # Reconstruct an AtmosphericGeometry from params; MODTRAN consumes it
        # via build_state below.
        geometry = AtmosphericGeometry(
            sensor_altitude_m=float(params.get("geometry.sensor_altitude_m")),
            target_altitude_m=0.0,
            path_zenith_rad=float(los.theta_o),
            solar_zenith_rad=(
                float(los.theta_s) if los.theta_s is not None
                else float(params.get("geometry.solar_zenith_rad"))
            ),
            solar_azimuth_rad=(
                float(los.delta_phi) if los.delta_phi is not None
                else float(params.get("geometry.solar_azimuth_rad"))
            ),
        )

        legacy_state = self.build_state(wavelength_um, geometry)
        tau = np.asarray(legacy_state.transmittance.values, dtype=np.float64)
        lpath = np.asarray(legacy_state.path_radiance.values, dtype=np.float64)
        ldown = np.asarray(legacy_state.atm_emission_down.values, dtype=np.float64)

        warnings.warn(
            (
                "ModtranAtmosphere.evaluate: the MODTRAN-tape7 backend does not "
                "carry the Option C two-leg split — collapsing "
                "τ_sun=τ_up=τ_full_up and L_path_up=L_path_full to the single "
                "MODTRAN transmittance.  Two-leg scenarios need a richer MODTRAN "
                "rendering (Stage 6+)."
            ),
            UserWarning,
            stacklevel=2,
        )

        E_TOA = np.asarray(
            toa_solar_spectral_irradiance(wavelength_um), dtype=np.float64
        )
        E_sky_thermal = np.maximum(np.pi * ldown, 0.0)
        E_sky_scattered = np.zeros_like(wavelength_um, dtype=np.float64)

        return AtmosphericQuantities(
            wavelength_um=np.asarray(wavelength_um, dtype=np.float64),
            tau_sun=tau,
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
                f"ModtranAtmosphere(profile={self._config.atmosphere_profile}, "
                f"aerosol={self._config.aerosol_model})",
                f"cache_key={cache_key}",
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
