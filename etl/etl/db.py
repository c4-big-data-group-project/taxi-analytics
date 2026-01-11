from sqlalchemy import Table, MetaData, Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import (
    NUMERIC,
    TIMESTAMP,
    INTEGER,
    BOOLEAN,
    VARCHAR,
    BIGINT,
    TEXT,
)


class RawSchema:
    def __init__(self, metadata: MetaData):
        self.metadata = metadata
        # fmt: off
        self.vendors_table = Table(
            "tpep_vendors",
            metadata,
            Column("tpep_vendor_id", INTEGER, primary_key=True),
            Column("tpep_vendor_name", VARCHAR),
        )
        self.payment_types_table = Table(
            "payment_types",
            metadata,
            Column("payment_type", INTEGER, primary_key=True),
            Column("payment_description", VARCHAR),
        )
        self.rate_codes_table = Table(
            "rate_codes",
            metadata,
            Column("rate_code_id", INTEGER),
            Column("rate_code_description", VARCHAR),
        )
        self.trips_table = Table(
            "trips",
            metadata,
            Column("tpep_vendor_id", INTEGER),
            Column("tpep_pickup_datetime", TIMESTAMP(timezone=True), primary_key=True),
            Column("tpep_dropoff_datetime", TIMESTAMP(timezone=True), primary_key=True),
            Column("passenger_count", INTEGER),
            Column("trip_distance_miles", NUMERIC(5, 2)),  # type: ignore
            Column("pickup_longitude", NUMERIC(9, 6)),  # type: ignore
            Column("pickup_latitude", NUMERIC(8, 6)),  # type: ignore
            Column("dropoff_longitude", NUMERIC(9, 6)),  # type: ignore
            Column("dropoff_latitude", NUMERIC(8, 6)),  # type: ignore
            Column("rate_code_id", INTEGER),
            Column("store_and_forward_flag", BOOLEAN),
            Column("payment_type", INTEGER),
            Column("extra_charge", NUMERIC(2, 1)),  # type: ignore
            Column("mta_tax", NUMERIC(2, 1)),  # type: ignore
            Column("improvement_surcharge", NUMERIC(2, 1)),  # type: ignore
            Column("credit_card_tip_amount", NUMERIC(5, 2)),  # type: ignore
            Column("fare_amount", NUMERIC(5, 2)),  # type: ignore
            Column("tolls_amount", NUMERIC(5, 2)),  # type: ignore
            Column("total_amount", NUMERIC(5, 2)),  # type: ignore
        )
        # fmt: on


class AnalyticsSchema:
    def __init__(self, metadata: MetaData):
        self.metadata = metadata
        # fmt: off
        self.dim_datetime = Table(
            "dim_datetime",
            metadata,
            Column("datetime_id", INTEGER, primary_key=True),
            Column("datetime", TIMESTAMP(timezone=True), nullable=False, unique=True),
            Column("hour", INTEGER, nullable=False),
            Column("day", INTEGER, nullable=False),
            Column("month", INTEGER, nullable=False),
            Column("year", INTEGER, nullable=False),
            Column("day_of_week", INTEGER, nullable=False),
            Column("is_weekend", BOOLEAN, nullable=False),
        )
        self.dim_location = Table(
            "dim_location",
            metadata,
            Column("location_id", INTEGER, primary_key=True),
            Column("zone", VARCHAR, nullable=False),
            Column("borough", VARCHAR, nullable=False),
            UniqueConstraint("zone", "borough", name="dim_zone_borough_unique_constraint"),
        )
        self.dim_tpep_vendor = Table(
            "dim_tpep_vendor",
            metadata,
            Column("tpep_vendor_id", INTEGER, primary_key=True),
            Column("tpep_vendor_name", VARCHAR, nullable=False),
        )
        self.dim_payment_type = Table(
            "dim_payment_type",
            metadata,
            Column("payment_type_id", INTEGER, primary_key=True),
            Column("payment_type_description", VARCHAR, nullable=False),
        )
        self.dim_rate_code = Table(
            "dim_rate_code",
            metadata,
            Column("rate_code_id", INTEGER, primary_key=True),
            Column("rate_code_description", VARCHAR, nullable=False),
        )
        self.fact_trip = Table(
            "fact_trip",
            metadata,
            Column("trip_id", BIGINT, primary_key=True),
            Column("trip_distance_meters", INTEGER),  # type: ignore
            Column("trip_duration_minutes", INTEGER),  # type: ignore
            Column("passenger_count", INTEGER),
            Column("fare_amount", NUMERIC(5, 2)),  # type: ignore
            Column("tip_amount", NUMERIC(5, 2)),  # type: ignore
            Column("tolls_amount", NUMERIC(5, 2)),  # type: ignore
            Column("total_amount", NUMERIC(5, 2)),  # type: ignore
            Column("extra_charge", NUMERIC(2, 1)),  # type: ignore
            Column("mta_tax", NUMERIC(2, 1)),  # type: ignore
            Column("store_and_forward_flag", BOOLEAN),
            Column("pickup_latitude", NUMERIC(8, 6)),  # type: ignore
            Column("pickup_longitude", NUMERIC(9, 6)),  # type: ignore
            Column("dropoff_latitude", NUMERIC(8, 6)),  # type: ignore
            Column("dropoff_longitude", NUMERIC(9, 6)),  # type: ignore
            Column("pickup_datetime_id", INTEGER, ForeignKey("dim_datetime.datetime_id")),
            Column("dropoff_datetime_id", INTEGER, ForeignKey("dim_datetime.datetime_id")),
            Column("pickup_location_id", INTEGER, ForeignKey("dim_location.location_id")),
            Column("dropoff_location_id", INTEGER, ForeignKey("dim_location.location_id")),
            Column("payment_type_id", INTEGER, ForeignKey("dim_payment_type.payment_type_id")),
            Column("tpep_vendor_id", INTEGER, ForeignKey("dim_tpep_vendor.tpep_vendor_id")),
            Column("rate_code_id", INTEGER, ForeignKey("dim_rate_code.rate_code_id")),
            UniqueConstraint("pickup_datetime_id", "dropoff_datetime_id", name="fact_trip_pickup_dropoff_dt_unique_constraint"),
        )
        # fmt: on


class StagingSchema:
    def __init__(self, metadata: MetaData):
        self.metadata = metadata
        # fmt: off
        self.fact_trip = Table(
            "staging_trips",
            metadata,
            Column("trip_distance_meters", INTEGER),  # type: ignore
            Column("trip_duration_minutes", INTEGER),  # type: ignore
            Column("passenger_count", INTEGER),
            Column("fare_amount", NUMERIC(5, 2)),  # type: ignore
            Column("tip_amount", NUMERIC(5, 2)),  # type: ignore
            Column("tolls_amount", NUMERIC(5, 2)),  # type: ignore
            Column("total_amount", NUMERIC(5, 2)),  # type: ignore
            Column("extra_charge", NUMERIC(2, 1)),  # type: ignore
            Column("mta_tax", NUMERIC(2, 1)),  # type: ignore
            Column("store_and_forward_flag", BOOLEAN),
            Column("pickup_datetime", TIMESTAMP(timezone=True)),
            Column("dropoff_datetime", TIMESTAMP(timezone=True)),
            Column("pickup_latitude", NUMERIC(8, 6)),  # type: ignore
            Column("pickup_longitude", NUMERIC(9, 6)),  # type: ignore
            Column("dropoff_latitude", NUMERIC(8, 6)),  # type: ignore
            Column("dropoff_longitude", NUMERIC(9, 6)),  # type: ignore
            Column("payment_type_id", INTEGER),
            Column("payment_type_description", TEXT),
            Column("tpep_vendor_id", INTEGER),
            Column("tpep_vendor_name", TEXT),
            Column("rate_code_id", INTEGER),
            Column("rate_code_description", TEXT),
            Column("pickup_borough", VARCHAR),
            Column("pickup_zone", VARCHAR),
            Column("dropoff_borough", VARCHAR),
            Column("dropoff_zone", VARCHAR),
            Column("improvement_surcharge", NUMERIC(2, 1)),  # type: ignore
        )
        # fmt: on
