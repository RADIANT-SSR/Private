"""Phase 0 smoke test — verify package and required RADIANT imports resolve."""


def test_radiant_geometry_imports() -> None:
    from radiant.core.geometry import (  # noqa: F401
        ObserverGeometry,
        SceneGeometry,
        TargetGeometry,
    )


def test_radiant_sphere_import() -> None:
    from radiant.source.shapes.sphere import Sphere  # noqa: F401


def test_geometry_gui_app_import() -> None:
    from dev_tools.geometry_gui.app.main import app

    assert app is not None
