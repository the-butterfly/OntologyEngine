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

    # Pre-defined query specs for mutual index relations (class-level constant)
    _MUTUAL_INDEX_QUERIES: dict[str, list[dict[str, str]]] = {
        "EXTRACTED_FROM": [
            {"rel": "EXTRACTED_FROM", "from_label": "Entity", "from_pk": "entity_id", "to_label": "Entity", "to_pk": "entity_id"},
        ],
        "SUPPORTED_BY": [
            {"rel": "SUPPORTED_BY", "from_label": "Entity", "from_pk": "entity_id", "to_label": "Entity", "to_pk": "entity_id"},
        ],
        "DEFINED_IN": [
            {"rel": "DEFINED_IN", "from_label": "Entity", "from_pk": "entity_id", "to_label": "Entity", "to_pk": "entity_id"},
            {"rel": "DEFINED_IN_FROM_METRIC", "from_label": "MetricDeclaration", "from_pk": "id", "to_label": "Entity", "to_pk": "entity_id"},
        ],
        "TRACE_TO": [
            {"rel": "TRACE_TO", "from_label": "ExecutionStepSnapshot", "from_pk": "id", "to_label": "Entity", "to_pk": "entity_id"},
        ],
    }

    def _default_path(self) -> str:
        """Return default kuzu database path."""
        base = os.path.expanduser("~/.ontology_engine/data")
        return os.path.join(base, "default", "graph.kuzu")

    async def initialize(self, db_path: str | None = None) -> None:
        """Initialize kuzu database connection.

        Args:
            db_path: Database path. Defaults to ``~/.ontology_engine/data/{space_id}/graph.kuzu``.

        Raises:
            GraphQueryError: If already initialized or kuzu not installed.
        """
        if self._initialized:
            raise GraphQueryError("KuzuGraphStore already initialized")

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
        """Create node/rel tables if they don't exist.

        Schema v2 tables:
        - Entity: core entity node table
        - ExecutionStepSnapshot: for TRACE_TO source (S-1)
        - MetricDeclaration: for DEFINED_IN source (S-2)
        - CategoryTag: categorization node
        - MetricValue: metric value node
        - Relation: general business relation edge
        - EXTRACTED_FROM / SUPPORTED_BY / DEFINED_IN / TRACE_TO: mutual index edges
        - CATEGORIZED_AS / HAS_METRIC: classification edges
        - PRECEDES / SUCCEEDS / LEADS_TO / BECAUSE_OF / ENABLES / PREVENTS / same_entity_as: temporal edges (S-5)
        """
        self._ensure_initialized()

        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS Entity(
                entity_id STRING PRIMARY KEY,
                concept STRING,
                space_id STRING,
                properties JSON
            )
        """)

        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS ExecutionStepSnapshot(
                id STRING PRIMARY KEY,
                pipeline_run_id STRING,
                step_name STRING,
                step_index INT,
                status STRING,
                started_at STRING,
                finished_at STRING,
                context_snapshot JSON,
                error_message STRING
            )
        """)

        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS MetricDeclaration(
                id STRING PRIMARY KEY,
                name STRING,
                metric_type STRING,
                value_type STRING,
                source STRING,
                formula STRING,
                domain_id STRING
            )
        """)

        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS CategoryTag(
                id STRING PRIMARY KEY,
                entity_id STRING,
                dimension_name STRING,
                value_code STRING,
                assigned_at STRING,
                assigned_by STRING,
                confidence DOUBLE
            )
        """)

        self._conn.execute("""
            CREATE NODE TABLE IF NOT EXISTS MetricValue(
                id STRING PRIMARY KEY,
                entity_id STRING,
                metric_name STRING,
                value DOUBLE,
                computed_at STRING,
                valid_from STRING,
                valid_to STRING,
                computed_by STRING,
                computation_snapshot JSON
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS Relation(
                FROM Entity TO Entity,
                relation_type STRING,
                relation_id STRING,
                properties JSON
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS EXTRACTED_FROM(
                FROM Entity TO Entity,
                edge_type STRING DEFAULT 'EXTRACTED_FROM',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS SUPPORTED_BY(
                FROM Entity TO Entity,
                edge_type STRING DEFAULT 'SUPPORTED_BY',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS DEFINED_IN(
                FROM Entity TO Entity,
                edge_type STRING DEFAULT 'DEFINED_IN',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS DEFINED_IN_FROM_METRIC(
                FROM MetricDeclaration TO Entity,
                edge_type STRING DEFAULT 'DEFINED_IN',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS TRACE_TO(
                FROM ExecutionStepSnapshot TO Entity,
                edge_type STRING DEFAULT 'TRACE_TO',
                source_file STRING,
                offset_start INT,
                offset_end INT,
                confidence DOUBLE,
                edge_text STRING,
                created_at STRING
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS CATEGORIZED_AS(
                FROM Entity TO CategoryTag,
                assigned_at STRING,
                confidence DOUBLE
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS HAS_METRIC(
                FROM Entity TO MetricValue,
                computed_at STRING,
                confidence DOUBLE
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS PRECEDES(
                FROM Entity TO Entity,
                time_delta DOUBLE,
                confidence DOUBLE
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS SUCCEEDS(
                FROM Entity TO Entity,
                time_delta DOUBLE,
                confidence DOUBLE
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS LEADS_TO(
                FROM Entity TO Entity,
                confidence DOUBLE,
                evidence STRING
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS BECAUSE_OF(
                FROM Entity TO Entity,
                confidence DOUBLE,
                evidence STRING
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS ENABLES(
                FROM Entity TO Entity,
                confidence DOUBLE,
                evidence STRING
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS PREVENTS(
                FROM Entity TO Entity,
                confidence DOUBLE,
                evidence STRING
            )
        """)

        self._conn.execute("""
            CREATE REL TABLE IF NOT EXISTS same_entity_as(
                FROM Entity TO Entity,
                confidence DOUBLE,
                source_pipeline STRING
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
            "fact_object": row["concept"],
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
        as_of: str | None = None,
        include_history: bool = False,
    ) -> list[dict[str, Any]]:
        """Get 1-hop neighbors of a node.

        Args:
            node_concept: When provided, kuzu pushes this filter into the WHERE clause
                          to avoid returning nodes that don't match the fact_object, eliminating
                          the need for post-filtering via MetaStore lookups.
            as_of: Optional point-in-time timestamp for temporal filtering.
            include_history: If true, include all historical versions.
        """
        self._ensure_initialized()

        arrow_left = ""
        arrow_right = ""
        if direction == "outgoing":
            arrow_left = "-"
            arrow_right = "->"
        elif direction == "incoming":
            arrow_left = "<-"
            arrow_right = "-"
        else:
            arrow_left = "-"
            arrow_right = "-"

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
            MATCH (src:Entity {{entity_id: '{node_id}'}}){arrow_left}{rel_match}{arrow_right}(n:Entity)
            {where_clause}
            RETURN n.entity_id AS neighbor_id, r.relation_type AS edge_type,
                   r.relation_id AS edge_id, label(r) AS rel_table,
                   n.properties AS properties
            LIMIT {limit}
        """
        result = self._conn.execute(cypher)
        df = result.get_as_df()
        if df.empty:
            return []

        import json
        filtered_rows = []
        for _, row in df.iterrows():
            if as_of and not include_history:
                props_raw = row.get("properties")
                props = json.loads(props_raw) if isinstance(props_raw, str) else (props_raw or {})
                valid_from = props.get("valid_from")
                valid_to = props.get("valid_to")
                if valid_from and valid_from > as_of:
                    continue
                if valid_to and valid_to <= as_of:
                    continue
            filtered_rows.append({
                "neighbor_id": row["neighbor_id"],
                "edge_id": row["edge_id"],
                "edge_type": row["edge_type"],
                "direction": direction if direction != "both" else "outgoing",
            })
        return filtered_rows

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
            cypher = f"""
                MATCH (src:Entity {{entity_id: $src}})-[r*1..{max_depth}]-(tgt:Entity {{entity_id: $tgt}})
                RETURN src.entity_id AS source, tgt.entity_id AS target
                LIMIT 50
            """
            result = self._conn.execute(cypher, {"src": source_id, "tgt": target_id})
        else:
            cypher = f"""
                MATCH (src:Entity {{entity_id: $src}})-[r*1..{max_depth}]-(n:Entity)
                RETURN src.entity_id AS source, n.entity_id AS target
                LIMIT 50
            """
            result = self._conn.execute(cypher, {"src": source_id})

        df = result.get_as_df()
        if df.empty:
            return []

        paths: list[list[dict[str, Any]]] = []
        for _, row in df.iterrows():
            paths.append([
                {"node_id": row["source"]},
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
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute a graph algorithm (centrality, community, etc.).

        Note: Kuzu does not have built-in graph algorithms. This method provides
        a thin wrapper around simple Cypher-based computations. For full
        algorithm support (PageRank, betweenness centrality, etc.), use
        kuzu's Python bindings directly or a dedicated graph processing library.
        """
        self._ensure_initialized()
        config = config or {}
        config.update(kwargs)

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

    # --- Schema v2 Extended Methods ---

    async def get_neighborhood(
        self,
        node_id: str,
        depth: int = 1,
        limit: int = 100,
        min_confidence: float = 0.0,
    ) -> dict[str, Any]:
        """Get neighborhood subgraph around a node.

        Args:
            node_id: Center node ID.
            depth: Traversal depth (1-3).
            limit: Max nodes to return.
            min_confidence: Minimum confidence filter on edges.

        Returns:
            Dict with "nodes" and "edges" lists.
        """
        self._ensure_initialized()
        import json

        cypher = f"""
            MATCH path = (center:Entity {{entity_id: $id}})-[r*1..{depth}]-(n)
            RETURN DISTINCT n.entity_id AS id, n.concept AS concept,
                   n.space_id AS space_id, n.properties AS properties,
                   [rel IN relationships(path) | {{
                       from_id: startNode(rel).entity_id,
                       to_id: endNode(rel).entity_id,
                       type: type(rel),
                       props: rel.properties
                   }}] AS edges
            LIMIT {limit}
        """
        result = self._conn.execute(cypher, {"id": node_id})
        df = result.get_as_df()
        if df.empty:
            return {"nodes": [], "edges": []}

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen_nodes: set[str] = {node_id}
        seen_edges: set[str] = set()

        center_result = self._conn.execute(
            "MATCH (c:Entity {entity_id: $id}) RETURN c.entity_id AS id, "
            "c.concept AS concept, c.space_id AS space_id, c.properties AS properties",
            {"id": node_id},
        )
        center_df = center_result.get_as_df()
        if not center_df.empty:
            row = center_df.iloc[0]
            nodes.append({
                "id": row["id"],
                "fact_object": row["concept"],
                "space_id": row["space_id"],
                "properties": json.loads(row["properties"]) if row["properties"] else {},
            })

        for _, row in df.iterrows():
            nid = row["id"]
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                nodes.append({
                    "id": nid,
                    "fact_object": row["concept"],
                    "space_id": row["space_id"],
                    "properties": json.loads(row["properties"]) if row["properties"] else {},
                })
            for edge_info in row.get("edges", []):
                edge_key = f"{edge_info.get('from_id')}:{edge_info.get('to_id')}:{edge_info.get('type')}"
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    props = edge_info.get("props")
                    if isinstance(props, str):
                        try:
                            props = json.loads(props)
                        except (json.JSONDecodeError, TypeError):
                            props = {}
                    confidence = (props or {}).get("confidence", 1.0)
                    if confidence >= min_confidence:
                        edges.append({
                            "from_id": edge_info.get("from_id"),
                            "to_id": edge_info.get("to_id"),
                            "type": edge_info.get("type"),
                            "properties": props or {},
                        })

        return {"nodes": nodes, "edges": edges}

    async def get_entity_at(
        self,
        fact_object: str,
        as_of: str,
        domain_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Temporal slice query: get entities at a specific point in time.

        Args:
            fact_object: Entity type filter.
            as_of: Timestamp for point-in-time query.
            domain_id: Optional domain filter.

        Returns:
            List of node records valid at the given time.
        """
        self._ensure_initialized()
        import json

        where_parts = ["n.concept = $concept"]
        params: dict[str, Any] = {"concept": fact_object}

        if domain_id:
            where_parts.append("n.space_id = $domain")
            params["domain"] = domain_id

        where = "WHERE " + " AND ".join(where_parts)
        cypher = f"""
            MATCH (n:Entity)
            {where}
            RETURN n.entity_id AS id, n.concept AS concept,
                   n.space_id AS space_id, n.properties AS properties
        """
        result = self._conn.execute(cypher, params)
        df = result.get_as_df()
        if df.empty:
            return []

        records = []
        for _, row in df.iterrows():
            props = json.loads(row["properties"]) if row["properties"] else {}
            valid_from = props.get("valid_from")
            valid_to = props.get("valid_to")
            if valid_from and valid_from > as_of:
                continue
            if valid_to and valid_to <= as_of:
                continue
            records.append({
                "id": row["id"],
                "fact_object": row["concept"],
                "space_id": row["space_id"],
                "properties": props,
            })
        return records

    async def get_edge_at(
        self,
        relation_name: str,
        as_of: str,
        min_confidence: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Temporal slice query: get edges at a specific point in time.

        Args:
            relation_name: Edge type filter.
            as_of: Timestamp for point-in-time query.
            min_confidence: Minimum confidence filter.

        Returns:
            List of edge records valid at the given time.
        """
        self._ensure_initialized()
        import json

        cypher = """
            MATCH (a:Entity)-[r:Relation {relation_type: $rtype}]->(b:Entity)
            RETURN a.entity_id AS from_id, b.entity_id AS to_id,
                   r.relation_type AS edge_type, r.relation_id AS edge_id,
                   r.properties AS properties
        """
        result = self._conn.execute(cypher, {"rtype": relation_name})
        df = result.get_as_df()
        if df.empty:
            return []

        records = []
        for _, row in df.iterrows():
            props = json.loads(row["properties"]) if row["properties"] else {}
            valid_from = props.get("valid_from")
            valid_to = props.get("valid_to")
            if valid_from and valid_from > as_of:
                continue
            if valid_to and valid_to <= as_of:
                continue
            confidence = props.get("confidence", 1.0)
            if confidence < min_confidence:
                continue
            records.append({
                "from_id": row["from_id"],
                "to_id": row["to_id"],
                "edge_type": row["edge_type"],
                "edge_id": row["edge_id"],
                "properties": props,
            })
        return records

    async def get_by_source_pipeline(
        self,
        source_pipeline: str,
        label: str | None = None,
    ) -> list[dict[str, Any]]:
        """Traceability query: get entities by source pipeline.

        Args:
            source_pipeline: Source pipeline identifier.
            label: Optional entity type filter.

        Returns:
            List of node records from the given pipeline.
        """
        self._ensure_initialized()
        import json

        where_parts = ["n.properties CONTAINS $pipeline"]
        params: dict[str, Any] = {"pipeline": source_pipeline}

        if label:
            where_parts.append("n.concept = $label")
            params["label"] = label

        where = "WHERE " + " AND ".join(where_parts)
        cypher = f"""
            MATCH (n:Entity)
            {where}
            RETURN n.entity_id AS id, n.concept AS concept,
                   n.space_id AS space_id, n.properties AS properties
        """
        result = self._conn.execute(cypher, params)
        df = result.get_as_df()
        if df.empty:
            return []

        records = []
        for _, row in df.iterrows():
            props = json.loads(row["properties"]) if row["properties"] else {}
            if props.get("source_pipeline") != source_pipeline:
                continue
            records.append({
                "id": row["id"],
                "fact_object": row["concept"],
                "space_id": row["space_id"],
                "properties": props,
            })
        return records

    async def create_mutual_index_edge(
        self,
        edge_type: str,
        from_id: str,
        to_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a mutual-index edge (EXTRACTED_FROM, SUPPORTED_BY, DEFINED_IN, TRACE_TO).

        Args:
            edge_type: One of EXTRACTED_FROM, SUPPORTED_BY, DEFINED_IN, TRACE_TO.
            from_id: Source node ID.
            to_id: Target node ID.
            properties: Edge properties (confidence, edge_text, source_file, etc.).

        Returns:
            Created edge record.
        """
        self._ensure_initialized()

        valid_types = {"EXTRACTED_FROM", "SUPPORTED_BY", "DEFINED_IN", "TRACE_TO"}
        if edge_type not in valid_types:
            raise GraphQueryError(f"Invalid mutual-index edge type: {edge_type}. Must be one of {valid_types}")

        if edge_type == "TRACE_TO":
            from_label = "ExecutionStepSnapshot"
            from_id_field = "id"
        elif edge_type == "DEFINED_IN" and from_id.startswith("metric:"):
            from_label = "MetricDeclaration"
            from_id_field = "id"
        else:
            from_label = "Entity"
            from_id_field = "entity_id"
        to_label = "Entity"
        to_id_field = "entity_id"

        rel_label = "DEFINED_IN_FROM_METRIC" if (
            edge_type == "DEFINED_IN" and from_label == "MetricDeclaration"
        ) else edge_type

        props_parts = []
        params: dict[str, Any] = {"from_id": from_id, "to_id": to_id}
        for k, v in properties.items():
            props_parts.append(f"{k}: ${k}")
            params[k] = v

        props_str = ", ".join(props_parts) if props_parts else ""

        cypher = f"""
            MATCH (a:{from_label} {{{from_id_field}: $from_id}}), (b:{to_label} {{{to_id_field}: $to_id}})
            MERGE (a)-[r:{rel_label}]->(b)
            {"SET " + props_str if props_str else ""}
            RETURN label(r) AS edge_type, a.{from_id_field} AS from_id, b.{to_id_field} AS to_id
        """
        self._conn.execute(cypher, params)
        return {
            "edge_type": edge_type,
            "from_id": from_id,
            "to_id": to_id,
            "properties": properties,
        }

    async def get_mutual_index_edges(
        self,
        node_id: str,
        edge_type: str | None = None,
        direction: str = "both",
    ) -> list[dict[str, Any]]:
        """Get mutual-index edges for a node.

        Args:
            node_id: Node ID to query.
            edge_type: Optional specific edge type filter.
            direction: "outgoing", "incoming", or "both".

        Returns:
            List of mutual-index edge records.
        """
        self._ensure_initialized()
        import json

        mutual_types = ["EXTRACTED_FROM", "SUPPORTED_BY", "DEFINED_IN", "TRACE_TO"]
        if edge_type:
            mutual_types = [edge_type]

        results: list[dict[str, Any]] = []
        for mtype in mutual_types:
            query_specs = self._MUTUAL_INDEX_QUERIES.get(mtype, [])
            for spec in query_specs:
                rel_name = spec["rel"]
                fl = spec["from_label"]
                fpk = spec["from_pk"]
                tl = spec["to_label"]
                tpk = spec["to_pk"]

                if direction in ("outgoing", "both"):
                    cypher = f"""
                        MATCH (a:{fl} {{{fpk}: $id}})-[r:{rel_name}]->(b:{tl})
                        RETURN a.{fpk} AS from_id, b.{tpk} AS to_id,
                               label(r) AS edge_type, r AS props
                    """
                    try:
                        result = self._conn.execute(cypher, {"id": node_id})
                        df = result.get_as_df()
                        for _, row in df.iterrows():
                            props = row.get("props", {})
                            if isinstance(props, str):
                                try:
                                    props = json.loads(props)
                                except (json.JSONDecodeError, TypeError):
                                    props = {}
                            results.append({
                                "from_id": row["from_id"],
                                "to_id": row["to_id"],
                                "edge_type": row["edge_type"],
                                "direction": "outgoing",
                                "properties": props if isinstance(props, dict) else {},
                            })
                    except Exception:
                        pass

                if direction in ("incoming", "both"):
                    cypher = f"""
                        MATCH (a:{fl})-[r:{rel_name}]->(b:{tl} {{{tpk}: $id}})
                        RETURN a.{fpk} AS from_id, b.{tpk} AS to_id,
                               label(r) AS edge_type, r AS props
                    """
                    try:
                        result = self._conn.execute(cypher, {"id": node_id})
                        df = result.get_as_df()
                        for _, row in df.iterrows():
                            props = row.get("props", {})
                            if isinstance(props, str):
                                try:
                                    props = json.loads(props)
                                except (json.JSONDecodeError, TypeError):
                                    props = {}
                            results.append({
                                "from_id": row["from_id"],
                                "to_id": row["to_id"],
                                "edge_type": row["edge_type"],
                                "direction": "incoming",
                                "properties": props if isinstance(props, dict) else {},
                            })
                    except Exception:
                        pass

        return results

    async def update_feedback_weight(
        self,
        entity_id: str,
        feedback: float,
        learning_rate: float = 0.1,
    ) -> None:
        """Update feedback weight for an entity (memory reinforcement).

        Uses exponential moving average:
            new_weight = (1 - lr) * old_weight + lr * feedback

        Args:
            entity_id: Entity to update.
            feedback: New feedback value (0.0 to 1.0).
            learning_rate: Learning rate for EMA.
        """
        self._ensure_initialized()
        import json

        cypher = """
            MATCH (n:Entity {entity_id: $id})
            RETURN n.properties AS props
        """
        result = self._conn.execute(cypher, {"id": entity_id})
        df = result.get_as_df()
        if df.empty:
            return

        props_str = df.iloc[0]["props"]
        props = json.loads(props_str) if props_str else {}
        old_weight = props.get("feedback_weight", 0.5)
        new_weight = (1 - learning_rate) * old_weight + learning_rate * feedback
        props["feedback_weight"] = new_weight

        self._conn.execute(
            "MATCH (n:Entity {entity_id: $id}) SET n.properties = $props",
            {"id": entity_id, "props": json.dumps(props)},
        )
