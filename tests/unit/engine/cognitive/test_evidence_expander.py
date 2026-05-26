"""Unit tests for EvidenceExpander deep module."""

from __future__ import annotations

import pytest

from ontology_engine.engine.cognitive.evidence_expander import EvidenceExpander, EvidenceItem
from ontology_engine.engine.cognitive.errors import CognitiveNodeNotFoundError, EvidenceExpansionError
from ontology_engine.engine.cognitive.models import CognitiveNode
from ontology_engine.storage.models import CognitiveEdge


def _make_node(
    node_id: str = "mem:entity:test1",
    memory_type: str = "entity",
    content: str = "test content",
    source_fragment_ids: list[str] | None = None,
    **kwargs,
) -> CognitiveNode:
    return CognitiveNode(
        id=node_id,
        memory_type=memory_type,
        cognitive_layer=kwargs.get("cognitive_layer", "semantic"),
        content=content,
        space_id=kwargs.get("space_id", "default"),
        source_fragment_ids=source_fragment_ids or [],
        **{k: v for k, v in kwargs.items() if k not in {"cognitive_layer", "space_id"}},
    )


class MockRepository:
    def __init__(
        self,
        nodes: dict[str, CognitiveNode] | None = None,
        edges: list[CognitiveEdge] | None = None,
    ):
        self._nodes = nodes or {}
        self._edges = edges or []
        self.get_node_calls: list[str] = []

    async def get_node(self, node_id: str) -> CognitiveNode | None:
        self.get_node_calls.append(node_id)
        return self._nodes.get(node_id)

    async def query_cognitive_edges(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
        edge_type: str | None = None,
        limit: int = 100,
    ) -> list[CognitiveEdge]:
        results = []
        for e in self._edges:
            if from_id and e.from_id != from_id:
                continue
            if to_id and e.to_id != to_id:
                continue
            if edge_type and e.edge_type != edge_type:
                continue
            results.append(e)
            if len(results) >= limit:
                break
        return results


class TestEvidenceItem:
    def test_default_values(self):
        item = EvidenceItem(doc_id="n1", content="hello")
        assert item.source == "unknown"
        assert item.memory_type == "fragment"
        assert item.edge_type == "SUPPORTS"
        assert item.confidence == 1.0
        assert item.contribution == 0.5

    def test_custom_values(self):
        item = EvidenceItem(
            doc_id="n1", content="hello",
            source="cog_supported_by", memory_type="entity",
            edge_type="COG_SUPPORTED_BY", confidence=0.8, contribution=0.3,
        )
        assert item.source == "cog_supported_by"
        assert item.confidence == 0.8


class TestEvidenceExpanderStrategy1:
    @pytest.mark.asyncio
    async def test_node_not_found_raises(self):
        repo = MockRepository()
        expander = EvidenceExpander(repo)
        with pytest.raises(CognitiveNodeNotFoundError):
            await expander.expand("nonexistent", "default")

    @pytest.mark.asyncio
    async def test_cog_supported_by_returns_evidence(self):
        source = _make_node("mem:fragment:f1", memory_type="fragment", content="evidence text")
        target = _make_node("mem:entity:t1")
        edge = CognitiveEdge(
            edge_type="COG_SUPPORTED_BY",
            from_id="mem:fragment:f1",
            to_id="mem:entity:t1",
            properties={"edge_confidence": 0.9, "contribution": 0.6},
        )
        repo = MockRepository(
            nodes={"mem:entity:t1": target, "mem:fragment:f1": source},
            edges=[edge],
        )
        expander = EvidenceExpander(repo)
        result = await expander.expand("mem:entity:t1", "default")

        assert len(result) == 1
        assert result[0].doc_id == "mem:fragment:f1"
        assert result[0].source == "cog_supported_by"
        assert result[0].confidence == 0.9
        assert result[0].contribution == 0.6

    @pytest.mark.asyncio
    async def test_cog_supported_by_skips_missing_source(self):
        target = _make_node("mem:entity:t1")
        edge = CognitiveEdge(
            edge_type="COG_SUPPORTED_BY",
            from_id="mem:fragment:missing",
            to_id="mem:entity:t1",
        )
        repo = MockRepository(nodes={"mem:entity:t1": target}, edges=[edge])
        expander = EvidenceExpander(repo)
        result = await expander.expand("mem:entity:t1", "default")

        assert result == []


class TestEvidenceExpanderStrategy2:
    @pytest.mark.asyncio
    async def test_source_fragment_ids_fallback(self):
        frag = _make_node("mem:fragment:f1", memory_type="fragment", content="fragment text")
        target = _make_node("mem:entity:t1", source_fragment_ids=["mem:fragment:f1"])
        repo = MockRepository(
            nodes={"mem:entity:t1": target, "mem:fragment:f1": frag},
        )
        expander = EvidenceExpander(repo)
        result = await expander.expand("mem:entity:t1", "default")

        assert len(result) == 1
        assert result[0].doc_id == "mem:fragment:f1"
        assert result[0].source == "source_fragment"
        assert result[0].contribution == 1.0

    @pytest.mark.asyncio
    async def test_source_fragment_ids_contribution_split(self):
        frag1 = _make_node("mem:fragment:f1", memory_type="fragment", content="frag1")
        frag2 = _make_node("mem:fragment:f2", memory_type="fragment", content="frag2")
        target = _make_node("mem:entity:t1", source_fragment_ids=["mem:fragment:f1", "mem:fragment:f2"])
        repo = MockRepository(
            nodes={"mem:entity:t1": target, "mem:fragment:f1": frag1, "mem:fragment:f2": frag2},
        )
        expander = EvidenceExpander(repo)
        result = await expander.expand("mem:entity:t1", "default")

        assert len(result) == 2
        assert result[0].contribution == 0.5
        assert result[1].contribution == 0.5


class TestEvidenceExpanderStrategy3:
    @pytest.mark.asyncio
    async def test_consolidated_into_fallback(self):
        frag = _make_node("mem:fragment:f1", memory_type="fragment", content="deep evidence")
        consolidated = _make_node("mem:obs:c1", memory_type="observation", source_fragment_ids=["mem:fragment:f1"])
        target = _make_node("mem:entity:t1")
        edge = CognitiveEdge(
            edge_type="CONSOLIDATED_INTO",
            from_id="mem:entity:t1",
            to_id="mem:obs:c1",
        )
        repo = MockRepository(
            nodes={"mem:entity:t1": target, "mem:obs:c1": consolidated, "mem:fragment:f1": frag},
            edges=[edge],
        )
        expander = EvidenceExpander(repo)
        result = await expander.expand("mem:entity:t1", "default")

        assert len(result) == 1
        assert result[0].doc_id == "mem:fragment:f1"
        assert result[0].source == "source_fragment"


class TestEvidenceExpanderDepth2:
    @pytest.mark.asyncio
    async def test_depth2_expands_evidence_sources(self):
        deeper = _make_node("mem:fragment:d1", memory_type="fragment", content="deeper evidence")
        frag = _make_node("mem:fragment:f1", memory_type="fragment", content="evidence", source_fragment_ids=["mem:fragment:d1"])
        target = _make_node("mem:entity:t1", source_fragment_ids=["mem:fragment:f1"])
        repo = MockRepository(
            nodes={"mem:entity:t1": target, "mem:fragment:f1": frag, "mem:fragment:d1": deeper},
        )
        expander = EvidenceExpander(repo)
        result = await expander.expand("mem:entity:t1", "default", depth=2)

        doc_ids = [r.doc_id for r in result]
        assert "mem:fragment:f1" in doc_ids
        assert "mem:fragment:d1" in doc_ids

        depth2_items = [r for r in result if r.source == "evidence_depth_2"]
        assert len(depth2_items) == 1
        assert depth2_items[0].doc_id == "mem:fragment:d1"

    @pytest.mark.asyncio
    async def test_depth1_does_not_expand_recursively(self):
        deeper = _make_node("mem:fragment:d1", memory_type="fragment", content="deeper")
        frag = _make_node("mem:fragment:f1", memory_type="fragment", content="evidence", source_fragment_ids=["mem:fragment:d1"])
        target = _make_node("mem:entity:t1", source_fragment_ids=["mem:fragment:f1"])
        repo = MockRepository(
            nodes={"mem:entity:t1": target, "mem:fragment:f1": frag, "mem:fragment:d1": deeper},
        )
        expander = EvidenceExpander(repo)
        result = await expander.expand("mem:entity:t1", "default", depth=1)

        doc_ids = [r.doc_id for r in result]
        assert "mem:fragment:f1" in doc_ids
        assert "mem:fragment:d1" not in doc_ids


class TestEvidenceExpanderSerialFallback:
    @pytest.mark.asyncio
    async def test_strategy1_skips_strategy2(self):
        source = _make_node("mem:fragment:f1", memory_type="fragment", content="direct evidence")
        target = _make_node("mem:entity:t1", source_fragment_ids=["mem:fragment:f2"])
        edge = CognitiveEdge(
            edge_type="COG_SUPPORTED_BY",
            from_id="mem:fragment:f1",
            to_id="mem:entity:t1",
        )
        frag2 = _make_node("mem:fragment:f2", memory_type="fragment", content="indirect evidence")
        repo = MockRepository(
            nodes={"mem:entity:t1": target, "mem:fragment:f1": source, "mem:fragment:f2": frag2},
            edges=[edge],
        )
        expander = EvidenceExpander(repo)
        result = await expander.expand("mem:entity:t1", "default")

        assert len(result) == 1
        assert result[0].doc_id == "mem:fragment:f1"
        assert result[0].source == "cog_supported_by"

    @pytest.mark.asyncio
    async def test_no_evidence_returns_empty(self):
        target = _make_node("mem:entity:t1")
        repo = MockRepository(nodes={"mem:entity:t1": target})
        expander = EvidenceExpander(repo)
        result = await expander.expand("mem:entity:t1", "default")

        assert result == []
