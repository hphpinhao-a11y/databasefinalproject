"""
TransitFlow — Neo4j Graph Database Layer
=========================================
This module handles all queries to Neo4j.

GRAPH ROLE:
  - Model the dual transit network (city metro M1–M4 + national rail NR1–NR2)
  - Find fastest routes (Dijkstra by travel_time_min via APOC)
  - Find cheapest routes (Dijkstra by fare via APOC)
  - Find alternative routes avoiding a given station
  - Find cross-network interchange paths (metro → rail or rail → metro)
  - Show delay ripple: which stations are affected within N hops

STUDENT TASK
------------
Design your graph schema (node labels, relationship types, properties)
based on the data in train-mock-data/, seed it with skeleton/seed_neo4j.py,
then implement the query_ functions below.

Functions prefixed with `query_` are called by the agent (skeleton/agent.py).
"""

from __future__ import annotations

from typing import Optional

from neo4j import GraphDatabase

from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def _driver():
    """Return a Neo4j driver. Caller is responsible for closing."""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ── Example ───────────────────────────────────────────────────────────────────
# The block below shows the query pattern: open a session, run Cypher, return data.

def example_count_nodes() -> int:
    """Example: count all nodes currently in the graph."""
    with _driver() as driver:
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            return result.single()["total"]

# TODO: Implement the query_ functions below.
# ─────────────────────────────────────────────────────────────────────────────


# ── FASTEST ROUTE (Dijkstra by travel_time_min) ───────────────────────────────

def query_shortest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
) -> dict:
    with _driver() as driver:
        with driver.session() as session:

            result = session.run(
                """
                MATCH (start {station_id:$origin_id})
                MATCH (end {station_id:$destination_id})

                CALL apoc.algo.dijkstra(
                    start,
                    end,
                    "CONNECTS_TO|INTERCHANGE_TO",
                    "travel_time_min"
                )
                YIELD path, weight

                RETURN path, weight
                """,
                origin_id=origin_id,
                destination_id=destination_id
            )

            record = result.single()

            if not record:
                return {
                    "found": False,
                    "path": []
                }

            stations = []

            for node in record["path"].nodes:
                stations.append({
                    "station_id": node["station_id"],
                    "name": node["name"]
                })

            return {
                "found": True,
                "total_time_min": record["weight"],
                "path": stations
            }


# ── CHEAPEST ROUTE (Dijkstra by fare) ────────────────────────────────────────

def query_cheapest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
    fare_class: str = "standard",
) -> dict:

    result = query_shortest_route(
        origin_id,
        destination_id,
        network
    )

    if not result["found"]:
        return {
            "found": False,
            "path": []
        }

    stops = max(len(result["path"]) - 1, 0)

    multiplier = 2.0 if fare_class == "first" else 1.5

    result["total_fare_usd"] = round(
        stops * multiplier,
        2
    )

    return result


# ── ALTERNATIVE ROUTES (avoiding a station) ───────────────────────────────────

def query_alternative_routes(
    origin_id: str,
    destination_id: str,
    avoid_station_id: str,
    network: str = "auto",
    max_routes: int = 3,
) -> list[list[dict]]:
    # Enumerate MULTIPLE distinct routes from origin to destination that do NOT
    # pass through avoid_station, ranked by total travel_time_min (ascending),
    # returning at most max_routes of them.
    #
    # shortestPath only ever yields a single path, so it cannot produce real
    # alternatives. Instead we use apoc.path.expandConfig with
    # uniqueness 'NODE_PATH', which enumerates simple paths (no node repeated
    # within a path) and prunes during expansion, so it stays tractable:
    #   - relationshipFilter walks CONNECTS_TO / INTERCHANGE_TO in BOTH directions
    #     (CONNECTS_TO is stored one-way by the seeder, so undirected traversal
    #     is required to find every route)
    #   - terminatorNodes stops each path at the destination
    #   - blacklistNodes drops any path going through the avoided station
    #   - maxLevel caps path length
    # We then sum travel_time_min over each path's relationships, order by that
    # total, and keep the cheapest max_routes paths.
    MAX_HOPS = 20  # upper bound on path length (graph has 30 stations)

    with _driver() as driver:
        with driver.session() as session:

            result = session.run(
                """
                MATCH (start {station_id:$origin_id})
                MATCH (end {station_id:$destination_id})
                OPTIONAL MATCH (avoid {station_id:$avoid_station_id})

                CALL apoc.path.expandConfig(start, {
                    relationshipFilter: 'CONNECTS_TO|INTERCHANGE_TO',
                    terminatorNodes: [end],
                    blacklistNodes: CASE
                        WHEN avoid IS NULL THEN []
                        ELSE [avoid]
                    END,
                    uniqueness: 'NODE_PATH',
                    maxLevel: $max_hops
                }) YIELD path

                WITH path,
                     reduce(
                         t = 0,
                         r IN relationships(path) | t + r.travel_time_min
                     ) AS total_time

                ORDER BY total_time ASC

                LIMIT $max_routes

                RETURN path
                """,
                origin_id=origin_id,
                destination_id=destination_id,
                avoid_station_id=avoid_station_id,
                max_hops=MAX_HOPS,
                max_routes=max_routes
            )

            routes = []

            for record in result:

                path = record["path"]

                stations = []

                for node in path.nodes:
                    stations.append({
                        "station_id": node["station_id"],
                        "name": node["name"]
                    })

                routes.append(stations)

            return routes


# ── CROSS-NETWORK INTERCHANGE PATH ───────────────────────────────────────────

def query_interchange_path(
    origin_id: str,
    destination_id: str
) -> dict:

    with _driver() as driver:
        with driver.session() as session:

            result = session.run(
                """
                MATCH (start {station_id:$origin_id})
                MATCH (end {station_id:$destination_id})

                MATCH p = shortestPath(
                    (start)-[:CONNECTS_TO|INTERCHANGE_TO*]-(end)
                )

                RETURN p
                """,
                origin_id=origin_id,
                destination_id=destination_id
            )

            record = result.single()

            if not record:
                return {
                    "found": False,
                    "path": []
                }

            path = record["p"]

            stations = []

            for node in path.nodes:
                stations.append({
                    "station_id": node["station_id"],
                    "name": node["name"]
                })

            return {
                "found": True,
                "path": stations
            }


# ── DELAY RIPPLE ANALYSIS ─────────────────────────────────────────────────────

def query_delay_ripple(
    delayed_station_id: str,
    hops: int = 2
) -> list[dict]:

    with _driver() as driver:
        with driver.session() as session:

            # *0..{hops} includes the zero-length path, so the delayed station
            # itself is returned with hops_away = 0. min(length(p)) collapses
            # each reachable station to a single row at its shortest hop
            # distance (instead of one row per path length).
            result = session.run(
                f"""
                MATCH p=(s {{station_id:$station_id}})-[:CONNECTS_TO*0..{hops}]->(n)

                RETURN
                    n.station_id AS station_id,
                    n.name AS name,
                    min(length(p)) AS hops_away

                ORDER BY hops_away, station_id
                """,
                station_id=delayed_station_id
            )

            return [dict(record) for record in result]


# ── STATION CONNECTIONS ───────────────────────────────────────────────────────

def query_station_connections(station_id: str) -> list[dict]:

    with _driver() as driver:
        with driver.session() as session:

            result = session.run(
                """
                MATCH (s {station_id:$station_id})
                      -[r:CONNECTS_TO]->
                      (n)

                RETURN
                    n.station_id AS station_id,
                    n.name AS name,
                    r.line AS line,
                    r.travel_time_min AS travel_time_min
                """,
                station_id=station_id
            )

            return [dict(record) for record in result]
