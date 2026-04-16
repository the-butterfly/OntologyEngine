"""Kuzu-based graph store for production use.

Provides persistent graph storage with native Cypher support.
Requires ``kuzu`` Python binding (``pip install kuzu``).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ontology_engine.storage.base import GraphQueryError, GraphStoreBackend

logger = logging.getLogger(__name__)


class KuzuGraphStore(GraphStoreBackend):
    """Kuzu-based graph store.

    Data model:
    - Nodes: stored in ``Entity`` table (entity_id, concept, space_id, properties)
    - Edges: stored in ``Relation`` table (from, to, relation_type, relation_id, properties)

    Default database path: ``~/.ontology_engine/data/{space_id}/graph.kuzu``
    """

    def __init__(self) -> None:
        self._db: Any | None = None  # kuzu.Database
        self._conn: Any | None = None  # kuzu.Connection
        self._initialized = False

    def _default_path(self) -> str:
        """Return default kuzu database path."""
        base = os.path.expanduser("~/.ontology_engine/data")
        return os.path.join(base, "default", "graph.kuzu")

    async def initialize(self, db_path: str | None = None) -> None:
        """Initialize kuzu database connection.

        Args:
            db_path: Database path. Defaults to ``~/.ontology_engine/data/{space_id}/graph.kuzu``.
        """
        try:
            import kuzu
        except ImportError as exc:
            raise GraphQueryError(
                "kuzu is not installed. Install with: pip install ontology-engine[kuzu]"
            ) from exc

        path = db_path or self._default_path()
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

        self._db = kuzu.Database(path)
        self._conn = kuzu.Connection(self._db)
        self._initialized = True
        await self._ensure_schema()
        logger.info("Kuzu graph store initialized at %s", path)

    async def _ensure_schema(self) -> None:
        """Create node/rel tables if they don't exist."""
        self._ensure_initialized()

        # Create Entity node table
        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Entity(
                entity_id STRING PRIMARY KEY,
                concept STRING NOT NULL,
                space_id STRING NOT NULL,
                properties JSON
            )
        """)

        # Create Relation rel table
        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS Relation(
                FROM Entity TO Entity,
                relation_type STRING NOT NULL,
                relation_id STRING,
                properties JSON,
                PRIMARY KEY(FROM, TO, relation_type)
            )
        """)

    def _ensure_initialized(self) -> None:
        if not self._initialized or self._conn is None:
            raise GraphQueryError(
                "KuzuGraphStore not initialized. Call initialize() first."
            )

    async def close(self) -> None:
        """Close database connection."""
        if self._db is not None:
            self._db.close()
        self._db = None
        self._conn = None
        self._initialized = False

    # --- Node Management ---

    async def upsert_node(
        self,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any],
    ) -> None:
        """Create or update a node."""
        self._ensure_initialized()
        import json

        concept = labels[0] if labels else "Unknown"
        space_id = properties.get("space_id", "default")
        props_json = json.dumps(properties)

        self._conn.execute(
            "MERGE (n:Entity {entity_id: $id}) SET n.concept = $concept, "
            "n.space_id = $space_id, n.properties = $props",
            {"id": node_id, "concept": concept, "space_id": space_id, "props": props_json},
        )

    async def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Get a single node by ID."""
        self._ensure_initialized()
        result = self._conn.execute(
            "MATCH (n:Entity {entity_id: $id}) RETURN n.entity_id AS id, "
            "n.concept AS concept, n.space_id AS space_id, n.properties AS properties",
            {"id": node_id},
        )
        df = result.get_as_df()
        if df.empty:
            return None
        row = df.iloc[0]
        import json

        return {
            "id": row["id"],
            "concept": row["concept"],
            "space_id": row["space_id"],
            "properties": json.loads(row["properties"]) if row["properties"] else {},
        }

    async def delete_node(self, node_id: str) -> None:
        """Delete a node and all its edges."""
        self._ensure_initialized()
        self._conn.execute(
            "MATCH (n:Entity {entity_id: $id}) DELETE n",
            {"id": node_id},
        )

    # --- Edge Management ---

    async def upsert_edge(
        self,
        edge_id: str,
        from_node_id: str,
        to_node_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create or update an edge."""
        self._ensure_initialized()
        import json

        props_json = json.dumps(properties or {})
        self._conn.execute(
            "MATCH (a:Entity {entity_id: $from}), (b:Entity {entity_id: $to}) "
            "CREATE (a)-[r:Relation {relation_type: $rtype, relation_id: $eid, "
            "properties: $props}]->(b)",
            {
                "from": from_node_id,
                "to": to_node_id,
                "rtype": edge_type,
                "eid": edge_id,
                "props": props_json,
            },
        )

    async def get_edges(
        self,
        from_node_id: str | None = None,
        to_node_id: str | None = None,
        edge_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query edges."""
        self._ensure_initialized()
        import json

        where_clauses = []
        params: dict[str, Any] = {}

        if from_node_id is not None:
            where_clauses.append("a.entity_id = $from")
            params["from"] = from_node_id
        if to_node_id is not None:
            where_clauses.append("b.entity_id = $to")
            params["to"] = to_node_id
        if edge_type is not None:
            where_clauses.append("r.relation_type = $rtype")
            params["rtype"] = edge_type

        where = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        query = f"""
            MATCH (a:Entity)-[r:Relation]->(b:Entity)
            {where}
            RETURN a.entity_id AS from_node_id, b.entity_id AS to_node_id,
                   r.relation_type AS edge_type, r.relation_id AS edge_id,
                   r.properties AS properties
        """
        result = self._conn.execute(query, params)
        df = result.get_as_df()
        if df.empty:
            return []
        return [
            {
                "from_node_id": row["from_node_id"],
                "to_node_id": row["to_node_id"],
                "edge_type": row["edge_type"],
                "edge_id": row["edge_id"],
                "properties": json.loads(row["properties"]) if row["properties"] else {},
            }
            for _, row in df.iterrows()
        ]

    async def delete_edge(self, edge_id: str) -> None:
        """Delete an edge."""
        self._ensure_initialized()
        self._conn.execute(
            "MATCH (a:Entity)-[r:Relation {relation_id: $eid}]->(b:Entity) DELETE r",
            {"eid": edge_id},
        )

    # --- Graph Queries ---

    async def get_neighbors(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "outgoing",
        limit: int = 100,
        filter_props: dict[str, Any] | None = None,
        node_concept: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get 1-hop neighbors of a node.

        Args:
            node_concept: When provided, kuzu pushes this filter into the WHERE clause
                          to avoid returning nodes that don't match the concept, eliminating
                          the need for post-filtering via DuckDB lookups.
        """
        self._ensure_initialized()

        arrow = {
            "outgoing": "->",
            "incoming": "<-",
            "both": "-",
        }[direction]

        rel_match = (
            f"[r:Relation {{relation_type: '{edge_type}'}}]"
            if edge_type
            else "[r:Relation]"
        )
        where_parts = []
        if node_concept:
            where_parts.append(f"n.concept = '{node_concept}'")
        if filter_props:
            for k, v in filter_props.items():
                where_parts.append(f"n.{k} = '{v}'")
        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        cypher = f"""
            MATCH (src:Entity {{entity_id: '{node_id}'}}){arrow}{rel_match}{arrow}(n:Entity)
            {where_clause}
            RETURN n.entity_id AS neighbor_id, r.relation_type AS edge_type,
                   r.relation_id AS edge_id, type(r) AS rel_table
            LIMIT {limit}
        """
        result = self._conn.execute(cypher)
        df = result.get_as_df()
        if df.empty:
            return []
        return [
            {
                "neighbor_id": row["neighbor_id"],
                "edge_id": row["edge_id"],
                "edge_type": row["edge_type"],
                "direction": direction if direction != "both" else "outgoing",
            }
            for _, row in df.iterrows()
        ]

    async def find_paths(
        self,
        source_id: str,
        target_id: str | None = None,
        max_depth: int = 3,
        edge_types: list[str] | None = None,
    ) -> list[list[dict[str, Any]]]:
        """Find paths between nodes."""
        self._ensure_initialized()

        if target_id:
            # Find all simple paths up to max_depth
            rel_constraint = ""
            if edge_types:
                type_list = " | ".join(f"r{i}.relation_type = '{et}'" for i, et in enumerate(edge_types))
                rel_constraint = f" WHERE {type_list}"

            cypher = f"""
                MATCH path = (src:Entity {{entity_id: '$src'}})-{rel_constraint}*1..{max_depth}-
                (tgt:Entity {{entity_id: '$tgt'}})
                RETURN path
                LIMIT 50
            """
            result = self._conn.execute(cypher, {"src": source_id, "tgt": target_id})
        else:
            # BFS from source
            cypher = f"""
                MATCH (src:Entity {{entity_id: '$src'}})-[r*1..{max_depth}]-(n:Entity)
                RETURN src.entity_id AS source, n.entity_id AS target,
                       [rel IN r | rel.relation_type] AS edge_types
                LIMIT 50
            """
            result = self._conn.execute(cypher, {"src": source_id})

        df = result.get_as_df()
        if df.empty:
            return []

        paths: list[list[dict[str, Any]]] = []
        for _, row in df.iterrows():
            if "path" in row:
                # Full path objects from Cypher
                path_obj = row["path"]
                nodes = [dict(n) for n in path_obj.nodes]
                edges = [dict(r) for r in path_obj.rels]
                paths.append(nodes + [{"_edge": edges}])
            else:
                # Simplified result
                paths.append([
                    {"node_id": row["source"]},
                    {"edge_types": row.get("edge_types", [])},
                    {"node_id": row["target"]},
                ])
        return paths

    async def detect_cycles(
        self,
        center_id: str,
        edge_types: list[str] | None = None,
        max_depth: int = 10,
    ) -> list[list[str]]:
        """Detect cycles starting from a node."""
        self._ensure_initialized()
        rel_constraint = ""
        if edge_types:
            types = " | ".join(f"'{et}'" for et in edge_types)
            rel_constraint = f":Relation WHERE r.relation_type IN [{types}]"
        else:
            rel_constraint = ":Relation"

        cypher = f"""
            MATCH cycle = (center:Entity {{entity_id: '$cid'}})-{rel_constraint}*2..{max_depth}-
            (center)
            RETURN [node IN nodes(cycle) | node.entity_id] AS cycle
            LIMIT 50
        """
        result = self._conn.execute(cypher, {"cid": center_id})
        df = result.get_as_df()
        if df.empty:
            return []
        return [list(row["cycle"]) for _, row in df.iterrows()]

    async def execute_cypher(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query (advanced interface).

        This is the primary escape hatch for complex graph patterns that are
        better expressed in Cypher than as a series of ``get_neighbors`` calls.

        Args:
            query: Cypher query string.
            parameters: Query parameters dict.

        Returns:
            List of result rows as dicts.
        """
        self._ensure_initialized()
        import json

        result = self._conn.execute(query, parameters or {})
        df = result.get_as_df()
        if df.empty:
            return []
        # Convert JSON columns back to dicts
        records = []
        for _, row in df.iterrows():
            record = dict(row)
            for k, v in record.items():
                if isinstance(v, str) and v.startswith("{"):
                    try:
                        record[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        pass
            records.append(record)
        return records

    # --- Graph Algorithms ---

    async def compute_graph_metric(
        self,
        algorithm: str,
        node_id: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a graph algorithm (centrality, community, etc.).

        Note: Kuzu does not have built-in graph algorithms. This method provides
        a thin wrapper around simple Cypher-based computations. For full
        algorithm support (PageRank, betweenness centrality, etc.), use
        kuzu's Python bindings directly or a dedicated graph processing library.
        """
        self._ensure_initialized()
        config = config or {}

        if algorithm == "centrality":
            metric = config.get("metric", "degree")
            if metric == "degree":
                cypher = """
                    MATCH (n:Entity)-[r:Relation]->(m:Entity)
                    WITH n.entity_id AS node, count(r) AS degree
                    RETURN node, degree
                    ORDER BY degree DESC
                    LIMIT 100
                """
                result = self._conn.execute(cypher)
                df = result.get_as_df()
                if node_id:
                    row = df[df["node"] == node_id]
                    return {"algorithm": "centrality", "metric": "degree", "node_id": node_id, "value": int(row["degree"].iloc[0]) if not row.empty else 0}
                return {"algorithm": "centrality", "metric": "degree", "values": {r["node"]: int(r["degree"]) for _, r in df.iterrows()}}

        elif algorithm == "component":
            # Weakly connected components via label propagation
            cypher = """
                MATCH (n:Entity)
                WITH collect(n.entity_id) AS nodes
                UNWIND nodes AS a
                UNWIND nodes AS b
                WITH a, b WHERE a <> b
                MATCH path = (a:Entity {entity_id: a})-[*0..2]-(b:Entity {entity_id: b})
                WITH a, collect(DISTINCT b) AS reachable
                RETURN a AS node, size(reachable) AS component_size
            """
            result = self._conn.execute(cypher)
            df = result.get_as_df()
            return {"algorithm": "component", "component_count": int(df["component_size"].max()) if not df.empty else 0}

        elif algorithm == "community":
            # Simple community detection via connected components
            cypher = """
                MATCH (n:Entity)
                OPTIONAL MATCH (n)-[r]-()
                WITH n.entity_id AS node, count(r) AS degree
                RETURN node, degree
                ORDER BY degree DESC
                LIMIT 100
            """
            result = self._conn.execute(cypher)
            df = result.get_as_df()
            return {"algorithm": "community", "community_count": len(df)}

        else:
            raise GraphQueryError(f"Unknown graph algorithm: {algorithm}")

        return {"algorithm": algorithm}

    # --- Batch Operations ---

    async def batch_upsert(
        self,
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
    ) -> dict[str, int]:
        """Batch write nodes and edges.

        Returns:
            {"nodes_written": N, "edges_written": M}
        """
        self._ensure_initialized()
        nodes_written = 0
        edges_written = 0

        if nodes:
            for node in nodes:
                await self.upsert_node(
                    node_id=node["node_id"],
                    labels=node.get("labels", []),
                    properties=node.get("properties", {}),
                )
                nodes_written += 1

        if edges:
            for edge in edges:
                await self.upsert_edge(
                    edge_id=edge["edge_id"],
                    from_node_id=edge["from_node_id"],
                    to_node_id=edge["to_node_id"],
                    edge_type=edge["edge_type"],
                    properties=edge.get("properties"),
                )
                edges_written += 1

        return {"nodes_written": nodes_written, "edges_written": edges_written}
