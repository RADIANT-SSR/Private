"""The session document as YAML text — serialize and re-parse (arch doc §4.2f).

The GUI's *document* is a :class:`~radiant.api.config_set.ConfigurationSet`
(§4.2b), and exactly one question decides how that document is written: **is this
session a study?** A plain single-configuration session with nothing configured is
written as ``Sensor.to_yaml`` output — byte for byte the format the app has always
written, with no ``configurations:`` section — and a study is written as
``ConfigurationSet.to_yaml``, the shared body plus that section.

That decision is made **here, once**, so the three surfaces that render or re-read
the document (``File → Save`` / ``Export YAML``, the right rail's *Edit Config
(YAML)* modal, and the scripting console's Refresh) cannot drift apart:

* :func:`is_study` — the predicate;
* :func:`serialize_document` — the document's YAML text;
* :func:`load_document_from_text` — the inverse, through the public loader.

Both directions round-trip: a study's text carries its ``configurations:`` section
and reloads as the full set; a plain session's text carries none and reloads as the
degenerate one-configuration set. Editing a study's text to *remove* the section is
therefore a legal edit that collapses the study to a plain session — the analyst's
call, made explicit by what they typed, not silently by the GUI.

Qt-free by design (no widget imports), so every rule above is unit-tested without a
window. This module holds no reader or writer of its own: every call below is one
public ``radiant.api`` call (R-API).
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from radiant.api.config_set import ConfigurationSet

logger = logging.getLogger(__name__)


def is_study(config_set: ConfigurationSet | None) -> bool:
    """Whether *config_set* is a **study** rather than a plain single-model session.

    A study is any set that carries more than one configuration *or* any configured
    parameter. The second half matters: a one-configuration set with a configured
    dot-path is still a study document (its ``configurations:`` section holds a
    one-element column that would be lost if it were written as a bare sensor).

    ``None`` — an empty window — is not a study.
    """
    if config_set is None:
        return False
    return len(config_set) > 1 or bool(config_set.configured())


def serialize_document(config_set: ConfigurationSet) -> str:
    """Return *config_set* serialized as the YAML document the session would save.

    One public call either way: ``Sensor.to_yaml(scope="inputs")`` for a plain
    session (unchanged file format, no section) and ``ConfigurationSet.to_yaml()``
    for a study (shared body + ``configurations:``). The text round-trips through
    :func:`load_document_from_text` exactly, which is the contract the YAML editor's
    Apply and the Export surface both rely on.
    """
    if is_study(config_set):
        return config_set.to_yaml()
    return config_set.base.to_yaml(scope="inputs")


def load_document_from_text(yaml_text: str) -> ConfigurationSet:
    """Parse *yaml_text* into a fresh :class:`ConfigurationSet` via the public loader.

    ``ConfigurationSet.load`` reads **both** document kinds and is the API surface
    that decides which is which — a section-bearing text becomes the full study, a
    plain one becomes the degenerate one-configuration set. The GUI never sniffs the
    text itself.

    The loader takes a path only (there is no string-load surface — Gap 88), so the
    text is written to a throwaway temp file and read back. Any parse or validation
    failure propagates to the caller with its full what/why/action — the live
    document is never touched here (validate-before-commit, §4.1).
    """
    from radiant.api.config_set import ConfigurationSet

    fd, tmp_path = tempfile.mkstemp(suffix=".yaml", prefix="radiant_gui_yaml_edit_")
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(yaml_text)
        return ConfigurationSet.load(tmp_path)
    finally:
        # Best-effort cleanup; a failed unlink is benign (the OS reclaims the temp
        # dir) but it is logged, never silently swallowed (Rule 17).
        try:
            os.unlink(tmp_path)
        except OSError as exc:  # pragma: no cover - benign
            logger.debug("Could not remove temp YAML file %s: %s", tmp_path, exc)


__all__ = ["is_study", "load_document_from_text", "serialize_document"]
