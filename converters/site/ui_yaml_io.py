#!/usr/bin/env python3
"""Read and write an annotation file without destroying its comments.

Both schedule.ui.yaml and realtime.ui.yaml carry hand-written comments that
record *why* a rule is a warning rather than an error — the most valuable part
of either file, and exactly what a naive load-then-dump would silently delete.
So writes go through ruamel.yaml's round-trip mode, which keeps comments
attached to the keys they document, and only the entries that actually changed
are replaced.

The two files have different annotation vocabularies, so the emission order is
passed in by the caller, read out of whichever JSON Schema governs the file.

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


def _ordered(annotation: dict, order: tuple[str, ...]) -> CommentedMap:
    out = CommentedMap()
    for key in order:
        if key in annotation and annotation[key] not in (None, "", {}):
            out[key] = _convert(annotation[key])
    return out


def key_order(schema: dict) -> tuple[str, ...]:
    """The annotation's property order, taken from its schema.

    The writer emits keys in this order so an entry rewritten by the editor
    keeps the same shape as the hand-written ones around it.
    """
    return tuple(schema["definitions"]["annotation"]["properties"])


def _table_of(key: str) -> str:
    """'stops.stop_lat' -> 'stops'; 'Alert.header_text' -> 'Alert'.

    The group an entry belongs to, which is the GTFS file on the Schedule side
    and the protobuf message on the Realtime side. Either way it is what the
    section header comments in the file divide the entries by.
    """
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


def _tail(node: Any) -> tuple[Any, Any, int] | None:
    """The (container, key, slot) whose value ends a subtree, walking bottom-right.

    A section header like `# ---- routes.txt ----` belongs to the entry it
    introduces, but ruamel attaches it to the *last scalar of the previous
    entry*, which for these annotations is several levels down (i18n -> pt ->
    help). This is where that comment lives.

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
    """Remove and return the comment block trailing a subtree's last value.

    Only a real comment counts. ruamel also files the blank line *between* two
    entries in this slot, as a token whose whole value is newlines — treating
    that as a comment and moving it around is how a section header two entries
    away gets overwritten with nothing.
    """
    if (tail := _tail(node)) is None:
        return None
    container, key, slot = tail
    item = container.ca.items.get(key)
    if not item or item[slot] is None or "#" not in item[slot].value:
        return None
    token = item[slot]
    # Leave a bare newline behind so entries stay separated by a blank line.
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


def _section_lead(document: CommentedMap) -> list | None:
    """The comment slot holding the header that introduces the first annotation.

    That header sits after `fields:` and before the first entry, so ruamel
    files it on the parent key rather than on either entry.
    """
    item = document.ca.items.get("fields")
    return item[3] if item and len(item) > 3 else None


def _insert(fields: CommentedMap, position: int, key: str, value: CommentedMap) -> None:
    """Insert a key, keeping any section header with the block it introduces."""
    keys = list(fields.keys())
    header = None
    if 0 < position < len(keys):
        header = _detach_trailing(fields[keys[position - 1]])

    fields.insert(position, key, value)

    if header is not None:
        _attach_leading(fields, keys[position], header)


def _delete(fields: CommentedMap, key: str, document: CommentedMap) -> None:
    """Remove an entry without taking a neighbouring section header with it.

    A header like `# ---- routes.txt ----` introduces a *block* of entries, and
    ruamel stores it away from all of them: trailing the last scalar of the
    entry before the block. Two consequences, and they pull opposite ways:

      the header trailing *this* entry introduces the NEXT block, so deleting
      the key alone would delete it and leave the next block unlabelled;

      the header that introduces this entry's own block must stay exactly
      where it is — unless this was the last entry of the block, in which case
      it now labels nothing and has to go.
    """
    keys = list(fields.keys())
    index = keys.index(key)
    previous = keys[index - 1] if index else None
    following = keys[index + 1] if index + 1 < len(keys) else None
    table = _table_of(key)
    emptied = not any(_table_of(k) == table for k in keys if k != key)

    introduces_next = _detach_trailing(fields[key])
    del fields[key]

    if previous is not None:
        # The header introducing this block trails `previous`. Drop it only if
        # the block is now empty; either way what trails `previous` afterwards
        # is the header for whatever block comes next.
        if emptied:
            _detach_trailing(fields[previous])
        if introduces_next is not None:
            _attach_trailing(fields[previous], introduces_next)
        return

    # No previous entry: this block's header is not on an entry at all, it is
    # filed on the `fields` key itself, so it has to be replaced there.
    lead = _section_lead(document)
    if lead is None:
        if introduces_next is not None and following is not None:
            _attach_leading(fields, following, introduces_next)
        return
    if not emptied:
        return  # the block continues; its header stays where it is
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


def apply_changes(document: CommentedMap, changes: dict[str, Any],
                  order: tuple[str, ...]) -> dict[str, int]:
    """Merge `{key: annotation | None}` into the document in place.

    A value of None deletes the entry. Returns per-operation counts.
    """
    fields = document.setdefault("fields", CommentedMap())
    counts = {"added": 0, "updated": 0, "removed": 0}

    for key, annotation in changes.items():
        if annotation is None:
            if key in fields:
                _delete(fields, key, document)
                counts["removed"] += 1
        elif key in fields:
            fields[key] = _ordered(annotation, order)
            counts["updated"] += 1
        else:
            _insert(fields, _insert_position(fields, key), key,
                    _ordered(annotation, order))
            counts["added"] += 1

    return counts


def dump(document: CommentedMap, path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        _yaml().dump(document, handle)
