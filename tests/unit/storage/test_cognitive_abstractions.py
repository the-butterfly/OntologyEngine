"""Cognitive storage abstraction layer tests.

Tests that verify:
1. CognitiveStorageBackend (base.py) defines all required abstract methods
2. StorageInterface (cognitive_interface.py) defines all required methods
3. Both interfaces cover the same conceptual operations
4. CognitiveStore (cognitive/store.py) correctly delegates to its underlying store
5. LadybugGraphStore implements CognitiveStorageBackend directly

Running:
    pytest tests/unit/storage/test_cognitive_abstractions.py -v
"""

from __future__ import annotations

import inspect
from abc import ABC
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ontology_engine.storage.base import CognitiveStorageBackend
from ontology_engine.storage.cognitive_interface import StorageInterface
from ontology_engine.storage.cognitive.store import CognitiveStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_abstract_methods(cls: type) -> set[str]:
    """Return the set of abstract method names defined on *cls*."""
    return {
        name
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction)
        if getattr(method, "__isabstractmethod__", False)
    }


def _get_public_methods(cls: type) -> set[str]:
    """Return the set of public method names defined on *cls* (not inherited from ABC/object)."""
    return {
        name
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction)
        if not name.startswith("_") and name != "initialize" and name != "close"
    }


# ---------------------------------------------------------------------------
# Test: CognitiveStorageBackend abstract methods
# ---------------------------------------------------------------------------


class TestCognitiveStorageBackendAbstractMethods:
    """Verify CognitiveStorageBackend defines all required abstract methods."""

    def test_is_abstract_class(self):
        """CognitiveStorageBackend must be an abstract class."""
        assert issubclass(CognitiveStorageBackend, ABC)
        with pytest.raises(TypeError):
            CognitiveStorageBackend()  # type: ignore[abstract]

    def test_has_initialize_method(self):
        """CognitiveStorageBackend must define abstract initialize()."""
        methods = _get_abstract_methods(CognitiveStorageBackend)
        assert "initialize" in methods, f"initialize not in abstract methods: {methods}"

    def test_has_close_method(self):
        """CognitiveStorageBackend must define abstract close()."""
        methods = _get_abstract_methods(CognitiveStorageBackend)
        assert "close" in methods, f"close not in abstract methods: {methods}"

    def test_has_node_crud_methods(self):
        """CognitiveStorageBackend must define node CRUD abstract methods."""
        methods = _get_abstract_methods(CognitiveStorageBackend)
        expected = {
            "save_cognitive_node",
            "get_cognitive_node",
            "list_cognitive_nodes",
            "delete_cognitive_node",
        }
        missing = expected - methods
        assert not missing, f"Missing node CRUD abstract methods: {missing}"

    def test_has_belief_update_method(self):
        """CognitiveStorageBackend must define update_cognitive_node_belief()."""
        methods = _get_abstract_methods(CognitiveStorageBackend)
        assert "update_cognitive_node_belief" in methods

    def test_has_occ_update_method(self):
        """CognitiveStorageBackend must define update_cognitive_node_with_occ()."""
        methods = _get_abstract_methods(CognitiveStorageBackend)
        assert "update_cognitive_node_with_occ" in methods

    def test_has_edge_crud_methods(self):
        """CognitiveStorageBackend must define edge CRUD abstract methods."""
        methods = _get_abstract_methods(CognitiveStorageBackend)
        expected = {
            "save_cognitive_edge",
            "list_cognitive_edges",
        }
        missing = expected - methods
        assert not missing, f"Missing edge CRUD abstract methods: {missing}"

    def test_has_disposition_methods(self):
        """CognitiveStorageBackend must define disposition abstract methods."""
        methods = _get_abstract_methods(CognitiveStorageBackend)
        expected = {
            "save_disposition",
            "get_disposition",
            "compute_dynamic_weights",
        }
        missing = expected - methods
        assert not missing, f"Missing disposition abstract methods: {missing}"

    def test_has_activity_log_methods(self):
        """CognitiveStorageBackend must define activity log abstract methods."""
        methods = _get_abstract_methods(CognitiveStorageBackend)
        expected = {
            "save_activity_log",
            "get_activity_log",
        }
        missing = expected - methods
        assert not missing, f"Missing activity log abstract methods: {missing}"

    def test_has_search_method(self):
        """CognitiveStorageBackend must define search_cognitive()."""
        methods = _get_abstract_methods(CognitiveStorageBackend)
        assert "search_cognitive" in methods

    def test_total_abstract_method_count(self):
        """CognitiveStorageBackend should have a stable set of abstract methods."""
        methods = _get_abstract_methods(CognitiveStorageBackend)
        # Document expected count to catch accidental additions/removals
        # 16 = initialize, close, 4 node CRUD, belief_update, occ_update,
        #      2 edge ops, 3 disposition ops, 2 activity log ops, search
        expected_count = 16
        assert len(methods) == expected_count, (
            f"CognitiveStorageBackend has {len(methods)} abstract methods, "
            f"expected {expected_count}. Methods: {sorted(methods)}"
        )


# ---------------------------------------------------------------------------
# Test: StorageInterface abstract methods
# ---------------------------------------------------------------------------


class TestStorageInterfaceAbstractMethods:
    """Verify StorageInterface defines all required methods."""

    def test_is_abstract_class(self):
        """StorageInterface must be an abstract class."""
        assert issubclass(StorageInterface, ABC)
        with pytest.raises(TypeError):
            StorageInterface()  # type: ignore[abstract]

    def test_has_core_abstract_methods(self):
        """StorageInterface must define core abstract methods (save_node, get_node, search, delete_node)."""
        methods = _get_abstract_methods(StorageInterface)
        expected = {
            "save_node",
            "get_node",
            "search",
            "delete_node",
        }
        missing = expected - methods
        assert not missing, f"Missing core abstract methods: {missing}"

    def test_has_batch_save_method(self):
        """StorageInterface must define abstract batch_save()."""
        methods = _get_abstract_methods(StorageInterface)
        assert "batch_save" in methods

    def test_has_count_method(self):
        """StorageInterface must define abstract count()."""
        methods = _get_abstract_methods(StorageInterface)
        assert "count" in methods

    def test_has_default_methods(self):
        """StorageInterface must define default (non-abstract) methods for edge/disposition/OCC."""
        # These are provided with default implementations (raise NotImplementedError)
        instance_methods = {
            name
            for name, _ in inspect.getmembers(StorageInterface, predicate=inspect.isfunction)
            if not name.startswith("_")
        }
        expected_defaults = {
            "traverse",
            "list_nodes",
            "update_node_with_occ",
            "save_disposition",
            "get_disposition",
            "compute_dynamic_weights",
            "save_edge",
            "list_edges",
        }
        missing = expected_defaults - instance_methods
        assert not missing, f"Missing default methods: {missing}"


# ---------------------------------------------------------------------------
# Test: Interface coverage alignment
# ---------------------------------------------------------------------------


class TestInterfaceCoverageAlignment:
    """Verify both interfaces cover the same conceptual operations."""

    def test_node_crud_coverage(self):
        """Both interfaces must cover node CRUD operations."""
        backend_methods = _get_public_methods(CognitiveStorageBackend)
        interface_methods = _get_public_methods(StorageInterface)

        # CognitiveStorageBackend: save_cognitive_node, get_cognitive_node,
        #   list_cognitive_nodes, delete_cognitive_node
        # StorageInterface: save_node, get_node, list_nodes, delete_node
        backend_node_ops = {m for m in backend_methods if "node" in m.lower() and "edge" not in m.lower()}
        interface_node_ops = {m for m in interface_methods if "node" in m.lower() and "edge" not in m.lower()}

        assert len(backend_node_ops) >= 4, (
            f"CognitiveStorageBackend should have at least 4 node operations, "
            f"got: {backend_node_ops}"
        )
        assert len(interface_node_ops) >= 4, (
            f"StorageInterface should have at least 4 node operations, "
            f"got: {interface_node_ops}"
        )

    def test_edge_crud_coverage(self):
        """Both interfaces must cover edge CRUD operations."""
        backend_methods = _get_public_methods(CognitiveStorageBackend)
        interface_methods = _get_public_methods(StorageInterface)

        backend_edge_ops = {m for m in backend_methods if "edge" in m.lower()}
        interface_edge_ops = {m for m in interface_methods if "edge" in m.lower()}

        assert len(backend_edge_ops) >= 2, (
            f"CognitiveStorageBackend should have at least 2 edge operations, "
            f"got: {backend_edge_ops}"
        )
        assert len(interface_edge_ops) >= 2, (
            f"StorageInterface should have at least 2 edge operations, "
            f"got: {interface_edge_ops}"
        )

    def test_disposition_coverage(self):
        """Both interfaces must cover disposition operations."""
        backend_methods = _get_public_methods(CognitiveStorageBackend)
        interface_methods = _get_public_methods(StorageInterface)

        backend_disp_ops = {m for m in backend_methods if "disposition" in m.lower() or "dynamic_weight" in m.lower()}
        interface_disp_ops = {m for m in interface_methods if "disposition" in m.lower() or "dynamic_weight" in m.lower()}

        assert len(backend_disp_ops) >= 3, (
            f"CognitiveStorageBackend should have at least 3 disposition operations, "
            f"got: {backend_disp_ops}"
        )
        assert len(interface_disp_ops) >= 3, (
            f"StorageInterface should have at least 3 disposition operations, "
            f"got: {interface_disp_ops}"
        )

    def test_search_coverage(self):
        """Both interfaces must cover search operations."""
        backend_methods = _get_public_methods(CognitiveStorageBackend)
        interface_methods = _get_public_methods(StorageInterface)

        backend_search_ops = {m for m in backend_methods if "search" in m.lower()}
        interface_search_ops = {m for m in interface_methods if "search" in m.lower()}

        assert len(backend_search_ops) >= 1, (
            f"CognitiveStorageBackend should have at least 1 search operation, "
            f"got: {backend_search_ops}"
        )
        assert len(interface_search_ops) >= 1, (
            f"StorageInterface should have at least 1 search operation, "
            f"got: {interface_search_ops}"
        )

    def test_occ_update_coverage(self):
        """Both interfaces must cover OCC (optimistic concurrency control) update."""
        backend_methods = _get_public_methods(CognitiveStorageBackend)
        interface_methods = _get_public_methods(StorageInterface)

        backend_occ = {m for m in backend_methods if "occ" in m.lower()}
        interface_occ = {m for m in interface_methods if "occ" in m.lower()}

        assert len(backend_occ) >= 1, (
            f"CognitiveStorageBackend should have at least 1 OCC method, "
            f"got: {backend_occ}"
        )
        assert len(interface_occ) >= 1, (
            f"StorageInterface should have at least 1 OCC method, "
            f"got: {interface_occ}"
        )


# ---------------------------------------------------------------------------
# Test: LadybugGraphStore implements CognitiveStorageBackend
# ---------------------------------------------------------------------------


class TestLadybugGraphStoreImplementsCognitiveStorageBackend:
    """Verify LadybugGraphStore directly implements CognitiveStorageBackend."""

    def test_is_subclass(self):
        """LadybugGraphStore must be a subclass of CognitiveStorageBackend."""
        from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore

        assert issubclass(LadybugGraphStore, CognitiveStorageBackend)

    def test_all_abstract_methods_implemented(self):
        """LadybugGraphStore must implement all CognitiveStorageBackend abstract methods."""
        from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore

        abstract_methods = _get_abstract_methods(CognitiveStorageBackend)
        # Check that LadybugGraphStore can be instantiated without TypeError
        # (meaning all abstract methods are implemented)
        instance_methods = {
            name
            for name, _ in inspect.getmembers(LadybugGraphStore, predicate=inspect.isfunction)
        }
        missing = abstract_methods - instance_methods
        assert not missing, (
            f"LadybugGraphStore is missing CognitiveStorageBackend methods: {missing}"
        )

    def test_can_be_used_as_cognitive_storage_backend(self):
        """LadybugGraphStore instance should be assignable to CognitiveStorageBackend type."""
        from ontology_engine.storage.graph.ladybug_store import LadybugGraphStore

        store = LadybugGraphStore()
        assert isinstance(store, CognitiveStorageBackend)


# ---------------------------------------------------------------------------
# Test: CognitiveStore delegation (deprecated wrapper)
# ---------------------------------------------------------------------------


class TestCognitiveStoreDelegation:
    """Verify CognitiveStore correctly delegates to its underlying store.

    CognitiveStore is deprecated but still delegates correctly through
    the CognitiveStorageBackend interface methods.
    """

    def _make_store(self) -> CognitiveStore:
        """Create a CognitiveStore with a mock graph store."""
        mock_graph = AsyncMock(spec=CognitiveStorageBackend)
        mock_graph.initialize = AsyncMock()
        mock_graph.close = AsyncMock()
        return CognitiveStore(graph_store=mock_graph)

    @pytest.mark.asyncio
    async def test_initialize_delegates_to_graph_store(self):
        """CognitiveStore.initialize() delegates to graph_store.initialize()."""
        store = self._make_store()
        await store.initialize(db_path="/tmp/test")
        store._store.initialize.assert_awaited_once_with("/tmp/test")

    @pytest.mark.asyncio
    async def test_close_delegates_to_graph_store(self):
        """CognitiveStore.close() delegates to graph_store.close()."""
        store = self._make_store()
        await store.close()
        store._store.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_cognitive_node_delegates(self):
        """CognitiveStore.save_cognitive_node() delegates to graph_store.save_cognitive_node()."""
        store = self._make_store()
        store._store.save_cognitive_node = AsyncMock()

        node_data: dict[str, Any] = {
            "id": "test-node-1",
            "memory_type": "observation",
            "cognitive_layer": "opinion",
            "content": "test content",
            "space_id": "default",
        }
        await store.save_cognitive_node(node_data)
        store._store.save_cognitive_node.assert_awaited_once_with(node_data)

    @pytest.mark.asyncio
    async def test_get_cognitive_node_delegates(self):
        """CognitiveStore.get_cognitive_node() delegates to graph_store.get_cognitive_node()."""
        store = self._make_store()
        store._store.get_cognitive_node = AsyncMock(return_value={"id": "test-node-1"})

        result = await store.get_cognitive_node("test-node-1")
        store._store.get_cognitive_node.assert_awaited_once_with("test-node-1")
        assert result == {"id": "test-node-1"}

    @pytest.mark.asyncio
    async def test_list_cognitive_nodes_delegates(self):
        """CognitiveStore.list_cognitive_nodes() delegates to graph_store.list_cognitive_nodes()."""
        store = self._make_store()
        store._store.list_cognitive_nodes = AsyncMock(return_value=[])

        result = await store.list_cognitive_nodes(space_id="default", limit=50)
        store._store.list_cognitive_nodes.assert_awaited_once()
        call_kwargs = store._store.list_cognitive_nodes.call_args.kwargs
        assert call_kwargs.get("space_id") == "default"
        assert call_kwargs.get("limit") == 50

    @pytest.mark.asyncio
    async def test_delete_cognitive_node_delegates(self):
        """CognitiveStore.delete_cognitive_node() delegates to graph_store.delete_cognitive_node()."""
        store = self._make_store()
        store._store.delete_cognitive_node = AsyncMock()

        await store.delete_cognitive_node("test-node-1")
        store._store.delete_cognitive_node.assert_awaited_once_with("test-node-1")

    @pytest.mark.asyncio
    async def test_update_cognitive_node_belief_delegates(self):
        """CognitiveStore.update_cognitive_node_belief() delegates to graph_store.update_cognitive_node_belief()."""
        store = self._make_store()
        store._store.update_cognitive_node_belief = AsyncMock()

        await store.update_cognitive_node_belief("test-node-1", "pending_review", reason="test")
        store._store.update_cognitive_node_belief.assert_awaited_once_with(
            "test-node-1", "pending_review", "test"
        )

    @pytest.mark.asyncio
    async def test_save_cognitive_edge_delegates(self):
        """CognitiveStore.save_cognitive_edge() delegates to graph_store.save_cognitive_edge()."""
        store = self._make_store()
        store._store.save_cognitive_edge = AsyncMock(return_value={"edge_type": "SUPPORTS"})

        result = await store.save_cognitive_edge(
            edge_type="SUPPORTS",
            from_id="n1",
            to_id="n2",
            properties={"weight": 0.8},
        )
        store._store.save_cognitive_edge.assert_awaited_once()
        call_kwargs = store._store.save_cognitive_edge.call_args.kwargs
        assert call_kwargs.get("edge_type") == "SUPPORTS"
        assert call_kwargs.get("from_id") == "n1"
        assert call_kwargs.get("to_id") == "n2"

    @pytest.mark.asyncio
    async def test_list_cognitive_edges_delegates(self):
        """CognitiveStore.list_cognitive_edges() delegates to graph_store.list_cognitive_edges()."""
        store = self._make_store()
        store._store.list_cognitive_edges = AsyncMock(return_value=[])

        result = await store.list_cognitive_edges(from_id="n1", edge_type="SUPPORTS")
        store._store.list_cognitive_edges.assert_awaited_once()
        call_kwargs = store._store.list_cognitive_edges.call_args.kwargs
        assert call_kwargs.get("from_id") == "n1"
        assert call_kwargs.get("edge_type") == "SUPPORTS"

    @pytest.mark.asyncio
    async def test_save_disposition_delegates(self):
        """CognitiveStore.save_disposition() delegates to graph_store.save_disposition()."""
        store = self._make_store()
        store._store.save_disposition = AsyncMock()

        profile_data: dict[str, Any] = {
            "id": "disp-1",
            "scene": "default",
            "skepticism": 0.5,
        }
        await store.save_disposition(profile_data)
        store._store.save_disposition.assert_awaited_once_with(profile_data)

    @pytest.mark.asyncio
    async def test_get_disposition_delegates(self):
        """CognitiveStore.get_disposition() delegates to graph_store.get_disposition()."""
        store = self._make_store()
        store._store.get_disposition = AsyncMock(return_value={"id": "disp-1"})

        result = await store.get_disposition(profile_id="disp-1")
        store._store.get_disposition.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_compute_dynamic_weights_delegates(self):
        """CognitiveStore.compute_dynamic_weights() delegates to graph_store.compute_dynamic_weights()."""
        store = self._make_store()
        store._store.compute_dynamic_weights = AsyncMock(return_value={"fragment": 1.0})

        result = await store.compute_dynamic_weights({"id": "disp-1"})
        store._store.compute_dynamic_weights.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_save_activity_log_delegates(self):
        """CognitiveStore.save_activity_log() delegates to graph_store.save_activity_log()."""
        store = self._make_store()
        store._store.save_activity_log = AsyncMock()

        await store.save_activity_log("n1", {"action": "access"})
        store._store.save_activity_log.assert_awaited_once_with("n1", {"action": "access"})

    @pytest.mark.asyncio
    async def test_get_activity_log_delegates(self):
        """CognitiveStore.get_activity_log() delegates to graph_store.get_activity_log()."""
        store = self._make_store()
        store._store.get_activity_log = AsyncMock(
            return_value=[{"action": "access"}]
        )

        result = await store.get_activity_log("n1")
        store._store.get_activity_log.assert_awaited_once_with("n1")
        assert result == [{"action": "access"}]


# ---------------------------------------------------------------------------
# Test: CognitiveStore no longer accesses private methods
# ---------------------------------------------------------------------------


class TestCognitiveStoreNoPrivateAccess:
    """Verify CognitiveStore does NOT access private methods of its delegate.

    After refactoring, CognitiveStore delegates entirely through the
    CognitiveStorageBackend public interface methods.
    """

    def test_no_private_method_access(self):
        """CognitiveStore should NOT access private methods of its delegate."""
        import re

        for name, method in inspect.getmembers(CognitiveStore, predicate=inspect.isfunction):
            if name.startswith("_") and name != "__init__":
                continue

            source = inspect.getsource(method)
            # Look for self._store._<method_name>( calls specifically
            private_call_pattern = r"self\._store\._\w+\("
            matches = re.findall(private_call_pattern, source)
            assert not matches, (
                f"CognitiveStore.{name}() accesses private method of its delegate: "
                f"{matches} — this is a boundary violation"
            )

    def test_deprecated_warning_on_init(self):
        """CognitiveStore.__init__() should emit a DeprecationWarning."""
        mock_graph = AsyncMock(spec=CognitiveStorageBackend)
        with pytest.warns(DeprecationWarning, match="CognitiveStore is deprecated"):
            CognitiveStore(graph_store=mock_graph)
