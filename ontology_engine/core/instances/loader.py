from __future__ import annotations
from pathlib import Path
import yaml
from ontology_engine.storage.duckdb import EntityInstance, RelationInstance


class InstanceLoadError(Exception):
    """Error loading instances"""
    pass


class InstanceLoader:
    """Load instance data from YAML files."""

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

        for item in instances:
            # Support both 'concept' and 'fact_object' as the concept field name
            concept = item.get("concept") or item.get("fact_object")
            data_list = item.get("data", [])

            if not concept or not data_list:
                continue

            # Handle data as a list of entity objects
            if isinstance(data_list, list):
                for data in data_list:
                    entity_id = self._extract_entity_id(concept, data)
                    if not entity_id:
                        continue

                    # Add concept to data for reference
                    data["_concept"] = concept

                    entities.append(EntityInstance(
                        concept=concept,
                        entity_id=entity_id,
                        data=data
                    ))

                    # Extract relations
                    for rel_data in data.get("has_invoice", []):
                        relations.append(RelationInstance(
                            relation_type="has_invoice",
                            from_entity_id=entity_id,
                            to_entity_id=rel_data.get("invoice_no"),
                            data={}
                        ))

                    for rel_data in data.get("supplies_to", []):
                        relations.append(RelationInstance(
                            relation_type="supplies_to",
                            from_entity_id=entity_id,
                            to_entity_id=rel_data.get("enterprise_id"),
                            data={}
                        ))

                    for rel_data in data.get("guaranteed_by", []):
                        relations.append(RelationInstance(
                            relation_type="guaranteed_by",
                            from_entity_id=entity_id,
                            to_entity_id=rel_data.get("supplier_id"),
                            data={}
                        ))
            else:
                # Handle data as a single dict (fallback)
                data = data_list
                entity_id = self._extract_entity_id(concept, data)
                if entity_id:
                    data["_concept"] = concept
                    entities.append(EntityInstance(
                        concept=concept,
                        entity_id=entity_id,
                        data=data
                    ))

        return entities, relations

    def _extract_entity_id(self, concept: str, data: dict) -> str | None:
        """Extract entity ID from data based on concept type."""
        # Map concept to ID field
        id_fields = {
            "Supplier": "supplier_id",
            "CoreEnterprise": "enterprise_id",
            "Invoice": "invoice_no",
            "Contract": "contract_no",
            "GuaranteeRelation": "guarantor_id",  # Simplified
        }

        field = id_fields.get(concept, f"{concept.lower()}_id")
        return data.get(field)
