#!/usr/bin/env python3
"""Read and write schedule.ui.yaml without destroying its comments.

schedule.ui.yaml carries hand-written comments that record *why* a rule is a
warning rather than an error — the most valuable part of the file, and exactly
what a naive load-then-dump would silently delete. So writes go through
ruamel.yaml's round-trip mode, which keeps comments attached to the keys they
document, and only the entries that actually changed are replaced.

Comments written inside an annotation the editor rewrites are still lost; there
is nothing to attach them to once the block is replaced. Comments on every
untouched entry, on `regions`, and the file header all survive.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import SingleQuotedScalarString
from ruamel.yaml.tokens import CommentToken

# Values that read as identifiers stay unquoted; anything else is quoted, which
# matches how the file is written by hand.
BARE = re.compile(r"^[a-z][a-z0-9_.]*$")

# Emission order inside one annotation, mirroring the schema's property order.
ANNOTATION_KEYS = ("component", "group", "references", "validation", "i18n")


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096  # never fold long help strings
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def _scalar(value: Any) -> Any:
    if isinstance(value, str):
        return value if BARE.match(value) else SingleQuotedScalarString(value)
    return value


def _convert(value: Any) -> Any:
    """Turn a plain JSON value into ruamel nodes with the file's own style."""
    if isinstance(value, dict):
        out = CommentedMap()
        for k, v in value.items():
            out[k] = _convert(v)
        return out
    if isinstance(value, list):
        seq = CommentedSeq(_convert(v) for v in value)
        if len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
            seq.fa.set_flow_style()  # `range: [-90, 90]`
        return seq
    return _scalar(value)


def _ordered(annotation: dict) -> CommentedMap:
    out = CommentedMap()
    for key in ANNOTATION_KEYS:
        if key in annotation and annotation[key] not in (None, "", {}):
            out[key] = _convert(annotation[key])
    return out


def _table_of(key: str) -> str:
    return key.split(".", 1)[0]


def _insert_position(fields: CommentedMap, key: str) -> int:
    """Where a new key goes: after the last entry of its own table, else last.

    Existing keys are never reordered. Section header comments are attached to
    the first key of each block, so moving keys around would scramble them.
    """
    table = _table_of(key)
    last = None
    for index, existing in enumerate(fields.keys()):
        if _table_of(existing) == table:
            last = index
    return len(fields) if last is None else last + 1


def _detach_trailing(node: Any) -> Any:
    """Remove and return the comment block trailing a subtree's last value.

    A section header like `# ---- routes.txt ----` is not attached to the key it
    introduces. ruamel hangs it off the *last scalar of the previous entry*,
    which for these annotations is several levels down (i18n -> pt -> help). So
    finding it means walking to the bottom-right of the previous entry.
    """
    if not hasattr(node, "items") or not len(node):
        return None
    last = list(node.keys())[-1]
    if (found := _detach_trailing(node[last])) is not None:
        return found
    item = node.ca.items.get(last)
    if item and item[2] is not None:
        token = item[2]
        # Leave a bare newline behind so entries stay separated by a blank line.
        item[2] = CommentToken("\n\n", token.start_mark)
        return token
    return None


def _insert(fields: CommentedMap, position: int, key: str, value: CommentedMap) -> None:
    """Insert a key, keeping any section header with the block it introduces."""
    keys = list(fields.keys())
    header = None
    if 0 < position < len(keys):
        header = _detach_trailing(fields[keys[position - 1]])

    fields.insert(position, key, value)

    if header is not None:
        # Re-attach ahead of the following key. One leading newline is dropped:
        # as a trailing comment it terminated the previous line, as a leading
        # one it would render as an extra blank.
        header.value = header.value[1:] if header.value.startswith("\n\n") else header.value
        following = keys[position]
        fields.ca.items.setdefault(following, [None, None, None, None])[1] = [header]


def load(path: Path) -> CommentedMap:
    return _yaml().load(path.read_text(encoding="utf-8"))


def apply_changes(document: CommentedMap, changes: dict[str, Any]) -> dict[str, int]:
    """Merge `{key: annotation | None}` into the document in place.

    A value of None deletes the entry. Returns per-operation counts.
    """
    fields = document.setdefault("fields", CommentedMap())
    counts = {"added": 0, "updated": 0, "removed": 0}

    for key, annotation in changes.items():
        if annotation is None:
            if key in fields:
                del fields[key]
                counts["removed"] += 1
        elif key in fields:
            fields[key] = _ordered(annotation)
            counts["updated"] += 1
        else:
            _insert(fields, _insert_position(fields, key), key, _ordered(annotation))
            counts["added"] += 1

    return counts


def dump(document: CommentedMap, path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        _yaml().dump(document, handle)
