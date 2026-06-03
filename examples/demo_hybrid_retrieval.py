#!/usr/bin/env python3
"""Demonstration of Phase 2 hybrid retrieval with supply chain finance data.

This script demonstrates:
1. Semantic search - find suppliers by text description
2. Hybrid search - combine semantic similarity with graph proximity
3. Graph pattern match - find guarantee chains

Run with: python examples/demo_hybrid_retrieval.py
Requires: pip install ontology-engine[ladybug] (optional - falls back to NetworkX)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ontology_engine.storage.base import (
    EntityInstance,
    RelationInstance,
    VectorSearchResult,
)
from ontology_engine.storage.sqlite.store import SQLiteStorage
from ontology_engine.storage.graph import NetworkXGraphStore
from ontology_engine.storage.retrieval import DefaultRetrievalBackend


# ============================================================================
# Example Data (from supply_chain_finance/instances.yaml)
# ============================================================================

ENTITIES = [
    # Core Enterprises
    EntityInstance(
        concept="CoreEnterprise",
        entity_id="CORE_001",
        data={
            "company_name": "国家电网有限公司",
            "registered_capital": {"value": 5000000000, "currency": "CNY"},
            "annual_revenue": {"value": 300000000000, "currency": "CNY"},
        },
    ),
    EntityInstance(
        concept="CoreEnterprise",
        entity_id="CORE_002",
        data={
            "company_name": "中国建筑集团有限公司",
            "registered_capital": {"value": 1000000000, "currency": "CNY"},
            "annual_revenue": {"value": 150000000000, "currency": "CNY"},
        },
    ),
    # Suppliers
    EntityInstance(
        concept="Supplier",
        entity_id="SUP_001",
        data={
            "company_name": "东方钢铁有限公司",
            "registered_capital": {"value": 50000000, "currency": "CNY"},
            "annual_revenue": {"value": 200000000, "currency": "CNY"},
            "industry_category": "C",
            "employee_count": 500,
        },
    ),
    EntityInstance(
        concept="Supplier",
        entity_id="SUP_002",
        data={
            "company_name": "华南贸易集团有限公司",
            "registered_capital": {"value": 20000000, "currency": "CNY"},
            "annual_revenue": {"value": 80000000, "currency": "CNY"},
            "industry_category": "F",
            "employee_count": 200,
        },
    ),
    EntityInstance(
        concept="Supplier",
        entity_id="SUP_003",
        data={
            "company_name": "精密机械制造厂",
            "registered_capital": {"value": 10000000, "currency": "CNY"},
            "annual_revenue": {"value": 50000000, "currency": "CNY"},
            "industry_category": "C",
            "employee_count": 100,
        },
    ),
    EntityInstance(
        concept="Supplier",
        entity_id="SUP_004",
        data={
            "company_name": "逾期应收账款管理公司",
            "registered_capital": {"value": 5000000, "currency": "CNY"},
            "annual_revenue": {"value": 10000000, "currency": "CNY"},
            "industry_category": "F",
            "employee_count": 50,
        },
    ),
]

RELATIONS = [
    # Supply relationships
    RelationInstance(
        relation_type="supplies_to",
        from_entity_id="SUP_001",
        to_entity_id="CORE_001",
        data={"transaction_amount": {"value": 10000000, "currency": "CNY"}},
    ),
    RelationInstance(
        relation_type="supplies_to",
        from_entity_id="SUP_002",
        to_entity_id="CORE_001",
        data={"transaction_amount": {"value": 5000000, "currency": "CNY"}},
    ),
    RelationInstance(
        relation_type="supplies_to",
        from_entity_id="SUP_003",
        to_entity_id="CORE_002",
        data={"transaction_amount": {"value": 3000000, "currency": "CNY"}},
    ),
    # Guarantee relationships (guarantee chain)
    RelationInstance(
        relation_type="guarantees",
        from_entity_id="SUP_001",
        to_entity_id="SUP_003",
        data={"guarantee_amount": {"value": 3000000, "currency": "CNY"}, "guarantee_type": "GUARANTEE"},
    ),
    RelationInstance(
        relation_type="guarantees",
        from_entity_id="SUP_003",
        to_entity_id="SUP_001",
        data={"guarantee_amount": {"value": 2000000, "currency": "CNY"}, "guarantee_type": "COUNTER_GUARANTEE"},
    ),
    RelationInstance(
        relation_type="guarantees",
        from_entity_id="SUP_002",
        to_entity_id="SUP_004",
        data={"guarantee_amount": {"value": 1000000, "currency": "CNY"}, "guarantee_type": "GUARANTEE"},
    ),
]


# ============================================================================
# Mock Embedder for demonstration (simulates sentence-transformers)
# ============================================================================

class MockEmbedder:
    """Simulates an embedder for demonstration purposes.

    In production, this would use sentence-transformers:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        embedding = model.encode(text)
    """

    # Pre-defined embeddings for demo data
    TEXT_EMBEDDINGS = {
        "高风险": [0.9, 0.1],
        "应收账款逾期": [0.85, 0.15],
        "优质供应商": [0.2, 0.8],
        "大规模": [0.3, 0.7],
        "制造业": [0.4, 0.6],
        "贸易": [0.6, 0.4],
        "低风险": [0.1, 0.9],
        "逾期严重": [0.95, 0.05],
    }

    def __call__(self, text: str) -> list[float]:
        """Convert text to embedding vector."""
        # Simple hash-based mock - in production use real embeddings
        import hashlib
        h = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        # Generate consistent mock vector based on text
        v1 = (h % 100) / 100.0
        v2 = 1.0 - v1
        return [v1, v2]


# ============================================================================
# Mock VectorStore for demonstration
# ============================================================================

class MockVectorStore:
    """Mock vector store for demonstration.

    In production, this would be FaissVectorStore.
    """

    def __init__(self):
        self._vectors: dict[str, list[float]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    async def initialize(self, dimension: int) -> None:
        pass

    async def close(self) -> None:
        pass

    async def add_vectors(
        self,
        ids: list[str],
        vectors: list[list[float]],
        metadata: list[dict[str, Any]] | None = None,
    ) -> None:
        for i, vid in enumerate(ids):
            self._vectors[vid] = vectors[i]
            self._metadata[vid] = metadata[i] if metadata else {}

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Simple cosine similarity search."""
        if not self._vectors:
            return []

        def cosine_sim(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            return dot / (norm_a * norm_b + 1e-9)

        scored = []
        for vid, vec in self._vectors.items():
            sim = cosine_sim(query_vector, vec)
            md = self._metadata.get(vid, {})
            if filters:
                if not all(md.get(k) == v for k, v in filters.items()):
                    continue
            scored.append(VectorSearchResult(id=vid, score=sim, metadata=md))

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]


# ============================================================================
# Demonstration
# ============================================================================

async def main():
    print("=" * 70)
    print("Phase 2 统一检索演示 - 供应链金融场景")
    print("=" * 70)

    # 1. Initialize storage backends
    print("\n[1] 初始化存储后端...")
    sqlite_store = SQLiteStorage(db_path=":memory:")
    await sqlite_store.initialize()

    graph_store = NetworkXGraphStore()
    await graph_store.initialize()

    vector_store = MockVectorStore()
    await vector_store.initialize(dimension=2)

    # 2. Load example data into DuckDB
    print("\n[2] 加载实体数据到 DuckDB...")
    for entity in ENTITIES:
        await sqlite_store.save_entity(entity)
    print(f"    已加载 {len(ENTITIES)} 个实体")

    # 3. Load example data into Graph Store
    print("\n[3] 加载关系数据到图存储...")
    for rel in RELATIONS:
        await sqlite_store.save_relation(rel)
        await graph_store.upsert_node(
            node_id=rel.from_entity_id,
            labels=["Supplier" if rel.from_entity_id.startswith("SUP") else "CoreEnterprise"],
            properties={},
        )
        await graph_store.upsert_node(
            node_id=rel.to_entity_id,
            labels=["Supplier" if rel.to_entity_id.startswith("SUP") else "CoreEnterprise"],
            properties={},
        )
        edge_id = f"{rel.from_entity_id}:{rel.to_entity_id}:{rel.relation_type}"
        await graph_store.upsert_edge(
            edge_id=edge_id,
            from_node_id=rel.from_entity_id,
            to_node_id=rel.to_entity_id,
            edge_type=rel.relation_type,
            properties=rel.data or {},
        )
    print(f"    已加载 {len(RELATIONS)} 条关系")

    # 4. Load vector embeddings
    print("\n[4] 加载向量数据...")
    mock_embedder = MockEmbedder()
    for entity in ENTITIES:
        # Create mock semantic description for each entity
        if entity.concept == "Supplier":
            if "逾期" in entity.data.get("company_name", "") or entity.entity_id == "SUP_004":
                text_desc = "高风险 应收账款逾期 逾期严重"
            elif entity.data.get("annual_revenue", {}).get("value", 0) > 100000000:
                text_desc = "优质供应商 大规模 制造业"
            else:
                text_desc = "供应商 中等规模"
        else:
            text_desc = "核心企业 大规模"

        vector = mock_embedder(text_desc)
        await vector_store.add_vectors(
            ids=[entity.entity_id],
            vectors=[vector],
            metadata=[{"concept_type": entity.concept, "company_name": entity.data.get("company_name", "")}],
        )
    print(f"    已加载 {len(ENTITIES)} 个向量")

    # 5. Initialize retrieval backend
    print("\n[5] 初始化检索后端...")
    retrieval = DefaultRetrievalBackend(
        storage=sqlite_store,
        graph_store=graph_store,
        vector_store=vector_store,
        embedder=mock_embedder,
    )
    print("    DefaultRetrievalBackend 初始化完成")

    # =========================================================================
    # DEMO 1: Semantic Search
    # =========================================================================
    print("\n" + "=" * 70)
    print("演示 1: 语义检索 (Semantic Search)")
    print("=" * 70)
    print("\n查询文本: '应收账款逾期严重的供应商'")
    print("预期: 找到 SUP_004 (逾期应收账款管理公司)")

    results = await retrieval.semantic_search(
        query_text="应收账款逾期严重",
        concept_type="Supplier",
        top_k=5,
    )

    print(f"\n结果数量: {len(results)}")
    for r in results:
        meta = r.metadata
        print(f"  - {r.id} ({meta.get('company_name', 'N/A')})")
        print(f"    concept: {meta.get('concept_type', 'N/A')}")
        print(f"    语义相似度: {r.score:.4f}")

    # =========================================================================
    # DEMO 2: Hybrid Search with Graph Expansion
    # =========================================================================
    print("\n" + "=" * 70)
    print("演示 2: 混合检索 (Hybrid Search) - 语义 + 图扩展")
    print("=" * 70)
    print("\n查询: 语义='高风险', 图扩展起点=SUP_001 (东方钢铁)")
    print("预期: 结合语义相似度和图邻接关系进行融合排序")

    result = await retrieval.hybrid_search(
        query_text="高风险",
        graph_seed_id="SUP_001",
        top_k=10,
        semantic_weight=0.6,
        graph_weight=0.4,
        fusion_strategy="independent_then_fuse",
    )

    print(f"\n融合结果 ({result.fusion_metadata['strategy']}):")
    print(f"  语义候选数: {result.fusion_metadata['semantic_candidates']}")
    print(f"  图扩展候选数: {result.fusion_metadata['graph_candidates']}")
    print(f"  总候选数: {result.fusion_metadata['candidate_count']}")
    print(f"\n融合权重: semantic={result.fusion_metadata['weights']['semantic']}, "
          f"graph={result.fusion_metadata['weights']['graph']}")

    print(f"\n最终结果 (top {len(result.results)}):")
    for r in result.results:
        sem_score = result.semantic_scores.get(r.id, 0.0)
        graph_score = result.graph_scores.get(r.id, 0.0)
        print(f"  - {r.id}: 最终得分={r.score:.4f} (语义={sem_score:.4f}, 图={graph_score:.4f})")

    # =========================================================================
    # DEMO 3: Hybrid Search with Path Pattern
    # =========================================================================
    print("\n" + "=" * 70)
    print("演示 3: 混合检索 + 路径模式 (Hybrid Search with Path Pattern)")
    print("=" * 70)
    print("\n查询: 语义='供应商', 图扩展起点=CORE_001, 路径模式=[('supplies_to', 'Supplier')]")
    print("预期: 找向 CORE_001 供货的供应商，融合语义和路径匹配得分")

    result = await retrieval.hybrid_search(
        query_text="供应商",
        graph_seed_id="CORE_001",
        path_pattern=[("supplies_to", "Supplier")],
        top_k=10,
        semantic_weight=0.5,
        graph_weight=0.3,
        path_weight=0.2,
        fusion_strategy="independent_then_fuse",
    )

    print(f"\n结果:")
    print(f"  路径候选数: {result.fusion_metadata['path_candidates']}")
    for r in result.results:
        sem_score = result.semantic_scores.get(r.id, 0.0)
        graph_score = result.graph_scores.get(r.id, 0.0)
        path_score = result.path_match_scores.get(r.id, 0.0)
        print(f"  - {r.id}: 得分={r.score:.4f} (语义={sem_score:.4f}, 图={graph_score:.4f}, 路径={path_score:.4f})")

    # =========================================================================
    # DEMO 4: Graph Pattern Match - Find Guarantee Chains
    # =========================================================================
    print("\n" + "=" * 70)
    print("演示 4: 图模式匹配 (Graph Pattern Match) - 担保链查询")
    print("=" * 70)
    print("\n模式: Company -(guarantees)-> Company")
    print("场景: 查找所有存在担保关系的企业对")

    results = await retrieval.graph_pattern_match(
        start_concept="Supplier",
        path_pattern=[("guarantees", "Supplier")],
        limit=50,
    )

    print(f"\n找到 {len(results)} 条担保关系:")
    for path in results:
        if len(path["nodes"]) >= 2:
            src = path["nodes"][0]["entity_id"]
            tgt = path["nodes"][1]["entity_id"]
            rel = path["edges"][0]["relation_type"] if path["edges"] else "N/A"
            print(f"  - {src} --[{rel}]--> {tgt}")

    # =========================================================================
    # DEMO 5: Complex Path Pattern - Multi-hop Guarantee Chain
    # =========================================================================
    print("\n" + "=" * 70)
    print("演示 5: 多跳路径模式 (Multi-hop Pattern)")
    print("=" * 70)
    print("\n模式: Supplier -(guarantees)-> Supplier -(guarantees)-> Supplier")
    print("场景: 查找担保链深度为2的供应商 (A担保B, B担保C)")

    results = await retrieval.graph_pattern_match(
        start_concept="Supplier",
        path_pattern=[
            ("guarantees", "Supplier"),
            ("guarantees", "Supplier"),
        ],
        limit=50,
    )

    print(f"\n找到 {len(results)} 条长度为2跳的担保链:")
    for path in results:
        if len(path["nodes"]) >= 3:
            n0 = path["nodes"][0]["entity_id"]
            n1 = path["nodes"][1]["entity_id"]
            n2 = path["nodes"][2]["entity_id"]
            print(f"  - {n0} --> {n1} --> {n2}")

    # =========================================================================
    # DEMO 6: Filter-Then-Fuse Strategy
    # =========================================================================
    print("\n" + "=" * 70)
    print("演示 6: 融合策略对比 - filter_then_fuse vs independent_then_fuse")
    print("=" * 70)

    result_filter = await retrieval.hybrid_search(
        query_text="供应商",
        graph_seed_id="CORE_001",
        path_pattern=[("supplies_to", "Supplier")],
        top_k=5,
        semantic_weight=0.5,
        graph_weight=0.3,
        path_weight=0.2,
        fusion_strategy="filter_then_fuse",
    )

    result_independent = await retrieval.hybrid_search(
        query_text="供应商",
        graph_seed_id="CORE_001",
        path_pattern=[("supplies_to", "Supplier")],
        top_k=5,
        semantic_weight=0.5,
        graph_weight=0.3,
        path_weight=0.2,
        fusion_strategy="independent_then_fuse",
    )

    print("\n策略: filter_then_fuse")
    print("  (先按路径模式过滤候选集, 再与语义融合)")
    for r in result_filter.results:
        print(f"  - {r.id}: 得分={r.score:.4f}")

    print("\n策略: independent_then_fuse")
    print("  (语义/图/路径各自独立打分, 再加权融合)")
    for r in result_independent.results:
        print(f"  - {r.id}: 得分={r.score:.4f}")

    # Cleanup
    await sqlite_store.close()
    await graph_store.close()
    await vector_store.close()

    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
