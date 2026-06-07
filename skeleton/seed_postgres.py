"""
Seed PostgreSQL with all TransitFlow mock data from train-mock-data/.

Usage:
    python skeleton/seed_postgres.py

Run AFTER docker-compose up -d.
You must first design and create your tables in databases/relational/schema.sql.
Safe to re-run: implement your inserts with ON CONFLICT DO NOTHING.
"""

import json
import os
import sys
import hashlib
import secrets

import psycopg2
from psycopg2.extras import execute_values

# ── resolve paths ────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR    = os.path.join(PROJECT_DIR, "train-mock-data")

sys.path.insert(0, PROJECT_DIR)
from skeleton import config as cfg


def load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def connect():
    return psycopg2.connect(
        host=cfg.PG_HOST,
        port=cfg.PG_PORT,
        dbname=cfg.PG_DB,
        user=cfg.PG_USER,
        password=cfg.PG_PASSWORD,
    )


def insert_many(cur, table, columns, rows):
    """Bulk insert with ON CONFLICT DO NOTHING. Returns row count inserted."""
    if not rows:
        return 0
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT DO NOTHING"
    )
    execute_values(cur, sql, rows)
    return cur.rowcount


# ── seeders ──────────────────────────────────────────────────────────────────

def seed_metro_stations(cur):
    data = load("metro_stations.json")

    station_rows = []
    line_rows = []

    for station in data:

        station_rows.append(
            (
                station["station_id"],
                station["name"],
                station["is_interchange_metro"],
                station["is_interchange_national_rail"],
                station["interchange_national_rail_station_id"]
            )
        )

        for line in station["lines"]:
            line_rows.append(
                (
                    station["station_id"],
                    line
                )
            )

    insert_many(
        cur,
        "metro_stations",
        [
            "station_id",
            "station_name",
            "is_interchange_metro",
            "is_interchange_national_rail",
            "interchange_national_rail_station_id"
        ],
        station_rows
    )

    insert_many(
        cur,
        "metro_station_lines",
        [
            "station_id",
            "line_code"
        ],
        line_rows
    )

    print(f"Metro stations: {len(station_rows)}")
    print(f"Metro station lines: {len(line_rows)}")


def seed_national_rail_stations(cur):
    data = load("national_rail_stations.json")

    station_rows = []
    line_rows = []

    for station in data:

        station_rows.append(
            (
                station["station_id"],
                station["name"],
                station["is_interchange_national_rail"],
                station["is_interchange_metro"],
                station["interchange_metro_station_id"]
            )
        )

        for line in station["lines"]:
            line_rows.append(
                (
                    station["station_id"],
                    line
                )
            )

    insert_many(
        cur,
        "national_rail_stations",
        [
            "station_id",
            "station_name",
            "is_interchange_national_rail",
            "is_interchange_metro",
            "interchange_metro_station_id"
        ],
        station_rows
    )

    insert_many(
        cur,
        "national_rail_station_lines",
        [
            "station_id",
            "line_code"
        ],
        line_rows
    )

    print(f"National rail stations: {len(station_rows)}")
    print(f"National rail station lines: {len(line_rows)}")


def seed_metro_schedules(cur):
    data = load("metro_schedules.json")

    schedule_rows = []
    stop_rows = []
    day_rows = []

    for schedule in data:

        schedule_rows.append(
            (
                schedule["schedule_id"],
                schedule["line"],
                schedule["direction"],
                schedule["origin_station_id"],
                schedule["destination_station_id"],
                schedule["first_train_time"],
                schedule["last_train_time"],
                schedule["base_fare_usd"],
                schedule["per_stop_rate_usd"],
                schedule["frequency_min"]
            )
        )

        for order, station_id in enumerate(
            schedule["stops_in_order"],
            start=1
        ):

            stop_rows.append(
                (
                    schedule["schedule_id"],
                    station_id,
                    order,
                    schedule["travel_time_from_origin_min"][station_id]
                )
            )

        for day in schedule["operates_on"]:

            day_rows.append(
                (
                    schedule["schedule_id"],
                    day
                )
            )

    insert_many(
        cur,
        "metro_schedules",
        [
            "schedule_id",
            "line",
            "direction",
            "origin_station_id",
            "destination_station_id",
            "first_train_time",
            "last_train_time",
            "base_fare_usd",
            "per_stop_rate_usd",
            "frequency_min"
        ],
        schedule_rows
    )

    insert_many(
        cur,
        "metro_schedule_stops",
        [
            "schedule_id",
            "station_id",
            "stop_order",
            "travel_time_min"
        ],
        stop_rows
    )

    insert_many(
        cur,
        "metro_schedule_days",
        [
            "schedule_id",
            "day_of_week"
        ],
        day_rows
    )

    print(f"Metro schedules: {len(schedule_rows)}")
    print(f"Metro schedule stops: {len(stop_rows)}")
    print(f"Metro schedule days: {len(day_rows)}")

def seed_national_rail_schedules(cur):
    data = load("national_rail_schedules.json")

    schedule_rows = []
    stop_rows = []
    day_rows = []
    fare_rows = []

    for schedule in data:

        schedule_rows.append(
            (
                schedule["schedule_id"],
                schedule["line"],
                schedule["service_type"],
                schedule["direction"],
                schedule["origin_station_id"],
                schedule["destination_station_id"],
                schedule["first_train_time"],
                schedule["last_train_time"],
                schedule["frequency_min"]
            )
        )

        for order, station_id in enumerate(
            schedule["stops_in_order"],
            start=1
        ):

            stop_rows.append(
                (
                    schedule["schedule_id"],
                    station_id,
                    order,
                    schedule["travel_time_from_origin_min"][station_id]
                )
            )

        for day in schedule["operates_on"]:

            day_rows.append(
                (
                    schedule["schedule_id"],
                    day
                )
            )

        for fare_class, fare_info in schedule["fare_classes"].items():

            fare_rows.append(
                (
                    schedule["schedule_id"],
                    fare_class,
                    fare_info["base_fare_usd"],
                    fare_info["per_stop_rate_usd"]
                )
            )

    insert_many(
        cur,
        "national_rail_schedules",
        [
            "schedule_id",
            "line",
            "service_type",
            "direction",
            "origin_station_id",
            "destination_station_id",
            "first_train_time",
            "last_train_time",
            "frequency_min"
        ],
        schedule_rows
    )

    insert_many(
        cur,
        "national_rail_schedule_stops",
        [
            "schedule_id",
            "station_id",
            "stop_order",
            "travel_time_min"
        ],
        stop_rows
    )

    insert_many(
        cur,
        "national_rail_schedule_days",
        [
            "schedule_id",
            "day_of_week"
        ],
        day_rows
    )

    insert_many(
        cur,
        "national_rail_fares",
        [
            "schedule_id",
            "fare_class",
            "base_fare_usd",
            "per_stop_rate_usd"
        ],
        fare_rows
    )

    print(f"National rail schedules: {len(schedule_rows)}")
    print(f"National rail schedule stops: {len(stop_rows)}")
    print(f"National rail schedule days: {len(day_rows)}")
    print(f"National rail fares: {len(fare_rows)}")


def seed_seat_layouts(cur):
    data = load("national_rail_seat_layouts.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


def seed_users(cur):
    data = load("registered_users.json")

    user_rows = []
    credential_rows = []
    salt_rows = []

    for user in data:

        salt = secrets.token_hex(16)

        password_hash = hashlib.sha256(
            (user["password"] + salt).encode("utf-8")
        ).hexdigest()

        user_rows.append(
            (
                user["user_id"],
                user["full_name"],
                user["email"],
                user["phone"],
                user["date_of_birth"],
                user["secret_question"],
                user["secret_answer"],
                user["registered_at"],
                user["is_active"]
            )
        )

        credential_rows.append(
            (
                user["user_id"],
                password_hash
            )
        )

        salt_rows.append(
            (
                user["user_id"],
                salt
            )
        )

    insert_many(
        cur,
        "users",
        [
            "user_id",
            "full_name",
            "email",
            "phone",
            "date_of_birth",
            "secret_question",
            "secret_answer",
            "registered_at",
            "is_active"
        ],
        user_rows
    )

    insert_many(
        cur,
        "user_credentials",
        [
            "user_id",
            "password_hash"
        ],
        credential_rows
    )

    insert_many(
        cur,
        "user_salts",
        [
            "user_id",
            "salt"
        ],
        salt_rows
    )

    print(f"Users: {len(user_rows)}")


def seed_national_rail_bookings(cur):
    data = load("bookings.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


def seed_metro_travels(cur):
    data = load("metro_travel_history.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


def seed_payments(cur):
    data = load("payments.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


def seed_feedback(cur):
    data = load("feedback.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to PostgreSQL...")
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Seeding tables (dependency order):")
        seed_metro_stations(cur)
        seed_national_rail_stations(cur)
        seed_metro_schedules(cur)
        seed_national_rail_schedules(cur)
        seed_seat_layouts(cur)
        seed_users(cur)
        seed_national_rail_bookings(cur)
        seed_metro_travels(cur)
        seed_payments(cur)
        seed_feedback(cur)
        conn.commit()
        print("\nAll done. Database seeded successfully.")
    except Exception as e:
        conn.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
