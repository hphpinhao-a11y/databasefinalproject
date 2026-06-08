"""
TransitFlow — Neo4j Seeder
Run once after starting Docker:
    python skeleton/seed_neo4j.py

Loads station and network data from train-mock-data/:
  - metro_stations.json         — city metro stations and adjacencies
  - national_rail_stations.json — national rail stations and adjacencies

Design your graph schema (node labels, relationship types, properties)
based on the data in these files, then implement the seed() function below.
"""

import json
import os
import sys

sys.path.insert(0, ".")

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train-mock-data")
)


def _load(filename):
    with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def seed():
    metro_stations = _load("metro_stations.json")
    rail_stations  = _load("national_rail_stations.json")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:

        session.run("MATCH (n) DETACH DELETE n")
        print("  Cleared existing graph data")

        # Metro stations
        for station in metro_stations:
            session.run(
                """
                CREATE (:MetroStation {
                    station_id: $station_id,
                    name: $name
                })
                """,
                station_id=station["station_id"],
                name=station["name"]
            )

        print(f"  Created {len(metro_stations)} metro stations")

        # Rail stations
        for station in rail_stations:
            session.run(
                """
                CREATE (:RailStation {
                    station_id: $station_id,
                    name: $name
                })
                """,
                station_id=station["station_id"],
                name=station["name"]
            )

        print(f"  Created {len(rail_stations)} rail stations")

        # Metro connections
        for station in metro_stations:
            for adjacent in station["adjacent_stations"]:

                session.run(
                    """
                    MATCH (a:MetroStation {station_id:$from_id})
                    MATCH (b:MetroStation {station_id:$to_id})

                    CREATE (a)-[:CONNECTS_TO {
                        line:$line,
                        travel_time_min:$travel_time
                    }]->(b)
                    """,
                    from_id=station["station_id"],
                    to_id=adjacent["station_id"],
                    line=adjacent["line"],
                    travel_time=adjacent["travel_time_min"]
                )

        print("  Created metro connections")

        # Rail connections
        for station in rail_stations:
            for adjacent in station["adjacent_stations"]:

                session.run(
                    """
                    MATCH (a:RailStation {station_id:$from_id})
                    MATCH (b:RailStation {station_id:$to_id})

                    CREATE (a)-[:CONNECTS_TO {
                        line:$line,
                        travel_time_min:$travel_time
                    }]->(b)
                    """,
                    from_id=station["station_id"],
                    to_id=adjacent["station_id"],
                    line=adjacent["line"],
                    travel_time=adjacent["travel_time_min"]
                )

        print("  Created rail connections")

        # Interchanges
        for station in metro_stations:

            if station["is_interchange_national_rail"]:

                session.run(
                    """
                    MATCH (m:MetroStation {station_id:$metro_id})
                    MATCH (r:RailStation {station_id:$rail_id})

                    CREATE (m)-[:INTERCHANGE]->(r)
                    CREATE (r)-[:INTERCHANGE]->(m)
                    """,
                    metro_id=station["station_id"],
                    rail_id=station["interchange_national_rail_station_id"]
                )

        print("  Created interchange links")

    driver.close()
    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()
