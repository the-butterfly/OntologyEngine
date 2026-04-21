"""Incremental cache for extraction pipeline (AST + semantic + checkpoints)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


class IncrementalCache:
    """Three-layer cache manager: AST cache + semantic cache + checkpoints."""

    def __init__(self, cache_dir: str = ".ontology/cache") -> None:
        self._cache_dir = Path(cache_dir)
        self._ast_dir = self._cache_dir / "ast"
        self._semantic_dir = self._cache_dir / "semantic"
        self._checkpoint_dir = self._cache_dir / "checkpoint"

    @staticmethod
    def file_hash(path: Path, root: Path) -> str:
        try:
            content = path.read_bytes()
            relative = str(path.relative_to(root))
            return hashlib.sha256(content + b"\x00" + relative.encode()).hexdigest()
        except (OSError, ValueError):
            return ""

    @staticmethod
    def body_content(content: bytes) -> bytes:
        parts = content.split(b"---", 2)
        if len(parts) >= 3:
            return parts[2]
        return content

    def load_ast_cache(self, path: Path, root: Path) -> dict[str, Any] | None:
        return self._load_cached(path, root, self._ast_dir)

    def save_ast_cache(self, path: Path, result: dict[str, Any], root: Path) -> None:
        self._save_cached(path, result, root, self._ast_dir)

    def check_semantic_cache(
        self, files: list[str], root: Path,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        cached_entities: list[dict[str, Any]] = []
        cached_edges: list[dict[str, Any]] = []
        cached_categories: list[dict[str, Any]] = []
        uncached_files: list[str] = []

        for f in files:
            data = self._load_cached(Path(f), root, self._semantic_dir)
            if data is not None:
                cached_entities.extend(data.get("entities", []))
                cached_edges.extend(data.get("edges", []))
                cached_categories.extend(data.get("categories", []))
            else:
                uncached_files.append(f)

        return cached_entities, cached_edges, cached_categories, uncached_files

    def save_semantic_cache(
        self, entities: list[Any], edges: list[Any], categories: list[Any], root: Path,
    ) -> int:
        return 0

    def _load_cached(self, path: Path, root: Path, cache_subdir: Path) -> dict[str, Any] | None:
        h = self.file_hash(path, root)
        if not h:
            return None
        entry = cache_subdir / f"{h}.json"
        if not entry.exists():
            return None
        try:
            return json.loads(entry.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _save_cached(self, path: Path, result: dict[str, Any], root: Path, cache_subdir: Path) -> None:
        h = self.file_hash(path, root)
        if not h:
            return
        cache_subdir.mkdir(parents=True, exist_ok=True)
        entry = cache_subdir / f"{h}.json"
        tmp = entry.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, entry)
        except OSError:
            try:
                shutil.copy2(str(tmp), str(entry))
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def create_checkpoint(self, run_id: str) -> None:
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = self._checkpoint_dir / f"pipeline_{run_id}.json"
        checkpoint.write_text(json.dumps({
            "run_id": run_id,
            "started_at": datetime.utcnow().isoformat(),
            "total_files": 0,
            "processed_files": 0,
            "current_file": "",
            "results": {"entities": [], "edges": [], "categories": []},
        }), encoding="utf-8")

    def update_checkpoint(self, run_id: str, file_path: str, results: dict[str, Any]) -> None:
        checkpoint = self._checkpoint_dir / f"pipeline_{run_id}.json"
        if not checkpoint.exists():
            return
        try:
            data = json.loads(checkpoint.read_text(encoding="utf-8"))
            data["processed_files"] = data.get("processed_files", 0) + 1
            data["current_file"] = file_path
            for key in ("entities", "edges", "categories"):
                if key in results:
                    data["results"][key].extend(results[key])
            checkpoint.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            pass

    def load_checkpoint(self, run_id: str) -> dict[str, Any] | None:
        checkpoint = self._checkpoint_dir / f"pipeline_{run_id}.json"
        if not checkpoint.exists():
            return None
        try:
            return json.loads(checkpoint.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def clear_checkpoint(self, run_id: str) -> None:
        checkpoint = self._checkpoint_dir / f"pipeline_{run_id}.json"
        try:
            checkpoint.unlink(missing_ok=True)
        except OSError:
            pass

    def clear_cache(self, root: Path) -> None:
        for subdir in (self._ast_dir, self._semantic_dir, self._checkpoint_dir):
            if subdir.exists():
                shutil.rmtree(subdir, ignore_errors=True)
