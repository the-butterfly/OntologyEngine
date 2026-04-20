# tests/conftest.py
"""Test configuration and fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_storage():
    """Create a mock storage."""
    storage = AsyncMock()
    storage.get_entity = AsyncMock(return_value=None)
    storage.save_entity = AsyncMock()
    storage.get_neighbors = AsyncMock(return_value=([], []))
    storage.get_metric = AsyncMock(return_value=None)
    storage.save_metric = AsyncMock()
    storage.get_category_tags = AsyncMock(return_value=None)
    storage.save_category_tags = AsyncMock()
    return storage
