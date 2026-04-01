"""
Pydantic models for GTFS static schedule (revision 2025-10-28).
Scope: only `agency.txt` and `stops.txt` as defined in the YAML reference.
Presence conditions are noted in comments; optional fields remain Optional.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class Agency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Required when multiple agencies are present; recommended otherwise.
    agency_id: Optional[str] = Field(default=None)
    agency_name: str
    agency_url: str
    agency_timezone: str
    agency_lang: Optional[str] = Field(default=None)
    agency_phone: Optional[str] = Field(default=None)
    agency_fare_url: Optional[str] = Field(default=None)
    agency_email: Optional[str] = Field(default=None)
    # 0 or empty: no cEMV info; 1: supported; 2: not supported
    cemv_support: Optional[int] = Field(default=None)


class Stop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stop_id: str
    stop_code: Optional[str] = Field(default=None)
    # Required for location_type 0, 1, 2; optional otherwise.
    stop_name: Optional[str] = Field(default=None)
    tts_stop_name: Optional[str] = Field(default=None)
    stop_desc: Optional[str] = Field(default=None)
    # Required for location_type 0, 1, 2; optional for 3, 4.
    stop_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    stop_lon: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    zone_id: Optional[str] = Field(default=None)
    stop_url: Optional[str] = Field(default=None)
    location_type: Optional[int] = Field(default=None, ge=0, le=4)
    # Required for entrances (2), generic nodes (3), boarding areas (4);
    # optional for stops/platforms (0); forbidden for stations (1).
    parent_station: Optional[str] = Field(default=None)
    stop_timezone: Optional[str] = Field(default=None)
    wheelchair_boarding: Optional[int] = Field(default=None, ge=0, le=2)
    level_id: Optional[str] = Field(default=None)
    platform_code: Optional[str] = Field(default=None)
    # Optional when parent_station is set and location_type is a stop/platform.
    # Forbidden for stations, entrances, generic nodes, boarding areas, or when parent_station is empty.
    stop_access: Optional[int] = Field(default=None, ge=0, le=1)


class GtfsFeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agency: Optional[list[Agency]] = Field(default=None)
    stops: Optional[list[Stop]] = Field(default=None)
