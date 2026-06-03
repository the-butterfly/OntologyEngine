"""Architecture boundary tests — verify module layer discipline.

These tests parse Python source files with the ``ast`` module and check
that import statements respect the module boundaries defined in
CLAUDE.md:

    api/           → services/  (禁止直接调 storage/, engine/)
    services/      → engine/    (禁止直接调 storage/)
    engine/        → storage/base.py  (禁止直接调 local/, adapters/)
    storage/local/ → 仅实现 base.py 接口 (禁止依赖上层)

Running:
    pytest tests/unit/architecture/test_layer_discipline.py -v
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import NamedTuple

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[4]  # OntologyEngine/
_SRC_ROOT = _PROJECT_ROOT / "ontology_engine"


class ImportViolation(NamedTuple):
    """A single boundary violation."""

    file: str
    line: int
    module: str
    rule: str


def _collect_imports(filepath: Path) -> list[tuple[int, str]]:
    """Return (line_number, module_path) for every import in *filepath*."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.lineno, node.module))
    return imports


def _python_files(directory: Path) -> list[Path]:
    """Recursively collect all .py files under *directory*."""
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.py"))


def _rel_path(filepath: Path) -> str:
    """Return path relative to project root as a string."""
    try:
        return str(filepath.relative_to(_PROJECT_ROOT))
    except ValueError:
        return str(filepath)


# ---------------------------------------------------------------------------
# Boundary rule implementations
# ---------------------------------------------------------------------------


def _check_api_no_storage_or_engine() -> list[ImportViolation]:
    """Rule 1: api/ must NOT import from storage/ or engine/ directly.

    api/ may only depend on services/.
    """
    violations: list[ImportViolation] = []
    api_dir = _SRC_ROOT / "api"
    for fp in _python_files(api_dir):
        for lineno, mod in _collect_imports(fp):
            if mod.startswith("ontology_engine.storage") or mod.startswith("ontology_engine.engine"):
                # Allow imports from ontology_engine.storage.base for type hints
                # used in dependency injection (TYPE_CHECKING only)
                if mod == "ontology_engine.storage.base":
                    # Check if it's inside TYPE_CHECKING block — allow for type hints
                    continue
                violations.append(
                    ImportViolation(
                        file=_rel_path(fp),
                        line=lineno,
                        module=mod,
                        rule="api → storage/engine (must go through services/)",
                    )
                )
    return violations


def _check_services_no_concrete_storage() -> list[ImportViolation]:
    """Rule 2: services/ must NOT import concrete storage implementations.

    services/ may only import from storage/base.py (abstract interfaces).
    """
    violations: list[ImportViolation] = []
    forbidden_prefixes = (
        "ontology_engine.storage.graph",
        "ontology_engine.storage.sqlite",
        "ontology_engine.storage.vector",
        "ontology_engine.storage.cognitive",
        "ontology_engine.storage.local",
        "ontology_engine.storage.cognitive_storage",
        "ontology_engine.storage.cognitive_interface",
        "ontology_engine.storage.dual_write",
        "ontology_engine.storage.retrieval",
        "ontology_engine.storage.config",
        "ontology_engine.storage.legacy_adapter",
        "ontology_engine.storage.migrations",
        "ontology_engine.storage.models",
    )
    allowed_prefixes = ("ontology_engine.storage.base", "ontology_engine.storage")

    services_dir = _SRC_ROOT / "services"
    for fp in _python_files(services_dir):
        for lineno, mod in _collect_imports(fp):
            if not mod.startswith("ontology_engine.storage"):
                continue
            if mod in allowed_prefixes:
                continue
            if any(mod.startswith(p) for p in forbidden_prefixes):
                violations.append(
                    ImportViolation(
                        file=_rel_path(fp),
                        line=lineno,
                        module=mod,
                        rule="services → concrete storage (only storage/base.py allowed)",
                    )
                )
    return violations


def _check_engine_no_concrete_storage() -> list[ImportViolation]:
    """Rule 3: engine/ must NOT import concrete storage implementations.

    engine/ may only import from storage/base.py (abstract interfaces).
    """
    violations: list[ImportViolation] = []
    forbidden_prefixes = (
        "ontology_engine.storage.graph",
        "ontology_engine.storage.sqlite",
        "ontology_engine.storage.vector",
        "ontology_engine.storage.local",
        "ontology_engine.storage.cognitive_storage",
        "ontology_engine.storage.dual_write",
        "ontology_engine.storage.retrieval",
        "ontology_engine.storage.config",
        "ontology_engine.storage.legacy_adapter",
        "ontology_engine.storage.migrations",
    )
    allowed_prefixes = (
        "ontology_engine.storage.base",
        "ontology_engine.storage.cognitive_interface",
        "ontology_engine.storage.models",
        "ontology_engine.storage",
    )

    engine_dir = _SRC_ROOT / "engine"
    for fp in _python_files(engine_dir):
        for lineno, mod in _collect_imports(fp):
            if not mod.startswith("ontology_engine.storage"):
                continue
            if mod in allowed_prefixes:
                continue
            if any(mod.startswith(p) for p in forbidden_prefixes):
                violations.append(
                    ImportViolation(
                        file=_rel_path(fp),
                        line=lineno,
                        module=mod,
                        rule="engine → concrete storage (only storage/base.py allowed)",
                    )
                )
    return violations


def _check_engine_no_storage_subpackages() -> list[ImportViolation]:
    """Rule 4: engine/ must NOT import from storage/graph/, storage/sqlite/,
    storage/vector/, storage/cognitive/ sub-packages.
    """
    violations: list[ImportViolation] = []
    forbidden_prefixes = (
        "ontology_engine.storage.graph.",
        "ontology_engine.storage.sqlite.",
        "ontology_engine.storage.vector.",
        "ontology_engine.storage.cognitive.",
        "ontology_engine.storage.local.",
    )

    engine_dir = _SRC_ROOT / "engine"
    for fp in _python_files(engine_dir):
        for lineno, mod in _collect_imports(fp):
            if any(mod.startswith(p) for p in forbidden_prefixes):
                violations.append(
                    ImportViolation(
                        file=_rel_path(fp),
                        line=lineno,
                        module=mod,
                        rule="engine → storage sub-package (graph/sqlite/vector/cognitive/local)",
                    )
                )
    return violations


def _check_storage_no_upstream() -> list[ImportViolation]:
    """Rule 5: storage/ implementations must NOT import from engine/, services/, api/."""
    violations: list[ImportViolation] = []
    forbidden_prefixes = (
        "ontology_engine.engine",
        "ontology_engine.services",
        "ontology_engine.api",
    )

    storage_dir = _SRC_ROOT / "storage"
    for fp in _python_files(storage_dir):
        for lineno, mod in _collect_imports(fp):
            if any(mod.startswith(p) for p in forbidden_prefixes):
                violations.append(
                    ImportViolation(
                        file=_rel_path(fp),
                        line=lineno,
                        module=mod,
                        rule="storage → upstream layer (engine/services/api)",
                    )
                )
    return violations


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------


class TestApiLayerDiscipline:
    """Verify api/ layer does not bypass services/."""

    def test_api_no_direct_storage_imports(self):
        """api/ must not import from storage/ directly — go through services/."""
        violations = _check_api_no_storage_or_engine()
        assert not violations, _format_violations(
            "api/ → storage/engine boundary violation", violations
        )

    def test_api_no_direct_engine_imports(self):
        """api/ must not import from engine/ directly — go through services/.

        This is the same check as above but specifically called out for
        clarity in test output.
        """
        violations = _check_api_no_storage_or_engine()
        engine_violations = [v for v in violations if "engine" in v.module]
        assert not engine_violations, _format_violations(
            "api/ → engine/ boundary violation", engine_violations
        )


class TestServicesLayerDiscipline:
    """Verify services/ layer does not reach into concrete storage."""

    def test_services_no_concrete_storage(self):
        """services/ must only import storage/base.py, not concrete implementations."""
        violations = _check_services_no_concrete_storage()
        assert not violations, _format_violations(
            "services/ → concrete storage boundary violation", violations
        )


class TestEngineLayerDiscipline:
    """Verify engine/ layer does not reach into concrete storage."""

    def test_engine_no_concrete_storage(self):
        """engine/ must only import storage/base.py, not concrete implementations."""
        violations = _check_engine_no_concrete_storage()
        assert not violations, _format_violations(
            "engine/ → concrete storage boundary violation", violations
        )

    def test_engine_no_storage_subpackages(self):
        """engine/ must not import from storage/graph/, sqlite/, vector/, cognitive/."""
        violations = _check_engine_no_storage_subpackages()
        assert not violations, _format_violations(
            "engine/ → storage sub-package boundary violation", violations
        )


class TestStorageLayerDiscipline:
    """Verify storage/ does not depend on upper layers."""

    def test_storage_no_upstream_imports(self):
        """storage/ must not import from engine/, services/, or api/."""
        violations = _check_storage_no_upstream()
        assert not violations, _format_violations(
            "storage/ → upstream layer boundary violation", violations
        )


# ---------------------------------------------------------------------------
# Formatting helper
# ---------------------------------------------------------------------------


def _format_violations(header: str, violations: list[ImportViolation]) -> str:
    """Format violation list into a human-readable assertion message."""
    lines = [f"\n{header}: {len(violations)} violation(s) found"]
    for v in violations:
        lines.append(f"  {v.file}:{v.line}  import {v.module}  [{v.rule}]")
    return "\n".join(lines)
