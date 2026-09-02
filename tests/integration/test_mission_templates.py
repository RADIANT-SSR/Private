"""Mission templates are runnable + representative — the truth bar as CI.

The welcome screen (GUI) offers every YAML under ``examples/templates/`` as a
one-click starting scenario (owner-confirmed brief, 2026-08-31). The templates'
contract, enforced here so it cannot rot:

* every template **loads and evaluates cleanly** — no error, no chain warning
  (a template that opens with a warning banner teaches noise);
* every template carries complete ``_radiant.template`` metadata — display
  name, blurb, specs line, and a 3–5 item ``tune_next`` list;
* every ``tune_next`` entry is a real schema dot-path (a renamed parameter
  breaks the guidance loudly, not silently);
* the derived radiometric regime matches the declared ``source.scene_type``
  (a template must not open with the declared-vs-derived mismatch warning);
* the headline SNR is finite and positive (a representative scenario, not a
  degenerate one).

Only metadata-carrying files are mission templates; the Phase-2E band/platform
configs sharing the directory are the source-inferrer golden corpus (CU-339
tracks their relocation to a fixtures home) and are exempt from this bar —
the welcome screen's discovery filter already excludes them.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from radiant.api import Sensor
from radiant.io.config import read_radiant_meta

_REPO = Path(__file__).resolve()
while not (_REPO / "pyproject.toml").exists():
    _REPO = _REPO.parent
_TEMPLATES = _REPO / "examples" / "templates"


def _is_mission_template(path: Path) -> bool:
    return bool(read_radiant_meta(path).get("template"))


TEMPLATE_PATHS = sorted(p for p in _TEMPLATES.glob("*.yaml") if _is_mission_template(p))

# The welcome screen needs a non-degenerate card set; the brief ships six.
_MIN_TEMPLATES = 6  # the brief ships six


def test_the_template_set_exists() -> None:
    assert len(TEMPLATE_PATHS) >= _MIN_TEMPLATES, (
        f"expected at least {_MIN_TEMPLATES} mission templates in {_TEMPLATES}"
    )


@pytest.mark.parametrize("path", TEMPLATE_PATHS, ids=lambda p: p.stem)
class TestEveryTemplate:
    def test_metadata_is_complete(self, path: Path) -> None:
        meta = read_radiant_meta(path).get("template", {})
        assert isinstance(meta, dict) and meta, f"{path.name}: missing _radiant.template block"
        for key in ("name", "blurb", "specs", "tune_next"):
            assert meta.get(key), f"{path.name}: _radiant.template.{key} missing/empty"
        tune_next = meta["tune_next"]
        assert isinstance(tune_next, list) and 3 <= len(tune_next) <= 5, (
            f"{path.name}: tune_next must list 3–5 dot-paths, got {tune_next!r}"
        )

    def test_tune_next_names_real_parameters(self, path: Path) -> None:
        sensor = Sensor.load(path)
        defs = sensor.parameter_defs()
        for dotpath in read_radiant_meta(path)["template"]["tune_next"]:
            assert dotpath in defs, f"{path.name}: tune_next names unknown parameter {dotpath!r}"

    def test_loads_and_evaluates_clean_with_matching_regime(self, path: Path) -> None:
        sensor = Sensor.load(path)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = sensor.evaluate()
        assert not caught, (
            f"{path.name}: a mission template must evaluate warning-free; got: "
            + "; ".join(str(w.message)[:100] for w in caught)
        )
        snr = result.snr()
        assert snr > 0.0 and snr == snr, f"{path.name}: degenerate SNR {snr!r}"
        declared = sensor.get_input("source.scene_type")
        if declared and declared != "auto":
            derived = result.stage_outputs["optics"]["regime"].value
            assert derived == declared, (
                f"{path.name}: declared scene_type={declared!r} but the chain derived "
                f"{derived!r} — the template would open with a mismatch warning"
            )
