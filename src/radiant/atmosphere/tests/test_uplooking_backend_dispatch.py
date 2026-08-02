"""Observer-leg backend dispatch for the up-looking topology (CU-226).

Level 0 — which backend arrangement ``supports_uplooking`` admits, which leg
each one serves, and what the refusals say.  The physics of the interpolated
column itself is pinned by ``test_interpolated_uplooking.py``; this module is
the *dispatch* contract:

* a bare ``SimpleAtmosphere`` still serves every leg (zero drift);
* an up-looking run family with a companion serves the observer leg from the
  family and everything else from the companion;
* an up-looking run family **without** a companion is not admitted — it would
  otherwise reach the illumination proxy and fail five calls deeper;
* a level path on a column ladder is refused, not approximated;
* ``L_toward_upper`` is never asked of a one-direction family — the up-looking
  observer leg always reads ``toward_lower`` (design question (i)).
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import pytest

from radiant.atmosphere._schema import ALL_PARAMETERS as ATMO_PARAMS
from radiant.atmosphere.interpolated import GeometryPoint, InterpolatedAtmosphere
from radiant.atmosphere.observer_leg import observer_leg_from_los
from radiant.atmosphere.simple import SimpleAtmosphere
from radiant.atmosphere.uplooking_quantities import (
    evaluate_uplooking_topology,
    supports_uplooking,
)
from radiant.core.los_geometry import LineOfSightGeometry
from radiant.core.parameters import ParameterBoundsError, ParameterSet
from radiant.core.spectral import SpectralData
from radiant.geometry._schema import ALL_PARAMETERS as GEO_PARAMS

_WL = np.linspace(3.0, 5.0, 9)


@pytest.fixture
def params() -> ParameterSet:
    ps = ParameterSet(list(GEO_PARAMS + ATMO_PARAMS))
    ps.set("geometry.sensor_altitude_m", 0.0)
    ps.set("atmosphere.model", "simple")
    ps.resolve()
    return ps


# Grey synthetic rungs: tau = 1 at the sensor plane, tau = 0.25 at 10 km, so
# every expected value below is an exact hand calculation.
_TAU_TOP = 0.25
_L_TOP = 4.0


def _spectral(name: str, value: float, unit: str) -> SpectralData:
    return SpectralData(
        name=name,
        wavelength_um=_WL.copy(),
        values=np.full_like(_WL, value),
        unit=unit,
        source="test fixture",
    )


def _point(target_m: float, tau: float, l_down: float) -> GeometryPoint:
    return GeometryPoint(
        coordinates={
            "sensor_altitude_m": 0.0,
            "target_altitude_m": target_m,
            "path_zenith_rad": 0.0,
            "solar_zenith_rad": 0.0,
            "solar_azimuth_rad": 0.0,
        },
        transmittance=_spectral("tau", tau, ""),
        path_radiance=_spectral("L_toward_lower", l_down, "W/m²/sr/µm"),
        atm_emission_down=_spectral("unused", 0.0, "W/m²/sr/µm"),
    )


def _simple() -> SimpleAtmosphere:
    return SimpleAtmosphere(
        visibility_km=23.0,
        aerosol_type="rural",
        precipitable_water_cm=1.4,
        standard_atmosphere="midlat_summer",
    )


def _family(*, companion: object | None) -> InterpolatedAtmosphere:
    return InterpolatedAtmosphere(
        [_point(0.0, 1.0, 0.0), _point(10_000.0, _TAU_TOP, _L_TOP)],
        axes=["target_altitude_m"],
        family_direction="up",
        uplooking_companion=companion,
    )


def _shipped_nodes(family_dir: Path) -> list[dict[str, float]]:
    """The committed node geometries of a bundled family, read from the NPZs."""
    nodes: list[dict[str, float]] = []
    for npz_file in sorted(family_dir.glob("*.npz")):
        with np.load(npz_file, allow_pickle=True) as data:
            nodes.append(dict(data["geometry"].item()))
    assert nodes, f"{family_dir} holds no NPZ runs"
    return nodes


def _load_shipped_uplooking_family(
    family_dir: Path,
    *,
    axes: list[str],
    companion: object,
) -> InterpolatedAtmosphere:
    """Build a bundled up-looking family straight from its committed NPZs."""
    from radiant.atmosphere.interpolated import UPLOOKING_RADIANCE_KEY

    points: list[GeometryPoint] = []
    for npz_file in sorted(family_dir.glob("*.npz")):
        with np.load(npz_file, allow_pickle=True) as data:
            coords = dict(data["geometry"].item())
            wl = np.asarray(data["wavelength_um"], dtype=np.float64)
            tau = np.asarray(data["transmittance"], dtype=np.float64)
            l_down = np.asarray(data[UPLOOKING_RADIANCE_KEY], dtype=np.float64)
        points.append(
            GeometryPoint(
                coordinates=coords,
                transmittance=SpectralData(
                    name="tau",
                    wavelength_um=wl.copy(),
                    values=tau,
                    unit="",
                    source=str(npz_file),
                ),
                path_radiance=SpectralData(
                    name="L_toward_lower",
                    wavelength_um=wl.copy(),
                    values=l_down,
                    unit="W/m²/sr/µm",
                    source=str(npz_file),
                ),
                atm_emission_down=SpectralData(
                    name="unused",
                    wavelength_um=wl.copy(),
                    values=np.zeros_like(wl),
                    unit="W/m²/sr/µm",
                    source=str(npz_file),
                ),
            )
        )
    return InterpolatedAtmosphere(
        points,
        axes=axes,
        family_direction="up",
        uplooking_companion=companion,
    )


def _los(h_sensor: float = 0.0, h_tgt: float = 10_000.0) -> LineOfSightGeometry:
    return LineOfSightGeometry(
        h_sensor=h_sensor,
        h_tgt=h_tgt,
        theta_o=math.pi,
        theta_s=math.radians(30.0),
        delta_phi=0.0,
    )


def _column_los(h_sensor: float, zeta_low_rad: float, h_tgt: float) -> LineOfSightGeometry:
    """An up-looking LOS at a given sensor-side zenith (``θ_o = π − ζ_low``)."""
    return LineOfSightGeometry(
        h_sensor=h_sensor,
        h_tgt=h_tgt,
        theta_o=math.pi - zeta_low_rad,
        theta_s=math.radians(30.0),
        delta_phi=0.0,
    )


class TestSupportsUplooking:
    """Which backend arrangements are admitted."""

    def test_simple_is_admitted(self) -> None:
        assert supports_uplooking(_simple()) is True

    def test_uplooking_family_with_companion_is_admitted(self) -> None:
        assert supports_uplooking(_family(companion=_simple())) is True

    def test_uplooking_family_without_companion_is_refused(self) -> None:
        """No companion means no illumination and no sky leg — refuse at the gate."""
        assert supports_uplooking(_family(companion=None)) is False

    def test_down_looking_family_is_refused(self) -> None:
        down = InterpolatedAtmosphere(
            [_point(0.0, 1.0, 0.0), _point(10_000.0, _TAU_TOP, _L_TOP)],
            axes=["target_altitude_m"],
        )
        assert supports_uplooking(down) is False

    def test_unrelated_object_is_refused(self) -> None:
        assert supports_uplooking(object()) is False

    def test_companion_on_a_down_looking_family_is_refused_at_construction(self) -> None:
        from radiant.atmosphere.errors import AtmosphereValidationError

        with pytest.raises(AtmosphereValidationError, match="uplooking_companion"):
            InterpolatedAtmosphere(
                [_point(0.0, 1.0, 0.0), _point(10_000.0, _TAU_TOP, _L_TOP)],
                axes=["target_altitude_m"],
                family_direction="down",
                uplooking_companion=_simple(),
            )


class TestObserverLegComesFromTheFamily:
    """The whole point of CU-226: the shipped data reaches a composed answer."""

    @pytest.fixture()
    def products(self, params):  # type: ignore[no-untyped-def]
        with pytest.warns(UserWarning, match="TWO atmosphere models"):
            return evaluate_uplooking_topology(_family(companion=_simple()), _WL, _los(), params)

    def test_tau_up_is_the_family_value(self, products) -> None:  # type: ignore[no-untyped-def]
        """τ_obs at the top rung is the rung's own τ, to floating-point exactness."""
        assert products.quantities.tau_up == pytest.approx(_TAU_TOP, abs=1e-12)

    def test_l_path_up_is_the_family_downwelling(self, products) -> None:  # type: ignore[no-untyped-def]
        assert products.quantities.L_path_up == pytest.approx(_L_TOP, abs=1e-12)

    def test_provenance_names_the_evaluator(self, products) -> None:  # type: ignore[no-untyped-def]
        prov = products.provenance["observer_segment_provenance"]
        assert prov["evaluator"] == "InterpolatedAtmosphere.uplooking_column_product"
        assert prov["radiance_product"] == "L_toward_lower"

    def test_backend_split_is_recorded(self, products) -> None:  # type: ignore[no-untyped-def]
        split = products.provenance["backend_split"]
        assert "InterpolatedAtmosphere" in split
        assert "SimpleAtmosphere companion" in split

    def test_sky_at_aperture_is_still_computed(self, products) -> None:  # type: ignore[no-untyped-def]
        """The companion serves the leg the family cannot: a non-zero sky."""
        sky = np.asarray(products.sky_radiance_at_aperture)
        assert sky.shape == _WL.shape
        assert np.all(sky >= 0.0)
        assert float(sky.max()) > 0.0

    def test_the_split_is_also_logged_at_info(self, params, caplog) -> None:  # type: ignore[no-untyped-def]
        """All three declarations, not two (CU-224 ratification condition).

        The hybrid was owner-ratified 2026-08-01 **conditional on staying
        declared**: ``UserWarning`` + INFO log record + ``backend_split``
        provenance marker.  The warning and the marker have their own tests
        above; this pins the third, so softening any one of them fails a test
        rather than passing quietly.
        """
        with (
            caplog.at_level(logging.INFO, logger="radiant.atmosphere.uplooking_quantities"),
            pytest.warns(UserWarning, match="TWO atmosphere models"),
        ):
            evaluate_uplooking_topology(_family(companion=_simple()), _WL, _los(), params)
        assert any("backend" in record.getMessage().lower() for record in caplog.records), (
            "the hybrid split must leave an INFO record, not only a warning"
        )


class TestZeroDriftForSimple:
    """``atmosphere.model='simple'`` takes exactly the pre-CU-226 route."""

    def test_simple_records_a_single_backend(self, params) -> None:  # type: ignore[no-untyped-def]
        products = evaluate_uplooking_topology(_simple(), _WL, _los(), params)
        assert products.provenance["backend_split"] == "all legs: SimpleAtmosphere"

    def test_simple_emits_no_hybrid_warning(self, params, recwarn) -> None:  # type: ignore[no-untyped-def]
        evaluate_uplooking_topology(_simple(), _WL, _los(), params)
        assert not [w for w in recwarn.list if "TWO atmosphere models" in str(w.message)]


class TestRefusals:
    def test_level_path_on_a_column_ladder_is_refused(self, params) -> None:  # type: ignore[no-untyped-def]
        """A level arm is no rung of a ladder — Rule 17 refusal, not an approximation."""
        level = LineOfSightGeometry(
            h_sensor=3_000.0,
            h_tgt=3_000.0,
            theta_o=math.pi / 2.0,
            theta_s=math.radians(30.0),
            delta_phi=0.0,
        )
        with pytest.raises(ParameterBoundsError, match="LEVEL path"):
            evaluate_uplooking_topology(_family(companion=_simple()), _WL, level, params)

    def test_capability_error_names_the_interpolated_route(self, params) -> None:  # type: ignore[no-untyped-def]
        """The refusal an unsupported backend gets must mention what now works."""
        with pytest.raises(ParameterBoundsError, match="up-looking run family"):
            evaluate_uplooking_topology(object(), _WL, _los(), params)


class TestDirectionIsAlwaysTowardLower:
    """Design question (i): ``L_toward_upper`` is unreachable on this branch."""

    @pytest.mark.parametrize("h_tgt", [1.0, 5_000.0, 10_000.0])
    def test_up_looking_observer_leg_reads_toward_lower(self, h_tgt: float) -> None:
        leg = observer_leg_from_los(_los(h_tgt=h_tgt))
        assert leg.toward_sensor == "toward_lower"


_SPECTRAL_FIELDS = (
    "tau_sun",
    "tau_up",
    "tau_full_up",
    "E_TOA",
    "E_sky_scattered",
    "E_sky_thermal",
    "L_path_up",
    "L_path_full",
)


class TestLibraryBackedExoTargetGuard:
    """CU-224 checklist (ex-CU-308): the exo branch is decided by code now.

    ``_illumination_products``' exo branch substitutes the exact vacuum
    identity for the proxy down-looking evaluation when the target sits at or
    above ``h_atm_top``.  Whether that identity may be *composed* with a
    library-backed observer leg is a property of the backing family, and the
    guard asks the family itself (``uplooking_target_ceiling_m``):

    * **full column** (ceiling ≥ ``h_atm_top``) — permitted.  Everything above
      ``h_atm_top`` is vacuum, so the composed observer leg for any exo target
      is *identically* the family's own top-of-column run.  The anchor the
      refusal demanded is the family.  Asserted below by exact identity
      (``h_atm_top`` vs 400 km vs GEO) and by the top-node value.
    * **partial column** (ceiling < ``h_atm_top``) — refused.  Real, unmeasured
      air lies between the top rung and the target.
    """

    _H_ATM_TOP = 100_000.0

    def _full_column_family(self) -> InterpolatedAtmosphere:
        """A synthetic up-looking family whose rungs reach ``h_atm_top``."""
        return InterpolatedAtmosphere(
            [
                _point(0.0, 1.0, 0.0),
                _point(self._H_ATM_TOP, _TAU_TOP, _L_TOP),
            ],
            axes=["target_altitude_m"],
            family_direction="up",
            uplooking_companion=_simple(),
        )

    def _exo_los(self, h_tgt: float | None = None) -> LineOfSightGeometry:
        return LineOfSightGeometry(
            h_sensor=0.0,
            h_tgt=self._H_ATM_TOP if h_tgt is None else h_tgt,
            h_atm_top=self._H_ATM_TOP,
            theta_o=math.pi,
            theta_s=math.radians(30.0),
            delta_phi=0.0,
        )

    # -- the full-column arm: permitted, and exact -----------------------

    def test_full_column_family_serves_an_exo_target(self, params) -> None:  # type: ignore[no-untyped-def]
        """The capability the batch-2 M/P families shipped for is reachable."""
        with pytest.warns(UserWarning, match="TWO atmosphere models"):
            products = evaluate_uplooking_topology(
                self._full_column_family(), _WL, self._exo_los(400_000.0), params
            )
        assert np.all(np.isfinite(np.asarray(products.quantities.tau_up)))

    def test_the_exo_observer_leg_is_the_top_of_column_run(self, params) -> None:  # type: ignore[no-untyped-def]
        """The measured anchor, hand-calculable on the synthetic rungs.

        The family's top rung is τ = 0.25, L = 4.0 W/m²/sr/µm at 100 km. An
        exo target at 400 km is separated from that rung by vacuum, so the
        composed observer leg must be that rung *exactly* — not an
        interpolation toward it, not an extrapolation past it.
        """
        with pytest.warns(UserWarning, match="TWO atmosphere models"):
            products = evaluate_uplooking_topology(
                self._full_column_family(), _WL, self._exo_los(400_000.0), params
            )
        assert products.quantities.tau_up == pytest.approx(_TAU_TOP, abs=1e-12)
        assert products.quantities.L_path_up == pytest.approx(_L_TOP, abs=1e-12)

    @pytest.mark.parametrize("h_tgt", [400_000.0, 35_786_000.0])
    def test_every_exo_altitude_gives_bit_identical_products(self, params, h_tgt: float) -> None:  # type: ignore[no-untyped-def]
        """The vacuum identity, stated as an identity: 100 km ≡ 400 km ≡ GEO.

        Vacuum has zero extinction and zero emission, so *where* above the
        column top the target sits cannot move the composed bundle. Bitwise on
        the eight fields, not to a tolerance — a tolerance would let a real
        dependence hide.

        The sky-at-aperture leg is checked to float-noise instead, and the
        reason is geometry rather than radiative transfer: it is served by the
        *companion*, keyed to the sensor-side zenith, and
        ``eta_from_theta_o(π, 0, h_tgt)`` returns π − 8.9e-16 rather than π at
        a GEO target — 13 ULP of spherical-solve residue in an angle that is
        physically exactly zero for a vertical ray. The companion's sky column
        carries that through at ~3e-15 relative. Nothing in the family's own
        product moves.
        """
        with pytest.warns(UserWarning, match="TWO atmosphere models"):
            at_top = evaluate_uplooking_topology(
                self._full_column_family(), _WL, self._exo_los(), params
            )
            exo = evaluate_uplooking_topology(
                self._full_column_family(), _WL, self._exo_los(h_tgt), params
            )
        for field in _SPECTRAL_FIELDS:
            np.testing.assert_array_equal(
                np.asarray(getattr(exo.quantities, field)),
                np.asarray(getattr(at_top.quantities, field)),
                err_msg=f"{field} moved with an exo target altitude — vacuum is not inert",
            )
        assert np.asarray(exo.sky_radiance_at_aperture) == pytest.approx(
            np.asarray(at_top.sky_radiance_at_aperture), rel=1e-12
        )

    def test_the_clamp_is_declared_in_provenance(self, params) -> None:  # type: ignore[no-untyped-def]
        """Rule 16: the identity that served the query is inspectable."""
        with pytest.warns(UserWarning, match="TWO atmosphere models"):
            products = evaluate_uplooking_topology(
                self._full_column_family(), _WL, self._exo_los(400_000.0), params
            )
        prov = products.provenance["observer_segment_provenance"]
        assert prov["target_ceiling_m"] == pytest.approx(self._H_ATM_TOP, abs=0.0)
        assert prov["target_altitude_served_m"] == pytest.approx(self._H_ATM_TOP, abs=0.0)
        assert "vacuum" in prov["exo_target_vacuum_clamp"]

    # -- the partial-column arm: still refused ---------------------------

    def test_partial_column_family_with_an_exo_target_is_refused(self, params) -> None:  # type: ignore[no-untyped-def]
        """The 10 km ladder never measured the column top — Rule 17 refusal."""
        with pytest.raises(ParameterBoundsError) as exc:
            evaluate_uplooking_topology(
                _family(companion=_simple()), _WL, self._exo_los(400_000.0), params
            )
        message = str(exc.value)
        assert "at or above h_atm_top" in message
        assert "interpolated run family" in message
        assert exc.value.context["h_tgt"] == pytest.approx(400_000.0, abs=0.0)
        assert exc.value.context["h_atm_top"] == pytest.approx(self._H_ATM_TOP, abs=0.0)
        assert exc.value.context["family_target_ceiling_m"] == pytest.approx(10_000.0, abs=0.0)

    def test_the_refusal_names_the_families_that_do_serve_it(self, params) -> None:  # type: ignore[no-untyped-def]
        """Rule 15: the way through is in the message, not in a doc."""
        with pytest.raises(ParameterBoundsError) as exc:
            evaluate_uplooking_topology(_family(companion=_simple()), _WL, self._exo_los(), params)
        message = str(exc.value)
        assert "midlat_summer_sst_column_fan" in message
        assert "midlat_summer_uplooking_sensor_ladder" in message

    def test_a_sub_exo_target_past_the_top_rung_still_refuses_on_coverage(self, params) -> None:  # type: ignore[no-untyped-def]
        """The clamp is gated at ``h_atm_top`` — it is not a general hull escape.

        A 50 km target through the 10 km ladder is 40 km of real, unmeasured
        atmosphere. It must keep failing on the family's own hull check, not
        get clamped to the top rung (Rule 17 — no extrapolation).
        """
        from radiant.atmosphere.errors import AtmosphereValidationError

        with (
            pytest.warns(UserWarning, match="TWO atmosphere models"),
            pytest.raises(AtmosphereValidationError, match="outside the available range"),
        ):
            evaluate_uplooking_topology(
                _family(companion=_simple()), _WL, self._exo_los(50_000.0), params
            )

    def test_guard_is_silent_on_the_shipped_ladder_geometry(self, params) -> None:  # type: ignore[no-untyped-def]
        """Behaviour-preserving: an endo target on a family evaluates as before."""
        products = evaluate_uplooking_topology(
            _family(companion=_simple()), _WL, _los(h_tgt=10_000.0), params
        )
        assert products.quantities.tau_up[0] == pytest.approx(_TAU_TOP, rel=1e-12)

    # -- the tripwire ----------------------------------------------------

    def test_every_shipped_uplooking_family_is_below_the_top_or_is_exact_there(
        self,
        params,  # type: ignore[no-untyped-def]
    ) -> None:
        """Every bundled up-looking family takes one arm of the guard, correctly.

        The invariant, asserted against the committed node sets rather than
        against the catalogue's prose:

        * a family whose target ceiling is **below** ``h_atm_top`` refuses an
          exo target;
        * a family that **reaches** ``h_atm_top`` serves one, and the vacuum
          identity holds on its real data — the composed products at the
          column top and at 400 km are bit-identical.

        This fails for a future family that reaches the top *without* the
        identity holding, which is the case the old data-shaped guard could
        not see. The synthetic-rung versions of the same two anchors are
        ``test_every_exo_altitude_gives_bit_identical_products`` and
        ``test_partial_column_family_with_an_exo_target_is_refused`` above.
        """
        from radiant.atmosphere.interpolation_coverage import (
            BUNDLED_ATMOSPHERES_DIR,
            BUNDLED_FAMILIES,
        )
        from radiant.atmosphere.protocol import H_ATM_TOP_M

        up_families = [f for f in BUNDLED_FAMILIES if f.los_direction == "up"]
        assert up_families, "no shipped up-looking family found — fixture drift"
        for fam in up_families:
            nodes = _shipped_nodes(BUNDLED_ATMOSPHERES_DIR / fam.name)
            ceiling = max(float(g["target_altitude_m"]) for g in nodes)
            # Query the family at a geometry it can serve, derived from its own
            # nodes: its lowest rendered observer and lowest rendered zenith.
            h_sensor = min(float(g["sensor_altitude_m"]) for g in nodes)
            zeta = min(float(g["path_zenith_rad"]) for g in nodes)
            model = _load_shipped_uplooking_family(
                BUNDLED_ATMOSPHERES_DIR / fam.name,
                axes=fam.interpolation_axes.split(","),
                companion=_simple(),
            )
            wl = model.wavelength_um[::1500]
            exo_los = _column_los(h_sensor, zeta, 400_000.0)

            if ceiling < H_ATM_TOP_M:
                with pytest.raises(ParameterBoundsError, match="at or above h_atm_top"):
                    evaluate_uplooking_topology(model, wl, exo_los, params)
                continue

            with pytest.warns(UserWarning):
                at_top = evaluate_uplooking_topology(
                    model, wl, _column_los(h_sensor, zeta, H_ATM_TOP_M), params
                )
                exo = evaluate_uplooking_topology(model, wl, exo_los, params)
            for field in _SPECTRAL_FIELDS:
                np.testing.assert_array_equal(
                    np.asarray(getattr(exo.quantities, field)),
                    np.asarray(getattr(at_top.quantities, field)),
                    err_msg=(
                        f"{fam.name} reaches h_atm_top but its {field} moves with an "
                        "exo target altitude — the vacuum identity the guard now "
                        "relies on does not hold for it"
                    ),
                )

    def test_simple_backend_keeps_the_exo_vacuum_identity(self, params) -> None:  # type: ignore[no-untyped-def]
        """``model='simple'`` has no column backend, so the guard never applies."""
        products = evaluate_uplooking_topology(_simple(), _WL, self._exo_los(), params)
        np.testing.assert_array_equal(products.quantities.E_sky_thermal, np.zeros_like(_WL))
        np.testing.assert_array_equal(products.quantities.E_sky_scattered, np.zeros_like(_WL))
