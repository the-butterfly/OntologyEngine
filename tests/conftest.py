"""Shared pytest fixtures for integration tests."""

import pytest
import pytest_asyncio

pytest_plugins = ["pytest_asyncio"]

from httpx import AsyncClient, ASGITransport

from ontology_engine.api.server import create_app
from ontology_engine.storage.sqlite.store import SQLiteStorage
from ontology_engine.services.dataset_service import DatasetService
from ontology_engine.services.incremental_update import IncrementalUpdateService


@pytest_asyncio.fixture
async def storage():
    """In-memory SQLite storage for each test."""
    s = SQLiteStorage(db_path=":memory:")
    await s.initialize()
    try:
        yield s
    finally:
        await s.close()


@pytest_asyncio.fixture
async def app(storage):
    """FastAPI app with in-memory services via dependency_overrides and globals."""
    application = create_app()
    from ontology_engine.api import dependencies

    # Override via dependency_overrides (works for routes using Depends())
    application.dependency_overrides[dependencies.get_dataset_service] = lambda: DatasetService(storage=storage)
    application.dependency_overrides[dependencies.get_incremental_update_service] = lambda: IncrementalUpdateService(storage=storage)

    # Also set the global _storage directly (categories routes call get_storage() directly, not via Depends)
    original_storage = dependencies._storage
    dependencies._storage = storage

    yield application

    application.dependency_overrides.clear()
    dependencies._storage = original_storage


@pytest_asyncio.fixture
async def client(app):
    """Async HTTP client for integration testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
