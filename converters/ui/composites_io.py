#!/usr/bin/env python3
"""Read and write composites.yaml without destroying its comments.

Same reasoning as converters/schedule/ui_yaml_io.py: the file's comments record
decisions the data cannot ("Fares v2 on purpose", "provisional, confirm against
the sheet"), and a naive load-then-dump would delete them. Writes go through
ruamel's round-trip mode and replace only the entries that changed.

One difference from the annotations file: a composite carries most of its prose
as data — `note`, `compute`, `notes` are schema fields — so rewriting one entry
loses much less than it would there. What survives regardless: the file header,
the section banner above each composite, and every untouched entry.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import SingleQuotedScalarString
from ruamel.yaml.tokens import CommentToken

# Whether a scalar is quoted follows the *key*, not the value. Deciding by
# value would leave a label of 'Code' bare while quoting 'Route code', which is
# both inconsistent and not how the file is written by hand.
IDENTIFIER_KEYS = frozenset({
    "name", "entity", "cardinality", "mode", "key", "source", "composite",
    "freshness",
})
# Sequence items that are identifiers rather than prose.
IDENTIFIER_SEQUENCES = frozenset({"sources", "from", "blocks"})

SECTIONS = ("derived_sources", "composites", "views")


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096  # never fold a long note
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def _scalar(value: Any, bare: bool) -> Any:
    if isinstance(value, str) and not bare:
        return SingleQuotedScalarString(value)
    return value


def _convert(value: Any, key: str = "", flow: bool = False) -> Any:
    if isinstance(value, dict):
        out = CommentedMap()
        for k, v in value.items():
            # i18n entries are written inline in the hand-authored file:
            #   es: {label: 'Código'}
            out[k] = _convert(v, k, flow or (k in ("es", "en", "pt") and len(v or {}) == 1))
        if flow and value:
            out.fa.set_flow_style()
        return out
    if isinstance(value, list):
        return CommentedSeq(_convert(v, key) for v in value)
    return _scalar(value, key in IDENTIFIER_KEYS or key in IDENTIFIER_SEQUENCES)


def _ordered(entry: dict, keys: tuple[str, ...]) -> CommentedMap:
    """Emit in the schema's own property order, then anything unexpected."""
    out = CommentedMap()
    for key in list(keys) + [k for k in entry if k not in keys]:
        if key in entry and entry[key] not in (None, "", {}, []):
            out[key] = _convert(entry[key], key)
    return out


def _tail(node: Any) -> tuple[Any, Any, int] | None:
    """The (container, key, slot) whose value ends a subtree, walking bottom-right.

    A banner like `# ---- RouteMap ----` belongs to the entry it introduces, but
    ruamel attaches it to the *last scalar of the previous entry*, which sits
    several levels down. This is where that comment lives.

    The slot differs by container: ruamel files a mapping value's trailing
    comment at index 2 of its entry, and a sequence item's at index 0.
    """
    if isinstance(node, CommentedSeq) and len(node):
        return _tail(node[-1]) or (node, len(node) - 1, 0)
    if not hasattr(node, "items") or not len(node):
        return None
    last = list(node.keys())[-1]
    return _tail(node[last]) or (node, last, 2)


def _detach_trailing(node: Any) -> Any:
    """Remove and return the comment block trailing a subtree's last value."""
    if (tail := _tail(node)) is None:
        return None
    container, key, slot = tail
    item = container.ca.items.get(key)
    if not item or item[slot] is None:
        return None
    token = item[slot]
    # Leave a bare newline so entries stay separated by a blank line.
    item[slot] = CommentToken("\n\n", token.start_mark)
    return token


def _attach_trailing(node: Any, token: Any) -> None:
    """Put a comment block back after a subtree's last value."""
    if (tail := _tail(node)) is None:
        return
    container, key, slot = tail
    container.ca.items.setdefault(key, [None, None, None, None])[slot] = token


def _attach_leading(section: CommentedMap, key: str, token: Any) -> None:
    """Put a comment block ahead of a key.

    One leading newline is dropped: as a trailing comment it terminated the
    previous line, as a leading one it would render as an extra blank.
    """
    token.value = token.value[1:] if token.value.startswith("\n\n") else token.value
    section.ca.items.setdefault(key, [None, None, None, None])[1] = [token]


def _insert(section: CommentedMap, key: str, value: CommentedMap) -> None:
    """Append a new entry, keeping any banner with the entry it introduces."""
    keys = list(section.keys())
    section[key] = value
    if not keys:
        return
    # Appending at the end cannot strand a banner: there is no following key.
    # Only re-anchor when something was already trailing the previous entry.
    header = _detach_trailing(section[keys[-1]])
    if header is not None:
        _attach_leading(section, key, header)


def _section_lead(document: CommentedMap, name: str) -> list | None:
    """The comment slot holding the banner that introduces a section's first key.

    That banner sits after `composites:` and before the first entry, so ruamel
    files it on the parent key rather than on either entry.
    """
    item = document.ca.items.get(name)
    return item[3] if item and len(item) > 3 else None


def _delete(section: CommentedMap, key: str,
            document: CommentedMap | None = None, name: str = "") -> None:
    """Remove an entry along with the banner that introduces *it*.

    Both banners around an entry are stored away from it: the one introducing
    it trails the previous entry, and the one introducing the next entry trails
    this one. Deleting the key alone would therefore drop the wrong banner and
    leave `# ---- RouteFares ----` sitting above RouteAlerts.
    """
    keys = list(section.keys())
    index = keys.index(key)
    previous = keys[index - 1] if index else None
    following = keys[index + 1] if index + 1 < len(keys) else None

    introduces_next = _detach_trailing(section[key])
    if previous is not None:
        _detach_trailing(section[previous])  # the banner that introduced `key`

    del section[key]

    if previous is not None:
        if introduces_next is not None:
            _attach_trailing(section[previous], introduces_next)
        return

    # Deleting the first entry: its banner lives on the parent key, so it has
    # to be replaced there rather than removed with the entry.
    lead = _section_lead(document, name) if document is not None else None
    if lead is None:
        if introduces_next is not None and following is not None:
            _attach_leading(section, following, introduces_next)
        return
    keep = lead[:1] if lead and lead[0].value == "\n" else []
    if introduces_next is None or following is None:
        lead[:] = keep
    else:
        introduces_next.value = (introduces_next.value[1:]
                                 if introduces_next.value.startswith("\n\n")
                                 else introduces_next.value)
        lead[:] = keep + [introduces_next]


def load(path: Path) -> CommentedMap:
    return _yaml().load(path.read_text(encoding="utf-8"))


def apply_changes(document: CommentedMap, changes: dict[str, dict],
                  order: dict[str, tuple[str, ...]]) -> dict[str, int]:
    """Merge `{section: {name: entry | None}}` into the document in place.

    A value of None deletes the entry. `order` gives each section's key order,
    which comes from the schema rather than being restated here.
    """
    counts = {"added": 0, "updated": 0, "removed": 0}

    for name in SECTIONS:
        edits = changes.get(name) or {}
        if not edits:
            continue
        section = document.get(name)
        if section is None:
            section = document[name] = CommentedMap()

        for key, entry in edits.items():
            if entry is None:
                if key in section:
                    _delete(section, key, document, name)
                    counts["removed"] += 1
            elif key in section:
                # The banner introducing the *next* entry trails this one's
                # last scalar. Replacing the value would take it with it.
                trailing = _detach_trailing(section[key])
                section[key] = _ordered(entry, order.get(name, ()))
                if trailing is not None:
                    _attach_trailing(section[key], trailing)
                counts["updated"] += 1
            else:
                _insert(section, key, _ordered(entry, order.get(name, ())))
                counts["added"] += 1

        # An emptied optional section is removed rather than left as `{}`.
        if not len(section) and name == "derived_sources":
            del document[name]

    return counts


def dump(document: CommentedMap, path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        _yaml().dump(document, handle)
