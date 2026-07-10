"""Hierarchy contract for RADIANT exception classes (CU-NEW-01).

Pins three things that the rest of the codebase + downstream user code
relies on:

1. Every concrete RADIANT exception inherits from
   :class:`radiant.core.exceptions.RadiantError`, so user code can do
   ``except RadiantError`` to catch every framework-defined error.
2. The back-compat carve-outs documented in CLAUDE.md §15 hold —
   ``ParameterBoundsError`` is still a ``ValueError``,
   ``ModtranUnavailableError`` is still a ``RuntimeError``, etc., so
   existing ``pytest.raises(ValueError, ...)`` patterns keep working.
3. ``RadiantError`` is re-exported at the top level (``from radiant
   import RadiantError``) and from :mod:`radiant.core.exceptions`.

Lives in [tests/](../tests/) (not under any package boundary) because the
contract crosses every physics subpackage: a test in ``radiant.core.tests``
that imports from ``radiant.optics`` / ``radiant.atmosphere`` / ``radiant.io``
would violate the "core has no radiant imports" import-linter contract.

Reference:
[RADIANT_Master_Architecture.md §C12/§7.4](../docs/RADIANT_Master_Architecture.md),
[RADIANT_Testing_Validation.md §8.5](../docs/RADIANT_Testing_Validation.md),
[CLAUDE.md §15](../CLAUDE.md).
"""

from __future__ import annotations

import pytest


@pytest.mark.level0
class TestRadiantErrorHierarchy:
    """Every RADIANT-defined exception is-a RadiantError."""

    def test_radiant_error_imports_from_core(self) -> None:
        from radiant.core.exceptions import RadiantError

        assert issubclass(RadiantError, Exception)

    def test_radiant_error_re_exported_at_top_level(self) -> None:
        import radiant
        from radiant.core.exceptions import RadiantError as RadiantError_core

        assert radiant.RadiantError is RadiantError_core
        assert "RadiantError" in radiant.__all__

    def test_parameter_bounds_error_is_radiant_error(self) -> None:
        from radiant.core.exceptions import RadiantError
        from radiant.core.parameters import ParameterBoundsError

        assert issubclass(ParameterBoundsError, RadiantError)
        assert issubclass(ParameterBoundsError, ValueError)  # back-compat

    def test_kirchhoff_violation_error_is_radiant_error(self) -> None:
        from radiant.core.exceptions import RadiantError
        from radiant.optics.element import KirchhoffViolationError

        assert issubclass(KirchhoffViolationError, RadiantError)
        assert issubclass(KirchhoffViolationError, ValueError)  # back-compat

    def test_modtran_unavailable_error_is_radiant_error(self) -> None:
        from radiant.atmosphere.modtran import ModtranUnavailableError
        from radiant.core.exceptions import RadiantError

        assert issubclass(ModtranUnavailableError, RadiantError)
        assert issubclass(ModtranUnavailableError, RuntimeError)  # back-compat

    def test_tape7_parse_error_is_radiant_error(self) -> None:
        from radiant.atmosphere.modtran import Tape7ParseError
        from radiant.core.exceptions import RadiantError

        assert issubclass(Tape7ParseError, RadiantError)
        assert issubclass(Tape7ParseError, ValueError)  # back-compat

    def test_config_error_is_radiant_error(self) -> None:
        from radiant.core.exceptions import RadiantError
        from radiant.io.config import ConfigError

        assert issubclass(ConfigError, RadiantError)

    def test_element_config_error_is_radiant_error(self) -> None:
        from radiant.core.exceptions import RadiantError
        from radiant.io.element_config import ElementConfigError

        assert issubclass(ElementConfigError, RadiantError)
        assert issubclass(ElementConfigError, ValueError)  # back-compat


@pytest.mark.level0
class TestRadiantErrorAsCatchAll:
    """User code catching RadiantError catches every framework error."""

    def test_caught_by_radiant_error(self) -> None:
        from radiant.core.parameters import ParameterBoundsError

        with pytest.raises(Exception) as exc_info:
            raise ParameterBoundsError(
                what="x = -1 is out of bounds",
                why="x must be positive",
                action="set x > 0",
                context={"param": "x", "value": -1},
            )

        from radiant import RadiantError

        assert isinstance(exc_info.value, RadiantError)

    def test_back_compat_value_error_pattern(self) -> None:
        """pytest.raises(ValueError, ...) still catches migrated exceptions."""
        from radiant.core.parameters import ParameterBoundsError

        with pytest.raises(ValueError, match="out of bounds"):
            raise ParameterBoundsError(
                what="x = -1 is out of bounds",
                why="x must be positive",
                action="set x > 0",
            )


@pytest.mark.level0
class TestStageErrorClasses:
    """CU-043: every stage package exposes RadiantError-derived error types."""

    STAGE_CLASSES = [
        ("radiant.core.exceptions", "CoreValidationError", ValueError),
        ("radiant.core.exceptions", "CoreStateError", RuntimeError),
        ("radiant.source.errors", "SourceValidationError", ValueError),
        ("radiant.atmosphere.errors", "AtmosphereValidationError", ValueError),
        ("radiant.atmosphere.errors", "AtmosphereStateError", RuntimeError),
        ("radiant.optics.errors", "OpticsValidationError", ValueError),
        ("radiant.platform.errors", "PlatformValidationError", ValueError),
        (
            "radiant.spectral_integration.errors",
            "SpectralIntegrationValidationError",
            ValueError,
        ),
        (
            "radiant.spectral_integration.errors",
            "SpectralIntegrationStateError",
            RuntimeError,
        ),
        ("radiant.detector.errors", "DetectorValidationError", ValueError),
        ("radiant.readout.errors", "ReadoutValidationError", ValueError),
        ("radiant.performance.errors", "PerformanceValidationError", ValueError),
        ("radiant.api.errors", "ApiValidationError", ValueError),
    ]

    @pytest.mark.parametrize("module,name,builtin", STAGE_CLASSES)
    def test_class_hierarchy(self, module: str, name: str, builtin: type) -> None:
        """Each class derives RadiantError AND its back-compat built-in."""
        import importlib

        from radiant import RadiantError

        cls = getattr(importlib.import_module(module), name)
        assert issubclass(cls, RadiantError)
        assert issubclass(cls, builtin)

    def test_live_raise_caught_as_radiant_error(self) -> None:
        """A migrated raise site is caught by `except RadiantError`."""
        from radiant import RadiantError
        from radiant.core.blackbody import planck_spectral_radiance

        with pytest.raises(RadiantError):
            planck_spectral_radiance(4.0, -10.0)  # negative temperature

    def test_live_raise_still_caught_as_value_error(self) -> None:
        """...and still by the historical `except ValueError` pattern."""
        from radiant.core.blackbody import planck_spectral_radiance

        with pytest.raises(ValueError):
            planck_spectral_radiance(4.0, -10.0)


@pytest.mark.level0
class TestNoBareBuiltinRaises:
    """CU-043 regression guard: no bare ValueError/RuntimeError raises in
    core or physics modules — only RadiantError subclasses."""

    def test_source_tree_is_clean(self) -> None:
        import re
        from pathlib import Path

        import radiant

        root = Path(radiant.__file__).parent
        pattern = re.compile(r"raise (ValueError|RuntimeError)\(")
        offenders: list[str] = []
        for path in root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            for i, line in enumerate(path.read_text().split("\n"), 1):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(root)}:{i}")
        assert not offenders, (
            "Bare built-in raises found (use a RadiantError subclass, "
            f"Rule 15 / CU-043): {offenders}"
        )
