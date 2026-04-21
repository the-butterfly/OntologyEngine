"""AST-based deterministic extraction for structured source files."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ENTITY_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


@dataclass
class LanguageConfig:
    name: str
    extensions: set[str]
    class_types: set[str]
    function_types: set[str]
    import_types: set[str]
    call_types: set[str]


LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "python": LanguageConfig(
        name="python",
        extensions={".py"},
        class_types={"class_definition"},
        function_types={"function_definition"},
        import_types={"import_statement", "import_from_statement"},
        call_types={"call"},
    ),
    "javascript": LanguageConfig(
        name="javascript",
        extensions={".js", ".jsx", ".ts", ".tsx"},
        class_types={"class_declaration", "class"},
        function_types={"function_declaration", "arrow_function", "function"},
        import_types={"import_statement", "import_declaration"},
        call_types={"call_expression"},
    ),
    "yaml": LanguageConfig(
        name="yaml",
        extensions={".yaml", ".yml"},
        class_types=set(),
        function_types=set(),
        import_types=set(),
        call_types=set(),
    ),
    "markdown": LanguageConfig(
        name="markdown",
        extensions={".md", ".mdx"},
        class_types=set(),
        function_types=set(),
        import_types=set(),
        call_types=set(),
    ),
}


def _generate_entity_id(identity_fields: list[str]) -> str:
    name = ":".join(identity_fields)
    return str(uuid.uuid5(ENTITY_NAMESPACE, name))


@dataclass
class ASTExtractionResult:
    entities: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    extracted_from_edges: list[dict[str, Any]] = field(default_factory=list)


class ASTExtractor:
    """Pass 1: AST deterministic extraction from source files."""

    def extract(self, source_file_path: str) -> ASTExtractionResult:
        path = Path(source_file_path)
        if not path.exists():
            return ASTExtractionResult()

        lang = self.identify_language(str(path))
        if lang is None:
            return ASTExtractionResult()

        if lang.name == "yaml":
            return self._extract_yaml(str(path))
        if lang.name == "markdown":
            return self._extract_markdown(str(path))

        return self._extract_code(str(path), lang)

    def identify_language(self, file_path: str) -> LanguageConfig | None:
        ext = Path(file_path).suffix.lower()
        for config in LANGUAGE_CONFIGS.values():
            if ext in config.extensions:
                return config
        return None

    def _extract_code(self, file_path: str, lang: LanguageConfig) -> ASTExtractionResult:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ASTExtractionResult()

        entities: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        extracted_from_edges: list[dict[str, Any]] = []

        file_id = _generate_entity_id([file_path])
        entities.append({
            "entity_id": file_id,
            "_fact_object": "code:File",
            "attributes": {"relative_path": file_path, "name": Path(file_path).name},
            "confidence": 1.0,
            "source_pipeline": "ast_extraction",
        })

        class_pattern = re.compile(r"class\s+(\w+)")
        func_pattern = re.compile(r"def\s+(\w+)")

        for match in class_pattern.finditer(content):
            class_name = match.group(1)
            class_id = _generate_entity_id([file_path, class_name])
            entities.append({
                "entity_id": class_id,
                "_fact_object": "code:Class",
                "attributes": {"name": class_name, "source_file": file_path},
                "confidence": 1.0,
                "source_pipeline": "ast_extraction",
            })
            edges.append({
                "from_id": file_id,
                "to_id": class_id,
                "relation_name": "code:contains",
                "confidence": 1.0,
                "source_pipeline": "ast_extraction",
            })
            extracted_from_edges.append({
                "from_id": class_id,
                "to_id": file_id,
                "edge_type": "EXTRACTED_FROM",
                "confidence": 1.0,
                "source_file": file_path,
                "offset_start": match.start(),
                "offset_end": match.end(),
            })

        for match in func_pattern.finditer(content):
            func_name = match.group(1)
            func_id = _generate_entity_id([file_path, func_name])
            entities.append({
                "entity_id": func_id,
                "_fact_object": "code:Function",
                "attributes": {"name": func_name, "source_file": file_path},
                "confidence": 1.0,
                "source_pipeline": "ast_extraction",
            })
            edges.append({
                "from_id": file_id,
                "to_id": func_id,
                "relation_name": "code:contains",
                "confidence": 1.0,
                "source_pipeline": "ast_extraction",
            })
            extracted_from_edges.append({
                "from_id": func_id,
                "to_id": file_id,
                "edge_type": "EXTRACTED_FROM",
                "confidence": 1.0,
                "source_file": file_path,
                "offset_start": match.start(),
                "offset_end": match.end(),
            })

        return ASTExtractionResult(
            entities=entities,
            edges=edges,
            extracted_from_edges=extracted_from_edges,
        )

    def _extract_yaml(self, file_path: str) -> ASTExtractionResult:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ASTExtractionResult()

        entities: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        try:
            import yaml
            data = yaml.safe_load(content)
        except Exception:
            return ASTExtractionResult()

        if isinstance(data, dict):
            for key in data:
                fact_object = f"schema:{key}"
                entity_id = _generate_entity_id([file_path, key])
                entities.append({
                    "entity_id": entity_id,
                    "_fact_object": fact_object,
                    "attributes": {"name": key, "source_file": file_path},
                    "confidence": 1.0,
                    "source_pipeline": "ast_extraction",
                })

        return ASTExtractionResult(entities=entities, edges=edges)

    def _extract_markdown(self, file_path: str) -> ASTExtractionResult:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ASTExtractionResult()

        entities: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        extracted_from_edges: list[dict[str, Any]] = []

        file_id = _generate_entity_id([file_path])
        entities.append({
            "entity_id": file_id,
            "_fact_object": "doc:Document",
            "attributes": {"name": Path(file_path).name, "source_file": file_path},
            "confidence": 1.0,
            "source_pipeline": "ast_extraction",
        })

        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        for match in heading_pattern.finditer(content):
            level = len(match.group(1))
            text = match.group(2).strip()
            heading_id = _generate_entity_id([file_path, str(level), text])
            entities.append({
                "entity_id": heading_id,
                "_fact_object": "doc:Heading",
                "attributes": {"text": text, "level": level, "source_file": file_path},
                "confidence": 1.0,
                "source_pipeline": "ast_extraction",
            })
            edges.append({
                "from_id": file_id,
                "to_id": heading_id,
                "relation_name": "doc:contains",
                "confidence": 1.0,
                "source_pipeline": "ast_extraction",
            })
            extracted_from_edges.append({
                "from_id": heading_id,
                "to_id": file_id,
                "edge_type": "EXTRACTED_FROM",
                "confidence": 1.0,
                "source_file": file_path,
                "offset_start": match.start(),
                "offset_end": match.end(),
            })

        return ASTExtractionResult(
            entities=entities,
            edges=edges,
            extracted_from_edges=extracted_from_edges,
        )
