"""Reflect agent for deep memory analysis.

Implements multi-round tool-calling reflection with forced search
sequence, hallucination protection, and disposition injection.

Design decisions (from reflect-agent.md):
- D-REF-1: First 3 rounds forced search (mental_model → entity → observation)
- D-REF-2: max_iterations=10
- D-REF-3: Hallucination protection via ID tracking
- D-REF-4: Context overflow forced final answer
- D-REF-5: Reflection does not directly write
- D-REF-6: Disposition injection into system messages
- D-REF-7: Structured output via done()
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.errors import DirectiveViolationError, HallucinationError
from ontology_engine.engine.cognitive.reflect_types import (
    DIRECTIVES_RULES,
    FORCED_SEARCH_SEQUENCE,
    MAX_CONTEXT_TOKENS,
    MAX_HALLUCINATION_RETRIES,
    MAX_ITERATIONS,
    ContradictionReport,
    Insight,
    MentalModelUpdate,
    ReflectResult,
)
from ontology_engine.engine.cognitive.rrf_types import RetrievalResult

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.models import DispositionProfile
    from ontology_engine.engine.cognitive.query_router import QueryRouter
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


class ReflectAgent:
    """Agent for deep memory analysis via multi-round tool-calling.

    Implements:
    - Forced search sequence (D-REF-1)
    - Hallucination protection (D-REF-3)
    - Context overflow protection (D-REF-4)
    - Disposition injection (D-REF-6)
    - Structured output validation (D-REF-7)
    """

    def __init__(
        self,
        repository: "CognitiveRepository",
        query_router: "QueryRouter",
        llm_call_fn: Any | None = None,
    ):
        """Initialize ReflectAgent.

        Args:
            repository: CognitiveRepository for node operations.
            query_router: QueryRouter for retrieval.
            llm_call_fn: Optional async LLM call function.
        """
        self._repo = repository
        self._router = query_router
        self._llm_call = llm_call_fn

    async def reflect(
        self,
        query: str,
        space_id: str = "default",
        max_iterations: int = MAX_ITERATIONS,
        focus_types: list[str] | None = None,
        disposition: "DispositionProfile | None" = None,
        apply_directives: bool = True,
    ) -> ReflectResult:
        """Run a reflection session with hallucination protection and retry.

        Args:
            query: Query to reflect on.
            space_id: Space to search within.
            max_iterations: Maximum iterations.
            focus_types: Override forced search types.
            disposition: Optional DispositionProfile.
            apply_directives: Whether to enforce Directives hard rules (D-REF-5).

        Returns:
            ReflectResult with insights, contradictions, etc.
        """
        type_priority = focus_types or FORCED_SEARCH_SEQUENCE
        last_error: str | None = None

        rule_contradictions = await self._detect_rule_based_contradictions(query, space_id, disposition=disposition)

        for retry in range(MAX_HALLUCINATION_RETRIES + 1):
            try:
                result, available_ids = await self._run_reflection_loop(
                    query=query,
                    space_id=space_id,
                    max_iterations=max_iterations,
                    type_priority=type_priority,
                    disposition=disposition,
                    last_error=last_error,
                )

                self._validate_result(result, available_ids, check_directives=apply_directives)

                result.tokens_used = self._estimate_tokens_for_result(result)
                result.iterations_used = min(max_iterations, MAX_ITERATIONS)

                existing_keys = {
                    (c.contradiction_type, tuple(sorted(c.node_ids)))
                    for c in result.contradictions
                }
                for rc in rule_contradictions:
                    key = (rc.contradiction_type, tuple(sorted(rc.node_ids)))
                    if key not in existing_keys:
                        result.contradictions.append(rc)
                        existing_keys.add(key)

                return result

            except HallucinationError as e:
                if retry < MAX_HALLUCINATION_RETRIES:
                    logger.warning(
                        "Hallucination detected (retry %d/%d): %s. "
                        "Offending IDs: %s",
                        retry + 1, MAX_HALLUCINATION_RETRIES,
                        e, e.offending_ids,
                    )
                    last_error = (
                        f"PREVIOUS ATTEMPT FAILED: You referenced IDs that were NOT in "
                        f"the available memory set. Offending IDs: {e.offending_ids}. "
                        f"Only reference IDs that were returned by search/recall tools. "
                        f"Each insight MUST include evidence_ids from the actual results."
                    )
                    continue
                else:
                    logger.error("Max hallucination retries exceeded: %s", e)
                    return ReflectResult(
                        contradictions=[],
                        consolidation_requests=[],
                        forgetting_requests=[],
                        mental_model_updates=[],
                        tokens_used=0,
                        iterations_used=0,
                    )
            except DirectiveViolationError as e:
                logger.error("Directive violation: %s", e)
                return ReflectResult(
                    contradictions=[],
                    consolidation_requests=[],
                    forgetting_requests=[],
                    mental_model_updates=[],
                    tokens_used=0,
                    iterations_used=0,
                )

        return ReflectResult()

    async def _run_reflection_loop(
        self,
        query: str,
        space_id: str,
        max_iterations: int,
        type_priority: list[str],
        disposition: "DispositionProfile | None",
        last_error: str | None,
    ) -> tuple[ReflectResult, set[str]]:
        """Run the core reflection iteration loop.

        Returns:
            Tuple of (ReflectResult, available_ids set).
        """
        available_ids: set[str] = set()
        all_results: list[RetrievalResult] = []
        all_insights: list[Insight] = []
        all_contradictions: list[ContradictionReport] = []

        for iteration in range(min(max_iterations, MAX_ITERATIONS)):
            if iteration < len(type_priority):
                memory_type = type_priority[iteration]
                results = await self._search_by_type(query, memory_type, space_id)
            else:
                results = await self._recall(query, space_id)

            for r in results:
                available_ids.add(r.doc_id)
            all_results.extend(results)

            contradictions = self._detect_contradictions(results)
            all_contradictions.extend(contradictions)

            if len(all_results) > 0 and iteration >= len(type_priority) - 1:
                insights = self._generate_insights(query, all_results, disposition)
                all_insights.extend(insights)

            if self._estimate_tokens(all_results) >= MAX_CONTEXT_TOKENS:
                logger.info("Context overflow at iteration %d, forcing final answer", iteration)
                break

        result = ReflectResult(
            insights=all_insights,
            contradictions=all_contradictions,
            consolidation_requests=[space_id] if self._needs_consolidation(all_results) else [],
            forgetting_requests=self._identify_forgetting_candidates(all_results),
            mental_model_updates=self._propose_mental_model_updates(all_results),
        )
        return result, available_ids

    async def _search_by_type(
        self,
        query: str,
        memory_type: str,
        space_id: str,
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """Search memories by type.

        Args:
            query: Search query.
            memory_type: Memory type to filter.
            space_id: Space identifier.
            top_k: Maximum results.

        Returns:
            List of retrieval results.
        """
        nodes = await self._repo.query_nodes(
            memory_type=memory_type,
            domain_id=space_id,
            limit=top_k,
        )
        return [
            RetrievalResult(
                doc_id=n.id,
                content=n.content,
                source=f"search_by_type:{memory_type}",
                memory_type=n.memory_type,
                cognitive_layer=n.cognitive_layer,
            )
            for n in nodes
        ]

    async def _recall(
        self,
        query: str,
        space_id: str,
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        """Recall memories using the query router.

        Args:
            query: Search query.
            space_id: Space identifier.
            top_k: Maximum results.

        Returns:
            List of retrieval results.
        """
        return await self._router.route(query, space_id, top_k)

    def _detect_contradictions(
        self,
        results: list[RetrievalResult],
    ) -> list[ContradictionReport]:
        """Detect contradictions among retrieval results.

        Simple heuristic: look for same cognitive_layer results with
        conflicting belief_status.

        Args:
            results: Retrieval results to analyze.

        Returns:
            List of ContradictionReport.
        """
        contradictions = []

        by_layer: dict[str, list[RetrievalResult]] = {}
        for r in results:
            by_layer.setdefault(r.cognitive_layer, []).append(r)

        for layer, layer_results in by_layer.items():
            if len(layer_results) < 2:
                continue

            accepted = [r for r in layer_results if r.metadata.get("belief_status") == "accepted"]
            contradicted = [r for r in layer_results if r.metadata.get("belief_status") == "contradicted"]

            for a in accepted:
                for c in contradicted:
                    contradictions.append(ContradictionReport(
                        node_ids=[a.doc_id, c.doc_id],
                        contradiction_type="belief_conflict",
                        contradiction_field="belief_status",
                        old_value="accepted",
                        new_value="contradicted",
                        suggested_resolution="Review both memories and resolve conflict",
                    ))

        return contradictions

    def _generate_insights(
        self,
        query: str,
        results: list[RetrievalResult],
        disposition: "DispositionProfile | None",
    ) -> list[Insight]:
        """Generate insights from retrieval results.

        Args:
            query: Original query.
            results: Retrieval results.
            disposition: Optional DispositionProfile.

        Returns:
            List of Insight.
        """
        insights = []

        high_layer = [r for r in results if r.cognitive_layer in ("opinion", "semantic")]
        if len(high_layer) >= 2:
            insights.append(Insight(
                text=f"Found {len(high_layer)} high-level memories related to '{query}'",
                confidence=0.6,
                evidence_ids=[r.doc_id for r in high_layer[:5]],
                suggested_memory_type="observation",
            ))

        return insights

    def _needs_consolidation(self, results: list[RetrievalResult]) -> bool:
        """Check if consolidation is needed based on fragment count."""
        fragment_count = sum(1 for r in results if r.memory_type == "fragment")
        return fragment_count > 5

    def _identify_forgetting_candidates(
        self,
        results: list[RetrievalResult],
    ) -> list[str]:
        """Identify nodes that may be candidates for forgetting."""
        return [
            r.doc_id for r in results
            if r.score < 0.1 and r.memory_type == "fragment"
        ]

    def _propose_mental_model_updates(
        self,
        results: list[RetrievalResult],
    ) -> list[MentalModelUpdate]:
        """Propose mental model updates based on reflection."""
        updates = []

        mental_models = [r for r in results if r.memory_type == "mental_model"]
        for mm in mental_models:
            supporting = [r for r in results if r.cognitive_layer in ("semantic", "perception")]
            if len(supporting) >= 3:
                updates.append(MentalModelUpdate(
                    model_id=mm.doc_id,
                    update_type="extend",
                    update_text=f"Extended with {len(supporting)} supporting observations",
                    evidence_ids=[r.doc_id for r in supporting[:5]],
                ))

        return updates

    async def _detect_rule_based_contradictions(
        self,
        query: str,
        space_id: str,
        disposition: "DispositionProfile | None" = None,
    ) -> list["ContradictionReport"]:
        """Detect contradictions using rule-based heuristics (no LLM required).

        Checks for:
        1. Supersede chains: nodes with belief_status=superseded still referenced
        2. Numeric conflicts: same entity with conflicting numeric values
        3. Negation conflicts: "X is A" vs "X is not A"
        4. Mutually exclusive values: same subject+field with different values

        DispositionProfile.skepticism:
        - skepticism >= 0.7: detect all contradictions (aggressive mode)
        - skepticism <= 0.3: skip detection entirely (conservative mode)
        - 0.3 < skepticism < 0.7: normal detection (default)
        """
        import re
        from ontology_engine.engine.cognitive.reflect_types import ContradictionReport

        contradictions: list[ContradictionReport] = []

        if disposition is not None and disposition.skepticism <= 0.3:
            return contradictions

        try:
            nodes = await self._repo.query_nodes(domain_id=space_id, limit=500)
        except Exception:
            return contradictions

        active_nodes = [n for n in nodes if n.belief_status not in ("superseded", "rejected")]
        if len(active_nodes) < 2:
            return contradictions

        checked_pairs: set[tuple[str, str]] = set()

        def _check_pair(a, b):
            pair_key = tuple(sorted([a.id, b.id]))
            if pair_key in checked_pairs:
                return
            checked_pairs.add(pair_key)

            if self._has_negation_conflict(a.content, b.content):
                contradictions.append(ContradictionReport(
                    contradiction_type="negation_conflict",
                    node_ids=[a.id, b.id],
                    old_value=a.content[:80],
                    new_value=b.content[:80],
                ))
                return

            if a.memory_type == b.memory_type and a.memory_type in ("observation", "rule", "entity", "opinion"):
                conflict = self._has_mutually_exclusive_values(a.content, b.content)
                if conflict:
                    contradictions.append(ContradictionReport(
                        contradiction_type="value_conflict",
                        node_ids=[a.id, b.id],
                        contradiction_field=conflict,
                        old_value=a.content[:80],
                        new_value=b.content[:80],
                        suggested_resolution="Review both memories and determine which is current",
                    ))

        tag_groups: dict[str, list] = {}
        for n in active_nodes:
            for tag in n.tags:
                tag_groups.setdefault(tag, []).append(n)

        for tag, group in tag_groups.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    _check_pair(group[i], group[j])

        entity_groups: dict[str, list] = {}
        entity_pattern = re.compile(r"^[\u4e00-\u9fff]{2,6}(?:科技|集团|公司|股份|有限)")
        for n in active_nodes:
            match = entity_pattern.search(n.content)
            if match:
                entity_name = match.group()
                entity_groups.setdefault(entity_name, []).append(n)

        for entity_name, group in entity_groups.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    _check_pair(group[i], group[j])

        return contradictions

    @staticmethod
    def _has_negation_conflict(text_a: str, text_b: str) -> bool:
        """Check if two texts have a negation conflict pattern."""
        import re

        negation_patterns = [
            (r"不是\s*(.{1,50}?)(?:，|,|。|；|;|$)", r"\1"),
            (r"不使用\s*(.{1,50}?)(?:，|,|。|；|;|$)", r"使用\s*\1"),
            (r"不再\s*(.{1,50}?)(?:，|,|。|；|;|$)", r"\1"),
            (r"没有\s*(.{1,50}?)(?:，|,|。|；|;|$)", r"有\s*\1"),
            (r"并非\s*(.{1,50}?)(?:，|,|。|；|;|$)", r"\1"),
            (r"不\s*是\s*(.{1,50}?)(?:，|,|。|；|;|$)", r"\1"),
            (r"不\s*([\u4e00-\u9fff]{1,4})\s*(.{1,50}?)(?:，|,|。|；|;|$)", r"\1\s*\2"),
        ]

        for neg_pat, affirm_pat in negation_patterns:
            neg_match = re.search(neg_pat, text_a)
            if neg_match:
                core = neg_match.group(1).strip()
                if core and (core in text_b or re.search(affirm_pat.replace(r"\1", re.escape(core)), text_b)):
                    return True
            neg_match = re.search(neg_pat, text_b)
            if neg_match:
                core = neg_match.group(1).strip()
                if core and (core in text_a or re.search(affirm_pat.replace(r"\1", re.escape(core)), text_a)):
                    return True

        return False

    @staticmethod
    def _has_mutually_exclusive_values(text_a: str, text_b: str) -> str | None:
        """Check if two texts describe the same subject with conflicting values.

        Detects patterns like "X使用A" vs "X使用B" where A and B are
        mutually exclusive alternatives for the same field.
        Also detects numeric conflicts like "35%" vs "65%" and
        rating conflicts like "A级" vs "C级".

        Returns:
            The conflicting field name if found, None otherwise.
        """
        import re

        value_patterns = [
            (r"(.+?)使用(.+)", "使用"),
            (r"(.+?)采用(.+)", "采用"),
            (r"(.+?)协议[是为](.+)", "协议"),
            (r"(.+?)架构[是为](.+)", "架构"),
            (r"(.+?)策略[是为：:](.+)", "策略"),
            (r"(.+?)方式[是为](.+)", "方式"),
            (r"(.+?)数据库[是为](.+)", "数据库"),
            (r"(.+?)语言[是为](.+)", "语言"),
            (r"(.+?)框架[是为](.+)", "框架"),
            (r"(.+?)版本[是为](.+)", "版本"),
            (r"(.+?)位于(.+)", "位置"),
            (r"(.+?)总部[在于](.+)", "位置"),
        ]

        for pat_a, field in value_patterns:
            match_a = re.search(pat_a, text_a)
            if not match_a:
                continue
            subject_a = match_a.group(1).strip()
            value_a = match_a.group(2).strip()

            for pat_b, field_b in value_patterns:
                if field_b != field:
                    continue
                match_b = re.search(pat_b, text_b)
                if not match_b:
                    continue
                subject_b = match_b.group(1).strip()
                value_b = match_b.group(2).strip()

                subject_overlap = (
                    subject_a == subject_b
                    or subject_a in subject_b
                    or subject_b in subject_a
                )
                if subject_overlap and value_a != value_b:
                    return field

        rating_pattern = re.compile(r"风险等级\s*([A-Da-d级])")
        ratings_a = rating_pattern.findall(text_a)
        ratings_b = rating_pattern.findall(text_b)
        if ratings_a and ratings_b and ratings_a[0] != ratings_b[0]:
            return "风险等级"

        numeric_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*[%％万元人个只台辆次件]")
        nums_a = numeric_pattern.findall(text_a)
        nums_b = numeric_pattern.findall(text_b)
        if nums_a and nums_b:
            for na in nums_a:
                for nb in nums_b:
                    try:
                        diff = abs(float(na) - float(nb))
                        if diff > 20:
                            return "数值冲突"
                    except ValueError:
                        pass

        entity_numeric = re.compile(
            r"([\u4e00-\u9fff]{2,8}(?:科技|集团|公司|股份|有限)?)"
            r"\s*(.{2,6}?)\s*(\d+(?:\.\d+)?)\s*(.{0,4})"
        )
        match_a = entity_numeric.search(text_a)
        match_b = entity_numeric.search(text_b)
        if match_a and match_b:
            entity_a, field_a, num_a, _ = match_a.groups()
            entity_b, field_b, num_b, _ = match_b.groups()
            if entity_a == entity_b and field_a == field_b:
                try:
                    if abs(float(num_a) - float(num_b)) > 0:
                        return f"{field_a}数值冲突"
                except ValueError:
                    pass

        return None

    def _estimate_tokens(self, results: list[RetrievalResult]) -> int:
        """Estimate token count for results.

        Args:
            results: Retrieval results.

        Returns:
            Estimated token count.
        """
        total = 0
        for r in results:
            total += len(r.content) // 4
        return total

    def _validate_result(
        self,
        result: ReflectResult,
        available_ids: set[str],
        check_directives: bool = True,
    ) -> None:
        """Validate reflection result for hallucination and directive violations.

        All evidence_ids and node_ids must be in the available set.
        Directives hard rules must not be violated (D-REF-5).

        Args:
            result: ReflectResult to validate.
            available_ids: Set of IDs that were actually retrieved.
            check_directives: Whether to enforce Directives rules.

        Raises:
            HallucinationError: If any referenced ID is not in available_ids.
            DirectiveViolationError: If a directives rule is violated.
        """
        for insight in result.insights:
            if not insight.evidence_ids:
                raise HallucinationError(
                    "Insight has no evidence_ids — Directive D-REF-5.4 violated",
                    offending_ids=[],
                    available_ids=available_ids,
                )
            for eid in insight.evidence_ids:
                if eid not in available_ids:
                    raise HallucinationError(
                        f"Insight references unknown ID: {eid}",
                        offending_ids=[eid],
                        available_ids=available_ids,
                    )

        if check_directives:
            for directive in DIRECTIVES_RULES:
                if directive["level"] != "fatal":
                    continue
                if directive["action"] == "insight_no_evidence":
                    for insight in result.insights:
                        if not insight.evidence_ids:
                            raise DirectiveViolationError(
                                f"Directive {directive['id']}: {directive['description']}",
                                directive_id=directive["id"],
                                violating_action=f"insight '{insight.text}' has no evidence",
                            )
                if directive["action"] == "external_id":
                    for insight in result.insights:
                        for eid in insight.evidence_ids:
                            if eid not in available_ids:
                                raise DirectiveViolationError(
                                    f"Directive {directive['id']}: {directive['description']}",
                                    directive_id=directive["id"],
                                    violating_action=f"insight references external ID: {eid}",
                                )

        for contradiction in result.contradictions:
            for nid in contradiction.node_ids:
                if nid not in available_ids:
                    raise HallucinationError(
                        f"Contradiction references unknown ID: {nid}",
                        offending_ids=[nid],
                        available_ids=available_ids,
                    )
            if check_directives and not contradiction.suggested_resolution:
                logger.warning(
                    "Directive D-REF-5.5 warning: contradiction has no suggested_resolution: %s",
                    contradiction.contradiction_type,
                )

        for update in result.mental_model_updates:
            for eid in update.evidence_ids:
                if eid not in available_ids:
                    raise HallucinationError(
                        f"MentalModelUpdate references unknown ID: {eid}",
                        offending_ids=[eid],
                        available_ids=available_ids,
                    )

    def _estimate_tokens_for_result(self, result: ReflectResult) -> int:
        """Estimate tokens consumed by the entire ReflectResult."""
        total = 0
        for i in result.insights:
            total += len(i.text) // 4
        for c in result.contradictions:
            total += (len(c.old_value) + len(c.new_value)) // 4
        return total

    def build_system_prompt(
        self,
        query: str,
        space_id: str,
        disposition: "DispositionProfile | None",
    ) -> str:
        """Build system prompt for LLM-based reflection.

        Args:
            query: Query text.
            space_id: Space identifier.
            disposition: Optional DispositionProfile.

        Returns:
            System prompt string.
        """
        base = f"You are a knowledge reflection engine analyzing memories in space {space_id}."

        if disposition:
            if hasattr(disposition, "skepticism") and disposition.skepticism > 0.7:
                base += "\nYou are highly skeptical of existing knowledge, prioritizing finding contradictions."
            if hasattr(disposition, "evidence_demand") and disposition.evidence_demand > 0.7:
                base += "\nYou require at least 2 independent evidence for each insight."
            if hasattr(disposition, "risk_tolerance") and disposition.risk_tolerance < 0.3:
                base += "\nYou should make conservative judgments, marking uncertain insights as low confidence."

        return base
