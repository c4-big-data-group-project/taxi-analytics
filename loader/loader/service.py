import csv
import itertools
from typing import Any, Iterable, TypeVar
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Numeric,
    TIMESTAMP,
    Boolean,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import insert


T = TypeVar("T")


class Loader:
    _payment_types = [
        (1, "Credit card"),
        (2, "Cash"),
        (3, "No charge"),
        (4, "Dispute"),
        (5, "Unknown"),
        (6, "Voided trip"),
    ]
    _tpep_vendors = [
        (1, "Creative Mobile Technologies"),
        (2, "VeriFone Inc."),
    ]
    _rate_codes = [
        (1, "Standard rate"),
        (2, "JFK"),
        (3, "Newark"),
        (4, "Nassau or Westchester"),
        (5, "Negotiated Fare"),
        (6, "Group ride"),
    ]
    _csv_to_db_columns_map = {
        "VendorID": "tpep_vendor_id",
        "tpep_pickup_datetime": "tpep_pickup_datetime",
        "tpep_dropoff_datetime": "tpep_dropoff_datetime",
        "passenger_count": "passenger_count",
        "trip_distance": "trip_distance_miles",
        "pickup_longitude": "pickup_longitude",
        "pickup_latitude": "pickup_latitude",
        "dropoff_longitude": "dropoff_longitude",
        "dropoff_latitude": "dropoff_latitude",
        "RateCodeID": "rate_code_id",
        "store_and_fwd_flag": "store_and_forward_flag",
        "payment_type": "payment_type",
        "extra": "extra_charge",
        "mta_tax": "mta_tax",
        "improvement_surcharge": "improvement_surcharge",
        "tip_amount": "credit_card_tip_amount",
        "fare_amount": "fare_amount",
        "tolls_amount": "tolls_amount",
        "total_amount": "total_amount",
    }

    def __init__(self, db_uri: str, csv_path: str):
        self.db_uri = db_uri
        self.csv_path = csv_path
        self.engine = create_async_engine(self.db_uri)
        self.metadata = MetaData()
        self.vendors_table = Table(
            "tpep_vendors",
            self.metadata,
            Column("tpep_vendor_id", Integer, primary_key=True),
            Column("tpep_vendor_name", String),
        )
        self.payment_types_table = Table(
            "payment_types",
            self.metadata,
            Column("payment_type", Integer, primary_key=True),
            Column("payment_description", String),
        )
        self.rate_codes_table = Table(
            "rate_codes",
            self.metadata,
            Column("rate_code_id", Integer, primary_key=True),
            Column("rate_code_description", String),
        )
        self.trips_table = Table(
            "trips",
            self.metadata,
            Column(
                "tpep_vendor_id", Integer, ForeignKey("tpep_vendors.tpep_vendor_id")
            ),
            Column("tpep_pickup_datetime", TIMESTAMP(timezone=True), primary_key=True),
            Column("tpep_dropoff_datetime", TIMESTAMP(timezone=True), primary_key=True),
            Column("passenger_count", Integer),
            Column("trip_distance_miles", Numeric(5, 2)),
            Column("pickup_longitude", Numeric(9, 6)),
            Column("pickup_latitude", Numeric(8, 6)),
            Column("dropoff_longitude", Numeric(9, 6)),
            Column("dropoff_latitude", Numeric(8, 6)),
            Column("rate_code_id", Integer, ForeignKey("rate_codes.rate_code_id")),
            Column("store_and_forward_flag", Boolean),
            Column("payment_type", Integer, ForeignKey("payment_types.payment_type")),
            Column("extra_charge", Numeric(2, 1)),
            Column("mta_tax", Numeric(2, 1)),
            Column("improvement_surcharge", Numeric(2, 1)),
            Column("credit_card_tip_amount", Numeric(5, 2)),
            Column("fare_amount", Numeric(5, 2)),
            Column("tolls_amount", Numeric(5, 2)),
            Column("total_amount", Numeric(5, 2)),
        )

    async def init(self):
        async with self.engine.begin() as c:
            await c.run_sync(self.metadata.create_all)
            await c.execute(
                insert(self.payment_types_table).on_conflict_do_nothing(),
                [
                    {
                        "payment_type": t[0],
                        "payment_description": t[1],
                    }
                    for t in self._payment_types
                ],
            )
            await c.execute(
                insert(self.vendors_table).on_conflict_do_nothing(),
                [
                    {
                        "tpep_vendor_id": t[0],
                        "tpep_vendor_name": t[1],
                    }
                    for t in self._tpep_vendors
                ],
            )
            await c.execute(
                insert(self.rate_codes_table).on_conflict_do_nothing(),
                [
                    {
                        "rate_code_id": t[0],
                        "rate_code_description": t[1],
                    }
                    for t in self._rate_codes
                ],
            )
            await c.commit()

    async def load_csv(self, start: int = 0, stop: int = 100) -> int:
        with open(self.csv_path, "r") as file:
            reader = csv.DictReader(file)
            records = itertools.islice(reader, start, stop)
            count = 0
            for batch in self._batched(records, 1000):
                async with self.engine.connect() as c:
                    c = await c.execution_options(preserve_rowcount=True)
                    mapped_batch = self._csv_to_db_columns(batch)
                    res = await c.execute(
                        insert(self.trips_table)
                        .values(mapped_batch)
                        .on_conflict_do_nothing()
                    )
                    await c.commit()
                    count += res.rowcount
            return count

    def _batched(self, iterable: Iterable[T], size: int) -> Iterable[list[T]]:
        if size <= 0:
            raise ValueError("Batch size must be positive")
        it = iter(iterable)
        while True:
            batch = list(itertools.islice(it, size))
            if not batch:
                break
            yield batch

    def _csv_to_db_columns(
        self, rows: Iterable[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        def map_func(row: dict[str, Any]):
            mapped_row = {self._csv_to_db_columns_map[k]: v for k, v in row.items()}
            mapped_row["store_and_forward_flag"] = (
                mapped_row["store_and_forward_flag"] == "Y"
            )
            mapped_row["tpep_vendor_id"] = int(row["VendorID"])
            mapped_row["tpep_pickup_datetime"] = datetime.strptime(
                row["tpep_pickup_datetime"], "%Y-%m-%d %H:%M:%S"
            )
            mapped_row["tpep_dropoff_datetime"] = datetime.strptime(
                row["tpep_dropoff_datetime"], "%Y-%m-%d %H:%M:%S"
            )
            mapped_row["passenger_count"] = int(row["passenger_count"])
            mapped_row["trip_distance_miles"] = float(row["trip_distance"])
            mapped_row["pickup_longitude"] = float(row["pickup_longitude"])
            mapped_row["pickup_latitude"] = float(row["pickup_latitude"])
            mapped_row["dropoff_longitude"] = float(row["dropoff_longitude"])
            mapped_row["dropoff_latitude"] = float(row["dropoff_latitude"])
            mapped_row["rate_code_id"] = int(row["RateCodeID"])
            mapped_row["store_and_forward_flag"] = bool(row["store_and_fwd_flag"])
            mapped_row["payment_type"] = int(row["payment_type"])
            mapped_row["extra_charge"] = float(row["extra"])
            mapped_row["mta_tax"] = float(row["mta_tax"])
            mapped_row["improvement_surcharge"] = float(row["improvement_surcharge"])
            mapped_row["credit_card_tip_amount"] = float(row["tip_amount"])
            mapped_row["fare_amount"] = float(row["fare_amount"])
            mapped_row["tolls_amount"] = float(row["tolls_amount"])
            mapped_row["total_amount"] = float(row["total_amount"])
            return mapped_row

        return list(map(map_func, rows))
