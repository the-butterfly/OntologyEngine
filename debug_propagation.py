"""Debug: Check CONSOLIDATED_INTO edge query."""
import asyncio
import tempfile
import shutil
from pathlib import Path

from ontology_engine.engine.cognitive.models import CognitiveEdge
from ontology_engine.engine.cognitive.repository import CognitiveRepository
from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore


async def debug():
    tmpdir = tempfile.mkdtemp(prefix="debug_")
    db_path = str(Path(tmpdir) / "cognitive")
    try:
        store = LadybugGraphStore()
        await store.initialize(db_path)
        repo = CognitiveRepository(store)

        from ontology_engine.engine.cognitive.models import CognitiveNode
        node_a = CognitiveNode(id="node_a", memory_type="fragment", cognitive_layer="perception", content="test A", domain_id="test", space_id="test")
        node_b = CognitiveNode(id="node_b", memory_type="observation", cognitive_layer="semantic", content="test B", domain_id="test", space_id="test")
        await repo.create_node(node_a)
        await repo.create_node(node_b)

        # Create CONSOLIDATED_INTO edge
        edge = CognitiveEdge(edge_type="CONSOLIDATED_INTO", from_id="node_a", to_id="node_b")
        await repo.create_cognitive_edge(edge)
        print("CONSOLIDATED_INTO edge created")

        # Query all edges
        all_edges = await repo.query_cognitive_edges(from_id="node_a", limit=50)
        print(f"All edges from node_a: {len(all_edges)}")
        for e in all_edges:
            print(f"  {e.edge_type}: {e.from_id} -> {e.to_id}")

        # Query CONSOLIDATED_INTO specifically
        ci_edges = await repo.query_cognitive_edges(from_id="node_a", edge_type="CONSOLIDATED_INTO", limit=10)
        print(f"CONSOLIDATED_INTO edges: {len(ci_edges)}")

        # Direct Cypher query
        try:
            result_set = store._conn.execute("MATCH (a:CognitiveNode)-[r:CONSOLIDATED_INTO]->(b:CognitiveNode) RETURN a.id, b.id, r.consolidated_at")
            while result_set.has_next():
                row = result_set.get_next()
                print(f"  Direct query: {row[0]} -> {row[1]}, consolidated_at={row[2]}")
        except Exception as e:
            print(f"Direct query with consolidated_at FAILED: {e}")

        try:
            result_set = store._conn.execute("MATCH (a:CognitiveNode)-[r:CONSOLIDATED_INTO]->(b:CognitiveNode) RETURN a.id, b.id, r.created_at")
            while result_set.has_next():
                row = result_set.get_next()
                print(f"  Direct query with created_at: {row[0]} -> {row[1]}, created_at={row[2]}")
        except Exception as e:
            print(f"Direct query with created_at FAILED: {e}")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


asyncio.run(debug())
