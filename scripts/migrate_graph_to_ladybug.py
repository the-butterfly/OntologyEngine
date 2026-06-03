#!/usr/bin/env python3
"""Migrate graph data from SQLite to ladybug.

This script bulk-loads all entity and relation data from SQLite into ladybug,
enabling a one-time migration from SQLite-based graph storage to the
native ladybug graph database.

Usage:
    python scripts/migrate_graph_to_ladybug.py --db-path ~/.ontology_engine/data/meta.db

The script will:
1. Load all Entity records from SQLite
2. Load all Relation records from SQLite
3. Batch upsert all nodes and edges into ladybug
4. Report migration statistics

After migration, ladybug will be the primary graph store for queries,
while SQLite continues to serve entity/attribute storage.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ontology_engine.storage.sqlite.store import SQLiteStorage
from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def migrate_graph_data(
    sqlite_path: str,
    ladybug_db_path: str,
    batch_size: int = 1000,
    space_id: str = "default",
) -> dict[str, int]:
    """Migrate graph data from SQLite to ladybug.

    Args:
        sqlite_path: Path to the SQLite database file.
        ladybug_db_path: Path for the ladybug database.
        batch_size: Number of records to process per batch.
        space_id: Space identifier for the graph.

    Returns:
        Migration statistics dict.
    """
    logger.info(f"Starting migration: SQLite={sqlite_path} -> ladybug={ladybug_db_path}")

    sqlite_store = SQLiteStorage(db_path=sqlite_path)
    await sqlite_store.initialize()

    ladybug_store = LadybugGraphStore()
    await ladybug_store.initialize(db_path=ladybug_db_path)

    try:
        logger.info("Phase 1: Migrating nodes...")
        all_entities = await sqlite_store.query_entities(fact_object=None)

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
            result = await ladybug_store.batch_upsert(nodes=nodes)
            nodes_written += result["nodes_written"]
            logger.info(f"Nodes progress: {nodes_written}/{total_nodes}")

        logger.info(f"Phase 1 complete: {nodes_written} nodes written")

        logger.info("Phase 2: Migrating edges...")
        edges_written = 0
        total_edges = 0

        for entity in all_entities:
            relations = await sqlite_store.get_relations(entity.entity_id)
            total_edges += len(relations)

        logger.info(f"Found {total_edges} relations to migrate")

        for entity in all_entities:
            relations = await sqlite_store.get_relations(entity.entity_id)
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

            result = await ladybug_store.batch_upsert(edges=edges)
            edges_written += result["edges_written"]
            logger.info(f"Edges progress: {edges_written}/{total_edges}")

        logger.info(f"Phase 2 complete: {edges_written} edges written")

        summary = {
            "nodes_written": nodes_written,
            "edges_written": edges_written,
            "total_entities": total_nodes,
            "total_relations": total_edges,
        }
        logger.info(f"Migration complete: {summary}")
        return summary

    finally:
        await sqlite_store.close()
        await ladybug_store.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate graph data from SQLite to ladybug"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="~/.ontology_engine/data/meta.db",
        help="Path to SQLite database (default: ~/.ontology_engine/data/meta.db)",
    )
    parser.add_argument(
        "--ladybug-path",
        type=str,
        default="~/.ontology_engine/data/default/graph.ladybug",
        help="Path for ladybug database (default: ~/.ontology_engine/data/default/graph.ladybug)",
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

    db_path = str(Path(args.db_path).expanduser())
    ladybug_path = str(Path(args.ladybug_path).expanduser())

    ladybug_parent = Path(ladybug_path).parent
    ladybug_parent.mkdir(parents=True, exist_ok=True)

    try:
        summary = asyncio.run(migrate_graph_data(
            sqlite_path=db_path,
            ladybug_db_path=ladybug_path,
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
