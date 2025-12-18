/**
 * Type definitions for GTFS static schedule (revision 2025-10-28).
 * Scope: only `agency.txt` and `stops.txt` as defined in the YAML reference.
 * Presence conditions are noted in comments; optional fields are marked with `?`.
 */

export type ID = string;
export type URLString = string;
export type Timezone = string;

export type LocationType = 0 | 1 | 2 | 3 | 4;
export type WheelchairBoarding = 0 | 1 | 2;
export type StopAccess = 0 | 1;

export interface Agency {
	// Required when the dataset has multiple agencies; recommended otherwise.
	agency_id?: ID;
	agency_name: string;
	agency_url: URLString;
	agency_timezone: Timezone;
	agency_lang?: string; // IETF BCP 47 language code
	agency_phone?: string;
	agency_fare_url?: URLString;
	agency_email?: string;
	// 0 or empty: no cEMV info; 1: supported; 2: not supported
	cemv_support?: 0 | 1 | 2;
}

export interface Stop {
	stop_id: ID;
	stop_code?: string;
	// Required for location_type 0, 1, 2; optional otherwise.
	stop_name?: string;
	tts_stop_name?: string;
	stop_desc?: string;
	// Required for location_type 0, 1, 2; optional for 3, 4.
	stop_lat?: number;
	stop_lon?: number;
	zone_id?: ID;
	stop_url?: URLString;
	location_type?: LocationType;
	// Required for entrances (2), generic nodes (3), boarding areas (4);
	// optional for stops/platforms (0); forbidden for stations (1).
	parent_station?: ID;
	stop_timezone?: Timezone;
	wheelchair_boarding?: WheelchairBoarding;
	level_id?: ID;
	platform_code?: string;
	// Optional when parent_station is set and location_type is a stop/platform.
	// Forbidden for stations, entrances, generic nodes, boarding areas, or when parent_station is empty.
	stop_access?: StopAccess;
}

export interface GtfsFeed {
	agency?: Agency[];
	stops?: Stop[];
}
