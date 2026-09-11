#!/usr/bin/env python3
"""Read realtime.yaml as a graph of protobuf messages.

GTFS Realtime is not a set of tables. It is a message graph, and three things
follow from that which the Schedule side never has to deal with:

  A field is reached by a *path*. `TripUpdate.stop_time_update.departure.time`
  and `...arrival.time` are the same field definition seen from two places, so
  the annotations key on the definition (`StopTimeEvent.time`) while
  composites.yaml keys on the path. Both are right; they answer different
  questions.

  Enum names are not unique. There are two messages called
  `ScheduleRelationship`, one for a stop and one for a trip, with different
  values. Looking one up by name alone silently returns whichever the parser
  saw last.

  Nothing says which message is a root. FeedEntity's fields do, in practice.

This module is the one place that knows all three, so the coverage script, the
site builder and the composites resolver agree about what the reference says.
"""

from __future__ import annotations

from typing import Any


def index(spec: dict) -> dict[str, Any]:
    """Everything the walkers need, computed once.

    `by_name` keeps only the last element of an ambiguous name and exists for
    the unambiguous majority; `positions` is what disambiguates the rest.
    """
    elements = spec.get("elements", []) or []
    positions: dict[str, list[int]] = {}
    for i, element in enumerate(elements):
        positions.setdefault(element["name"], []).append(i)
    return {
        "elements": elements,
        "by_name": {e["name"]: e for e in elements},
        "positions": positions,
    }


def element_at(idx: dict, name: str, near: int | None = None) -> dict | None:
    """Look up an element by name, resolving a duplicate name by position.

    realtime.yaml documents a nested type directly after the message that uses
    it — `ScheduleRelationship` for stop times sits just below StopTimeUpdate,
    the one for trips just below TripDescriptor. So of several candidates the
    right one is the first that *follows* the referring message, falling back
    to the nearest one before it.
    """
    spots = idx["positions"].get(name)
    if not spots:
        return None
    if len(spots) == 1 or near is None:
        return idx["elements"][spots[0] if len(spots) == 1 else spots[-1]]
    after = [i for i in spots if i > near]
    return idx["elements"][after[0] if after else max(spots)]


def messages(idx: dict) -> list[dict]:
    """The message elements, in spec order. Enums have no fields to annotate."""
    return [e for e in idx["elements"] if e.get("data_type") == "message"]


def field_type(field: dict) -> tuple[str, str]:
    """(type name, 'message' | 'enum' | '') for one field."""
    kind = field.get("type") or {}
    if element := kind.get("element"):
        return element.get("name", ""), element.get("data_type", "")
    return (kind.get("format") or {}).get("name", ""), ""


def inventory(idx: dict) -> list[tuple[str, dict]]:
    """Every annotatable field as ('<Message>.<field>', field), in spec order."""
    return [
        (f"{message['name']}.{field['name']}", field)
        for message in messages(idx)
        for field in message.get("fields") or []
    ]


def enum_options(idx: dict, message: dict, field: dict) -> dict | None:
    """The values a field may take, when its type is an enum.

    Resolved from the *referring* message's position, which is what keeps the
    two ScheduleRelationship enums apart — and why the enum's own name and
    description come back with the values: on a field called
    `schedule_relationship` they are the only thing saying which of the two
    this is.
    """
    name, data_type = field_type(field)
    if data_type != "enum":
        return None
    near = idx["positions"].get(message["name"], [None])[0]
    element = element_at(idx, name, near)
    if not element:
        return None
    return {
        "name": name,
        "description": element.get("description", ""),
        "values": [
            {"value": str(o.get("value", "")), "description": o.get("description", "")}
            for o in element.get("options") or []
        ],
    }


def resolve_path(path: str, idx: dict) -> dict | None:
    """Walk 'TripUpdate.stop_time_update.departure.time' to the field it names.

    Returns the field plus `owner`, the message that *declares* it, which is
    how a path in composites.yaml finds the annotation keyed on the definition.
    """
    head, *rest = path.split(".")
    element = idx["by_name"].get(head)
    if element is None or element.get("data_type") != "message" or not rest:
        return None

    field = owner = None
    for step, segment in enumerate(rest):
        if element is None or element.get("data_type") != "message":
            return None
        field = next((f for f in element.get("fields") or [] if f["name"] == segment), None)
        if field is None:
            return None
        owner = element
        nested, _ = field_type(field)
        last = step == len(rest) - 1
        near = idx["positions"].get(element["name"], [None])[0]
        element = element_at(idx, nested, near) if nested else None
        if not last and element is None:
            return None  # more path left, but this field is a scalar

    type_name, _ = field_type(field)
    return {
        "message": head,
        "owner": owner["name"],
        "key": f"{owner['name']}.{field['name']}",
        "name": field["name"],
        "type": type_name,
        "presence": field.get("presence", ""),
        "cardinality": field.get("cardinality", ""),
        "description": field.get("description", ""),
    }
