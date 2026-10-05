"""CU-371: product strings carry no process language (audit F-52/F-53, II-003, II-015).

Scope (owner ruling 2026-10-04, CU-395): ``_schema.py`` modules **are** scanned, and in
them exactly one field is read — ``ParameterDef.description``. That string reaches the
operator twice, as a GUI tooltip and through the generated ``parameter_reference.md``
that ships inside the Technical Reference, so it is product copy by this rule's own
test. Nothing else in a schema module is: ``default_justification`` surfaces nowhere,
and the module comments that sit beside these definitions are developer-facing like
every other comment.

The finding that prompted this ruling reported "21 descriptions across 7 modules". The
real number was **three**, because the measuring grep counted the module comments around
the definitions as well as the definitions themselves. Worth stating because the
over-count is what made this look like a scope decision rather than an afternoon.

Operators read the GUI's notes, tooltips, refusals and warnings in every session, and
the manuals quote them; a string that says "Gap 65", "ADR-0010 D-E", "v1-minimal
(owner-ratified …)" or "Rule 8" is talking to the project's tracking system, not to
the operator. This test walks the **string literals** (never docstrings — those are
for developers) of every GUI module and of the library modules whose messages the
audit named, and fails on the first process token. It failed on the pre-fix code with
33 GUI hits and 19 library hits.

Qt-free: a source scan, so it runs anywhere the package is importable.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import radiant

_SRC = Path(radiant.__file__).resolve().parent

#: Tracking-system vocabulary that must not reach an operator.
_TOKEN = re.compile(
    r"\b(?:Gap|CU|ADR)[- ]?\d"  # Gap 65, CU-122, ADR-0010
    r"|owner[- ]ratified"
    r"|v1[-.]minimal|\bv1\.x\b|post-v1"
    r"|\bRule \d|\bplan §|\bPhase [A-Z0-9]\b"
)

#: Physics vocabulary that collides with the process tokens. "Rule 07" and "Rule 22"
#: are Tennant's empirical HgCdTe dark-current laws — literature model names an operator
#: needs to see, not RADIANT's architectural rules — and they live only in the two
#: modules that implement them. Exempted there and nowhere else.
_PHYSICS_RULE_MODULES = ("detector/rule07.py", "detector/rule22.py")
_PHYSICS_RULE_TOKENS = re.compile(r"\bRule (?:07|22)\b")

#: The stylesheet's string is CSS whose comments cite the design history; it is never
#: rendered as text.
_EXCLUDED = ("gui/themes/stylesheet.py",)


def _gui_files() -> list[Path]:
    """Every GUI module. Its strings are operator-facing by construction, so all are scanned."""
    return sorted(
        p
        for p in (_SRC / "gui").rglob("*.py")
        if "/tests/" not in p.as_posix() and not p.as_posix().endswith(_EXCLUDED)
    )


def _library_files() -> list[Path]:
    """Every non-GUI library module — selected by existing, not by a hand-kept list.

    The original six-module list was the audit's sample, and a hand-kept list is exactly
    the kind that goes stale: CU-391's refusal in ``geometry/stage.py`` shipped "(CU-391)"
    in its ``why`` text unflagged, while the identical mistake in the listed
    ``api/config_set.py`` failed immediately. The scan now reaches every module —
    ``_schema.py`` included since the 2026-10-04 ruling — and narrows instead on *which
    strings* it reads (see :func:`process_language_hits`).
    """
    return sorted(
        p
        for p in _SRC.rglob("*.py")
        if "/tests/" not in p.as_posix() and not p.as_posix().startswith((_SRC / "gui").as_posix())
    )


def _scanned_files() -> list[Path]:
    return _gui_files() + _library_files()


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr):
                value = getattr(body[0], "value", None)
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    ids.add(id(value))
    return ids


#: A call whose string arguments an operator reads: ``warnings.warn(...)`` and any
#: exception constructor. Used to pick the user-facing strings out of a library module,
#: whose other literals (log lines, dict keys, SpectralData ``source=`` labels) are
#: developer-facing and may cite whatever they like.
_USER_FACING_CALL = re.compile(r"(?:Error|Violation)$")


def _schema_description_ids(tree: ast.AST) -> set[int]:
    """Only ``description=`` values in a ``_schema.py``.

    A schema module is almost entirely module-level assignment, so the general library
    selector below would sweep in every string it contains — ``default_justification``,
    which surfaces nowhere, and the prose around each definition. One field reaches the
    operator (tooltip + generated parameter reference), so one field is scanned.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.keyword) and node.arg == "description"):
            continue
        for sub in ast.walk(node.value):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                ids.add(id(sub))
    return ids


def _user_facing_string_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    # Module-level message tables: an error whose text lives in a constant
    # (``REMOVED_PARAMETERS``, ``_REMOVED_ENTRY_KEYS``) is raised elsewhere, so the
    # call-site rule below cannot see it.
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    ids.add(id(sub))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if not (name == "warn" or _USER_FACING_CALL.search(name or "")):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                ids.add(id(sub))
    return ids


def process_language_hits(path: Path) -> list[str]:
    """``"<file>:<line>: <excerpt>"`` for every operator-facing literal with a process token.

    In a **GUI** module every literal is read, as it always was. In a **library** module
    only the strings handed to a warning or an exception are — the rest never reach an
    operator, and holding them to this rule would be noise, not a contract. In a
    ``_schema.py`` only ``ParameterDef.description`` is read, for the same reason in the
    other direction: it is the one field there that an operator sees.
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    docstrings = _docstring_ids(tree)
    try:
        rel = path.relative_to(_SRC).as_posix()
    except ValueError:  # a path outside the package — the unit tests' synthetic modules
        rel = path.name
    is_gui = rel.startswith("gui/")
    if is_gui:
        wanted = None
    elif path.name == "_schema.py":
        wanted = _schema_description_ids(tree)
    else:
        wanted = _user_facing_string_ids(tree)
    physics_exempt = rel in _PHYSICS_RULE_MODULES
    hits: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in docstrings:
            continue
        if wanted is not None and id(node) not in wanted:
            continue
        text = _PHYSICS_RULE_TOKENS.sub("", node.value) if physics_exempt else node.value
        match = _TOKEN.search(text)
        if match:
            start = max(0, match.start() - 30)
            excerpt = text[start : match.end() + 20].replace("\n", " ")
            hits.append(f"{rel}:{node.lineno}: …{excerpt}…")
    return hits


def test_no_process_language_in_product_strings() -> None:
    hits = [hit for path in _scanned_files() for hit in process_language_hits(path)]
    assert not hits, "process language in product strings:\n  " + "\n  ".join(hits)


def test_scan_reaches_the_named_surfaces() -> None:
    """The scan covers the modules the audit named (a moved file must not silently drop out)."""
    names = {p.name for p in _scanned_files()}
    assert {"stage_views.py", "platform_inputs_form.py", "stage.py", "viewing_triangle.py"} <= names


def test_scan_reaches_every_library_module() -> None:
    """The hole this widening closed: a hand-kept file list went stale.

    CU-391 added a refusal to ``geometry/stage.py`` citing its own CU number, and the
    six-module list did not include that file, so the gate stayed silent while the same
    mistake in a listed module failed at once. Selection is now by existence.
    """
    scanned = {p.relative_to(_SRC).as_posix() for p in _scanned_files()}
    for rel in ("geometry/stage.py", "performance/stage.py", "source/_inferrer.py"):
        assert rel in scanned, f"{rel} is not scanned"


def test_library_developer_strings_are_not_policed(tmp_path: Path) -> None:
    """Only operator-facing strings in a library module count.

    A log line or a dict key may cite whatever it likes; holding every literal in 233
    physics modules to the product-copy rule would be noise, not a contract.
    """
    mod = tmp_path / "sample.py"
    mod.write_text(
        "import logging\n"
        "log = logging.getLogger(__name__)\n"
        "def f():\n"
        "    log.debug('placement follows Rule 17 here')\n"
        "    label = 'CU-123 internal'\n"
        "    return label\n",
        encoding="utf-8",
    )
    assert process_language_hits(mod) == []


def test_library_user_facing_strings_are_policed(tmp_path: Path) -> None:
    mod = tmp_path / "sample2.py"
    mod.write_text(
        "import warnings\n"
        "class ThingError(Exception):\n"
        "    pass\n"
        "def f():\n"
        "    warnings.warn('this is wrong (Rule 17)', UserWarning, stacklevel=2)\n"
        "def g():\n"
        "    raise ThingError('refused because of CU-391')\n",
        encoding="utf-8",
    )
    hits = process_language_hits(mod)
    assert len(hits) == 2, hits


def test_the_physics_rule_names_are_exempt_only_where_they_belong() -> None:
    """ "Rule 07"/"Rule 22" are Tennant's HgCdTe dark-current laws, not RADIANT rules.

    They are literature model names an operator needs, and the token regex cannot tell
    them from an architectural rule, so the two modules that implement them are exempt —
    for those two names only, and nowhere else.
    """
    for rel in _PHYSICS_RULE_MODULES:
        assert process_language_hits(_SRC / rel) == []
    # The exemption is name-scoped, not module-scoped: a real process token in the same
    # module is still caught.
    assert _PHYSICS_RULE_TOKENS.sub("", "fitted per Rule 07 (Rule 17 forbids it)")
    assert _TOKEN.search(_PHYSICS_RULE_TOKENS.sub("", "fitted per Rule 07 (Rule 17 forbids it)"))


class TestSchemaDescriptionsAreProductCopy:
    """CU-395, owner ruling 2026-10-04: a parameter description is read by an operator.

    It reaches them twice — as a GUI tooltip and through the generated
    ``parameter_reference.md`` bound into the Technical Reference — so it is held to the
    same rule as a refusal or a warning.
    """

    def test_a_description_citing_a_cleanup_unit_is_caught(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        module = tmp_path / "_schema.py"
        module.write_text(
            "FOO = ParameterDef(\n"
            "    name='x.y',\n"
            "    description='Speed of the thing (CU-391).',\n"
            ")\n",
            encoding="utf-8",
        )
        hits = process_language_hits(module)
        assert len(hits) == 1
        assert "CU-391" in hits[0]

    def test_other_schema_fields_are_not_scanned(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """``default_justification`` surfaces nowhere, so a citation there is fine.

        This is the narrowing that makes the rule hold: without it the module-level
        assignment branch would sweep in every string a schema file contains, and the
        rule would be noise rather than a contract.
        """
        module = tmp_path / "_schema.py"
        module.write_text(
            "FOO = ParameterDef(\n"
            "    name='x.y',\n"
            "    description='Speed of the thing.',\n"
            "    default_justification='Set to 0 by the ADR-0006 rule 2 convention.',\n"
            ")\n",
            encoding="utf-8",
        )
        assert process_language_hits(module) == []

    def test_the_shipped_parameter_reference_is_clean(self) -> None:
        """The artifact itself, not just its source — this is what readers get."""
        reference = (
            Path(__file__).resolve().parents[4] / "docs" / "guides" / "parameter_reference.md"
        )
        if not reference.is_file():  # pragma: no cover - a wheel-only checkout
            pytest.skip("generated parameter reference not present")
        assert not _TOKEN.search(reference.read_text(encoding="utf-8"))
