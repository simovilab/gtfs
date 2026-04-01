import pyarrow as pa

feed_message = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field(
            "header",
            pa.struct(
                [
                    pa.field("gtfs_realtime_version", pa.string()),
                    pa.field("incrementality", pa.string()),
                    pa.field("timestamp", pa.int64()),
                    pa.field("feed_version", pa.string()),
                ]
            ),
        ),
        pa.field("service_date", pa.string()),
        pa.field("hour", pa.int8()),
    ]
)

feed_entity = pa.schema(
    [
        pa.field("feed_timestamp", pa.int64()),
        pa.field("feed_message_id", pa.string()),
        pa.field("id", pa.string()),
        pa.field("is_deleted", pa.bool_()),
        pa.field("service_date", pa.string()),
        pa.field("hour", pa.int8()),
    ]
)

trip_update = pa.schema(
    [
        pa.field("feed_timestamp", pa.int64()),
        pa.field("feed_entity_id", pa.string()),
        pa.field("id", pa.string()),
        pa.field(
            "trip",
            pa.struct(
                [
                    pa.field("trip_id", pa.string()),
                    pa.field("route_id", pa.string()),
                    pa.field("direction_id", pa.int32()),
                    pa.field("start_time", pa.string()),
                    pa.field("start_date", pa.string()),
                    pa.field("schedule_relationship", pa.string()),
                    pa.field(
                        "modified_trip",
                        pa.struct(
                            [
                                pa.field("modifications_id", pa.string()),
                                pa.field("affected_trip_id", pa.string()),
                                pa.field("start_time", pa.string()),
                                pa.field("start_date", pa.string()),
                            ]
                        ),
                    ),
                ]
            ),
        ),
        pa.field(
            "vehicle",
            pa.struct(
                [
                    pa.field("id", pa.string()),
                    pa.field("label", pa.string()),
                    pa.field("license_plate", pa.string()),
                    pa.field("wheelchair_accessible", pa.string()),
                ]
            ),
        ),
        pa.field("timestamp", pa.int64()),
        pa.field("delay", pa.int32()),
        pa.field(
            "trip_properties",
            pa.struct(
                [
                    pa.field("trip_id", pa.string()),
                    pa.field("start_date", pa.string()),
                    pa.field("start_time", pa.string()),
                    pa.field("shape_id", pa.string()),
                    pa.field("trip_headsign", pa.string()),
                    pa.field("trip_short_name", pa.string()),
                ]
            ),
        ),
        pa.field("service_date", pa.string()),
        pa.field("hour", pa.int8()),
    ]
)

stop_time_update = pa.schema(
    [
        pa.field("feed_timestamp", pa.int64()),
        pa.field("trip_update_id", pa.string()),
        pa.field("trip_id", pa.string()),
        pa.field("route_id", pa.string()),
        pa.field("start_date", pa.string()),
        pa.field("start_time", pa.string()),
        pa.field("stop_sequence", pa.int32()),
        pa.field("stop_id", pa.string()),
        pa.field(
            "arrival",
            pa.struct(
                [
                    pa.field("delay", pa.int32()),
                    pa.field("time", pa.int64()),
                    pa.field("scheduled_time", pa.int64()),
                    pa.field("uncertainty", pa.int32()),
                ]
            ),
        ),
        pa.field(
            "departure",
            pa.struct(
                [
                    pa.field("delay", pa.int32()),
                    pa.field("time", pa.int64()),
                    pa.field("scheduled_time", pa.int64()),
                    pa.field("uncertainty", pa.int32()),
                ]
            ),
        ),
        pa.field("departure_occupancy_status", pa.string()),
        pa.field("schedule_relationship", pa.string()),
        pa.field(
            "stop_time_properties",
            pa.struct(
                [
                    pa.field("assigned_stop_id", pa.string()),
                    pa.field("stop_headsign", pa.string()),
                    pa.field("drop_off_type", pa.string()),
                    pa.field("pickup_type", pa.string()),
                ]
            ),
        ),
        pa.field("service_date", pa.string()),
        pa.field("hour", pa.int8()),
    ]
)
