from __future__ import annotations

from pathlib import Path
from uuid import uuid5, NAMESPACE_DNS

import yaml
from typing import Any
from ontology_engine.storage.base import EntityInstance, RelationInstance

ENTITY_UUID_NAMESPACE = uuid5(NAMESPACE_DNS, "ontology-engine.entity")


class InstanceLoadError(Exception):
    """Error loading instances"""
    pass


class InstanceValidationError(InstanceLoadError):
    """Validation error when instance data doesn't match schema declarations."""


class InstanceLoader:
    """Load instance data from YAML files.

    Supports both v1 (concepts) and v2 (fact_objects) schema formats.
    Relations are automatically extracted based on schema RelationDeclaration
    or from inline relation data in instances (belongs_to_store pattern).
    """

    def __init__(self, schema: Any | None = None):
        """Initialize with optional schema for relation extraction.

        Args:
            schema: KGMLSchema object for auto-extracting relations.
                    If None, falls back to hardcoded relation names.
        """
        self._schema = schema
        self._relation_map = self._build_relation_map() if schema else {}

    def _build_relation_map(self) -> dict[str, list[dict]]:
        """Build a map of entity_id -> list of relation declarations from schema."""
        rel_map: dict[str, list[dict]] = {}
        if not self._schema:
            return rel_map

        for concept in self._schema.concepts:
            for rel in concept.relations:
                if concept.name not in rel_map:
                    rel_map[concept.name] = []
                rel_map[concept.name].append({
                    "name": rel.name,
                    "target": rel.target,
                    "cardinality": rel.cardinality,
                    "inverse": rel.inverse,
                })

        return rel_map

    def load(self, path: str | Path) -> tuple[list[EntityInstance], list[RelationInstance]]:
        """Load entities and relations from YAML.

        Returns:
            Tuple of (entities, relations)
        """
        path = Path(path)
        if not path.exists():
            raise InstanceLoadError(f"Instance file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        if not raw:
            return [], []

        instances = raw.get("instances", [])

        entities = []
        relations = []

        entity_index: dict[str, str] = {}

        for item in instances:
            concept = item.get("concept") or item.get("fact_object")
            data_list = item.get("data", [])

            if not concept or not data_list:
                continue

            if isinstance(data_list, list):
                for data in data_list:
                    entity_id = self._extract_entity_id(concept, data)
                    if not entity_id:
                        continue

                    data["_fact_object"] = concept
                    entity_index[entity_id] = concept

                    validation_errors = self._validate_entity_against_schema(concept, data)
                    if validation_errors:
                        raise InstanceValidationError(
                            f"Entity {entity_id} ({concept}): {'; '.join(validation_errors)}"
                        )

                    entities.append(EntityInstance(
                        _fact_object=concept,
                        entity_id=entity_id,
                        data=data
                    ))

                    extracted = self._extract_relations(concept, entity_id, data)
                    relations.extend(extracted)
            else:
                data = data_list
                entity_id = self._extract_entity_id(concept, data)
                if entity_id:
                    data["_fact_object"] = concept
                    entity_index[entity_id] = concept

                    validation_errors = self._validate_entity_against_schema(concept, data)
                    if validation_errors:
                        raise InstanceValidationError(
                            f"Entity {entity_id} ({concept}): {'; '.join(validation_errors)}"
                        )

                    entities.append(EntityInstance(
                        _fact_object=concept,
                        entity_id=entity_id,
                        data=data
                    ))

                    extracted = self._extract_relations(concept, entity_id, data)
                    relations.extend(extracted)

        bidirectional = self._generate_bidirectional_relations(relations, entity_index)
        existing = {(r.relation_name, r.from_entity_id, r.to_entity_id) for r in relations}
        for br in bidirectional:
            key = (br.relation_name, br.from_entity_id, br.to_entity_id)
            if key not in existing:
                relations.append(br)
                existing.add(key)

        self._validate_relations(relations, entity_index)

        return entities, relations

    def _validate_relations(
        self,
        relations: list[RelationInstance],
        entity_index: dict[str, str],
    ) -> None:
        for r in relations:
            if r.from_entity_id == r.to_entity_id:
                raise InstanceValidationError(
                    f"Self-loop detected: {r.relation_name} from {r.from_entity_id} to itself"
                )
            if r.from_entity_id not in entity_index:
                raise InstanceValidationError(
                    f"Relation {r.relation_name}: from_entity_id '{r.from_entity_id}' not found in loaded entities"
                )
            if r.to_entity_id not in entity_index:
                raise InstanceValidationError(
                    f"Relation {r.relation_name}: to_entity_id '{r.to_entity_id}' not found in loaded entities"
                )

    def _extract_relations(
        self,
        concept: str,
        entity_id: str,
        data: dict,
    ) -> list[RelationInstance]:
        """Extract relations from entity data based on schema declarations.

        Strategy:
        1. Schema-driven: Use RelationDeclaration from schema to find inline relation data
        2. Inline reference: Detect dict-valued fields matching '{entity_id_key: value}' pattern
           (e.g., belongs_to_store: {store_id: "SH-001"})
        3. Fallback: Hardcoded legacy relation names for backward compatibility
        """
        relations: list[RelationInstance] = []

        schema_rels = self._relation_map.get(concept, [])

        if schema_rels:
            for rel_decl in schema_rels:
                rel_name = rel_decl["name"]
                rel_data = data.get(rel_name)
                if rel_data is None:
                    continue

                target_concept = rel_decl["target"]
                target_id = self._resolve_target_id(target_concept, rel_data)
                if target_id:
                    relations.append(RelationInstance(
                        relation_name=rel_name,
                        from_entity_id=entity_id,
                        to_entity_id=target_id,
                        data={},
                    ))
                elif isinstance(rel_data, list):
                    for item in rel_data:
                        target_id = self._resolve_target_id(target_concept, item)
                        if target_id:
                            relations.append(RelationInstance(
                                relation_name=rel_name,
                                from_entity_id=entity_id,
                                to_entity_id=target_id,
                                data={},
                            ))

        for key, value in list(data.items()):
            if key.startswith("_") or key in {c["name"] for c in schema_rels}:
                continue

            if isinstance(value, dict):
                target_id = self._resolve_target_id_from_dict(value)
                if target_id and target_id != entity_id:
                    relations.append(RelationInstance(
                        relation_name=key,
                        from_entity_id=entity_id,
                        to_entity_id=target_id,
                        data={},
                    ))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        target_id = self._resolve_target_id_from_dict(item)
                        if target_id and target_id != entity_id:
                            relations.append(RelationInstance(
                                relation_name=key,
                                from_entity_id=entity_id,
                                to_entity_id=target_id,
                                data={},
                            ))

        return relations

    def _generate_bidirectional_relations(
        self,
        relations: list[RelationInstance],
        entity_index: dict[str, str],
    ) -> list[RelationInstance]:
        """Generate inverse relations for schema-declared bidirectional relations.

        When schema declares a relation with an 'inverse' field, e.g.:
          Supplier --has_invoice--> Invoice  (inverse: issued_by)
          Invoice --issued_by--> Supplier    (inverse: has_invoice)

        If only the 'issued_by' direction is extracted from instance data,
        this method creates the 'has_invoice' direction automatically.

        Args:
            relations: Already extracted relations
            entity_index: Map of entity_id -> concept_name

        Returns:
            List of inverse RelationInstances to add
        """
        if not self._schema:
            return []

        inverse_map = self._build_inverse_map()
        if not inverse_map:
            return []

        new_relations: list[RelationInstance] = []

        for rel in relations:
            from_concept = entity_index.get(rel.from_entity_id)
            to_concept = entity_index.get(rel.to_entity_id)
            if not from_concept or not to_concept:
                continue

            key = (from_concept, rel.relation_name)
            inverse_info = inverse_map.get(key)
            if inverse_info:
                inv_rel_name, inv_from_concept = inverse_info
                if inv_from_concept == to_concept:
                    new_relations.append(RelationInstance(
                        relation_name=inv_rel_name,
                        from_entity_id=rel.to_entity_id,
                        to_entity_id=rel.from_entity_id,
                        data={},
                    ))

        return new_relations

    def _build_inverse_map(self) -> dict[tuple[str, str], tuple[str, str]]:
        """Build a map from (concept, relation_name) to (inverse_relation_name, inverse_concept).

        For each relation with an 'inverse' field, creates two entries:
        - (source_concept, rel_name) -> (inverse_name, target_concept)
        - (target_concept, inverse_name) -> (rel_name, source_concept)
        """
        inverse_map: dict[tuple[str, str], tuple[str, str]] = {}
        if not self._schema:
            return inverse_map

        for concept in self._schema.concepts:
            for rel in concept.relations:
                if rel.inverse:
                    inverse_map[(concept.name, rel.name)] = (rel.inverse, rel.target)
                    target_concept_def = self._schema.get_concept(rel.target)
                    if target_concept_def:
                        inverse_map[(rel.target, rel.inverse)] = (rel.name, concept.name)

        return inverse_map

    def _resolve_target_id(self, target_concept: str, rel_data: Any) -> str | None:
        """Resolve target entity ID from relation data.

        Handles patterns like:
        - {store_id: "SH-001"}  → "SH-001"
        - {enterprise_id: "CE_HW"}  → "CE_HW"
        - "SUP_001" (plain string)  → "SUP_001"
        """
        if isinstance(rel_data, str):
            return rel_data

        if not isinstance(rel_data, dict):
            return None

        id_field = self._infer_id_field(target_concept)
        if id_field in rel_data:
            return str(rel_data[id_field])

        for k, v in rel_data.items():
            if k.endswith("_id") or k.endswith("_no"):
                return str(v)

        return None

    def _resolve_target_id_from_dict(self, value: dict) -> str | None:
        """Resolve target entity ID from an inline dict value.

        Detects patterns like:
        - {store_id: "SH-001"}
        - {supplier_id: "SUP_001"}
        - {invoice_no: "INV-001"}
        """
        for k, v in value.items():
            if k.endswith("_id") or k.endswith("_no"):
                return str(v)
        return None

    def _infer_id_field(self, concept_name: str) -> str:
        """Infer the ID field name for a concept.

        Strategy:
        1. Use schema declarations (unique attribute) if available
        2. Convention: concept_name → concept_name_id (lowercased)
        3. Special naming conventions: Invoice → invoice_no, Contract → contract_no
        """
        if self._schema:
            id_field = self._schema.get_entity_id_field(concept_name)
            if id_field:
                return id_field

        lower = concept_name.lower()
        if lower.endswith("invoice") or lower.endswith("contract"):
            return f"{lower}_no"
        if lower.endswith("enterprise"):
            return "enterprise_id"

        return f"{lower}_id"

    def _extract_entity_id(self, concept: str, data: dict) -> str | None:
        """Extract entity ID from data based on concept type.

        Strategy:
        1. Use schema-driven identity_fields for UUID5 deterministic ID
        2. Use schema-driven ID field discovery
        3. Auto-detect by convention: {concept_lower}_id, {concept_lower}_no
        4. Scan data for any field ending in _id or _no
        """
        identity_fields = self._get_identity_fields(concept)
        if identity_fields:
            return self._generate_uuid5_id(concept, data, identity_fields)

        id_field = self._infer_id_field(concept)
        if id_field and id_field in data:
            return data[id_field]

        for candidate in [
            f"{concept.lower()}_id",
            f"{concept.lower()}_no",
        ]:
            if candidate in data:
                return data[candidate]

        for k, v in data.items():
            if k.endswith("_id") or k.endswith("_no"):
                if isinstance(v, str) and v:
                    return v

        return None

    def _get_identity_fields(self, concept: str) -> list[str]:
        """Get identity_fields from schema declaration for a concept."""
        if not self._schema:
            return []
        fo = self._schema.get_fact_object(concept)
        if fo and hasattr(fo, "identity_fields") and fo.identity_fields:
            return fo.identity_fields
        return []

    def _generate_uuid5_id(self, concept: str, data: dict, identity_fields: list[str]) -> str:
        """Generate deterministic UUID5 based on concept + identity field values."""
        parts = [concept]
        for field_name in identity_fields:
            val = data.get(field_name, "")
            parts.append(str(val))
        seed = "|".join(parts)
        return str(uuid5(ENTITY_UUID_NAMESPACE, seed))

    def _validate_entity_against_schema(self, concept: str, data: dict) -> list[str]:
        """Validate entity data against schema declarations.

        Returns list of validation error messages (empty if valid).
        """
        errors: list[str] = []
        if not self._schema:
            return errors

        fo = self._schema.get_fact_object(concept)
        if not fo:
            return errors

        declared_attrs = {attr.name for attr in fo.attributes}
        required_attrs = {attr.name for attr in fo.attributes if attr.required}

        data_keys = {k for k in data.keys() if not k.startswith("_")}

        undeclared = data_keys - declared_attrs
        if undeclared:
            errors.append(f"Undeclared attributes: {undeclared}")

        missing_required = required_attrs - data_keys
        if missing_required:
            errors.append(f"Missing required attributes: {missing_required}")

        return errors
