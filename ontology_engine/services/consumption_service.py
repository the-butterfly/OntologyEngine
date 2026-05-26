from __future__ import annotations

import asyncio
from typing import Any

from ontology_engine.core.semantic_space import (
    SpaceType,
    SemanticSpaceStorage,
)
from ontology_engine.services.analysis_orchestrator import AnalysisOrchestrator
from ontology_engine.services.impact_chain_service import ImpactChainService
from ontology_engine.services.rule_execution_service import RuleExecutionService


class ConsumptionService:

    def __init__(self, storage: SemanticSpaceStorage | None = None) -> None:
        self._storage = storage or SemanticSpaceStorage()
        self._rule_execution = RuleExecutionService()
        self._impact_chain = ImpactChainService()
        self._analysis_orchestrator = AnalysisOrchestrator(
            storage=self._storage,
            rule_execution=self._rule_execution,
        )

    async def list_views(self) -> list[dict[str, Any]]:
        all_metadata = await self._storage.list()
        consumption_views = [
            m for m in all_metadata if m.space_type == SpaceType.CONSUMPTION
        ]
        views = []
        for metadata in consumption_views:
            space = await self._storage.load(metadata.id)
            if space:
                views.append({
                    "id": space.metadata.id,
                    "name": space.metadata.name,
                    "description": space.metadata.description,
                    "status": space.metadata.status.value,
                    "entity_count": len(space.instances.entities),
                    "rule_count": len(space.layers.L4_business_logic.rule_definitions),
                    "created_at": space.metadata.created_at.isoformat(),
                })
        return views

    async def get_view(self, view_id: str) -> dict[str, Any] | None:
        space = await self._storage.load(view_id)
        if not space:
            return None
        if space.metadata.space_type != SpaceType.CONSUMPTION:
            return None
        return {
            "id": space.metadata.id,
            "name": space.metadata.name,
            "description": space.metadata.description,
            "status": space.metadata.status.value,
            "entity_count": len(space.instances.entities),
            "relation_count": len(space.instances.relations),
            "rule_definition_count": len(space.layers.L4_business_logic.rule_definitions),
            "L1_count": len(space.layers.L1_fact_objects),
            "L2_count": len(space.layers.L2_categorizations),
            "L3_count": len(space.layers.L3_analytical_elements),
            "created_at": space.metadata.created_at.isoformat(),
        }

    async def list_view_entities(
        self, view_id: str, concept: str | None = None
    ) -> list[dict] | None:
        space = await self._storage.load(view_id)
        if not space:
            return None
        entities = space.instances.entities
        if concept:
            entities = [
                e
                for e in entities
                if (e.get("_fact_object") or e.get("_concept")) == concept
            ]
        return entities

    async def get_schema_graph(
        self,
        view_id: str,
        graph_type: str = "entity_relation",
        layer_filter: str | None = None,
    ) -> dict[str, Any] | None:
        space = await self._storage.load(view_id)
        if not space:
            return None

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        for entity in space.layers.L1_fact_objects:
            entity_id = entity.get("id", entity.get("name", "unknown"))
            nodes.append({
                "id": entity_id,
                "type": "entity",
                "data": {
                    "label": entity.get("name", entity_id),
                    "category": "entity",
                    "layer": "L1",
                    "properties": entity.get("properties", []),
                    "description": entity.get("description", ""),
                },
            })
            for rel in entity.get("relations", []):
                rel_id = f"{entity_id}__{rel.get('target')}__{rel.get('name')}"
                edges.append({
                    "id": rel_id,
                    "source": entity_id,
                    "target": rel.get("target", ""),
                    "type": "relation",
                    "data": {
                        "label": rel.get("name", ""),
                        "cardinality": rel.get("cardinality", ""),
                    },
                })

        for cat in space.layers.L2_categorizations:
            cat_id = cat.get("id", cat.get("name", "unknown"))
            nodes.append({
                "id": cat_id,
                "type": "category",
                "data": {
                    "label": cat.get("name", cat_id),
                    "category": "categorization",
                    "layer": "L2",
                    "applicable_to": cat.get("applicable_to", []),
                    "description": cat.get("description", ""),
                },
            })

        for element in space.layers.L3_analytical_elements:
            elem_id = element.get("id", element.get("name", "unknown"))
            elem_type = self._metric_type(element)
            nodes.append({
                "id": elem_id,
                "type": "metric",
                "data": {
                    "label": element.get("name", elem_id),
                    "category": "element",
                    "layer": "L3",
                    "type": elem_type,
                    "formula": element.get("formula", ""),
                    "dependencies": element.get("dependencies", []),
                    "overridable": element.get("overridable", False),
                    "description": element.get("description", ""),
                },
            })
            for dep in element.get("dependencies", []):
                edges.append({
                    "id": f"{dep}__{elem_id}__dep",
                    "source": dep,
                    "target": elem_id,
                    "type": "dependency",
                    "data": {"label": "依赖"},
                })
            for comp in element.get("components", []) or []:
                comp_metric = comp.get("metric", "")
                if comp_metric:
                    edges.append({
                        "id": f"{comp_metric}__{elem_id}__component",
                        "source": comp_metric,
                        "target": elem_id,
                        "type": "component",
                        "data": {
                            "label": f"权重{comp.get('weight', 1.0)}",
                            "weight": comp.get("weight", 1.0),
                        },
                    })

        for rule in space.layers.L4_business_logic.rule_definitions:
            rule_id = rule.get("id", "unknown")
            nodes.append({
                "id": rule_id,
                "type": "rule",
                "data": {
                    "label": rule.get("name", rule_id),
                    "category": "rule_definition",
                    "layer": "L4",
                    "rule_type": rule.get("rule_type", "constraint"),
                    "priority": rule.get("priority", 100),
                    "enabled": rule.get("enabled", True),
                    "applies_to": rule.get("applies_to") or rule.get("target_objects") or [],
                    "inputs": [
                        e.get("name") or e.get("id", "")
                        for e in self._rule_inputs(rule)
                    ],
                    "outputs": [
                        e.get("name") or e.get("id", "")
                        for e in self._rule_outputs(rule)
                    ],
                    "logic_count": len(rule.get("logic_ids", [])),
                    "description": rule.get("description", ""),
                },
            })
            for in_elem in self._rule_inputs(rule):
                elem_name = in_elem.get("name") or in_elem.get("id", "")
                if elem_name:
                    edges.append({
                        "id": f"{elem_name}__{rule_id}__input",
                        "source": elem_name,
                        "target": rule_id,
                        "type": "rule_input",
                        "data": {"label": "输入"},
                    })

        if layer_filter:
            layers = [lyr.strip() for lyr in layer_filter.split(",")]
            layer_type_map = {
                "L1": "entity",
                "L2": "category",
                "L3": "metric",
                "L4": "rule",
            }
            allowed_types = {
                layer_type_map[lyr]
                for lyr in layers
                if lyr in layer_type_map
            }
            node_ids_in_filter = {
                n["id"] for n in nodes if n["type"] in allowed_types
            }
            nodes = [n for n in nodes if n["id"] in node_ids_in_filter]
            edges = [
                e
                for e in edges
                if e["source"] in node_ids_in_filter
                and e["target"] in node_ids_in_filter
            ]

        return {
            "view_id": view_id,
            "graph_type": graph_type,
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "entity_count": len(
                    [n for n in nodes if n["type"] == "entity"]
                ),
                "category_count": len(
                    [n for n in nodes if n["type"] == "category"]
                ),
                "metric_count": len(
                    [n for n in nodes if n["type"] == "metric"]
                ),
                "rule_count": len(
                    [n for n in nodes if n["type"] == "rule"]
                ),
                "edge_count": len(edges),
            },
        }

    async def get_rule_dependency_graph(
        self, view_id: str
    ) -> dict[str, Any] | None:
        space = await self._storage.load(view_id)
        if not space:
            return None

        rules = space.layers.L4_business_logic.rule_definitions
        rule_logics = space.layers.L4_business_logic.rule_logics

        nodes = []
        for rule in rules:
            logic_ids = rule.get("logic_ids", [])
            logics = [
                rl for rl in rule_logics if rl.get("id") in logic_ids
            ]
            nodes.append({
                "id": rule["id"],
                "label": rule.get("name") or rule["id"],
                "rule_type": rule.get("rule_type", "constraint"),
                "priority": rule.get("priority", 100),
                "enabled": rule.get("enabled", True),
                "applies_to": rule.get("applies_to")
                or rule.get("target_objects")
                or [],
                "applicable_categorizations": rule.get(
                    "applicable_categorizations", []
                ),
                "inputs": self._rule_inputs(rule),
                "outputs": self._rule_outputs(rule),
                "logic_count": len(logics),
                "logics": [
                    {
                        "id": lg.get("id"),
                        "name": lg.get("name"),
                        "applicable_conditions": lg.get(
                            "applicable_conditions", []
                        ),
                        "when": lg.get("when"),
                        "then_action": lg.get("then_action"),
                    }
                    for lg in logics
                ],
            })

        edges = []
        output_map: dict[str, list[str]] = {}
        for rule in rules:
            for out_elem in self._rule_outputs(rule):
                elem_name = out_elem.get("name") or out_elem.get("id", "")
                if elem_name:
                    output_map.setdefault(elem_name, []).append(rule["id"])

        for rule in rules:
            for in_elem in self._rule_inputs(rule):
                elem_name = in_elem.get("name") or in_elem.get("id", "")
                producers = output_map.get(elem_name, [])
                for producer_id in producers:
                    if producer_id != rule["id"]:
                        edges.append({
                            "id": f"{producer_id}__{rule['id']}__{elem_name}",
                            "source": producer_id,
                            "target": rule["id"],
                            "element": elem_name,
                            "type": "data_dependency",
                            "label": elem_name,
                        })

        exclusion_pairs = []
        for i, rule_a in enumerate(rules):
            for rule_b in rules[i + 1 :]:
                cats_a = set(rule_a.get("applicable_categorizations", []))
                cats_b = set(rule_b.get("applicable_categorizations", []))
                if cats_a and cats_b and not (cats_a & cats_b):
                    exclusion_pairs.append({
                        "rule_a": rule_a["id"],
                        "rule_b": rule_b["id"],
                        "reason": f"适用分类不重叠: {list(cats_a)} vs {list(cats_b)}",
                        "type": "categorization_exclusive",
                    })
                outputs_a = {
                    (e.get("name") or e.get("id", ""))
                    for e in self._rule_outputs(rule_a)
                }
                outputs_b = {
                    (e.get("name") or e.get("id", ""))
                    for e in self._rule_outputs(rule_b)
                }
                shared = outputs_a & outputs_b - {""}
                if shared:
                    exclusion_pairs.append({
                        "rule_a": rule_a["id"],
                        "rule_b": rule_b["id"],
                        "reason": f"输出元素冲突: {list(shared)}",
                        "type": "output_conflict",
                    })

        execution_order = self._analysis_orchestrator.topological_sort_rules(nodes, edges)

        return {
            "view_id": view_id,
            "nodes": nodes,
            "edges": edges,
            "mutual_exclusions": exclusion_pairs,
            "execution_order": execution_order,
            "stats": {
                "total_rules": len(nodes),
                "dependency_edges": len(edges),
                "exclusion_pairs": len(exclusion_pairs),
            },
        }

    async def get_rules_for_entity(
        self,
        view_id: str,
        entity_id: str,
        dimension: str | None = None,
    ) -> dict[str, Any] | None:
        space = await self._storage.load(view_id)
        if not space:
            return None

        entity = next(
            (
                e
                for e in space.instances.entities
                if e.get("entity_id") == entity_id
            ),
            None,
        )
        if not entity:
            return {"error": "entity_not_found", "entity_id": entity_id}

        entity_concept = entity.get("_fact_object") or entity.get(
            "_concept", ""
        )
        rules = space.layers.L4_business_logic.rule_definitions
        rule_logics = space.layers.L4_business_logic.rule_logics

        applicable_rules: list[dict[str, Any]] = []
        for rule in rules:
            if not rule.get("enabled", True):
                continue

            target_objects = self._rule_applies_to(rule)
            if (
                target_objects
                and entity_concept
                and entity_concept not in target_objects
            ):
                continue

            logic_ids = rule.get("logic_ids", [])
            matching_logics = []
            for logic_id in logic_ids:
                logic = next(
                    (
                        rl
                        for rl in rule_logics
                        if rl.get("id") == logic_id
                    ),
                    None,
                )
                if logic:
                    conditions = logic.get("applicable_conditions", [])
                    match = True
                    for cond in conditions:
                        classification = cond.get("classification", "")
                        operator = cond.get("operator", "eq")
                        value = cond.get("value")
                        entity_value = entity.get(classification, "")
                        if operator == "eq" and entity_value != value:
                            match = False
                            break
                        elif operator == "in" and entity_value not in (
                            value
                            if isinstance(value, list)
                            else [value]
                        ):
                            match = False
                            break
                    if match:
                        matching_logics.append({
                            "id": logic.get("id"),
                            "name": logic.get("name"),
                            "when": logic.get("when"),
                            "then_action": logic.get("then_action"),
                        })

            applicable_rules.append({
                "id": rule["id"],
                "name": rule.get("name") or rule["id"],
                "rule_type": rule.get("rule_type", "constraint"),
                "priority": rule.get("priority", 100),
                "applies_to": target_objects,
                "inputs": self._rule_inputs(rule),
                "outputs": self._rule_outputs(rule),
                "matching_logics": matching_logics,
                "applicable_logics_count": len(matching_logics),
            })

        applicable_rules.sort(key=lambda r: -r["priority"])

        output_map: dict[str, list[str]] = {}
        for rule in applicable_rules:
            for out_elem in self._rule_outputs(rule):
                elem_name = out_elem.get("name") or out_elem.get("id", "")
                if elem_name:
                    output_map.setdefault(elem_name, []).append(rule["id"])

        dependency_edges = []
        for rule in applicable_rules:
            for in_elem in self._rule_inputs(rule):
                elem_name = in_elem.get("name") or in_elem.get("id", "")
                for producer_id in output_map.get(elem_name, []):
                    if producer_id != rule["id"]:
                        dependency_edges.append({
                            "from": producer_id,
                            "to": rule["id"],
                            "via_element": elem_name,
                        })

        return {
            "entity_id": entity_id,
            "entity_concept": entity_concept,
            "view_id": view_id,
            "applicable_rules": applicable_rules,
            "dependency_edges": dependency_edges,
            "total": len(applicable_rules),
        }

    async def get_metric_snapshot(
        self,
        view_id: str,
        entity_id: str,
        dimension: str = "credit_assessment",
    ) -> dict[str, Any] | None:
        space = await self._storage.load(view_id)
        if not space:
            return None

        entity = next(
            (
                e
                for e in space.instances.entities
                if e.get("entity_id") == entity_id
            ),
            None,
        )
        if not entity:
            return {"error": "entity_not_found", "entity_id": entity_id}

        result = await self._analysis_orchestrator.run_full_analysis(
            space, entity, dimension, {}, include_trace=False
        )

        return {
            "entity_id": entity_id,
            "dimension": dimension,
            "metrics": result.get("computed_metrics", {}),
            "outputs": result.get("final_outputs", {}),
            "decision": result.get("decision", None),
            "decision_reasoning": None,
        }

    async def execute_analyze(
        self,
        view_id: str,
        entity_id: str,
        dimension: str = "credit_assessment",
        include_trace: bool = True,
    ) -> dict[str, Any] | None:
        space = await self._storage.load(view_id)
        if not space:
            return None

        entity = next(
            (
                e
                for e in space.instances.entities
                if e.get("entity_id") == entity_id
            ),
            None,
        )
        if not entity:
            return {"error": "entity_not_found", "entity_id": entity_id}

        return await self._analysis_orchestrator.run_full_analysis(
            space, entity, dimension, {}, include_trace
        )

    async def execute_simulate(
        self,
        view_id: str,
        entity_id: str,
        dimension: str = "credit_assessment",
        overrides: dict[str, Any] | None = None,
        include_trace: bool = True,
    ) -> dict[str, Any] | None:
        space = await self._storage.load(view_id)
        if not space:
            return None

        entity = next(
            (
                e
                for e in space.instances.entities
                if e.get("entity_id") == entity_id
            ),
            None,
        )
        if not entity:
            return {"error": "entity_not_found", "entity_id": entity_id}

        baseline, simulated = await asyncio.gather(
            self._analysis_orchestrator.run_full_analysis(
                space, entity, dimension, {}, include_trace
            ),
            self._analysis_orchestrator.run_full_analysis(
                space,
                entity,
                dimension,
                overrides or {},
                include_trace,
            ),
        )

        baseline_outputs = baseline.get("final_outputs", {})
        simulated_outputs = simulated.get("final_outputs", {})
        all_keys = set(baseline_outputs.keys()) | set(
            simulated_outputs.keys()
        )

        diffs = []
        for key in sorted(all_keys):
            bv = baseline_outputs.get(key)
            sv = simulated_outputs.get(key)
            if bv != sv:
                change_type = "changed"
                if key not in baseline_outputs:
                    change_type = "new"
                elif key not in simulated_outputs:
                    change_type = "removed"
                elif isinstance(bv, (int, float)) and isinstance(
                    sv, (int, float)
                ):
                    change_type = "increased" if sv > bv else "decreased"

                diffs.append({
                    "field": key,
                    "baseline_value": bv,
                    "simulated_value": sv,
                    "change_type": change_type,
                    "impact": f"{bv} → {sv}",
                })

        impact_chains = self._impact_chain.compute_impact_chains(
            space,
            entity,
            overrides or {},
            baseline_outputs,
            simulated_outputs,
        )

        return {
            "entity_id": entity_id,
            "dimension": dimension,
            "simulation_type": "what_if",
            "overrides": overrides or {},
            "baseline_outputs": baseline_outputs,
            "simulated_outputs": simulated_outputs,
            "final_outputs": simulated_outputs,
            "steps": simulated.get("steps", []),
            "execution_path": simulated.get("execution_path", []),
            "skipped_rules": simulated.get("skipped_rules", []),
            "comparison": {
                "diffs": diffs,
                "impact_chains": impact_chains,
                "changed_fields": len(diffs),
            },
        }

    def _metric_type(self, element: dict) -> str:
        return element.get("type") or element.get("element_type") or "derived"

    def _rule_inputs(self, rule: dict) -> list[dict]:
        return rule.get("inputs") or rule.get("input_elements") or []

    def _rule_outputs(self, rule: dict) -> list[dict]:
        return rule.get("outputs") or rule.get("output_elements") or []

    def _rule_applies_to(self, rule: dict) -> list:
        applies = rule.get("applies_to") or rule.get("target_objects") or []
        if isinstance(applies, dict):
            return applies.get("fact_objects", [])
        if isinstance(applies, list):
            if applies and isinstance(applies[0], dict):
                return [
                    item.get("id") or item.get("name", "")
                    for item in applies
                    if item.get("id") or item.get("name")
                ]
        return applies

    async def analyze_schema_impact(
        self,
        view_id: str,
        change_type: str,
        change_target: str,
    ) -> dict[str, Any] | None:
        space = await self._storage.load(view_id)
        if not space:
            return None

        affected_rules: list[dict[str, Any]] = []
        affected_entities: list[dict[str, Any]] = []
        affected_dimensions: set[str] = set()

        if change_type in ("rule_definition", "rule_logic"):
            for rd in space.layers.L4_business_logic.rule_definitions:
                if change_target in (rd.get("id", ""), rd.get("name", "")):
                    affected_rules.append({
                        "rule_id": rd.get("id"),
                        "rule_name": rd.get("name"),
                        "dimension": rd.get("dimension", ""),
                        "impact": "direct",
                    })
                    affected_dimensions.add(rd.get("dimension", ""))

            for rl in space.layers.L4_business_logic.rule_logics:
                if rl.get("definition_id") == change_target:
                    affected_rules.append({
                        "logic_id": rl.get("id"),
                        "definition_id": rl.get("definition_id"),
                        "impact": "cascaded",
                    })

        if change_type in ("fact_object", "entity_type"):
            for entity in space.instances.entities:
                if entity.get("_fact_object") == change_target:
                    affected_entities.append({
                        "entity_id": entity.get("entity_id"),
                        "fact_object": entity.get("_fact_object"),
                        "impact": "direct",
                    })

            for rd in space.layers.L4_business_logic.rule_definitions:
                applies_to_names = self._rule_applies_to(rd)
                if change_target in applies_to_names:
                    affected_rules.append({
                        "rule_id": rd.get("id"),
                        "rule_name": rd.get("name"),
                        "impact": "applies_to_match",
                    })
                    affected_dimensions.add(rd.get("dimension", ""))

        return {
            "space_id": view_id,
            "change_type": change_type,
            "change_target": change_target,
            "affected_rules": affected_rules,
            "affected_rules_count": len(affected_rules),
            "affected_entities": affected_entities[:50],
            "affected_entities_count": len(affected_entities),
            "affected_dimensions": list(affected_dimensions),
        }
