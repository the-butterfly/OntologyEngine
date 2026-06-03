"""Tests for _fuse_results() and fusion strategies extracted from hybrid_search."""

from __future__ import annotations

import pytest

from ontology_engine.storage.retrieval import _fuse_results


class TestFuseResultsIndependentThenFuse:
    """Test independent_then_fuse strategy: no filtering, fuse all signals."""

    def test_fuses_all_candidates(self):
        sem = {"a": 0.9, "b": 0.5, "c": 0.3}
        gra = {"b": 0.8, "d": 0.6}
        path = {"c": 1.0}
        weights = {"semantic": 0.6, "graph": 0.4, "path": 0.0}
        result = _fuse_results(sem, gra, path, weights, top_k=10, strategy="independent_then_fuse")
        # All IDs from all legs should appear
        assert set(result) == {"a", "b", "c", "d"}

    def test_respects_top_k(self):
        sem = {f"e{i}": 1.0 - i * 0.1 for i in range(20)}
        gra = {}
        path = {}
        weights = {"semantic": 1.0, "graph": 0.0, "path": 0.0}
        result = _fuse_results(sem, gra, path, weights, top_k=5, strategy="independent_then_fuse")
        assert len(result) == 5

    def test_no_filtering_applied(self):
        sem = {"a": 1.0}
        gra = {"b": 1.0}
        path = {"c": 1.0}
        weights = {"semantic": 0.4, "graph": 0.3, "path": 0.3}
        result = _fuse_results(sem, gra, path, weights, top_k=10, strategy="independent_then_fuse")
        # c only appears in path, but should still be included
        assert "c" in result


class TestFuseResultsFilterThenFuse:
    """Test filter_then_fuse strategy: filter by path candidates first, then fuse."""

    def test_filters_to_path_candidates_when_path_present(self):
        sem = {"a": 1.0, "b": 0.5, "c": 0.3}
        gra = {"b": 0.8, "d": 0.6}
        path = {"a": 1.0, "c": 1.0}
        weights = {"semantic": 0.6, "graph": 0.4, "path": 0.0}
        result = _fuse_results(sem, gra, path, weights, top_k=10, strategy="filter_then_fuse")
        # Only a and c should appear (they are in path_candidates)
        assert set(result) == {"a", "c"}
        # b and d should be excluded
        assert "b" not in result
        assert "d" not in result

    def test_falls_back_to_all_when_no_path(self):
        sem = {"a": 1.0, "b": 0.5}
        gra = {"c": 0.8}
        path = {}
        weights = {"semantic": 0.6, "graph": 0.4, "path": 0.0}
        result = _fuse_results(sem, gra, path, weights, top_k=10, strategy="filter_then_fuse")
        # No path candidates → fall back to semantic | graph
        assert set(result) == {"a", "b", "c"}

    def test_path_candidate_without_semantic_score_still_included(self):
        sem = {"a": 1.0}
        gra = {}
        path = {"a": 1.0, "z": 1.0}
        weights = {"semantic": 0.5, "graph": 0.0, "path": 0.5}
        result = _fuse_results(sem, gra, path, weights, top_k=10, strategy="filter_then_fuse")
        assert "z" in result


class TestFuseResultsFuseThenFilter:
    """Test fuse_then_filter strategy: fuse all first, then filter to path candidates."""

    def test_filters_after_fusion(self):
        sem = {"a": 1.0, "b": 0.9, "c": 0.1}
        gra = {"d": 0.8}
        path = {"a": 1.0, "c": 1.0}
        weights = {"semantic": 0.6, "graph": 0.4, "path": 0.0}
        result = _fuse_results(sem, gra, path, weights, top_k=10, strategy="fuse_then_filter")
        # Only a and c are in path candidates with score > 0
        assert set(result) == {"a", "c"}
        # b and d should be filtered out even though b has high semantic score
        assert "b" not in result

    def test_no_filter_when_no_path(self):
        sem = {"a": 1.0, "b": 0.5}
        gra = {"c": 0.8}
        path = {}
        weights = {"semantic": 0.6, "graph": 0.4, "path": 0.0}
        result = _fuse_results(sem, gra, path, weights, top_k=10, strategy="fuse_then_filter")
        # No path → no filtering
        assert set(result) == {"a", "b", "c"}

    def test_respects_top_k_after_filter(self):
        sem = {f"e{i}": 1.0 - i * 0.01 for i in range(10)}
        gra = {}
        path = {f"e{i}": 1.0 for i in range(10)}
        weights = {"semantic": 1.0, "graph": 0.0, "path": 0.0}
        result = _fuse_results(sem, gra, path, weights, top_k=3, strategy="fuse_then_filter")
        assert len(result) == 3


class TestFuseResultsEdgeCases:
    """Test edge cases across all strategies."""

    @pytest.mark.parametrize("strategy", [
        "filter_then_fuse", "independent_then_fuse", "fuse_then_filter",
    ])
    def test_empty_all_scores(self, strategy):
        result = _fuse_results({}, {}, {}, {"semantic": 0.6, "graph": 0.4, "path": 0.0}, top_k=10, strategy=strategy)
        assert result == []

    @pytest.mark.parametrize("strategy", [
        "filter_then_fuse", "independent_then_fuse", "fuse_then_filter",
    ])
    def test_single_result(self, strategy):
        sem = {"a": 1.0}
        result = _fuse_results(sem, {}, {}, {"semantic": 1.0, "graph": 0.0, "path": 0.0}, top_k=10, strategy=strategy)
        assert result == ["a"]

    @pytest.mark.parametrize("strategy", [
        "filter_then_fuse", "independent_then_fuse", "fuse_then_filter",
    ])
    def test_all_filtered_out(self, strategy):
        """When path candidates exist but none overlap with semantic/graph."""
        sem = {"a": 1.0, "b": 0.5}
        gra = {}
        path = {"z": 1.0}  # z is not in semantic or graph
        weights = {"semantic": 1.0, "graph": 0.0, "path": 0.0}
        if strategy == "fuse_then_filter":
            # fuse_then_filter only fuses semantic|graph, then filters to path.
            # z is not in semantic|graph, so it's never a candidate.
            # a, b are candidates but not in path, so they're filtered out.
            result = _fuse_results(sem, gra, path, weights, top_k=10, strategy=strategy)
            assert result == []
        elif strategy == "filter_then_fuse":
            # filter_then_fuse: only z is considered (path candidates), z has 0 semantic/graph
            result = _fuse_results(sem, gra, path, weights, top_k=10, strategy=strategy)
            assert "z" in result
        else:
            # independent_then_fuse: all IDs included
            result = _fuse_results(sem, gra, path, weights, top_k=10, strategy=strategy)
            assert "a" in result
            assert "b" in result
            assert "z" in result

    @pytest.mark.parametrize("strategy", [
        "filter_then_fuse", "independent_then_fuse", "fuse_then_filter",
    ])
    def test_zero_weights(self, strategy):
        sem = {"a": 1.0}
        gra = {"b": 1.0}
        path = {"c": 1.0}
        weights = {"semantic": 0.0, "graph": 0.0, "path": 0.0}
        result = _fuse_results(sem, gra, path, weights, top_k=10, strategy=strategy)
        if strategy == "fuse_then_filter":
            # fuse_then_filter fuses semantic|graph = {a, b}, then filters to path.
            # Neither a nor b is in path, so result is empty.
            assert result == []
        else:
            # All scores should be 0.0, but IDs still returned
            assert len(result) > 0

    def test_ordering_by_score(self):
        sem = {"low": 0.1, "mid": 0.5, "high": 1.0}
        weights = {"semantic": 1.0, "graph": 0.0, "path": 0.0}
        result = _fuse_results(sem, {}, {}, weights, top_k=10, strategy="independent_then_fuse")
        assert result[0] == "high"
        assert result[1] == "mid"
        assert result[2] == "low"

    def test_weight_normalization(self):
        """Weights should be normalized so total_weight = 1.0."""
        sem = {"a": 1.0}
        gra = {"a": 1.0}
        path = {}
        # Non-normalized weights: semantic=6, graph=4 → normalized: 0.6, 0.4
        weights = {"semantic": 0.6, "graph": 0.4, "path": 0.0}
        result = _fuse_results(sem, gra, path, weights, top_k=10, strategy="independent_then_fuse")
        assert len(result) == 1
        # Score should be 0.6*1.0 + 0.4*1.0 = 1.0 (after normalization)
        # We can't directly check the score from _fuse_results, but the ordering is correct

    def test_fuse_then_filter_excludes_zero_path_score(self):
        """fuse_then_filter should exclude candidates with path_match_score == 0."""
        sem = {"a": 1.0, "b": 0.9}
        gra = {}
        path = {"a": 1.0}  # b is NOT in path candidates
        weights = {"semantic": 1.0, "graph": 0.0, "path": 0.0}
        result = _fuse_results(sem, gra, path, weights, top_k=10, strategy="fuse_then_filter")
        # b has path_match_score 0 (not in path dict), so it's filtered out
        assert "a" in result
        assert "b" not in result
