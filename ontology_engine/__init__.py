"""
OntologyEngine - A toolchain for knowledge graph based analysis.

Usage:
    engine = OntologyEngine.from_config("schema.yaml")
    await engine.load_instances("instances.yaml")
    result = await engine.analyze(entity_id="SUP_001", dimension="credit_assessment")
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from ontology_engine.core.schema import KGMLSchema, SchemaLoader
from ontology_engine.core.instances import InstanceLoader
from ontology_engine.storage import SQLiteStorage
from ontology_engine.engine.rule import RuleExecutor
from ontology_engine.engine.rule.models import AnalysisResult

if TYPE_CHECKING:
    pass


class OntologyEngine:
    """Main engine for knowledge graph analysis."""

    def __init__(
        self,
        schema: KGMLSchema,
        storage: SQLiteStorage,
        rule_executor: RuleExecutor,
    ):
        self.schema = schema
        self.storage = storage
        self.rule_executor = rule_executor

    @classmethod
    def from_config(cls, schema_path: str) -> "OntologyEngine":
        """Create engine from schema configuration.

        Args:
            schema_path: Path to schema.yaml file

        Returns:
            Configured OntologyEngine instance
        """
        loader = SchemaLoader()
        schema = loader.load(schema_path)

        # Validate schema
        issues = loader.validate(schema)
        if issues:
            import warnings
            warnings.warn(f"Schema validation issues: {issues}")

        storage = SQLiteStorage(":memory:")

        rule_executor = RuleExecutor(schema)

        return cls(
            schema=schema,
            storage=storage,
            rule_executor=rule_executor,
        )

    async def initialize(self) -> None:
        """Initialize storage and load schema."""
        await self.storage.initialize()

    async def load_instances(self, instances_path: str) -> None:
        """Load instance data from YAML.

        Args:
            instances_path: Path to instances.yaml file
        """
        loader = InstanceLoader()
        entities, relations = loader.load(instances_path)

        # Save entities to storage
        for entity in entities:
            await self.storage.save_entity(entity)

        # Save relations to storage
        for relation in relations:
            await self.storage.save_relation(relation)

    async def get_entity(self, concept: str, entity_id: str) -> dict | None:
        """Get entity by concept and ID.

        Args:
            concept: Concept name (e.g., "Supplier")
            entity_id: Entity ID

        Returns:
            Entity data dict or None
        """
        entity = await self.storage.get_entity(concept, entity_id)
        return entity.data if entity else None

    async def query_entities(
        self,
        concept: str,
        filters: dict | None = None
    ) -> list[dict]:
        """Query entities by concept with optional filters.

        Args:
            concept: Concept name
            filters: Optional attribute filters

        Returns:
            List of entity data dicts
        """
        entities = await self.storage.query_entities(concept, filters)
        return [e.data for e in entities]

    async def analyze(
        self,
        entity_id: str,
        dimension: str,
        concept: str = "Supplier"
    ) -> AnalysisResult:
        """Analyze entity in a specific dimension.

        Args:
            entity_id: Entity ID to analyze
            dimension: Dimension name (e.g., "credit_assessment")
            concept: Concept type (default: "Supplier")

        Returns:
            AnalysisResult with rule execution results
        """
        # Get entity data
        entity = await self.get_entity(concept, entity_id)
        if not entity:
            return AnalysisResult(
                entity_id=entity_id,
                dimension=dimension,
                rule_results=[],
                computed_metrics={},
                alerts=[],
                decision=None,
                decision_reasoning=f"Entity {entity_id} not found"
            )

        # Pre-compute metrics for this entity
        entity = await self._compute_entity_metrics(entity)

        # Execute rules for dimension
        result = await self.rule_executor.execute_dimension(
            dimension=dimension,
            entity_id=entity_id,
            entity_data=entity
        )

        return result

    async def _compute_entity_metrics(self, entity: dict) -> dict:
        """Compute metrics for an entity based on related entities.

        For MVP, this computes basic metrics from related invoice/contract data.
        In production, this would be a more sophisticated metric computation engine.

        Args:
            entity: Entity data dict

        Returns:
            Entity data with computed metrics added
        """
        from datetime import date, datetime, timedelta

        entity = dict(entity)  # Don't mutate original
        entity_id = entity.get("supplier_id") or entity.get("enterprise_id") or entity.get("invoice_no", "")
        concept = entity.get("_concept", "Supplier")

        # Compute metrics based on concept
        if concept == "Supplier" and entity_id:
            # Get related invoices
            invoice_refs = entity.get("has_invoice", [])
            invoice_ids = [str(inv.get("invoice_no", "")) for inv in invoice_refs if isinstance(inv, dict) and inv.get("invoice_no")]
            invoices = []
            for inv_id in invoice_ids:
                inv = await self.get_entity("Invoice", inv_id)
                if inv:
                    invoices.append(inv)

            # Get related contracts
            contract_refs = entity.get("has_contract", [])
            contract_ids = [str(ctr.get("contract_no", "")) for ctr in contract_refs if isinstance(ctr, dict) and ctr.get("contract_no")]
            contracts = []
            for ctr_id in contract_ids:
                ctr = await self.get_entity("Contract", ctr_id)
                if ctr:
                    contracts.append(ctr)

            # Compute total_invoice_amount_90d
            today_date = date.today()
            days_90_ago = today_date - timedelta(days=90)
            total_amount_90d = 0
            overdue_amount = 0
            invoice_count_90d = 0

            for inv in invoices:
                inv_data = inv if isinstance(inv, dict) else (inv.data if hasattr(inv, 'data') else {})
                issue_date_str = inv_data.get("issue_date", "")
                if issue_date_str:
                    try:
                        issue_date = datetime.strptime(issue_date_str, "%Y-%m-%d").date()
                        if issue_date >= days_90_ago:
                            amount_val = inv_data.get("amount", {}).get("value", 0) if isinstance(inv_data.get("amount"), dict) else 0
                            total_amount_90d += amount_val
                            invoice_count_90d += 1
                            if inv_data.get("status") == "OVERDUE":
                                overdue_amount += amount_val
                    except (ValueError, TypeError):
                        pass

            # Add computed metrics to entity (using metric names from schema)
            entity["total_invoice_amount_90d"] = {"value": total_amount_90d, "currency": "CNY"}
            entity["invoice_count_90d"] = invoice_count_90d
            entity["overdue_invoice_amount"] = {"value": overdue_amount, "currency": "CNY"}

            # Compute overdue_invoice_ratio
            if total_amount_90d > 0:
                entity["overdue_invoice_ratio"] = (overdue_amount / total_amount_90d) * 100
            else:
                entity["overdue_invoice_ratio"] = 0

            # Add has_invoice boolean (true if has invoices)
            entity["has_invoice"] = len(invoices) > 0

            # Compute total_contract_amount
            total_contract = 0
            for ctr in contracts:
                ctr_data = ctr if isinstance(ctr, dict) else (ctr.data if hasattr(ctr, 'data') else {})
                ctr_amount = ctr_data.get("contract_amount", {}).get("value", 0) if isinstance(ctr_data.get("contract_amount"), dict) else 0
                total_contract += ctr_amount
            entity["total_contract_amount"] = {"value": total_contract, "currency": "CNY"}

            # Compute contract_utilization_rate
            if total_contract > 0:
                entity["contract_utilization_rate"] = round((total_amount_90d / total_contract) * 100, 2)
            else:
                entity["contract_utilization_rate"] = 0

            # Provide default values for metrics needed by credit score calculation
            if "tax_compliance_score" not in entity:
                entity["tax_compliance_score"] = 60  # Default medium score
            if "negative_news_count_90d" not in entity:
                entity["negative_news_count_90d"] = 0

            # Compute guarantee_chain_depth (traverse the chain to detect cycles)
            depth = 0
            visited: set[str] = set()
            initial_guarantors = entity.get("guaranteed_by", [])
            current_ids: list[str] = []
            for g in initial_guarantors:
                gid = str(g.get("supplier_id", "")) if isinstance(g, dict) else str(g) if g else ""
                if gid:
                    current_ids.append(gid)

            while current_ids and len(visited) < 10:  # Limit traversal to prevent infinite loops
                depth += 1
                next_ids = []
                for cid in current_ids:
                    if cid in visited:
                        # Cycle detected - this is a guarantee circle
                        depth += 1  # Count the edge back to the visited node
                        break
                    visited.add(cid)
                    guarantor_entity = await self.get_entity("Supplier", cid)
                    if guarantor_entity:
                        guarantor_list = guarantor_entity.get("guaranteed_by", [])
                        for g in guarantor_list:
                            next_id = str(g.get("supplier_id", "")) if isinstance(g, dict) else str(g) if g else ""
                            if next_id and next_id not in visited:
                                next_ids.append(next_id)
                current_ids = next_ids
                if len(current_ids) == 0:
                    break

            entity["guarantee_chain_depth"] = depth
            entity["has_guarantee_circle"] = depth >= 3

            # Compute core_enterprise_count (count of CoreEnterprise via supplies_to relation)
            core_enterprise_refs = entity.get("supplies_to", [])
            core_enterprise_count = len([ce for ce in core_enterprise_refs if isinstance(ce, dict)])
            entity["core_enterprise_count"] = core_enterprise_count

            # Compute business_stability_score (per Schema formula)
            # score = 50 + contract_utilization_bonus + core_enterprise_bonus + overdue_bonus
            business_stability = 50
            contract_util = entity.get("contract_utilization_rate", 0)
            if contract_util >= 80:
                business_stability += 20
            elif contract_util >= 50:
                business_stability += 10

            if core_enterprise_count >= 3:
                business_stability += 15
            elif core_enterprise_count >= 1:
                business_stability += 5

            overdue_ratio = entity.get("overdue_invoice_ratio", 0)
            if overdue_ratio < 5:
                business_stability += 15
            elif overdue_ratio < 10:
                business_stability += 5

            entity["business_stability_score"] = min(100, business_stability)

            # Compute reputation_score (per Schema formula)
            # base_score = 100 - news_deduction - overdue_deduction
            negative_news = entity.get("negative_news_count_90d", 0)
            news_deduction = negative_news * 10
            overdue_deduction = overdue_ratio * 2
            entity["reputation_score"] = max(0, 100 - news_deduction - overdue_deduction)

            # Compute network_centrality_score (simplified: based on connections)
            # For MVP, use a simplified proxy based on core_enterprise_count and invoice count
            network_score = min(100, (core_enterprise_count * 20) + (invoice_count_90d * 5))
            entity["network_centrality_score"] = network_score

        return entity

    async def close(self) -> None:
        """Close engine and cleanup resources."""
        await self.storage.close()


__version__ = "0.1.0"
__all__ = ["OntologyEngine", "__version__"]
