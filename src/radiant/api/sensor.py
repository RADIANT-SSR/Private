"""Sensor — high-level scripting API for RADIANT.

Wraps :class:`~radiant.api.session.RadiantSession` with a fluent
interface for loading configs, setting parameters, evaluating the
signal chain, and running trade studies (sweeps, Monte Carlo,
sensitivity analysis).

Usage::

    from radiant.api.sensor import Sensor

    s = Sensor.from_yaml("examples/mwir_leo_minimal.yaml")
    result = s.evaluate()
    print(result.metrics)
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from radiant.api._param_registry import build_parameter_set
from radiant.api.config_io import normalize_element_document
from radiant.api.errors import ApiValidationError
from radiant.api.sensitivity import SensitivityResult, sensitivity
from radiant.api.session import RadiantSession
from radiant.api.solve import SolveResult, solve_for
from radiant.api.sweep import Sweep2DResult, SweepResult, sweep, sweep_2d
from radiant.api.tolerance import MonteCarloResult, monte_carlo
from radiant.atmosphere.family_suitability import (
    AtmosphereFamilySuggestion,
)
from radiant.atmosphere.family_suitability import (
    family_suitability as _family_suitability,
)
from radiant.atmosphere.family_suitability import (
    select_atmosphere_family as _select_atmosphere_family,
)
from radiant.atmosphere.interpolation_coverage import (
    ShippedFamily,
)
from radiant.atmosphere.interpolation_coverage import (
    check_interpolation_coverage as _check_interpolation_coverage,
)
from radiant.atmosphere.interpolation_coverage import (
    profile_change_warning as _profile_change_warning,
)
from radiant.core.exceptions import RadiantError
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.orbit import ground_track_speed_m_s
from radiant.core.parameters import (
    ParameterDef,
    ParameterSet,
    Provenance,
    ResolvedValue,
    Tolerance,
)
from radiant.geometry.modes import resolve_solar, resolve_viewing
from radiant.io.config import (
    load_config,
    read_radiant_meta,
    save_config,
    serialize_config,
    unattached_section_error,
)
from radiant.io.element_config import parse_element_entries
from radiant.io.results import ChainResult
from radiant.source.target_spec import validate_target_spec as _validate_target_spec

logger = logging.getLogger(__name__)

# Default number of wavelength grid points.
_DEFAULT_WL_POINTS: int = 500


class Sensor:
    """High-level entry point for RADIANT trade studies.

    Wraps :class:`RadiantSession` and :class:`ParameterSet`, exposing a
    simple API for loading configs, setting parameters, and running
    analyses.

    Parameters
    ----------
    wavelength_points:
        Number of points in the spectral evaluation grid.  The grid
        spans from ``spectral_integration.filter_min_um`` to
        ``spectral_integration.filter_max_um`` (set via config or
        :meth:`set`).
    """

    def __init__(self, *, wavelength_points: int = _DEFAULT_WL_POINTS) -> None:
        self._params: ParameterSet = build_parameter_set()
        self._wl_points: int = wavelength_points
        # Non-scalar pre-chain injections (Gap 68): group -> key -> object,
        # forwarded to RadiantSession.run(extra_stage_outputs=...) on every
        # evaluation, including trade studies. Not serialized by save().
        self._extra_stage_outputs: dict[str, dict[str, Any]] = {}
        # Declarative optical-element document (ADR-0009 D4): the
        # `optical_elements:` entries, normalized (absolute file refs).
        # Parsed onto the evaluation grid per run and serialized by save().
        self._element_document: list[dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        *,
        wavelength_points: int = _DEFAULT_WL_POINTS,
        sections_out: dict[str, Any] | None = None,
    ) -> Sensor:
        """Load a YAML configuration file.

        Parameters
        ----------
        path:
            Path to a RADIANT YAML config file.
        wavelength_points:
            Number of spectral grid points.
        sections_out:
            Opt-in for structured sections a `Sensor` does **not** attach —
            today the ``configurations:`` section of a configuration set
            (ADR-0010). When a dict is passed, any such section is placed in it
            for the caller to parse (``ConfigurationSet.load`` does exactly
            that); when ``None`` (default), a config file carrying one raises an
            actionable :class:`~radiant.io.config.ConfigError` rather than
            loading a study as if it were a single config (Rule 17). The
            ``optical_elements`` section is always attached by the Sensor itself
            and never appears here.

        Returns
        -------
        Sensor
            A new Sensor with the config applied (not yet resolved).
        """
        sensor = cls(wavelength_points=wavelength_points)
        sections: dict[str, Any] = {}
        load_config(Path(path), sensor._params, sections_out=sections)
        if "optical_elements" in sections:
            sensor.set_optical_elements(
                sections.pop("optical_elements"), base_dir=Path(path).parent
            )
        _dispatch_unattached_sections(sections, sections_out, path)
        return sensor

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        wavelength_points: int = _DEFAULT_WL_POINTS,
        sections_out: dict[str, Any] | None = None,
    ) -> Sensor:
        """Create a Sensor from a nested configuration dict.

        Parameters
        ----------
        data:
            Nested dict matching the YAML structure (e.g.,
            ``{"optics": {"aperture_diameter_m": 0.3}}``).
        wavelength_points:
            Number of spectral grid points.
        sections_out:
            Structured-section opt-in, as on :meth:`from_yaml`.

        Returns
        -------
        Sensor
            A new Sensor with the config applied.
        """
        sensor = cls(wavelength_points=wavelength_points)
        sections: dict[str, Any] = {}
        load_config(data, sensor._params, sections_out=sections)
        if "optical_elements" in sections:
            sensor.set_optical_elements(sections.pop("optical_elements"))
        _dispatch_unattached_sections(sections, sections_out, None)
        return sensor

    # ------------------------------------------------------------------
    # Persistence (Gap 67)
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path, *, sections_out: dict[str, Any] | None = None) -> Sensor:
        """Load a Sensor saved with :meth:`save` (or any RADIANT YAML).

        Restores parameters, tolerance distributions, and the spectral
        grid size from the file's ``_radiant`` metadata block when
        present; plain configs load exactly as with :meth:`from_yaml`.
        ``sections_out`` is the same structured-section opt-in
        :meth:`from_yaml` documents — without it, a configuration-set file
        raises instead of loading as a single configuration.
        """
        meta = read_radiant_meta(path)
        wl_points = meta.get("wavelength_points", _DEFAULT_WL_POINTS)
        if not isinstance(wl_points, int) or wl_points < 2:
            raise ApiValidationError(
                f"Sensor.load: '_radiant.wavelength_points' must be an "
                f"integer >= 2, got {wl_points!r} in {path}."
            )
        return cls.from_yaml(path, wavelength_points=wl_points, sections_out=sections_out)

    def save(
        self,
        path: str | Path,
        *,
        extra_sections: Mapping[str, Any] | None = None,
        validate: bool = True,
    ) -> Path:
        """Save this Sensor to a YAML config that :meth:`load` restores.

        Writes the explicitly-set inputs (input units) plus a
        ``_radiant`` metadata block carrying ``wavelength_points`` and
        any tolerance distributions. Reloading reproduces this Sensor
        exactly: defaults re-apply, consistency groups re-derive, and
        provenance distinctions between explicit and defaulted
        parameters survive. The file is a normal RADIANT config: it
        also loads via :meth:`from_yaml` or the CLI.

        ``extra_sections`` writes additional registered structured sections
        alongside the Sensor's own ``optical_elements`` — the seam
        :meth:`ConfigurationSet.save <radiant.api.config_set.ConfigurationSet.save>`
        uses for the ``configurations:`` section (ADR-0010 D-D). Omitted (the
        default), the written file is byte-for-byte what it has always been.

        ``validate=False`` skips the resolve gate. Only the explicit inputs are
        written, so resolution is not needed to *produce* the document — it is a
        deliberate check that what is being saved is a complete, valid config.
        A caller that owns validation and whose sensor is legitimately
        incomplete passes ``False``: `ConfigurationSet` does, because a
        *required* parameter that has been configured is (by the single-store
        invariant, ADR-0010 D-B) absent from the shared base.
        """
        if validate:
            self._ensure_resolved()
        meta: dict[str, Any] = {
            "format": 1,
            "wavelength_points": self._wl_points,
        }
        tolerances = {
            name: {"distribution": tol.distribution, "params": dict(tol.params)}
            for name, tol in self._params.tolerances().items()
        }
        if tolerances:
            meta["tolerances"] = tolerances
        sections = self._sections(extra_sections)
        return save_config(
            self._params,
            Path(path),
            header="# RADIANT config — written by Sensor.save()\n",
            meta=meta,
            scope="inputs",
            sections=sections,
        )

    def to_yaml(
        self,
        *,
        scope: str = "inputs",
        relative_to: str | Path | None = None,
        extra_sections: Mapping[str, Any] | None = None,
        validate: bool = True,
    ) -> str:
        """Serialize this Sensor to a YAML string (Gap 88 — no temp file).

        ``scope="inputs"`` (default) is byte-identical to what :meth:`save`
        writes (explicit inputs + the ``_radiant`` meta block + any attached
        ``optical_elements`` document) and reloads exactly.
        ``scope="resolved"`` writes every resolved parameter — defaults and
        derived values included — as a fully-specified documentation export.

        ``relative_to`` (CU-177): a directory the emitted YAML will live in.
        When given, file-path parameters (``is_file_path``) that hold an absolute
        path are written relative to it, matching what :meth:`save` does with its
        own destination directory, so the string is portable when written there.

        ``extra_sections`` writes additional registered structured sections, and
        ``validate`` gates the resolve, both as on :meth:`save`
        (``validate=False`` requires ``scope="inputs"`` — a resolved export has
        nothing to write without resolving).
        """
        if validate or scope != "inputs":
            self._ensure_resolved()
        meta: dict[str, Any] = {"format": 1, "wavelength_points": self._wl_points}
        tolerances = {
            name: {"distribution": tol.distribution, "params": dict(tol.params)}
            for name, tol in self._params.tolerances().items()
        }
        if tolerances:
            meta["tolerances"] = tolerances
        sections = self._sections(extra_sections)
        return serialize_config(
            self._params,
            header="# RADIANT config — written by Sensor.to_yaml()\n",
            meta=meta,
            scope=scope,
            sections=sections,
            relative_to=Path(relative_to) if relative_to is not None else None,
        )

    # ------------------------------------------------------------------
    # Parameter access
    # ------------------------------------------------------------------

    def set(
        self,
        dotpath: str,
        value: Any,
        *,
        unit: str | None = None,
        source: str = "Sensor.set",
    ) -> Sensor:
        """Set a parameter by dot-path.

        With ``unit``, the value is converted from the caller's native
        unit at this boundary (Gap 6), e.g.
        ``sensor.set("optics.aperture_diameter_m", 30.0, unit="cm")``.

        ``source`` is the human-readable provenance label recorded with the
        input and shown by :meth:`resolved` / :meth:`explain` (CU-208). It
        defaults to ``"Sensor.set"``; a caller that sets values on behalf of a
        named context passes its own label, e.g.
        :class:`~radiant.api.config_set.ConfigurationSet` stamps
        ``source="config:<name>"`` (ADR-0010 D-C). The provenance *class*
        stays ``USER_SET``.

        Returns ``self`` for method chaining.
        """
        self._params.set(dotpath, value, Provenance.USER_SET, source, unit=unit)
        return self

    def set_many(self, overrides: dict[str, Any], *, source: str = "Sensor.set_many") -> Sensor:
        """Set multiple parameters at once.

        Parameters
        ----------
        overrides:
            Dict mapping dot-path → value.
        source:
            Provenance label recorded with every input (CU-208), as on
            :meth:`set`.

        Returns ``self`` for method chaining.
        """
        for dotpath, value in overrides.items():
            self._params.set(dotpath, value, Provenance.USER_SET, source)
        return self

    def inputs(self) -> Mapping[str, Any]:
        """Read-only snapshot of the explicitly-set inputs (CU-208).

        Passthrough to :meth:`ParameterSet.inputs`: dot-path → value **in
        input units**, holding only parameters actually set (by
        :meth:`set`/:meth:`set_many` or a config load) — defaults and derived
        values do not appear. This is the persistence/inspection surface
        :meth:`save` writes and :class:`~radiant.api.config_set.ConfigurationSet`
        reads to tell shared from configured parameters.
        """
        return self._params.inputs()

    def resolve(self) -> Sensor:
        """Resolve the parameter set now, if it is not already resolved (CU-208).

        Idempotent: applies defaults, derives consistency-group members, and
        validates bounds/enums exactly once — the same resolution
        :meth:`evaluate`, :meth:`get`, and :meth:`save` trigger implicitly.
        Calling it explicitly surfaces a configuration error (over-constrained
        group, out-of-bounds value) at a chosen point rather than inside a
        later call. Returns ``self`` for method chaining.
        """
        self._ensure_resolved()
        return self

    def get(self, dotpath: str) -> Any:
        """Get a resolved parameter value (in canonical units).

        Resolves the parameter set if needed.
        """
        self._ensure_resolved()
        return self._params.get(dotpath)

    def get_input(self, dotpath: str) -> Any:
        """Get a resolved parameter value in input (display) units."""
        self._ensure_resolved()
        return self._params.get_input(dotpath)

    def resolved(self, dotpath: str) -> ResolvedValue:
        """Return the full resolved record for *dotpath* (CU-105).

        A structured, machine-readable passthrough to
        :meth:`ParameterSet.get_resolved` — value (canonical), ``input_value``,
        units, ``provenance`` (a :class:`~radiant.core.parameters.Provenance`),
        and human-readable ``source``. This is the public alternative to parsing
        :meth:`explain`; GUI/tooling that needs provenance should read it here
        rather than scrape the explanation text. Raises ``KeyError`` for an
        unknown/unresolved parameter.
        """
        self._ensure_resolved()
        return self._params.get_resolved(dotpath)

    def provenance(self, dotpath: str) -> Provenance:
        """Return just the :class:`~radiant.core.parameters.Provenance` for *dotpath*.

        Convenience over :meth:`resolved` (CU-105) for callers that only need to
        know whether a value was user-set, config-file, default, or derived.
        """
        return self.resolved(dotpath).provenance

    def parameter_defs(self) -> Mapping[str, ParameterDef]:
        """Read-only view of the full parameter schema, keyed by dot-path.

        Passthrough to :meth:`ParameterSet.parameter_defs` (Gap 70): each
        :class:`ParameterDef` carries dtype, canonical/input units, bounds,
        enum values, default, description, and tags — the enumeration
        surface GUI panels and tooling generate from.
        """
        return self._params.parameter_defs()

    def parameter_def(self, dotpath: str) -> ParameterDef:
        """Return the :class:`ParameterDef` for one parameter.

        Raises ``KeyError`` (with a did-you-mean suggestion) for unknown
        names; deprecated aliases resolve with a ``DeprecationWarning``.
        """
        return self._params.parameter_def(dotpath)

    def reset(self, dotpath: str) -> Sensor:
        """Reset a parameter to its default value.

        Removes the user-set input so that the parameter reverts to
        its schema default (or is derived from a consistency group)
        on the next resolve.

        Returns ``self`` for method chaining.
        """
        self._params.clear_input(dotpath)
        return self

    def reset_all(self, *, scope: str = "user_set") -> Sensor:
        """Reset parameters in bulk by provenance scope (Gap 93).

        ``scope="user_set"`` (default) removes every input whose provenance is
        ``USER_SET`` (``Sensor.set`` / GUI edits). Inputs still carrying config-file
        provenance survive — but note an edit **replaces** an input's provenance, so
        a config value that was later edited reverts to its *schema default*, not to
        the file value (there is no layered history). To revert to the file exactly,
        reload it (``Sensor.load``). ``scope="all"`` removes every explicit input,
        reverting to pure schema defaults (an incomplete config will then fail
        resolution with its normal actionable errors).

        Returns ``self`` for method chaining.
        """
        if scope not in ("user_set", "all"):
            raise ApiValidationError(
                f"reset_all: scope must be 'user_set' or 'all', got {scope!r}."
            )
        for name, provenance in list(self._params.input_provenances().items()):
            if scope == "all" or provenance is Provenance.USER_SET:
                self._params.clear_input(name)
        return self

    def set_tolerance(
        self,
        dotpath: str,
        distribution: str,
        **kwargs: float,
    ) -> Sensor:
        """Set a tolerance distribution for Monte Carlo / sensitivity.

        Parameters
        ----------
        dotpath:
            Parameter dot-path.
        distribution:
            Distribution name: ``"gaussian"``, ``"uniform"``,
            ``"truncated_gaussian"``, ``"log_normal"``.
        **kwargs:
            Distribution parameters (e.g., ``std=0.01``).

        Returns ``self`` for method chaining.
        """
        tol = Tolerance(distribution=distribution, params=dict(kwargs))
        self._params.set_tolerance(dotpath, tol)
        return self

    def tolerances(self) -> Mapping[str, Tolerance]:
        """Read-only view of the set tolerance distributions (GT-2 surface).

        Feeds the GUI ± badges and the Monte Carlo script scaffold; the same
        data ``save``/``to_yaml`` persist in the ``_radiant.tolerances`` block.
        """
        return self._params.tolerances()

    def clear_tolerance(self, dotpath: str) -> Sensor:
        """Remove the tolerance on *dotpath* (no-op if none). Returns ``self``."""
        self._params.clear_tolerance(dotpath)
        return self

    def set_ground_velocity_from_orbit(self) -> Sensor:
        """Derive ``platform.ground_velocity_m_s`` from the orbital altitude (Gap 75).

        Computes the sub-satellite ground-track speed for a circular orbit
        at ``geometry.sensor_altitude_m``
        (:func:`radiant.core.orbit.ground_track_speed_m_s`) and sets
        ``platform.ground_velocity_m_s`` — the "enter altitude, get
        velocity" path. Because the two ground-speed parameters are a
        collapsed consistency group (Gap 75), this one value feeds both
        the smear (``platform``) and access-rate (``geometry``) consumers.

        Requires ``geometry.sensor_altitude_m`` to be set first. Valid only
        for orbital platforms — do **not** call it for airborne sensors,
        whose ground speed is not the orbital ground track. Returns
        ``self`` for chaining.
        """
        altitude_m = self._params.inputs().get("geometry.sensor_altitude_m")
        if altitude_m is None:
            raise ApiValidationError(
                "set_ground_velocity_from_orbit: geometry.sensor_altitude_m must be "
                "set first — it is the orbital altitude the ground velocity is "
                "derived from."
            )
        v_ground = ground_track_speed_m_s(float(altitude_m))
        self._params.set("platform.ground_velocity_m_s", v_ground, Provenance.DERIVED, "orbit")
        return self

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def set_stage_output(self, group: str, key: str, value: Any) -> Sensor:
        """Attach a non-scalar pre-chain input (Gap 68 interim seam).

        Stores *value* under ``stage_outputs[group][key]`` for every
        subsequent evaluation — ``evaluate`` and all trade studies
        (sweep, sweep_2d, monte_carlo, sensitivity, solve_for). This is
        the Rule 6 injection route for element lists, Zernike/OPD
        wavefronts, spectral curves, and filter stacks::

            s.set_stage_output("optics_config", "element_list", elements)
            s.set_stage_output("optics_config", "wavefront_error", wfe)

        Pass ``None`` as *value* to remove a previously set injection.
        Injections are session state, not parameters: they are carried
        by :meth:`clone` but **not** written by :meth:`save` (arbitrary
        objects have no YAML form — rebuild them when reloading).

        Returns ``self`` for method chaining.
        """
        if value is None:
            self._extra_stage_outputs.get(group, {}).pop(key, None)
            if group in self._extra_stage_outputs and not self._extra_stage_outputs[group]:
                del self._extra_stage_outputs[group]
        else:
            self._extra_stage_outputs.setdefault(group, {})[key] = value
        return self

    def set_optical_elements(
        self,
        entries: Sequence[Mapping[str, Any]] | None,
        *,
        base_dir: str | Path | None = None,
    ) -> Sensor:
        """Attach a declarative optical-element document (ADR-0009).

        *entries* is the ``optical_elements:`` document — the same entry
        dicts the YAML section carries (see ``RADIANT_Config_Format.md``).
        The document is validated immediately through the io parser
        (fail-fast; the single validation authority, Kirchhoff checks
        included), normalized (relative spectral-file references under
        *base_dir* become absolute), and stored. On every evaluation it
        is parsed onto the current wavelength grid and injected as
        ``stage_outputs["optics_config"]["element_list"]`` — the optics
        stage then runs in full-prescription mode. Unlike raw
        :meth:`set_stage_output` objects, the document **is** written by
        :meth:`save` and restored by :meth:`load` (persistence parity).

        Pass ``None`` to remove a previously attached document.
        Element emissivity is Kirchhoff-derived by construction — it is
        never an input field (Rule 5).

        Returns ``self`` for method chaining.
        """
        if entries is None:
            self._element_document = None
            return self
        self._element_document = normalize_element_document(
            [dict(entry) for entry in entries], base_dir=base_dir
        )
        return self

    def optical_elements(self) -> list[dict[str, Any]] | None:
        """The attached optical-element document (normalized copy), or None."""
        return copy.deepcopy(self._element_document)

    def _merged_extras(
        self,
        extra: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]] | None:
        """Sensor-held injections with one-off *extra* merged on top.

        Merge order (later wins): the parsed element document (ADR-0009),
        then :meth:`set_stage_output` injections, then the one-off
        *extra* — so an explicitly injected ``element_list`` overrides
        the document for that run.
        """
        merged: dict[str, dict[str, Any]] = {}
        if self._element_document is not None:
            self._ensure_resolved()
            elements = parse_element_entries(
                self._element_document,
                self._wavelength_grid(),
                source_label="Sensor.optical_elements",
            )
            merged["optics_config"] = {"element_list": elements}
        for group, values in self._extra_stage_outputs.items():
            merged.setdefault(group, {}).update(values)
        for group, values in (extra or {}).items():
            merged.setdefault(group, {}).update(values)
        return merged or None

    def _make_run_fn(self, session: RadiantSession) -> Callable[[ParameterSet], ChainResult]:
        """Session runner carrying the sensor-held injections (Gap 68)."""
        extras = self._merged_extras()
        if extras is None:
            return session.run

        def _run(ps: ParameterSet) -> ChainResult:
            return session.run(ps, extra_stage_outputs=extras)

        return _run

    def validate_target_spec(self) -> None:
        """Raise if the ``source.target.*`` spec surfaces are over-specified.

        The resolve-time seam for the target-spec mutual-exclusivity rules
        (CU-244): runs the same guards — same what/why/action text — that
        ``evaluate()`` runs inside the source inferrer, but without any physics,
        file I/O, or chain execution, so a conflicting pair (e.g. scalar
        ``source.target.reflectance`` [dimensionless] plus a tabulated
        ``source.target.reflectance_path`` CSV) can be rejected at the door.
        The GUI's clone-validate edit discipline calls this after each
        candidate ``set``; the evaluate-time check remains in place as defence
        in depth.

        Covered exclusivity families: the reflectance/albedo aliases (scalar
        and ``_path`` forms), ρ vs the legacy (ε, T) thermal surface, ρ vs the
        S8/S10 absolute radiance/intensity paths, ρ vs the S11/S12
        brightness/radiance-temperature forms, the S11/S12 internal pairings,
        the S10/S10b intensity door vs a declared target extent (CU-256), and —
        since CU-293 — the S8, S10 and S10b doors' own pairings: S8 vs (ε, T),
        S8 vs S10, the two point-intensity modes against each other, and S10 /
        S10b vs (ε, T). Completeness ("this form still needs its band edges")
        is deliberately not checked here — a half-entered spec is a legitimate
        intermediate state, and ``evaluate()`` reports what is missing.

        CU-293 also made the two entry points symmetric: every pair this seam
        refuses, ``evaluate()`` refuses too, with the identical message. The
        one prior exception — an S11 + S12 pair, which raised here but
        evaluated silently because the S11 builder dispatched first without an
        S12 guard — is closed.

        Raises
        ------
        radiant.core.parameters.ParameterBoundsError
            If more than one mutually exclusive target-spec surface is
            user-set. A no-op otherwise.
        """
        _validate_target_spec(self._params)

    def validate_atmosphere_coverage(self) -> None:
        """Raise if the interpolated atmosphere's axes cannot serve this scene.

        The resolve-time seam for the interpolated-backend coverage rules
        (CU-239): checks the two things that are knowable the moment the
        geometry and ``atmosphere.interpolation_axes`` are both set —

        1. a down-looking scene with ``geometry.target_altitude_m`` above 0 m
           needs a ``target_altitude_m`` axis (Gap 94), and
        2. an empty ``atmosphere.interpolated_data_dir`` needs the
           ``(los_direction, axes)`` pair to name a shipped library family.

        Both were previously discovered inside the chain — the first in
        ``InterpolatedAtmosphere.evaluate``, five stages deep — so the operator
        met a mid-evaluation refusal instead of a config-time message. The
        error names the exact ``interpolation_axes`` string to use and, when
        that selects a shipped family, its coverage in km/degrees plus a
        profile-change caveat if the family's rendered profile differs from
        ``atmosphere.standard_atmosphere``. No physics, no chain, no mutation;
        the evaluate-time checks stay in place as defence in depth.

        No-op for every ``atmosphere.model`` other than ``"interpolated"`` and
        for a config whose geometry altitudes are not registered.

        Raises
        ------
        radiant.atmosphere.errors.AtmosphereCapabilityError
            The axes cannot serve the scene's target altitude.
        radiant.atmosphere.errors.AtmosphereValidationError
            No shipped family covers the pair and no data directory was given.
        """
        self._ensure_resolved()
        _check_interpolation_coverage(self._params)

    def _line_of_sight(self) -> LineOfSightGeometry | None:
        """The scene's resolved LOS, built exactly as ``GeometryStage`` builds it.

        The one derivation of ``theta_o``: reading ``geometry.path_zenith_rad``
        off the parameter set instead would be a *different number* on every
        spherical scene — a 30.0000° input resolves to a 29.9482° zenith at the
        lower endpoint on scenario 10.1 — and a family keyed to one rendered
        zenith is refused on exactly that difference (CU-322).

        ``None`` when the geometry cannot be resolved (an unregistered schema, a
        half-entered config, an over-specified viewing mode). No physics runs
        here and nothing is mutated.
        """
        self._ensure_resolved()
        try:
            viewing = resolve_viewing(self._params)
            solar = resolve_solar(self._params)
            return LineOfSightGeometry(
                h_tgt=viewing.h_target_m,
                h_sensor=viewing.h_sensor_m,
                theta_o=viewing.theta_o_rad,
                theta_s=solar.theta_s_rad,
                delta_phi=solar.delta_phi_rad,
            )
        except (KeyError, RadiantError, TypeError, ValueError):
            return None

    def atmosphere_family_suggestion(self) -> AtmosphereFamilySuggestion:
        """The pre-validated bundled-family recommendation for this scene (CU-322).

        The full-query form of :meth:`suggested_atmosphere_family`: it walks the
        bundled catalogue in precedence order and returns the first family whose
        **complete** query the chain would accept — direction, axes, LOS zenith,
        target ceiling (including the up-looking exo guard) and the family's own
        rendered lower endpoint. ``explicit_dir_only`` families are candidates
        like any other; adopting one means writing
        :attr:`~radiant.atmosphere.interpolation_coverage.ShippedFamily.bundled_dir`
        into ``atmosphere.interpolated_data_dir`` as well as the axes.

        When no family serves the scene, the result's ``family`` is ``None`` and
        its ``gap`` names the **closest miss** — one structured reason, with
        :attr:`~radiant.atmosphere.family_suitability.AtmosphereFamilySuggestion.advisory_text`
        rendering it as one unit-bearing sentence and ``advisory_error()``
        returning the same thing in actionable what/why/action form for a message
        surface. That replaces the sequential wall of refusals an operator used to
        collect one gate at a time.

        A **recommendation only** — this method writes nothing, because adopting a
        family can change the run's atmosphere profile
        (:meth:`atmosphere_profile_change_warning` renders that caveat).

        For an unresolvable geometry the result is an empty suggestion (no family,
        no gap): there is no scene yet to recommend for.
        """
        los = self._line_of_sight()
        if los is None:
            return AtmosphereFamilySuggestion(
                family=None, gap=None, considered=(), los_direction="unknown"
            )
        return _select_atmosphere_family(los)

    def suggested_atmosphere_family(self) -> ShippedFamily | None:
        """The bundled interpolation family this scene's geometry calls for (CU-239).

        Since CU-322 this is the **pre-validated** recommendation — the family
        returned here is one the chain will actually serve, never one it would
        then refuse — and it may be an ``explicit_dir_only`` row, which no axes
        string can reach. It is the ``family`` field of
        :meth:`atmosphere_family_suggestion`; call that instead when the *reason*
        for a ``None`` matters.

        A **recommendation only** — this method writes nothing, because adopting a
        family can change the run's atmosphere profile
        (:meth:`atmosphere_profile_change_warning` renders that caveat). Callers
        write ``atmosphere.interpolation_axes`` (and, for an ``explicit_dir_only``
        family, ``atmosphere.interpolated_data_dir``) themselves.

        ``None`` when no bundled family serves the geometry (e.g. a level line of
        sight, or a sensor below every family's rendered floor) or the geometry
        cannot be resolved.
        """
        return self.atmosphere_family_suggestion().family

    def atmosphere_family_gap(self, family: ShippedFamily) -> str | None:
        """Why *family* cannot serve this scene, or ``None`` when it can (CU-322).

        The per-family form of :meth:`atmosphere_family_suggestion`: the same
        complete-query check, asked of one named family instead of the catalogue.
        A picker uses it to say whether the row the operator is looking at — or
        the one already configured — actually covers the scene, without setting a
        parameter to find out.

        The returned sentence carries its units (m, km, degrees). ``None`` when
        the family serves the scene **and** when the geometry cannot be resolved
        (there is no scene yet to answer for).
        """
        los = self._line_of_sight()
        if los is None:
            return None
        suitability = _family_suitability(family, los)
        return None if suitability.gap is None else suitability.gap.text

    def atmosphere_profile_change_warning(self, family: ShippedFamily) -> str | None:
        """Warn text if adopting *family* would change the requested profile (CU-239).

        ``None`` when ``atmosphere.standard_atmosphere`` was never user-set (there
        is no explicit request to contradict) or already matches the profile the
        family's runs were rendered with. Non-``None`` is a caller-surfaced
        sentence — choosing a family must never silently change the atmosphere the
        operator asked for. Never mutates and never suppresses.
        """
        self._ensure_resolved()
        return _profile_change_warning(self._params, family)

    def evaluate(
        self,
        *,
        extra_stage_outputs: dict[str, dict[str, Any]] | None = None,
    ) -> ChainResult:
        """Run the full signal chain and return the result.

        Parameters
        ----------
        extra_stage_outputs:
            One-off non-scalar pre-chain injections (Gap 68), merged over
            any set via :meth:`set_stage_output`, e.g.
            ``{"optics_config": {"element_list": elements}}``.
        """
        self._ensure_resolved()
        session = self._build_session()
        merged = self._merged_extras(extra_stage_outputs)
        if merged is None:
            return session.run(self._params)
        return session.run(self._params, extra_stage_outputs=merged)

    # ------------------------------------------------------------------
    # Trade studies
    # ------------------------------------------------------------------

    def sweep(
        self,
        param: str,
        values: Sequence[float] | npt.NDArray[np.float64],
        *,
        metric: str | Callable[[ChainResult], float] = "snr",
        keep_results: bool = True,
        n_workers: int = 1,
        progress: Callable[[int, int], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> SweepResult:
        """Run a 1-D parameter sweep.

        Parameters
        ----------
        param:
            Dot-path of the parameter to sweep.
        values:
            Array of parameter values.
        metric:
            Metric key string (looked up in ``result.metrics``) or a
            callable ``(ChainResult) -> float``.
        keep_results:
            Store full ChainResult at each point.
        n_workers:
            Parallel workers (1 = sequential).
        progress:
            ``progress(done, total)`` callback per completed point (Gap 72).
        cancel:
            ``cancel() -> bool`` poll; True aborts with
            :class:`~radiant.api._progress.OperationCancelledError`.
        """
        self._ensure_resolved()
        session = self._build_session()
        metric_fn, metric_name = self._resolve_metric(metric)
        return sweep(
            self._make_run_fn(session),
            self._params,
            param,
            values,
            metric=metric_fn,
            metric_name=metric_name,
            keep_results=keep_results,
            n_workers=n_workers,
            progress=progress,
            cancel=cancel,
        )

    def solve_for(
        self,
        param: str,
        target: float,
        *,
        bounds: tuple[float, float],
        metric: str | Callable[[ChainResult], float] = "snr",
        rtol: float = 1e-6,
    ) -> SolveResult:
        """Find the parameter value that makes *metric* equal *target* (Gap 10).

        Brent root-finding on the forward model over the *bounds*
        bracket (input units). Example::

            res = sensor.solve_for(
                "optics.aperture_diameter_m", 50.0,
                bounds=(0.05, 1.0), metric="snr",
            )
            res.solution   # aperture [m] giving SNR = 50

        Raises :class:`~radiant.api.solve.SolveBracketError` (with both
        endpoint metric values) when the target is not bracketed.
        """
        self._ensure_resolved()
        session = self._build_session()
        metric_fn, metric_name = self._resolve_metric(metric)
        return solve_for(
            self._make_run_fn(session),
            self._params,
            param,
            target,
            bounds,
            metric=metric_fn,
            metric_name=metric_name,
            rtol=rtol,
        )

    def sweep_2d(
        self,
        param1: str,
        values1: Sequence[float] | npt.NDArray[np.float64],
        param2: str,
        values2: Sequence[float] | npt.NDArray[np.float64],
        *,
        metric: str | Callable[[ChainResult], float] = "snr",
        progress: Callable[[int, int], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> Sweep2DResult:
        """Run a 2-D parameter sweep.

        Parameters
        ----------
        param1, param2:
            Dot-paths of the two swept parameters.
        values1, values2:
            Arrays of values for each axis.
        metric:
            Metric key string or callable.
        progress:
            ``progress(done, total)`` callback per grid cell (Gap 72).
        cancel:
            ``cancel() -> bool`` poll; True aborts with
            :class:`~radiant.api._progress.OperationCancelledError`.
        """
        self._ensure_resolved()
        session = self._build_session()
        metric_fn, metric_name = self._resolve_metric(metric)
        return sweep_2d(
            self._make_run_fn(session),
            self._params,
            param1,
            values1,
            param2,
            values2,
            metric=metric_fn,
            metric_name=metric_name,
            progress=progress,
            cancel=cancel,
        )

    def monte_carlo(
        self,
        n_trials: int = 1000,
        seed: int = 42,
        *,
        metric_names: tuple[str, ...] | None = None,
        keep_results: bool = False,
        progress: Callable[[int, int], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> MonteCarloResult:
        """Run Monte Carlo tolerance analysis.

        Requires at least one tolerance set via :meth:`set_tolerance`.

        Parameters
        ----------
        n_trials:
            Number of MC trials.
        seed:
            Random seed for reproducibility.
        metric_names:
            Metric keys to record. Auto-detected if None.
        keep_results:
            Store full ChainResult per trial.
        progress:
            ``progress(done, total)`` callback per trial (Gap 72).
        cancel:
            ``cancel() -> bool`` poll; True aborts with
            :class:`~radiant.api._progress.OperationCancelledError`.
        """
        self._ensure_resolved()
        session = self._build_session()
        return monte_carlo(
            self._make_run_fn(session),
            self._params,
            n_trials=n_trials,
            seed=seed,
            metric_names=metric_names,
            keep_results=keep_results,
            progress=progress,
            cancel=cancel,
        )

    def sensitivity(
        self,
        *,
        metric: str | Callable[[ChainResult], float] = "snr",
        param_names: Sequence[str] | None = None,
        delta_fraction: float = 0.01,
        progress: Callable[[int, int], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> SensitivityResult:
        """Run one-at-a-time sensitivity analysis.

        Parameters
        ----------
        metric:
            Metric key string or callable.
        param_names:
            Parameters to perturb. If None, uses toleranced or all
            float parameters.
        delta_fraction:
            Fractional perturbation (0.01 = ±1%).
        progress:
            ``progress(done, total)`` callback per perturbed parameter (Gap 72).
        cancel:
            ``cancel() -> bool`` poll; True aborts with
            :class:`~radiant.api._progress.OperationCancelledError`.
        """
        self._ensure_resolved()
        session = self._build_session()
        metric_fn, metric_name = self._resolve_metric(metric)
        return sensitivity(
            self._make_run_fn(session),
            self._params,
            metric=metric_fn,
            metric_name=metric_name,
            param_names=list(param_names) if param_names is not None else None,
            delta_fraction=delta_fraction,
            progress=progress,
            cancel=cancel,
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def clone(self) -> Sensor:
        """Return a deep copy of this Sensor."""
        return copy.deepcopy(self)

    @property
    def wavelength_points(self) -> int:
        """The number of spectral grid points this sensor evaluates on.

        The read counterpart of :meth:`with_wavelength_points` and of the
        ``_radiant.wavelength_points`` metadata field ``save``/``load`` carry, so
        a caller can display or re-serialize the grid density without evaluating
        the chain and measuring ``result.wavelength_um.size`` (CU-210).
        """
        return self._wl_points

    def with_wavelength_points(self, n: int) -> Sensor:
        """Return a clone evaluated on *n* spectral grid points.

        The grid still spans this sensor's own resolved
        ``spectral_integration.filter_min_um`` … ``filter_max_um`` band; only
        the point count changes. This sensor is left untouched — the supported
        way to vary the grid density after construction (ADR-0010 D-F, the
        per-configuration ``wavelength_points`` hook).

        Raises :class:`~radiant.api.errors.ApiValidationError` for ``n < 2`` or
        a non-integer, matching the check :meth:`load` applies to the
        ``_radiant.wavelength_points`` metadata field.
        """
        if not isinstance(n, int) or isinstance(n, bool) or n < 2:
            raise ApiValidationError(
                f"Sensor.with_wavelength_points: n must be an integer >= 2, got {n!r}."
            )
        clone = self.clone()
        clone._wl_points = n
        return clone

    def summary(self) -> str:
        """Return a human-readable summary of all resolved parameters."""
        self._ensure_resolved()
        resolved = self._params.all_resolved()
        lines: list[str] = ["RADIANT Sensor — Parameter Summary", "=" * 50]
        # Group by namespace prefix
        groups: dict[str, list[str]] = {}
        for name, rv in sorted(resolved.items()):
            prefix = name.split(".")[0]
            groups.setdefault(prefix, [])
            unit_str = f" {rv.input_unit}" if rv.input_unit else ""
            prov_str = rv.provenance.value
            groups[prefix].append(f"  {name} = {rv.input_value}{unit_str}  [{prov_str}]")
        for prefix in sorted(groups):
            lines.append(f"\n[{prefix}]")
            lines.extend(groups[prefix])
        return "\n".join(lines)

    def explain(self, dotpath: str | None = None) -> str:
        """Return a human-readable explanation.

        Parameters
        ----------
        dotpath:
            If provided, explain that parameter's provenance and value.
            If None, return a chain walkthrough with intermediate values
            from the most recent evaluation.
        """
        self._ensure_resolved()
        if dotpath is not None:
            return self._params.explain(dotpath)
        # Chain walkthrough — evaluate and describe the stages
        result = self.evaluate()
        lines: list[str] = ["RADIANT Chain Walkthrough", "=" * 50]
        for stage_name in result.history:
            lines.append(f"\n--- {stage_name} ---")
            outputs = result.stage_outputs.get(stage_name, {})
            for key, val in sorted(outputs.items()):
                lines.append(f"  {key}: {_format_value(val)}")
        lines.append("\n--- Metrics ---")
        for name, val in sorted(result.metrics.items()):
            lines.append(f"  {name}: {val:.6g}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_resolved(self) -> None:
        """Resolve the ParameterSet if it is not already resolved."""
        if not self._params.is_resolved:
            self._params.resolve()

    def _sections(self, extra: Mapping[str, Any] | None) -> dict[str, Any] | None:
        """Structured sections to write: the element document plus *extra*.

        ``None`` when there is nothing to write, so a Sensor with neither an
        element document nor extra sections produces exactly the document it
        always has.
        """
        sections: dict[str, Any] = {}
        if self._element_document is not None:
            sections["optical_elements"] = copy.deepcopy(self._element_document)
        for key, value in (extra or {}).items():
            if key in sections:
                raise ApiValidationError(
                    f"Sensor.save/to_yaml: section '{key}' is written by the Sensor "
                    "itself and cannot be passed in extra_sections. Attach it with "
                    "set_optical_elements() instead."
                )
            sections[key] = value
        return sections or None

    def _wavelength_grid(self) -> npt.NDArray[np.float64]:
        """The evaluation wavelength grid (filter band × wavelength_points)."""
        fmin: float = self._params.get("spectral_integration.filter_min_um")
        fmax: float = self._params.get("spectral_integration.filter_max_um")
        return np.linspace(fmin, fmax, self._wl_points)

    def _build_session(self) -> RadiantSession:
        """Build a RadiantSession with the appropriate wavelength grid."""
        return RadiantSession(wavelength_um=self._wavelength_grid())

    @staticmethod
    def _resolve_metric(
        metric: str | Callable[[ChainResult], float],
    ) -> tuple[Callable[[ChainResult], float], str]:
        """Convert a string metric key to a metric function + name."""
        if callable(metric):
            name = getattr(metric, "__name__", "metric")
            return metric, name
        metric_key = metric

        def _extract(result: ChainResult) -> float:
            val = result.metrics.get(metric_key)
            if val is None:
                raise ApiValidationError(
                    f"Metric '{metric_key}' not found in result.metrics. "
                    f"Available: {list(result.metrics.keys())}"
                )
            return float(val)

        return _extract, metric_key


def _dispatch_unattached_sections(
    sections: dict[str, Any],
    sections_out: dict[str, Any] | None,
    path: str | Path | None,
) -> None:
    """Hand over — or refuse — structured sections a ``Sensor`` does not attach.

    A ``Sensor`` attaches ``optical_elements`` itself; anything left (today the
    ``configurations:`` section of a configuration set) either goes to an
    opted-in caller or raises the actionable io error naming the loader that can
    read it. Never a silent drop (Rule 17).
    """
    if not sections:
        return
    if sections_out is None:
        raise unattached_section_error(sorted(sections), path)
    sections_out.update(sections)


def _format_value(val: Any) -> str:
    """Format a value for display in explain() output."""
    if isinstance(val, np.ndarray):
        if val.size <= 4:
            return repr(val)
        return f"ndarray shape={val.shape} dtype={val.dtype}"
    if isinstance(val, float):
        return f"{val:.6g}"
    return repr(val)
