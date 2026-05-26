from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from ontology_engine.core.semantic_space import SemanticSpace


def _rule_inputs(rule: dict) -> list[dict]:
    return rule.get("inputs") or rule.get("input_elements") or []


def _rule_outputs(rule: dict) -> list[dict]:
    return rule.get("outputs") or rule.get("output_elements") or []


class ImpactChainService:

    def compute_impact_chains(
        self,
        space: SemanticSpace,
        entity: dict,
        overrides: dict[str, Any],
        baseline_outputs: dict[str, Any],
        simulated_outputs: dict[str, Any],
    ) -> list[dict[str, Any]]:
        impact_chains: list[dict[str, Any]] = []

        if not overrides:
            return impact_chains

        elem_to_rules: dict[str, list[str]] = defaultdict(list)
        rule_outputs_map: dict[str, list[str]] = {}

        for rule in space.layers.L4_business_logic.rule_definitions:
            rule_id = rule["id"]
            out_names = [
                e.get("name") or e.get("id", "")
                for e in _rule_outputs(rule)
            ]
            rule_outputs_map[rule_id] = [n for n in out_names if n]
            for in_elem in _rule_inputs(rule):
                name = in_elem.get("name") or in_elem.get("id", "")
                if name:
                    elem_to_rules[name].append(rule_id)

        for override_field in overrides:
            affected_outputs: list[dict[str, Any]] = []
            visited_rules: set[str] = set()
            bfs_queue: deque[str] = deque([override_field])
            chain_path = [override_field]

            while bfs_queue:
                current = bfs_queue.popleft()
                for rule_id in elem_to_rules.get(current, []):
                    if rule_id not in visited_rules:
                        visited_rules.add(rule_id)
                        for out in rule_outputs_map.get(rule_id, []):
                            if (
                                out in baseline_outputs
                                or out in simulated_outputs
                            ):
                                bv = baseline_outputs.get(out)
                                sv = simulated_outputs.get(out)
                                if bv != sv:
                                    affected_outputs.append({
                                        "field": out,
                                        "baseline": bv,
                                        "simulated": sv,
                                        "via_rule": rule_id,
                                    })
                            bfs_queue.append(out)
                            chain_path.append(out)

            if affected_outputs:
                impact_chains.append({
                    "source_field": override_field,
                    "override_value": overrides[override_field],
                    "original_value": entity.get(override_field),
                    "affected_fields": [
                        a["field"] for a in affected_outputs
                    ],
                    "affected_details": affected_outputs,
                    "description": f"覆盖 {override_field} → 影响 {len(affected_outputs)} 个输出字段",
                })

        return impact_chains
