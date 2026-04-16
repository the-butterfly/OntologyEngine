#!/usr/bin/env python3
"""Migrate graph data from DuckDB to kuzu.

This script bulk-loads all entity and relation data from DuckDB into kuzu,
enabling a one-time migration from DuckDB-based graph storage to the
native kuzu graph database.

Usage:
    python scripts/migrate_graph_to_kuzu.py --db-path ~/.ontology_engine/data/default.db

The script will:
1. Load all Entity records from DuckDB
2. Load all Relation records from DuckDB
3. Batch upsert all nodes and edges into kuzu
4. Report migration statistics

After migration, kuzu will be the primary graph store for queries,
while DuckDB continues to serve entity/attribute storage.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ontology_engine.storage.duckdb import DuckDBStorage
from ontology_engine.storage.graph.kuzu_store import KuzuGraphStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def migrate_graph_data(
    duckdb_path: str,
    kuzu_db_path: str,
    batch_size: int = 1000,
    space_id: str = "default",
) -> dict[str, int]:
    """Migrate graph data from DuckDB to kuzu.

    Args:
        duckdb_path: Path to the DuckDB database file.
        kuzu_db_path: Path for the kuzu database.
        batch_size: Number of records to process per batch.
        space_id: Space identifier for the graph.

    Returns:
        Migration statistics dict.
    """
    logger.info(f"Starting migration: DuckDB={duckdb_path} -> kuzu={kuzu_db_path}")

    # Initialize storage backends
    duckdb_store = DuckDBStorage(db_path=duckdb_path)
    await duckdb_store.initialize()

    kuzu_store = KuzuGraphStore()
    await kuzu_store.initialize(db_path=kuzu_db_path)

    try:
        # Phase 1: Migrate nodes
        logger.info("Phase 1: Migrating nodes...")
        all_entities = await duckdb_store.query_entities(concept=None)

        total_nodes = len(all_entities)
        logger.info(f"Found {total_nodes} entities to migrate")

        nodes_written = 0
        for i in range(0, total_nodes, batch_size):
            batch = all_entities[i:i + batch_size]
            nodes = [
                {
                    "node_id": entity.entity_id,
                    "labels": [entity.concept],
                    "properties": {**entity.data, "space_id": space_id},
                }
                for entity in batch
            ]
            result = await kuzu_store.batch_upsert(nodes=nodes)
            nodes_written += result["nodes_written"]
            logger.info(f"Nodes progress: {nodes_written}/{total_nodes}")

        logger.info(f"Phase 1 complete: {nodes_written} nodes written")

        # Phase 2: Migrate edges
        logger.info("Phase 2: Migrating edges...")
        edges_written = 0
        total_edges = 0

        for entity in all_entities:
            relations = await duckdb_store.get_relations(entity.entity_id)
            total_edges += len(relations)

        logger.info(f"Found {total_edges} relations to migrate")

        for entity in all_entities:
            relations = await duckdb_store.get_relations(entity.entity_id)
            if not relations:
                continue

            edges = []
            for rel in relations:
                edge_id = f"{rel.from_entity_id}:{rel.to_entity_id}:{rel.relation_type}"
                edges.append({
                    "edge_id": edge_id,
                    "from_node_id": rel.from_entity_id,
                    "to_node_id": rel.to_entity_id,
                    "edge_type": rel.relation_type,
                    "properties": rel.data or {},
                })

            result = await kuzu_store.batch_upsert(edges=edges)
            edges_written += result["edges_written"]
            logger.info(f"Edges progress: {edges_written}/{total_edges}")

        logger.info(f"Phase 2 complete: {edges_written} edges written")

        # Summary
        summary = {
            "nodes_written": nodes_written,
            "edges_written": edges_written,
            "total_entities": total_nodes,
            "total_relations": total_edges,
        }
        logger.info(f"Migration complete: {summary}")
        return summary

    finally:
        await duckdb_store.close()
        await kuzu_store.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate graph data from DuckDB to kuzu"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="~/.ontology_engine/data/default.db",
        help="Path to DuckDB database (default: ~/.ontology_engine/data/default.db)",
    )
    parser.add_argument(
        "--kuzu-path",
        type=str,
        default="~/.ontology_engine/data/default/graph.kuzu",
        help="Path for kuzu database (default: ~/.ontology_engine/data/default/graph.kuzu)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Batch size for migration (default: 1000)",
    )
    parser.add_argument(
        "--space-id",
        type=str,
        default="default",
        help="Space identifier (default: default)",
    )

    args = parser.parse_args()

    # Expand user paths
    db_path = str(Path(args.db_path).expanduser())
    kuzu_path = str(Path(args.kuzu_path).expanduser())

    # Ensure kuzu parent directory exists
    kuzu_parent = Path(kuzu_path).parent
    kuzu_parent.mkdir(parents=True, exist_ok=True)

    try:
        summary = asyncio.run(migrate_graph_data(
            duckdb_path=db_path,
            kuzu_db_path=kuzu_path,
            batch_size=args.batch_size,
            space_id=args.space_id,
        ))
        print(f"\nMigration successful!")
        print(f"  Nodes written: {summary['nodes_written']}/{summary['total_entities']}")
        print(f"  Edges written: {summary['edges_written']}/{summary['total_relations']}")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
