# ontology_engine/core/semantic_space/storage.py
"""Storage layer for semantic spaces."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SpaceMetadata,
    SpaceVersion,
    SpaceStatus,
)


class SemanticSpaceStorageError(Exception):
    """Storage operation error."""
    pass


class SemanticSpaceStorage:
    """
    Storage backend for semantic spaces.

    Uses a directory-based storage strategy:
    - Spaces are stored as JSON files
    - Snapshots are stored in a snapshots/ subdirectory
    """

    def __init__(self, base_path: str = "data/semantic_spaces"):
        """Initialize storage.

        Args:
            base_path: Directory path for storing spaces
        """
        self.base_path = Path(base_path)
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure the base directory exists."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        (self.base_path / "snapshots").mkdir(parents=True, exist_ok=True)

    def _get_space_path(self, space_id: str) -> Path:
        """Get the file path for a space."""
        return self.base_path / f"{space_id}.json"

    def _get_snapshot_path(self, space_id: str, version: int) -> Path:
        """Get the file path for a snapshot."""
        return self.base_path / "snapshots" / f"{space_id}_v{version}.json"

    async def save(self, space: SemanticSpace) -> None:
        """Save a semantic space.

        Args:
            space: The semantic space to save
        """
        try:
            space.metadata.updated_at = datetime.utcnow()
            path = self._get_space_path(space.metadata.id)
            with open(path, "w", encoding="utf-8") as f:
                f.write(space.model_dump_json(indent=2))
        except Exception as e:
            raise SemanticSpaceStorageError(f"Failed to save space: {e}") from e

    async def load(self, space_id: str) -> SemanticSpace | None:
        """Load a semantic space by ID.

        Args:
            space_id: The space ID to load

        Returns:
            The semantic space or None if not found
        """
        path = self._get_space_path(space_id)
        if not path.exists():
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return SemanticSpace.model_validate(data)
        except Exception as e:
            raise SemanticSpaceStorageError(f"Failed to load space: {e}") from e

    async def delete(self, space_id: str) -> bool:
        """Delete a semantic space.

        Args:
            space_id: The space ID to delete

        Returns:
            True if deleted, False if not found
        """
        path = self._get_space_path(space_id)
        if not path.exists():
            return False

        # Delete main space file
        path.unlink()

        # Delete associated snapshots
        snapshots_dir = self.base_path / "snapshots"
        if snapshots_dir.exists():
            for snap_file in snapshots_dir.glob(f"{space_id}_v*.json"):
                snap_file.unlink()

        return True

    async def list(self) -> list[SpaceMetadata]:
        """List all semantic spaces (metadata only).

        Returns:
            List of space metadata
        """
        spaces = []
        for space_file in self.base_path.glob("*.json"):
            try:
                with open(space_file, encoding="utf-8") as f:
                    data = json.load(f)
                if "metadata" in data:
                    spaces.append(SpaceMetadata.model_validate(data["metadata"]))
            except Exception:
                # Skip corrupted files
                continue

        return spaces

    async def create_snapshot(
        self,
        space: SemanticSpace,
        description: str | None = None,
        created_by: str | None = None,
    ) -> SpaceVersion:
        """Create a version snapshot of a semantic space.

        Args:
            space: The space to snapshot
            description: Optional description of the snapshot
            created_by: Optional creator identifier

        Returns:
            The created space version
        """
        # Create new version
        new_version = len(space.versions) + 1
        space_version = SpaceVersion(
            version=new_version,
            space_id=space.metadata.id,
            created_at=datetime.utcnow(),
            created_by=created_by,
            change_description=description,
            is_stable=False,
        )

        # Save snapshot
        snapshot_path = self._get_snapshot_path(space.metadata.id, new_version)
        snapshot_data = space.model_dump_json()
        with open(snapshot_path, "w", encoding="utf-8") as f:
            f.write(snapshot_data)

        space_version.snapshot_path = str(snapshot_path)

        # Update space
        space.versions.append(space_version)
        space.active_version = new_version

        # Mark previous versions as stable (optional)
        for v in space.versions:
            if v.version < new_version:
                v.is_stable = True

        await self.save(space)

        return space_version

    async def rollback_to_version(
        self,
        space_id: str,
        target_version: int,
    ) -> SemanticSpace | None:
        """Rollback a space to a previous version.

        Args:
            space_id: The space ID
            target_version: The version to rollback to

        Returns:
            The restored space or None if not found
        """
        # Load the space first
        space = await self.load(space_id)
        if not space:
            return None

        # Find the target version
        target = next(
            (v for v in space.versions if v.version == target_version),
            None,
        )
        if not target:
            raise SemanticSpaceStorageError(
                f"Version {target_version} not found"
            )

        if not target.snapshot_path:
            raise SemanticSpaceStorageError(
                f"Snapshot for version {target_version} not available"
            )

        # Load snapshot
        snapshot_path = Path(target.snapshot_path)
        if not snapshot_path.exists():
            raise SemanticSpaceStorageError(
                f"Snapshot file not found: {snapshot_path}"
            )

        with open(snapshot_path, encoding="utf-8") as f:
            data = json.load(f)

        restored_space = SemanticSpace.model_validate(data)

        # Update versions
        for v in restored_space.versions:
            v.is_stable = v.version <= target_version

        restored_space.active_version = target_version

        # Save restored space
        await self.save(restored_space)

        return restored_space

    async def exists(self, space_id: str) -> bool:
        """Check if a space exists.

        Args:
            space_id: The space ID to check

        Returns:
            True if exists, False otherwise
        """
        return self._get_space_path(space_id).exists()
