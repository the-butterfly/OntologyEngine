#!/usr/bin/env python3
"""Migrate cognitive data from old KuzuDB format to new Ladybug format.

Usage:
    python scripts/migrate_kuzu_to_ladybug.py [--source PATH] [--target PATH]

Default source: ~/.ontology_engine/cognitive_db.bak.*
Default target: ~/.ontology_engine/cognitive_db

IMPORTANT: kuzu and ladybug share C++ symbols.  Importing kuzu prevents
ladybug's pybind backend from loading.  This script therefore runs the
kuzu read phase in a **subprocess** (dumping JSON to a temp file) and
the ladybug write phase in the main process.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import subprocess
import sys
import tempfile

# ── Add project root to path ─────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def find_backup_path(default_pattern: str = "~/.ontology_engine/cognitive_db.bak.*") -> str | None:
    """Find the most recent backup file."""
    pattern = os.path.expanduser(default_pattern)
    backups = sorted(glob.glob(pattern))
    return backups[-1] if backups else None


# ── Phase 1: Read from KuzuDB (runs in subprocess) ───────────────────

KUZU_READER_SCRIPT = '''
import json
import sys
import kuzu

source_path = sys.argv[1]
output_path = sys.argv[2]

db = kuzu.Database(source_path)
conn = kuzu.Connection(db)

# Read CognitiveNode
result = conn.execute("MATCH (n:CognitiveNode) RETURN n")
nodes = []
while result.has_next():
    row = result.get_next()[0]
    node = {k: v for k, v in row.items() if not k.startswith("_")}
    nodes.append(node)

# Read DispositionProfileNode
dispositions = []
try:
    result = conn.execute("MATCH (n:DispositionProfileNode) RETURN n")
    while result.has_next():
        row = result.get_next()[0]
        disp = {k: v for k, v in row.items() if not k.startswith("_")}
        dispositions.append(disp)
except Exception:
    pass

# Read edges
edge_tables = [
    "CONSOLIDATED_INTO", "COG_SUPPORTED_BY", "SUPERSEDES",
    "RELATES_TO", "SUMMARIZED_AS", "LEARNED_INTO",
    "MERGED_INTO", "INFORMS", "CO_OCCURS_WITH",
    "COGNITIVE_RELATES_TO", "FULFILLED_BY",
]
all_edges = {}
for table in edge_tables:
    try:
        result = conn.execute(f"MATCH (a)-[e:{table}]->(b) RETURN a.id AS src, b.id AS dst, e")
        edges = []
        while result.has_next():
            row = result.get_next()
            src_id = row[0]
            dst_id = row[1]
            edge_data = row[2]
            props = {k: v for k, v in edge_data.items() if not k.startswith("_")}
            edges.append({"src": src_id, "dst": dst_id, "props": props})
        if edges:
            all_edges[table] = edges
    except Exception:
        pass

data = {"nodes": nodes, "dispositions": dispositions, "edges": all_edges}
with open(output_path, "w") as f:
    json.dump(data, f)

print(f"Read {len(nodes)} nodes, {len(dispositions)} dispositions, "
      f"{sum(len(v) for v in all_edges.values())} edges")
'''


def read_kuzu_data(source_path: str) -> dict:
    """Read data from KuzuDB in a subprocess to avoid symbol conflicts with ladybug."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, "-c", KUZU_READER_SCRIPT, source_path, tmp_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            print(f"KuzuDB reader failed:\n{result.stderr}")
            sys.exit(1)
        print(result.stdout.strip())

        with open(tmp_path) as f:
            return json.load(f)
    finally:
        os.unlink(tmp_path)


# ── Phase 2: Write to Ladybug (main process) ─────────────────────────

async def write_ladybug_data(data: dict, target_path: str) -> None:
    """Write migrated data to a new Ladybug database."""
    from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore

    nodes = data["nodes"]
    dispositions = data["dispositions"]
    all_edges = data["edges"]

    print(f"\nOpening Ladybug target: {target_path}")
    store = LadybugGraphStore()
    await store.initialize(db_path=target_path)

    # ── Write CognitiveNode records ───────────────────────────────────
    print(f"\nMigrating {len(nodes)} CognitiveNode records...")
    success = 0
    failed = 0
    for i, node in enumerate(nodes):
        try:
            # Handle JSON string fields
            tags = node.get("tags", "[]")
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except (json.JSONDecodeError, TypeError):
                    tags = []
            attributes = node.get("attributes", "{}")
            if isinstance(attributes, str):
                try:
                    attributes = json.loads(attributes)
                except (json.JSONDecodeError, TypeError):
                    attributes = {}
            history = node.get("history", "[]")
            if isinstance(history, str):
                try:
                    history = json.loads(history)
                except (json.JSONDecodeError, TypeError):
                    history = []

            await store.upsert_cognitive_node(
                node_id=node["id"],
                memory_type=node.get("memory_type", "fragment"),
                cognitive_layer=node.get("cognitive_layer", "perception"),
                content=node.get("content", ""),
                content_vector=node.get("content_vector"),
                source_fragment_ids=node.get("source_fragment_ids"),
                belief_status=node.get("belief_status", "accepted"),
                ttl_seconds=node.get("ttl_seconds", 0),
                occurred_at=node.get("occurred_at"),
                extraction_hint=node.get("extraction_hint"),
                domain_id=node.get("domain_id", "default"),
                space_id=node.get("space_id", "default"),
                history=history,
                visibility=node.get("visibility", "shared"),
                created_by=node.get("created_by"),
                feedback_weight=node.get("feedback_weight", 0.5),
                confidence=node.get("confidence", 1.0),
                access_count=node.get("access_count", 0),
                last_access_at=node.get("last_access_at"),
                consolidated_at=node.get("consolidated_at"),
                schema_ref=node.get("schema_ref"),
                superseded_by=node.get("superseded_by"),
                proof_count=node.get("proof_count", 1),
                valid_from=node.get("valid_from"),
                valid_to=node.get("valid_to"),
                recorded_at=node.get("recorded_at"),
                tags=tags,
                attributes=attributes,
                confirmation_count=node.get("confirmation_count", 0),
                strength=node.get("strength", 1.0),
                entity_name=node.get("entity_name"),
                entity_type=node.get("entity_type"),
                version=node.get("version", 1),
                last_confirmed_at=node.get("last_confirmed_at"),
                consolidation_reasoning=node.get("consolidation_reasoning"),
                compiled_at=node.get("compiled_at"),
                model_domain=node.get("model_domain"),
                source_trust_tier=node.get("source_trust_tier"),
                scope=node.get("scope"),
                source_pipeline=node.get("source_pipeline"),
                source_content_hash=node.get("source_content_hash"),
            )
            success += 1
            if (i + 1) % 1000 == 0:
                print(f"  Progress: {i + 1}/{len(nodes)}")
        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  FAILED node {node.get('id', '?')}: {e}")
    print(f"  CognitiveNode: {success} succeeded, {failed} failed")

    # ── Write DispositionProfileNode records ──────────────────────────
    if dispositions:
        print(f"\nMigrating {len(dispositions)} DispositionProfileNode records...")
        for disp in dispositions:
            try:
                await store.upsert_disposition_profile(
                    node_id=disp["id"],
                    skepticism=disp.get("skepticism", 0.5),
                    evidence_demand=disp.get("evidence_demand", 0.5),
                    abstraction_preference=disp.get("abstraction_preference", 0.5),
                    thoroughness=disp.get("thoroughness", 0.5),
                    recency_bias=disp.get("recency_bias", 0.5),
                    empathy=disp.get("empathy", 0.5),
                    risk_tolerance=disp.get("risk_tolerance", 0.5),
                    scene=disp.get("scene", ""),
                    space_id=disp.get("space_id", "default"),
                )
            except Exception as e:
                print(f"  FAILED disposition {disp.get('id', '?')}: {e}")
        print(f"  DispositionProfileNode: {len(dispositions)} migrated")

    # ── Write edges ───────────────────────────────────────────────────
    if all_edges:
        print("\nMigrating edges...")
        total_edges = 0
        for table, edges in all_edges.items():
            edge_success = 0
            for edge in edges:
                try:
                    await store.create_cognitive_edge(
                        edge_type=table,
                        from_id=edge["src"],
                        to_id=edge["dst"],
                        properties=edge["props"],
                    )
                    edge_success += 1
                except Exception as e:
                    if edge_success == 0:
                        print(f"  First error in {table}: {e}")
            total_edges += edge_success
            print(f"  {table}: {edge_success}/{len(edges)} migrated")
        print(f"\nTotal edges migrated: {total_edges}")

    await store.close()
    print("\nMigration complete!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate KuzuDB cognitive data to Ladybug format")
    parser.add_argument("--source", default=None, help="Source KuzuDB path (auto-detect backup)")
    parser.add_argument("--target", default=None, help="Target Ladybug path (default: ~/.ontology_engine/cognitive_db)")
    args = parser.parse_args()

    source = args.source or find_backup_path()
    if not source:
        print("ERROR: No backup file found. Specify --source explicitly.")
        sys.exit(1)

    target = args.target or os.path.expanduser("~/.ontology_engine/cognitive_db")

    print(f"Source: {source}")
    print(f"Target: {target}")
    print()

    # Phase 1: Read from KuzuDB in subprocess
    print("Phase 1: Reading from KuzuDB...")
    data = read_kuzu_data(source)

    # Phase 2: Write to Ladybug in main process
    print("\nPhase 2: Writing to Ladybug...")
    asyncio.run(write_ladybug_data(data, target))


if __name__ == "__main__":
    main()
