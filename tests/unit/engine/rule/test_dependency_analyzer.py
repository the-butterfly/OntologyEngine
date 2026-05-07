"""Tests for dependency_analyzer module."""
from ontology_engine.engine.rule.dependency_analyzer import DependencyAnalyzer


def test_build_dependency_graph():
    """Test building dependency graph from rules."""
    rules = [
        {"id": "A", "inputs": [], "outputs": [{"id": "x"}]},
        {"id": "B", "inputs": [{"id": "x"}], "outputs": [{"id": "y"}]},
        {"id": "C", "inputs": [{"id": "y"}], "outputs": [{"id": "z"}]},
    ]
    analyzer = DependencyAnalyzer()
    graph = analyzer.build(rules)
    assert "A" in graph.adjacency
    assert "B" in graph.adjacency["A"]
    assert "C" in graph.adjacency["B"]


def test_compute_levels():
    """Test computing execution levels for rules."""
    rules = [
        {"id": "A", "inputs": [], "outputs": [{"id": "x"}]},
        {"id": "B", "inputs": [{"id": "x"}], "outputs": [{"id": "y"}]},
        {"id": "C", "inputs": [{"id": "x"}, {"id": "y"}], "outputs": [{"id": "z"}]},
    ]
    analyzer = DependencyAnalyzer()
    graph = analyzer.build(rules)
    levels = analyzer.compute_levels(graph)
    assert levels["A"] == 0
    assert levels["B"] == 1
    assert levels["C"] == 2


def test_no_dependencies():
    """Test rules with no dependencies."""
    rules = [
        {"id": "A", "inputs": [], "outputs": [{"id": "x"}]},
        {"id": "B", "inputs": [], "outputs": [{"id": "y"}]},
    ]
    analyzer = DependencyAnalyzer()
    graph = analyzer.build(rules)
    assert "A" in graph.adjacency
    assert "B" in graph.adjacency
    levels = analyzer.compute_levels(graph)
    assert levels["A"] == 0
    assert levels["B"] == 0


def test_empty_rules():
    """Test with empty rules list."""
    analyzer = DependencyAnalyzer()
    graph = analyzer.build([])
    assert graph.adjacency == {}
    assert graph.in_degree == {}
    assert graph.edges == []
    assert graph.rules == []
    levels = analyzer.compute_levels(graph)
    assert levels == {}