## General Transit Feed Specification Reference

**Revised October 28, 2025. See [Revision History](https://gtfs.org/schedule/process/#revision-history) for more details.**

This document defines the format and structure of the files that comprise a GTFS dataset.

## Document Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

### Term Definitions

This section defines terms that are used throughout this document.

* **Dataset** - A complete set of files defined by this specification reference. Altering the dataset creates a new version of the dataset. Datasets should be published at a public, permanent URL, including the zip file name. (e.g., https://www.agency.org/gtfs/gtfs.zip).
* **Record** - A basic data structure comprised of a number of different field values describing a single entity (e.g. transit agency, stop, route, etc.). Represented, in a table, as a row.
* **Field** - A property of an object or entity. Represented, in a table, as a column. The field exists if added in a file as a header. It may or may not have field values defined.
* **Field value** - An individual entry in a field. Represented, in a table, as a single cell.
* **Service day** - A service day is a time period used to indicate route scheduling. The exact definition of service day varies from agency to agency but service days often do not correspond with calendar days. A service day may exceed 24:00:00 if service begins on one day and ends on a following day. For example, service that runs from 08:00:00 on Friday to 02:00:00 on Saturday, could be denoted as running from 08:00:00 to 26:00:00 on a single service day.
* **Text-to-speech field** - The field should contain the same information than its parent field (on which it falls back if it is empty). It is aimed to be read as text-to-speech, therefore, abbreviation should be either removed ("St" should be either read as "Street" or "Saint"; "Elizabeth I" should be "Elizabeth the first") or kept to be read as it ("JFK Airport" is said abbreviated).
* **Leg** - Travel in which a rider boards and alights between a pair of subsequent locations along a trip.
* **Journey** - Overall travel from origin to destination, including all legs and transfers in-between.
* **Sub-journey** - Two or more legs that comprise a subset of a journey.
* **Fare product** - Purchassable fare products that can be used to pay for or validate travel.
* **Effective Fare Leg** - A sub-journey of two or more legs that should be treated as a single leg for matching rules in fare_leg_rules.txt for the purposes of fare calculation.

### Presence

Presence conditions applicable to fields and files.

* **Required** - The field or file must be included in the dataset and contain a valid value for each record.
* **Optional** - The field or file may be omitted from the dataset.
* **Conditionally Required** - The field or file must be included under conditions outlined in the field or file description.
* **Conditionally Forbidden** - The field or file must not be included under conditions outlined in the field or file description.
* **Recommended** - The field or file may be omitted from the dataset, but it is a best practice to include it. Before omitting this field or file, the best practice should be carefully evaluated and the full implications of omission should be understood.

### Field Types

Field types applicable to fields.

* **Color** - A color encoded as a six-digit hexadecimal number. Refer to https://htmlcolorcodes.com to generate a valid value (the leading "#" must not be included). <br> *Example: FFFFFF for white, 000000 for black or 0039A6 for the A,C,E lines in NYMTA.*
* **Currency code** - An ISO 4217 alphabetical currency code. For the list of current currency, refer to https://en.wikipedia.org/wiki/ISO_4217#Active_codes. <br> *Example: CAD for Canadian dollars, EUR for euros or JPY for Japanese yen.*
* **Currency amount** - A decimal value indicating a currency amount. The number of decimal places is specified by ISO 4217 for the accompanying Currency code. All financial calculations should be processed as decimal, currency, or another equivalent type suitable for financial calculations depending on the programming language used to consume data. Processing currency amounts as float is discouraged due to gains or losses of money during calculations. 
* **Date** - Service day in the YYYYMMDD format. Since time within a service day may be above 24:00:00, a service day may contain information for the subsequent day(s). <br> *Example: 20180913 for September 13th, 2018.*
* **Email** - An email address. <br> *Example: example@example.com*
* **Enum** - An option from a set of predefined constants defined in the Description column. <br> *Example: The route_type field contains a 0 for tram, a 1 for subway...*
* **ID** - An ID field value is an internal ID, not intended to be shown to riders, and is a sequence of any UTF-8 characters. Using only printable ASCII characters is recommended. An ID is labeled "unique ID" when it must be unique within a file. IDs defined in one .txt file are often referenced in another .txt file. IDs that reference an ID in another table are labeled "foreign ID". <br> *Example: The `stop_id` field in [stops.txt](#stopstxt) is a "unique ID". The `parent_station` field in [stops.txt](#stopstxt) is a "foreign ID referencing `stops.stop_id`".*
* **Language code** - An IETF BCP 47 language code. For an introduction to IETF BCP 47, refer to http://www.rfc-editor.org/rfc/bcp/bcp47.txt and http://www.w3.org/International/articles/language-tags/. <br> *Example: `en` for English, `en-US` for American English or `de` for German.*
* **Latitude** - WGS84 latitude in decimal degrees. The value must be greater than or equal to -90.0 and less than or equal to 90.0. <br> *Example: `41.890169` for the Colosseum in Rome.*
* **Longitude** - WGS84 longitude in decimal degrees. The value must be greater than or equal to -180.0 and less than or equal to 180.0. <br> *Example: `12.492269` for the Colosseum in Rome.*
* **Float** - A floating point number. 
* **Integer** - An integer. 
* **Phone number** - A phone number. 
* **Time** - Time in the HH:MM:SS format (H:MM:SS is also accepted). The time is measured from "noon minus 12h" of the service day (effectively midnight except for days on which daylight savings time changes occur). For times occurring after midnight on the service day, enter the time as a value greater than 24:00:00 in HH:MM:SS. <br> *Example: `14:30:00` for 2:30PM or `25:35:00` for 1:35AM on the next day.*
* **Local time** - Time in the HH:MM:SS format (H:MM:SS is also accepted). Represents a wall-clock time shown in the local time of the specified location. 
* **Text** - A string of UTF-8 characters, which is aimed to be displayed and which must therefore be human readable. 
* **Timezone** - TZ timezone from the https://www.iana.org/time-zones. Timezone names never contain the space character but may contain an underscore. Refer to http://en.wikipedia.org/wiki/List_of_tz_zones for a list of valid values. <br> *Example: `Asia/Tokyo`, `America/Los_Angeles` or `Africa/Cairo`.*
* **URL** - A fully qualified URL that includes http:// or https://, and any special characters in the URL must be correctly escaped. See the following http://www.w3.org/Addressing/URL/4_URI_Recommentations.html for a description of how to create fully qualified URL values. 

### Field Signs

Signs applicable to Float or Integer field types.

* **Non-negative** - Greater than or equal to 0.
* **Non-zero** - Not equal to 0.
* **Positive** - Greater than 0.

*Example: Non-negative float: A floating point number greater than or equal to 0.*

### Dataset Attributes

Attributes that apply to the entire dataset.

* **Primary key** - The primary key of a dataset is the field or combination of fields that uniquely identify a row. Primary key (*) is used when all provided fields for a file are used to uniquely identify a row. Primary key (none) means that the file allows only one row. <br> *Example: The trip_id and stop_sequence fields make the primary key of stop_times.txt.*

## Dataset Files

This specification defines the following files.

| **File Name** | **Presence** | **Description** |
|---------------|--------------|-----------------|
| agency.txt | Required | Transit agencies with service represented in this dataset. |
| stops.txt | Conditionally Required | Stops where vehicles pick up or drop off riders. Also defines stations and station entrances. |
| routes.txt | Required | Transit routes. A route is a group of trips that are displayed to riders as a single service. |
| trips.txt | Required | Trips for each route. A trip is a sequence of two or more stops that occur during a specific time period. |
| stop_times.txt | Required | Times that a vehicle arrives at and departs from stops for each trip. |
| calendar.txt | Conditionally Required | Service dates specified using a weekly schedule with start and end dates. |
| calendar_dates.txt | Conditionally Required | Exceptions for the services defined in the calendar.txt. |
| fare_attributes.txt | Optional | Fare information for a transit agency's routes. |
| fare_rules.txt | Optional | Rules to apply fares for itineraries. |
| timeframes.txt | Optional | Date and time periods to use in fare rules for fares that depend on date and time factors. |
| rider_categories.txt | Optional | Defines categories of riders (e.g. elderly, student). |
| fare_media.txt | Optional | To describe the fare media that can be employed to use fare products. |
| fare_products.txt | Optional | To describe the different types of tickets or fares that can be purchased by riders. |
| fare_leg_rules.txt | Optional | Fare rules for individual legs of travel. |
| fare_leg_join_rules.txt | Optional | Rules for defining two or more legs should be considered as a single effective fare leg for the purposes of matching against rules in fare_leg_rules.txt |
| fare_transfer_rules.txt | Optional | Fare rules for transfers between legs of travel. |
| areas.txt | Optional | Area grouping of locations. |
| stop_areas.txt | Optional | Rules to assign stops to areas. |
| networks.txt | Conditionally Forbidden | Network grouping of routes. |
| route_networks.txt | Conditionally Forbidden | Rules to assign routes to networks. |
| shapes.txt | Optional | Rules for mapping vehicle travel paths, sometimes referred to as route alignments. |
| frequencies.txt | Optional | Headway (time between trips) for headway-based service or a compressed representation of fixed-schedule service. |
| transfers.txt | Optional | Rules for making connections at transfer points between routes. |
| pathways.txt | Optional | Pathways linking together locations within stations. |
| levels.txt | Conditionally Required | Levels within stations. |
| location_groups.txt | Optional | A group of stops that together indicate locations where a rider may request pickup or drop off. |
| location_group_stops.txt | Optional | Rules to assign stops to location groups. |
| locations.geojson | Optional | Zones for rider pickup or drop-off requests by on-demand services, represented as GeoJSON polygons. |
| booking_rules.txt | Optional | Booking information for rider-requested services. |
| translations.txt | Optional | Translations of customer-facing dataset values. |
| feed_info.txt | Conditionally Required | Dataset metadata, including publisher, version, and expiration information. |
| attributions.txt | Optional | Dataset attributions. |

## File Requirements

The following requirements apply to the format and contents of the dataset files.


- All files must be saved as comma-delimited text.
- The first line of each file must contain field names. Each subsection of the Field Definitions section corresponds to one of the files in a GTFS dataset and lists the field names that may be used in that file.
- All file and field names are case-sensitive.
- Field values must not contain tabs, carriage returns or new lines.
- Field values that contain quotation marks or commas must be enclosed within quotation marks. In addition, each quotation mark in the field value must be preceded with a quotation mark. This is consistent with the manner in which Microsoft Excel outputs comma-delimited (CSV) files. For more information on the CSV file format, see http://tools.ietf.org/html/rfc4180.
- Field values must not contain HTML tags, comments or escape sequences.
- Extra spaces between fields or field names should be removed. Many parsers consider the spaces to be part of the value, which may cause errors.
- Each line must end with a CRLF or LF linebreak character.
- Files should be encoded in UTF-8 to support all Unicode characters. Files that include the Unicode byte-order mark (BOM) character are acceptable. See http://unicode.org/faq/utf_bom.html#BOM for more information on the BOM character and UTF-8.
- All dataset files must be zipped together. The files must reside at the root level directly, not in a subfolder.
- All customer-facing text strings (including stop names, route names, and headsigns) should use Mixed Case (not ALL CAPS), following local conventions for capitalization of place names on displays capable of displaying lower case characters (e.g. "Brighton Churchill Square", "Villiers-sur-Marne", "Market Street").
- The use of abbreviations should be avoided throughout the feed for names and other text (e.g. St. for Street) unless a location is called by its abbreviated name (e.g. "JFK Airport"). Abbreviations may be problematic for accessibility by screen reader software and voice user interfaces. Consuming software can be engineered to reliably convert full words to abbreviations for display, but converting from abbreviations to full words is prone to more risk of error.

## Dataset Publishing & General Practices

General practices for publishing a GTFS dataset.

- Datasets should be published at a public, permanent URL, including the zip file name. (e.g., www.agency.org/gtfs/gtfs.zip). Ideally, the URL should be directly downloadable without requiring login to access the file, to facilitate download by consuming software applications. While it is recommended (and the most common practice) to make a GTFS dataset openly downloadable, if a data provider does need to control access to GTFS for licensing or other reasons, it is recommended to control access to the GTFS dataset using API keys, which will facilitate automatic downloads.
- GTFS data should be published in iterations so that a single file at a stable location always contains the latest official description of service for a transit agency (or agencies).
- Datasets should maintain persistent identifiers (id fields) for stop_id, route_id, and agency_id across data iterations whenever possible.
- One GTFS dataset should contain current and upcoming service (sometimes called a "merged" dataset). There are multiple merge tools available that can be used to create a merged dataset from two different GTFS feeds.
- At any time, the published GTFS dataset should be valid for at least the next 7 days, and ideally for as long as the operator is confident that the schedule will continue to be operated.
- If possible, the GTFS dataset should cover at least the next 30 days of service.
- Old services (expired calendars) should be removed from the feed.
- If a service modification will go into effect in 7 days or fewer, this service change should be expressed through a GTFS-realtime feed (service advisories or trip updates) rather than static GTFS dataset.
- The web-server hosting GTFS data should be configured to correctly report the file modification date (see HTTP/1.1 - Request for Comments 2616, under Section 14.29).