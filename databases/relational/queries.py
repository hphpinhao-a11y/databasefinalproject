"""
TransitFlow — PostgreSQL / Relational Database Layer
=====================================================
This module handles all queries to PostgreSQL.

TWO ROLES ARE SERVED HERE:
  1. Relational  → dual-network transit (metro + national rail),
                   availability, fares, bookings, seat selection
  2. Vector      → policy document similarity search (pgvector)

STUDENT TASK
------------
Design your schema in databases/relational/schema.sql, seed it with
skeleton/seed_postgres.py, then implement the query functions below.

Functions prefixed with `query_`  are read-only lookups called by the agent.
Functions prefixed with `execute_` are write operations (booking/cancellation).

The vector functions (query_policy_vector_search, store_policy_document)
are already implemented — do not modify them.
"""

from __future__ import annotations

import json
import random
import string
from datetime import datetime, timezone
from typing import Optional
import hashlib
import secrets

import psycopg2
import psycopg2.extras

from skeleton.config import PG_DSN, VECTOR_TOP_K, VECTOR_SIMILARITY_THRESHOLD


def _connect():
    """Return a new psycopg2 connection with autocommit enabled."""
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = True
    return conn


def _gen_booking_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BK-{suffix}"


def _gen_payment_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PM-{suffix}"


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(
        (password + salt).encode("utf-8")
    ).hexdigest()


def _gen_user_id() -> str:
    suffix = "".join(
        random.choices(
            string.digits,
            k=4
        )
    )

    return f"RU{suffix}"


# ── Example ───────────────────────────────────────────────────────────────────
# The block below shows the query pattern: open a cursor, run SQL, return rows.
# Use _connect() for read-only queries; for write operations use a manual
# connection with conn.commit() / conn.rollback() (see execute_booking below).

def example_query() -> dict:
    """Example: returns the name of the connected database."""
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT current_database() AS db;")
            return dict(cur.fetchone())

# TODO: Implement the query_ and execute_ functions below.
# ─────────────────────────────────────────────────────────────────────────────


# ── NATIONAL RAIL AVAILABILITY ────────────────────────────────────────────────

def query_national_rail_availability(
    origin_id: str,
    destination_id: str,
    travel_date: Optional[str] = None,
) -> list[dict]:

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT
                    ns.*,

                    o.stop_order AS origin_order,
                    d.stop_order AS destination_order,

                    (d.stop_order - o.stop_order)
                        AS stops_travelled

                FROM national_rail_schedules ns

                JOIN national_rail_schedule_stops o
                    ON ns.schedule_id = o.schedule_id

                JOIN national_rail_schedule_stops d
                    ON ns.schedule_id = d.schedule_id

                WHERE o.station_id = %s
                  AND d.station_id = %s
                  AND o.stop_order < d.stop_order

                ORDER BY ns.schedule_id
                """,
                (origin_id, destination_id)
            )

            schedules = [
                dict(row)
                for row in cur.fetchall()
            ]

            if (
                not travel_date
                or str(travel_date).lower() == "null"
            ):
                return schedules

            for sched in schedules:

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM national_rail_bookings
                    WHERE schedule_id = %s
                      AND travel_date = %s
                      AND status <> 'cancelled'
                    """,
                    (
                        sched["schedule_id"],
                        travel_date
                    )
                )

                sched["booked_seats"] = cur.fetchone()["count"]

            return schedules


def query_national_rail_fare(
    schedule_id: str,
    fare_class: str,
    stops_travelled: int,
) -> Optional[dict]:

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT
                    schedule_id,
                    fare_class,
                    base_fare_usd,
                    per_stop_rate_usd
                FROM national_rail_fares
                WHERE schedule_id = %s
                AND fare_class = %s
                """,
                (schedule_id, fare_class)
            )

            row = cur.fetchone()

            if not row:
                return None

            result = dict(row)

            result["total_fare_usd"] = (
                float(result["base_fare_usd"])
                + float(result["per_stop_rate_usd"]) * stops_travelled
            )

            return result


# ── METRO SCHEDULES & FARE ────────────────────────────────────────────────────

def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT
                    ms.*,
                    o.stop_order AS origin_order,
                    d.stop_order AS destination_order,
                    (d.stop_order - o.stop_order) AS stops_travelled

                FROM metro_schedules ms

                JOIN metro_schedule_stops o
                    ON ms.schedule_id = o.schedule_id

                JOIN metro_schedule_stops d
                    ON ms.schedule_id = d.schedule_id

                WHERE o.station_id = %s
                  AND d.station_id = %s
                  AND o.stop_order < d.stop_order

                ORDER BY ms.schedule_id
                """,
                (origin_id, destination_id)
            )

            return [dict(row) for row in cur.fetchall()]


def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]:

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT
                    schedule_id,
                    base_fare_usd,
                    per_stop_rate_usd
                FROM metro_schedules
                WHERE schedule_id = %s
                """,
                (schedule_id,)
            )

            row = cur.fetchone()

            if not row:
                return None

            result = dict(row)

            result["total_fare_usd"] = (
                float(result["base_fare_usd"])
                + float(result["per_stop_rate_usd"]) * stops_travelled
            )

            return result


# ── SEAT SELECTION ────────────────────────────────────────────────────────────

def query_available_seats(
    schedule_id: str,
    travel_date: str,
    fare_class: str,
) -> list[dict]:

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT
                    s.seat_id,
                    s.coach,
                    s.row_no AS row,
                    s.column_no AS column

                FROM national_rail_seats s

                JOIN national_rail_seat_layouts l
                    ON s.layout_id = l.layout_id

                WHERE l.schedule_id = %s
                  AND s.fare_class = %s

                  AND s.seat_id NOT IN (

                        SELECT seat_id
                        FROM national_rail_bookings

                        WHERE schedule_id = %s
                          AND travel_date = %s
                          AND status <> 'cancelled'
                  )

                ORDER BY
                    s.coach,
                    s.row_no,
                    s.column_no
                """,
                (
                    schedule_id,
                    fare_class,
                    schedule_id,
                    travel_date
                )
            )

            return [dict(row) for row in cur.fetchall()]


def auto_select_adjacent_seats(available_seats: list[dict], count: int) -> list[str]:
    """
    Select `count` seats that are as close together as possible (same row preferred,
    then adjacent rows). Returns a list of seat_ids.

    Args:
        available_seats: output of query_available_seats()
        count:           number of seats needed
    """
    if not available_seats or count <= 0:
        return []
    if count >= len(available_seats):
        return [s["seat_id"] for s in available_seats[:count]]

    from collections import defaultdict
    rows: dict[int, list[dict]] = defaultdict(list)
    for seat in available_seats:
        rows[seat["row"]].append(seat)

    for row_seats in sorted(rows.values(), key=lambda s: s[0]["row"]):
        if len(row_seats) >= count:
            return [s["seat_id"] for s in row_seats[:count]]

    sorted_seats = sorted(available_seats, key=lambda s: (s["row"], s["column"]))
    return [s["seat_id"] for s in sorted_seats[:count]]


def query_user_profile(user_email: str) -> Optional[dict]:

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT
                    user_id,
                    full_name,
                    email,
                    phone,
                    date_of_birth,
                    is_active
                FROM users
                WHERE email = %s
                """,
                (user_email,)
            )

            row = cur.fetchone()

            if not row:
                return None

            return dict(row)


# ── USER & BOOKING QUERIES ────────────────────────────────────────────────────

def query_user_bookings(user_email: str) -> dict:

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT user_id
                FROM users
                WHERE email = %s
                """,
                (user_email,)
            )

            user = cur.fetchone()

            if not user:
                return {
                    "national_rail": [],
                    "metro": []
                }

            user_id = user["user_id"]

            cur.execute(
                """
                SELECT *
                FROM national_rail_bookings
                WHERE user_id = %s
                ORDER BY booked_at DESC
                """,
                (user_id,)
            )

            rail_bookings = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT *
                FROM metro_travel_history
                WHERE user_id = %s
                ORDER BY purchased_at DESC
                """,
                (user_id,)
            )

            metro_bookings = [dict(row) for row in cur.fetchall()]

            return {
                "national_rail": rail_bookings,
                "metro": metro_bookings
            }



def query_payment_info(booking_id: str) -> Optional[dict]:
    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT *
                FROM payments
                WHERE booking_id = %s
                """,
                (booking_id,)
            )

            row = cur.fetchone()

            return dict(row) if row else None


# ── TRANSACTIONAL OPERATIONS ──────────────────────────────────────────────────

def execute_booking(
    user_id: str,
    schedule_id: str,
    origin_station_id: str,
    destination_station_id: str,
    travel_date: str,
    fare_class: str,
    seat_id: str,
    ticket_type: str = "single",
) -> tuple[bool, dict | str]:

    conn = _connect()

    try:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            # Auto-select seat if requested
            if seat_id.lower() == "any":

                seats = query_available_seats(
                    schedule_id,
                    travel_date,
                    fare_class
                )

                if not seats:
                    return False, "No seats available"

                seat_id = seats[0]["seat_id"]

            # Check seat availability
            cur.execute(
                """
                SELECT 1
                FROM national_rail_bookings
                WHERE schedule_id = %s
                  AND travel_date = %s
                  AND seat_id = %s
                  AND status <> 'cancelled'
                """,
                (
                    schedule_id,
                    travel_date,
                    seat_id
                )
            )

            if cur.fetchone():
                return False, "Seat already booked"

            # Get schedule departure time
            cur.execute(
                """
                SELECT first_train_time
                FROM national_rail_schedules
                WHERE schedule_id = %s
                """,
                (schedule_id,)
            )

            schedule = cur.fetchone()

            if not schedule:
                return False, "Schedule not found"

            # Get coach from seat
            cur.execute(
                """
                SELECT coach
                FROM national_rail_seats
                WHERE seat_id = %s
                LIMIT 1
                """,
                (seat_id,)
            )

            seat_info = cur.fetchone()

            coach = seat_info["coach"] if seat_info else None

            # Calculate stops travelled
            cur.execute(
                """
                SELECT
                    (d.stop_order - o.stop_order)
                        AS stops_travelled

                FROM national_rail_schedule_stops o

                JOIN national_rail_schedule_stops d
                    ON o.schedule_id = d.schedule_id

                WHERE o.schedule_id = %s
                  AND o.station_id = %s
                  AND d.station_id = %s
                """,
                (
                    schedule_id,
                    origin_station_id,
                    destination_station_id
                )
            )

            stop_data = cur.fetchone()

            if not stop_data:
                return False, "Invalid station pair"

            stops_travelled = stop_data["stops_travelled"]

            # Calculate fare
            fare = query_national_rail_fare(
                schedule_id,
                fare_class,
                stops_travelled
            )

            if not fare:
                return False, "Fare not found"

            amount = fare["total_fare_usd"]

            booking_id = _gen_booking_id()
            payment_id = _gen_payment_id()

            # Insert booking
            cur.execute(
                """
                INSERT INTO national_rail_bookings (
                    booking_id,
                    user_id,
                    schedule_id,
                    origin_station_id,
                    destination_station_id,
                    travel_date,
                    departure_time,
                    ticket_type,
                    fare_class,
                    coach,
                    seat_id,
                    stops_travelled,
                    amount_usd,
                    status,
                    booked_at
                )
                VALUES (
                    %s,%s,%s,%s,%s,
                    %s,%s,%s,%s,%s,
                    %s,%s,%s,%s,NOW()
                )
                """,
                (
                    booking_id,
                    user_id,
                    schedule_id,
                    origin_station_id,
                    destination_station_id,
                    travel_date,
                    schedule["first_train_time"],
                    ticket_type,
                    fare_class,
                    coach,
                    seat_id,
                    stops_travelled,
                    amount,
                    "confirmed"
                )
            )

            # Insert payment
            cur.execute(
                """
                INSERT INTO payments (
                    payment_id,
                    booking_id,
                    amount_usd,
                    method,
                    status,
                    paid_at
                )
                VALUES (
                    %s,%s,%s,
                    %s,%s,NOW()
                )
                """,
                (
                    payment_id,
                    booking_id,
                    amount,
                    "credit_card",
                    "paid"
                )
            )

            conn.commit()

            return True, {
                "booking_id": booking_id,
                "payment_id": payment_id,
                "seat_id": seat_id,
                "coach": coach,
                "amount_usd": amount,
                "status": "confirmed"
            }

    except Exception as e:
        conn.rollback()
        return False, str(e)

    finally:
        conn.close()


def execute_cancellation(
    booking_id: str,
    user_id: str
) -> tuple[bool, dict | str]:

    conn = _connect()

    try:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            # Find booking
            cur.execute(
                """
                SELECT *
                FROM national_rail_bookings
                WHERE booking_id = %s
                """,
                (booking_id,)
            )

            booking = cur.fetchone()

            if not booking:
                return False, "Booking not found"

            # Ownership check
            if booking["user_id"] != user_id:
                return False, "Booking does not belong to this user"

            # Already cancelled?
            if booking["status"] == "cancelled":
                return False, "Booking already cancelled"

            refund_amount = float(booking["amount_usd"])

            # Update booking
            cur.execute(
                """
                UPDATE national_rail_bookings
                SET status = 'cancelled'
                WHERE booking_id = %s
                """,
                (booking_id,)
            )

            # Update payment
            cur.execute(
                """
                UPDATE payments
                SET status = 'refunded'
                WHERE booking_id = %s
                """,
                (booking_id,)
            )

            conn.commit()

            return True, {
                "booking_id": booking_id,
                "refund_amount_usd": refund_amount,
                "status": "cancelled"
            }

    except Exception as e:
        conn.rollback()
        return False, str(e)

    finally:
        conn.close()


# ── AUTHENTICATION QUERIES ────────────────────────────────────────────────────

def register_user(
    email: str,
    first_name: str,
    surname: str,
    year_of_birth: int,
    password: str,
    secret_question: str,
    secret_answer: str,
) -> tuple[bool, str]:

    conn = _connect()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT user_id
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            if cur.fetchone():
                return False, "Email already registered"

            user_id = _gen_user_id()

            full_name = f"{first_name} {surname}"

            salt = secrets.token_hex(16)

            password_hash = _hash_password(
                password,
                salt
            )

            cur.execute(
                """
                INSERT INTO users (
                    user_id,
                    full_name,
                    email,
                    date_of_birth,
                    secret_question,
                    secret_answer,
                    registered_at,
                    is_active
                )
                VALUES (
                    %s,%s,%s,%s,%s,%s,NOW(),TRUE
                )
                """,
                (
                    user_id,
                    full_name,
                    email,
                    f"{year_of_birth}-01-01",
                    secret_question,
                    secret_answer
                )
            )
            cur.execute(
                """
                INSERT INTO user_credentials (
                    user_id,
                    password_hash
                )
                VALUES (%s,%s)
                """,
                (
                    user_id,
                    password_hash
                )
            )

            cur.execute(
                """
                INSERT INTO user_salts (
                    user_id,
                    salt
                )
                VALUES (%s,%s)
                """,
                (
                    user_id,
                    salt
                )
            )

            conn.commit()

            return True, user_id

    except Exception as e:

        conn.rollback()

        return False, str(e)

    finally:
        conn.close()


def login_user(
    email: str,
    password: str
) -> Optional[dict]:

    with _connect() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    u.user_id,
                    u.email,
                    u.full_name,
                    u.phone,
                    u.date_of_birth,
                    u.is_active,
                    c.password_hash,
                    s.salt
                FROM users u

                JOIN user_credentials c
                    ON u.user_id = c.user_id

                JOIN user_salts s
                    ON u.user_id = s.user_id

                WHERE u.email = %s
                """,
                (email,)
            )

            row = cur.fetchone()

            if not row:
                return None

            (
                user_id,
                email_db,
                full_name,
                phone,
                date_of_birth,
                is_active,
                stored_hash,
                salt
            ) = row

            calculated_hash = _hash_password(
                password,
                salt
            )

            if calculated_hash != stored_hash:
                return None

            name_parts = full_name.split(" ", 1)

            first_name = name_parts[0]

            surname = (
                name_parts[1]
                if len(name_parts) > 1
                else ""
            )

            return {
                "user_id": user_id,
                "email": email_db,
                "full_name": full_name,
                "first_name": first_name,
                "surname": surname,
                "phone": phone,
                "date_of_birth": date_of_birth,
                "is_active": is_active
            }


def get_user_secret_question(email: str) -> Optional[str]:

    with _connect() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT secret_question
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            row = cur.fetchone()

            if not row:
                return None

            return row[0]


def verify_secret_answer(
    email: str,
    answer: str
) -> bool:

    with _connect() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT secret_answer
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            row = cur.fetchone()

            if not row:
                return False

            return (
                row[0].strip().lower()
                ==
                answer.strip().lower()
            )


def update_password(
    email: str,
    new_password: str
) -> bool:

    conn = _connect()

    try:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT user_id
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            row = cur.fetchone()

            if not row:
                return False

            user_id = row[0]

            salt = secrets.token_hex(16)

            password_hash = _hash_password(
                new_password,
                salt
            )

            cur.execute(
                """
                UPDATE user_credentials
                SET password_hash = %s
                WHERE user_id = %s
                """,
                (
                    password_hash,
                    user_id
                )
            )

            cur.execute(
                """
                UPDATE user_salts
                SET salt = %s
                WHERE user_id = %s
                """,
                (
                    salt,
                    user_id
                )
            )

            conn.commit()
            return True

    except Exception:
        conn.rollback()
        return False

    finally:
        conn.close()


# ── VECTOR / RAG QUERIES — do not modify ─────────────────────────────────────

def query_policy_vector_search(embedding: list[float], top_k: int = VECTOR_TOP_K) -> list[dict]:
    """
    Find the most relevant policy documents for a given query embedding.

    Args:
        embedding: Query vector from llm.embed(user_question)
        top_k:     Number of results to return

    Returns:
        List of dicts with title, category, content, and similarity score
    """
    sql = """
        SELECT
            title,
            category,
            content,
            1 - (embedding <=> %s::vector) AS similarity
        FROM policy_documents
        WHERE 1 - (embedding <=> %s::vector) > %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (vec_str, vec_str, VECTOR_SIMILARITY_THRESHOLD, vec_str, top_k))
            return [dict(row) for row in cur.fetchall()]


def store_policy_document(
    title: str,
    category: str,
    content: str,
    embedding: list[float],
    source_file: str = "",
) -> int:
    """
    Insert a policy document with its embedding into the database.
    Used by skeleton/seed_vectors.py — students don't need to call this directly.

    Returns:
        The new document's id
    """
    sql = """
        INSERT INTO policy_documents (title, category, content, embedding, source_file)
        VALUES (%s, %s, %s, %s::vector, %s)
        RETURNING id
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (title, category, content, vec_str, source_file))
            return cur.fetchone()[0]
