# tests/integration/test_credit_assessment_flow.py
"""End-to-end credit assessment flow test."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ontology_engine.storage.duckdb import DuckDBStorage, EntityInstance, RelationInstance
from ontology_engine.services import (
    SchemaService,
    EntityService,
    AnalysisService,
    QueryService,
    IngestionService,
)
from ontology_engine.services.dto import (
    EntityCreateRequest,
    RelationCreateRequest,
    IngestionRequest,
)
from ontology_engine.core.schema import SchemaLoader
from ontology_engine.core.schema.models import KGMLSchema, SchemaMetadata


class MockCategorizationEngine:
    """Mock CategorizationEngine for testing."""
    async def categorize(self, entity):
        class MockCategoryTags:
            def __init__(self):
                self.tags = {"risk_level": "MEDIUM"}
        return MockCategoryTags()


class MockMetricEngine:
    """Mock MetricEngine for testing."""
    async def compute_batch(self, metrics, entity, context=None):
        return {
            "total_invoice_amount_90d": {"value": 1000000, "currency": "CNY"},
            "overdue_invoice_amount": {"value": 50000, "currency": "CNY"},
            "invoice_count_90d": 10,
            "total_contract_amount": {"value": 2000000, "currency": "CNY"},
        }


class MockRuleResult:
    """Mock RuleResult."""
    def __init__(self, rule_id="R001", rule_name="Test Rule", passed=True, output=None, error=None):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.passed = passed
        self.output = output if output else {}
        self.error = error


class MockAlert:
    """Mock Alert."""
    def __init__(self, level="info", alert_type="general", message="", data=None):
        self.level = level
        self.type = alert_type
        self.message = message
        self.data = data if data else {}


class MockAnalysisResult:
    """Mock AnalysisResult."""
    def __init__(self):
        self.rule_results = [MockRuleResult(rule_id="R001", rule_name="Basic Eligibility", passed=True)]
        self.alerts = [MockAlert(level="info", message="Analysis completed")]
        self.computed_metrics = {"total_invoice_amount_90d": 1000000}
        self.decision = "APPROVED"
        self.decision_reasoning = "All rules passed"


class MockRuleExecutor:
    """Mock RuleExecutor for testing."""
    async def execute_dimension(self, dimension, entity_id, entity_data):
        return MockAnalysisResult()


@pytest.mark.asyncio
async def test_end_to_end_credit_assessment_flow():
    """Test complete credit assessment flow:
    1. Schema Service loads schema
    2. Ingestion Service imports entities
    3. Entity Service creates entities
    4. Analysis Service executes analysis
    5. Query Service retrieves results
    """
    # 1. Initialize storage
    storage = DuckDBStorage(db_path=":memory:")
    await storage.initialize()

    # 2. Load schema
    schema_loader = SchemaLoader()
    try:
        schema = schema_loader.load("examples/supply_chain_finance/schema.yaml")
    except FileNotFoundError:
        # Use minimal schema if file not found
        metadata = SchemaMetadata(id="test", name="test", version="1.0")
        from ontology_engine.core.schema.models import ConceptDefinition
        schema = KGMLSchema(
            metadata=metadata,
            concepts=[
                ConceptDefinition(name="Supplier", description="A supplier"),
                ConceptDefinition(name="Invoice", description="An invoice"),
            ],
            metrics=[],
            rules=None
        )

    # 3. Initialize services
    schema_service = SchemaService(storage=storage)
    entity_service = EntityService(storage=storage, schema=schema)
    analysis_service = AnalysisService(
        categorization_engine=MockCategorizationEngine(),
        metric_engine=MockMetricEngine(),
        rule_executor=MockRuleExecutor(),
        storage=storage,
        schema=schema
    )
    query_service = QueryService(storage=storage, rule_executor=None)
    ingestion_service = IngestionService(storage=storage, entity_service=entity_service)

    # 4. Import entities via IngestionService
    import_request = IngestionRequest(
        entities=[
            EntityCreateRequest(
                concept_type="Supplier",
                entity_id="SUP_001",
                attributes={
                    "company_name": "Test Supplier Co.",
                    "registered_capital": {"value": 5000000, "currency": "CNY"},
                    "status": "ACTIVE"
                }
            ),
            EntityCreateRequest(
                concept_type="Invoice",
                entity_id="INV_001",
                attributes={
                    "amount": {"value": 100000, "currency": "CNY"},
                    "status": "PAID"
                }
            ),
        ],
        relations=[
            RelationCreateRequest(
                relation_type="has_invoice",
                from_id="SUP_001",
                to_id="INV_001",
                attributes={}
            )
        ]
    )

    import_result = await ingestion_service.import_instances(import_request)
    assert import_result.entity_count == 2
    assert import_result.relation_count == 1
    assert import_result.error_count == 0

    # 5. Query entities
    entities = await entity_service.query_entities(concept_type="Supplier")
    assert len(entities) == 1
    assert entities[0].entity_id == "SUP_001"

    # 6. Execute analysis
    analysis_result = await analysis_service.execute_analysis(
        entity_id="SUP_001",
        dimension="credit_assessment"
    )

    assert analysis_result.entity_id == "SUP_001"
    assert analysis_result.dimension == "credit_assessment"
    assert analysis_result.decision == "APPROVED"

    # 7. Query pattern match
    results = await query_service.pattern_match("Supplier")
    assert len(results) >= 1

    # 8. Get neighbors
    neighbors = await entity_service.get_neighbors(
        entity_id="SUP_001",
        relation_type="has_invoice"
    )
    assert len(neighbors) >= 1

    # Cleanup
    await storage.close()


@pytest.mark.asyncio
async def test_entity_crud_operations():
    """Test basic entity CRUD operations through services."""
    storage = DuckDBStorage(db_path=":memory:")
    await storage.initialize()

    metadata = SchemaMetadata(id="test", name="test", version="1.0")
    from ontology_engine.core.schema.models import ConceptDefinition
    schema = KGMLSchema(
        metadata=metadata,
        concepts=[ConceptDefinition(name="Supplier", description="A supplier")],
        metrics=[],
        rules=None
    )

    entity_service = EntityService(storage=storage, schema=schema)

    # Create entity
    entity = await entity_service.create_entity(
        concept_type="Supplier",
        entity_id="SUP_TEST",
        attributes={"name": "Test Supplier"}
    )
    assert entity.entity_id == "SUP_TEST"
    assert entity.concept_type == "Supplier"

    # Get entity
    retrieved = await entity_service.get_entity("Supplier", "SUP_TEST")
    assert retrieved is not None
    assert retrieved.entity_id == "SUP_TEST"

    # Query entities
    entities = await entity_service.query_entities(concept_type="Supplier")
    assert len(entities) == 1

    # Create relation
    relation = await entity_service.create_relation(
        relation_type="has_invoice",
        from_id="SUP_TEST",
        to_id="INV_TEST",
        attributes={"amount": 100000}
    )
    assert relation.relation_type == "has_invoice"
    assert relation.from_id == "SUP_TEST"

    # Get neighbors (may be empty since INV_TEST entity doesn't exist in storage)
    neighbors = await entity_service.get_neighbors(entity_id="SUP_TEST")
    # Just verify the method works - neighbors may be empty since we didn't persist INV_TEST
    assert isinstance(neighbors, list)

    await storage.close()


@pytest.mark.asyncio
async def test_batch_operations():
    """Test batch entity operations."""
    storage = DuckDBStorage(db_path=":memory:")
    await storage.initialize()

    metadata = SchemaMetadata(id="test", name="test", version="1.0")
    from ontology_engine.core.schema.models import ConceptDefinition
    schema = KGMLSchema(
        metadata=metadata,
        concepts=[ConceptDefinition(name="Supplier", description="A supplier")],
        metrics=[],
        rules=None
    )

    entity_service = EntityService(storage=storage, schema=schema)

    # Batch create
    batch_request = [
        EntityCreateRequest(concept_type="Supplier", entity_id=f"SUP_{i}", attributes={})
        for i in range(5)
    ]

    result = await entity_service.batch_create(batch_request)
    assert result.success_count == 5
    assert result.error_count == 0

    # Query all
    entities = await entity_service.query_entities(concept_type="Supplier")
    assert len(entities) == 5

    await storage.close()


@pytest.mark.asyncio
async def test_schema_versioning():
    """Test schema loading and versioning."""
    storage = DuckDBStorage(db_path=":memory:")
    await storage.initialize()

    schema_service = SchemaService(storage=storage)

    # Try loading real schema
    try:
        result = await schema_service.load_schema(
            "examples/supply_chain_finance/schema.yaml"
        )
        assert result.schema_id is not None
        assert result.version == "v1"

        # Reload
        result2 = await schema_service.reload_schema(
            "examples/supply_chain_finance/schema.yaml"
        )
        assert result2.version == "v2"

        # Get versions
        versions = await schema_service.get_schema_versions()
        assert len(versions) == 2
    except FileNotFoundError:
        # Schema file not found - skip this part
        pass

    await storage.close()


@pytest.mark.asyncio
async def test_validation_and_import():
    """Test import validation."""
    storage = DuckDBStorage(db_path=":memory:")
    await storage.initialize()

    metadata = SchemaMetadata(id="test", name="test", version="1.0")
    schema = KGMLSchema(metadata=metadata, concepts=[], metrics=[], rules=None)

    entity_service = EntityService(storage=storage, schema=schema)
    ingestion_service = IngestionService(storage=storage, entity_service=entity_service)

    # Valid import
    valid_request = IngestionRequest(
        entities=[
            EntityCreateRequest(concept_type="Supplier", entity_id="SUP_001", attributes={}),
            EntityCreateRequest(concept_type="Invoice", entity_id="INV_001", attributes={}),
        ],
        relations=[
            RelationCreateRequest(
                relation_type="has_invoice",
                from_id="SUP_001",
                to_id="INV_001",
                attributes={}
            )
        ]
    )

    valid_ids, invalid_reasons = await ingestion_service.validate_import(valid_request)
    assert len(valid_ids) == 2
    assert len(invalid_reasons) == 0

    # Invalid import - missing entity_id
    invalid_request = IngestionRequest(
        entities=[
            EntityCreateRequest(concept_type="Supplier", entity_id="", attributes={}),
        ],
        relations=[]
    )

    valid_ids, invalid_reasons = await ingestion_service.validate_import(invalid_request)
    assert len(valid_ids) == 0
    assert len(invalid_reasons) == 1

    await storage.close()
