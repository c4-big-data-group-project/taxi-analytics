from datetime import datetime
from typing import Iterable, Any
import itertools

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.dialects.postgresql import insert

from etl.db import AnalyticsSchema, RawSchema, StagingSchema
from etl.constants import MILES_TO_METERS, CHUNK_SIZE, MAX_CHUNKS, MAX_TRIPS_PER_REQUEST


class ETLPipeline:
    def __init__(self, raw_db_uri: str, analytics_db_uri: str, taxi_zones_file: str):
        self.raw_db_uri = raw_db_uri
        self.analytics_db_uri = analytics_db_uri
        self.raw_db_engine = create_engine(self.raw_db_uri)
        self.analytics_db_engine = create_engine(self.analytics_db_uri)
        self.raw_db_metadata = MetaData()
        self.analytics_db_metadata = MetaData()
        self.raw_schema = RawSchema(self.raw_db_metadata)
        self.analytics_schema = AnalyticsSchema(self.analytics_db_metadata)
        self.staging_schema = StagingSchema(self.analytics_db_metadata)
        self.taxi_zones = gpd.read_file(taxi_zones_file)  # type: ignore

    def init(self):
        self.raw_db_metadata.create_all(self.raw_db_engine)
        self.analytics_db_metadata.create_all(self.analytics_db_engine)

    def load_raw_trips(self, since: datetime) -> pd.DataFrame:
        trips = pd.read_sql(  # type: ignore
            f"""
            SELECT
                trips.*,
                tpep_vendors.tpep_vendor_name,
                payment_types.payment_description as payment_type_description,
                rate_codes.rate_code_description
            FROM trips
            JOIN rate_codes ON rate_codes.rate_code_id = trips.rate_code_id
            JOIN payment_types ON payment_types.payment_type = trips.payment_type
            JOIN tpep_vendors ON tpep_vendors.tpep_vendor_id = trips.tpep_vendor_id
            WHERE tpep_pickup_datetime >= '{since.isoformat()}'
            ORDER BY tpep_pickup_datetime ASC
            LIMIT {MAX_TRIPS_PER_REQUEST}
            """,
            self.raw_db_engine,
        )
        trips = trips.rename(columns={"payment_type": "payment_type_id"})
        return trips

    def prepare_for_staging(self, trips: pd.DataFrame) -> pd.DataFrame:
        prepared_trips = trips.rename(
            columns={
                "credit_card_tip_amount": "tip_amount",
                "trip_distance_miles": "trip_distance_meters",
                "tpep_pickup_datetime": "pickup_datetime",
                "tpep_dropoff_datetime": "dropoff_datetime",
            }
        )
        prepared_trips["trip_distance_meters"] = (
            (prepared_trips["trip_distance_meters"] * MILES_TO_METERS)
            .round()
            .astype(int)
        )
        prepared_trips["trip_duration_minutes"] = (
            prepared_trips["dropoff_datetime"] - prepared_trips["pickup_datetime"]
        ).dt.seconds // 60
        prepared_trips = self.with_spatial_info(
            prepared_trips,
            latitude_column="pickup_latitude",
            longitude_column="pickup_longitude",
            prefix="pickup_",
        )
        prepared_trips = self.with_spatial_info(
            prepared_trips,
            latitude_column="dropoff_latitude",
            longitude_column="dropoff_longitude",
            prefix="dropoff_",
        )
        return prepared_trips

    def with_spatial_info(
        self,
        trips: pd.DataFrame,
        latitude_column: str,
        longitude_column: str,
        prefix: str,
    ) -> pd.DataFrame:
        trips_geometry: pd.Series = trips.apply(  # type: ignore
            lambda r: Point(r[longitude_column], r[latitude_column]),  # type: ignore
            axis=1,
        )
        trips_spatial_info = gpd.GeoDataFrame(
            trips_geometry.to_frame("geometry"),
            geometry="geometry",
            crs="EPSG:4326",
        ).to_crs(epsg=2263)
        trips_spatial_info = gpd.sjoin(
            trips_spatial_info, self.taxi_zones, how="left", predicate="within"
        )[["borough", "zone"]]
        trips_spatial_info = trips_spatial_info.add_prefix(prefix)
        return pd.concat([trips, trips_spatial_info], axis=1)

    def update_datetime_dim(self, trips: pd.DataFrame):
        dim_datetime_pickup = (
            trips[["pickup_datetime"]]
            .drop_duplicates()
            .assign(  # type: ignore
                hour=lambda x: x["pickup_datetime"].dt.hour,
                day=lambda x: x["pickup_datetime"].dt.day,
                month=lambda x: x["pickup_datetime"].dt.month,
                year=lambda x: x["pickup_datetime"].dt.year,
                day_of_week=lambda x: x["pickup_datetime"].dt.day_of_week,
                is_weekend=lambda x: x["pickup_datetime"].dt.day_of_week >= 5,
            )
            .rename(columns={"pickup_datetime": "datetime"})
        )
        dim_datetime_pickup.to_sql(
            "dim_datetime",
            self.analytics_db_engine,
            if_exists="append",
            index=False,
            method=self.postgres_upsert,
        )
        dim_datetime_dropoff = (
            trips[["dropoff_datetime"]]
            .drop_duplicates()
            .assign(  # type: ignore
                hour=lambda x: x["dropoff_datetime"].dt.hour,
                day=lambda x: x["dropoff_datetime"].dt.day,
                month=lambda x: x["dropoff_datetime"].dt.month,
                year=lambda x: x["dropoff_datetime"].dt.year,
                day_of_week=lambda x: x["dropoff_datetime"].dt.day_of_week,
                is_weekend=lambda x: x["dropoff_datetime"].dt.day_of_week >= 5,
            )
            .rename(columns={"dropoff_datetime": "datetime"})
        )
        dim_datetime_dropoff.to_sql(
            "dim_datetime",
            self.analytics_db_engine,
            if_exists="append",
            index=False,
            method=self.postgres_upsert,
        )

    def update_rate_code_dim(self, trips: pd.DataFrame):
        dim_rate_code = trips[
            ["rate_code_id", "rate_code_description"]
        ].drop_duplicates()
        dim_rate_code.to_sql(
            "dim_rate_code",
            self.analytics_db_engine,
            if_exists="append",
            index=False,
            method=self.postgres_upsert,
        )

    def update_tpep_vendor_dim(self, trips: pd.DataFrame):
        dim_tpep_vendor = trips[
            ["tpep_vendor_id", "tpep_vendor_name"]
        ].drop_duplicates()
        dim_tpep_vendor.to_sql(
            "dim_tpep_vendor",
            self.analytics_db_engine,
            if_exists="append",
            index=False,
            method=self.postgres_upsert,
        )

    def update_payment_type_dim(self, trips: pd.DataFrame):
        dim_payment_type = trips[
            ["payment_type_id", "payment_type_description"]
        ].drop_duplicates()
        dim_payment_type.to_sql(
            "dim_payment_type",
            self.analytics_db_engine,
            if_exists="append",
            index=False,
            method=self.postgres_upsert,
        )

    def update_location_dim(self, trips: pd.DataFrame):
        dim_location_dropoff = trips.dropna(subset=["dropoff_borough", "dropoff_zone"])[
            [
                "dropoff_borough",
                "dropoff_zone",
            ]
        ].rename(
            columns={
                "dropoff_borough": "borough",
                "dropoff_zone": "zone",
            }
        )
        dim_location_dropoff.to_sql(
            "dim_location",
            self.analytics_db_engine,
            if_exists="append",
            index=False,
            method=self.postgres_upsert,
        )
        dim_location_pickup = trips.dropna(subset=["pickup_borough", "pickup_zone"])[
            [
                "pickup_borough",
                "pickup_zone",
            ]
        ].rename(
            columns={
                "pickup_borough": "borough",
                "pickup_zone": "zone",
            }
        )
        dim_location_pickup.to_sql(
            "dim_location",
            self.analytics_db_engine,
            if_exists="append",
            index=False,
            method=self.postgres_upsert,
        )

    def update_trip_fact(self, trips: pd.DataFrame):
        with self.analytics_db_engine.begin() as c:
            c.execute(
                text(
                    """
                    INSERT INTO fact_trip(
                        trip_distance_meters,
                        trip_duration_minutes,
                        passenger_count,
                        fare_amount,
                        tip_amount,
                        tolls_amount,
                        total_amount,
                        extra_charge,
                        mta_tax,
                        store_and_forward_flag,
                        pickup_latitude,
                        pickup_longitude,
                        dropoff_latitude,
                        dropoff_longitude,
                        pickup_datetime_id,
                        dropoff_datetime_id,
                        pickup_location_id,
                        dropoff_location_id,
                        payment_type_id,
                        tpep_vendor_id,
                        rate_code_id
                    )
                    SELECT
                        t.trip_distance_meters,
                        t.trip_duration_minutes,
                        t.passenger_count,
                        t.fare_amount,
                        t.tip_amount,
                        t.tolls_amount,
                        t.total_amount,
                        t.extra_charge,
                        t.mta_tax,
                        t.store_and_forward_flag,
                        t.pickup_latitude,
                        t.pickup_longitude,
                        t.dropoff_latitude,
                        t.dropoff_longitude,
                        pickup_dt_t.datetime_id,
                        dropoff_dt_t.datetime_id,
                        pickup_loc_t.location_id,
                        dropoff_loc_t.location_id,
                        t.payment_type_id,
                        t.tpep_vendor_id,
                        t.rate_code_id
                    FROM staging_trips t
                    LEFT JOIN dim_datetime AS pickup_dt_t ON pickup_dt_t.datetime = t.pickup_datetime
                    LEFT JOIN dim_datetime AS dropoff_dt_t ON dropoff_dt_t.datetime = t.dropoff_datetime
                    LEFT JOIN dim_location AS pickup_loc_t ON pickup_loc_t.borough = t.pickup_borough AND pickup_loc_t.zone = t.pickup_zone
                    LEFT JOIN dim_location AS dropoff_loc_t ON dropoff_loc_t.borough = t.dropoff_borough AND dropoff_loc_t.zone = t.dropoff_zone
                    ON CONFLICT DO NOTHING;
                    """
                ),
            )
            c.commit()

    def postgres_upsert(
        self,
        table: Any,
        conn: Any,
        keys: list[str],
        data_iter: Iterable[tuple[Any, ...]],
    ):
        """
        This function should be passed to pd.DataFrame.to_sql to
        avoid conflicts when rows already exist in the table.
        """

        data = [dict(zip(keys, row)) for row in data_iter]
        conn.execute(insert(table.table).values(data).on_conflict_do_nothing())

    def pipe(self, since: datetime) -> datetime:
        # Load trips data from raw database.
        trips = self.load_raw_trips(since)

        def chunker(df: pd.DataFrame, size: int):
            for pos in itertools.islice(range(0, len(df), size), MAX_CHUNKS):
                yield df.iloc[pos : pos + size]

        # Put trips data into staging table so we can use it inside
        # the analytics database. But first, transform it to fit
        # the schema.
        trips = self.prepare_for_staging(trips)
        max_datetime = since
        for trips_chunk in chunker(trips, CHUNK_SIZE):
            with self.analytics_db_engine.begin() as c:
                c.execute(text("DELETE FROM staging_trips"))
                c.commit()
            trips_chunk.to_sql(
                "staging_trips",
                self.analytics_db_engine,
                if_exists="append",
                index=False,
                method=self.postgres_upsert,
            )

            # Update the dimension tables and then the fact table.
            self.update_datetime_dim(trips_chunk)
            self.update_rate_code_dim(trips_chunk)
            self.update_tpep_vendor_dim(trips_chunk)
            self.update_payment_type_dim(trips_chunk)
            self.update_location_dim(trips_chunk)
            self.update_trip_fact(trips_chunk)

            max_datetime = trips_chunk["pickup_datetime"].max()

        return max_datetime
