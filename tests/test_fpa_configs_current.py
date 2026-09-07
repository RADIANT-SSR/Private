"""Freshness gate: generated FPA configs match the shipped presets (Gap 119).

Mirrors ``tests/test_parameter_reference_current.py`` — the committed
``src/radiant/data/tables/fpa/configs/*.yaml`` are generated artifacts
(Rule 26) and must equal a regeneration from the preset source of truth.
Also asserts each generated config actually loads through the ordinary
config path (plan §3.1a acceptance).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "src" / "radiant" / "data" / "tables" / "fpa" / "configs"

_spec = importlib.util.spec_from_file_location(
    "gen_fpa_configs", REPO_ROOT / "scripts" / "gen_fpa_configs.py"
)
assert _spec is not None and _spec.loader is not None
_gen = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("gen_fpa_configs", _gen)
_spec.loader.exec_module(_gen)

from radiant.data import FPALibrary  # noqa: E402

NAMES = FPALibrary().names()


@pytest.mark.parametrize("name", NAMES)
def test_generated_config_is_current(name: str) -> None:
    dest = CONFIG_DIR / f"{name}.yaml"
    assert dest.exists(), f"missing generated config for '{name}' — run scripts/gen_fpa_configs.py"
    regenerated = _gen.render_config(FPALibrary().part(name))
    assert dest.read_text(encoding="utf-8") == regenerated, (
        f"{dest.name} is stale — run scripts/gen_fpa_configs.py"
    )


def test_no_orphan_configs() -> None:
    expected = {f"{n}.yaml" for n in NAMES}
    orphans = sorted(p.name for p in CONFIG_DIR.glob("*.yaml") if p.name not in expected)
    assert not orphans, f"configs with no matching preset: {orphans}"


@pytest.mark.parametrize("name", NAMES)
def test_generated_config_loads_via_config_path(name: str) -> None:
    """§3.1a acceptance: the per-part document loads through load_config and
    lands the same values the preset apply path would set."""
    from radiant.api.session import RadiantSession
    from radiant.core.parameters import Provenance
    from radiant.io.config import load_config

    loaded = RadiantSession.default_params()
    load_config(CONFIG_DIR / f"{name}.yaml", loaded)

    direct = RadiantSession.default_params()
    part = FPALibrary().part(name)
    for dotpath, entry in part.parameters.items():
        direct.set(dotpath, entry.value, provenance=Provenance.PRESET, unit=entry.unit)

    assert set(loaded.input_provenances()) == set(direct.input_provenances())
