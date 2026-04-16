# tests/unit/services/test_rule_service.py
"""Tests for RuleService."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from ontology_engine.services.rule_service import RuleService, RuleServiceError


class TestRuleService:
    """Test RuleService operations."""

    @pytest.fixture
    def storage(self):
        """Create mock storage."""
        storage = AsyncMock()
        storage.get_rule_group = AsyncMock(return_value=None)
        storage.save_rule_group = AsyncMock()
        storage.save_rule_step = AsyncMock()
        storage.list_rule_steps = AsyncMock(return_value=[])
        return storage

    @pytest.fixture
    def service(self, storage):
        """Create RuleService instance."""
        return RuleService(storage=storage)

    # =========================================================================
    # import_from_yaml - Phase 2 Format Tests
    # =========================================================================

    PHASE2_YAML = """
rule_group:
  name: "RD001_basic_eligibility"
  description: "供应商融资申请的基础资质门槛校验"
  type: "constraint"
  priority: 100
  enabled: true

  applies_to:
    fact_objects:
      - "Supplier"
    categories:
      industry_type:
        - "MANUFACTURING"

  preconditions:
    - expression: "entity.status == 'ACTIVE'"
      fail:
        action: "reject"
        reason: "企业经营状态异常"

  inputs:
    - name: "is_eligible"
      type: "flag"
      metric: "is_eligible"

  outputs:
    - name: "is_eligible"
      type: "flag"

rule_steps:
  - id: "step-1"
    name: "注册资本与成立年限检查"
    order: 1
    enabled: true
    description: "校验注册资本≥100万且成立≥1年"
    tags: ["eligibility"]

    when:
      type: "all_of"
      sub_conditions:
        - "entity.registered_capital_value >= 1000000"
        - "days_since(entity.establishment_date) >= 365"

    then:
      operator: "SET_FLAG"
      params:
        flag_name: "is_eligible"
        flag_value: true
      output_mapping: {}
"""

    @pytest.mark.asyncio
    async def test_import_from_yaml_phase2_format(self, service, storage):
        """Test importing Phase 2 YAML format."""
        saved_rg_data = None

        async def capture_save_rg(data, schema_id=None):
            nonlocal saved_rg_data
            saved_rg_data = data

        async def get_rule_group_after_save(name, schema_id=None):
            return saved_rg_data

        storage.save_rule_group.side_effect = capture_save_rg
        storage.get_rule_group.side_effect = get_rule_group_after_save

        result = await service.import_from_yaml(self.PHASE2_YAML, schema_id="test-schema")

        assert result.name == "RD001_basic_eligibility"
        assert result.description == "供应商融资申请的基础资质门槛校验"
        assert result.type == "constraint"
        assert result.priority == 100
        assert result.enabled is True
        assert result.schema_id == "test-schema"

        # Verify applies_to normalization
        assert result.applies_to.fact_objects == ["Supplier"]
        assert result.applies_to.categories == {"industry_type": ["MANUFACTURING"]}

        # Verify preconditions
        assert len(result.preconditions) == 1
        assert result.preconditions[0].expression == "entity.status == 'ACTIVE'"

        # Verify inputs/outputs
        assert len(result.inputs) == 1
        assert result.inputs[0].name == "is_eligible"
        assert len(result.outputs) == 1
        assert result.outputs[0].name == "is_eligible"

        # Verify storage calls
        storage.save_rule_group.assert_called_once()
        assert saved_rg_data["name"] == "RD001_basic_eligibility"

    @pytest.mark.asyncio
    async def test_import_from_yaml_phase2_saves_steps(self, service, storage):
        """Test that Phase 2 import saves rule steps."""
        saved_steps = []
        saved_rg_data = None

        async def capture_save_step(name, data):
            saved_steps.append(data)

        async def capture_save_rg(data, schema_id=None):
            nonlocal saved_rg_data
            saved_rg_data = data

        async def get_rule_group_after_save(name, schema_id=None):
            return saved_rg_data

        storage.save_rule_step.side_effect = capture_save_step
        storage.save_rule_group.side_effect = capture_save_rg
        storage.get_rule_group.side_effect = get_rule_group_after_save

        result = await service.import_from_yaml(self.PHASE2_YAML, schema_id="test-schema")

        assert len(saved_steps) == 1
        assert saved_steps[0]["id"] == "step-1"
        assert saved_steps[0]["name"] == "注册资本与成立年限检查"
        assert saved_steps[0]["step_order"] == 1
        assert saved_steps[0]["when"]["type"] == "all_of"
        assert saved_steps[0]["when"]["sub_conditions"] == [
            "entity.registered_capital_value >= 1000000",
            "days_since(entity.establishment_date) >= 365",
        ]
        assert saved_steps[0]["then"]["operator"] == "SET_FLAG"
        assert saved_steps[0]["then"]["params"]["flag_name"] == "is_eligible"

    @pytest.mark.asyncio
    async def test_import_from_yaml_phase2_with_expression_when(self, service, storage):
        """Test Phase 2 import with expression-type when clause."""
        yaml_content = """
rule_group:
  name: "RD002_single_condition"
  description: "单一条件检查"
  type: "decision"

  applies_to:
    fact_objects:
      - "Supplier"

  inputs: []
  outputs: []

rule_steps:
  - id: "step-1"
    name: "状态检查"
    order: 1
    enabled: true

    when:
      type: "expression"
      expression: "entity.status == 'ACTIVE'"

    then:
      operator: "SET_FLAG"
      params:
        flag_name: "is_active"
      output_mapping: {}
"""
        saved_rg_data = None

        async def capture_save_rg(data, schema_id=None):
            nonlocal saved_rg_data
            saved_rg_data = data

        async def get_rule_group_after_save(name, schema_id=None):
            return saved_rg_data

        storage.save_rule_group.side_effect = capture_save_rg
        storage.get_rule_group.side_effect = get_rule_group_after_save

        result = await service.import_from_yaml(yaml_content, schema_id="test-schema")

        assert result.name == "RD002_single_condition"
        storage.save_rule_step.assert_called_once()
        step_data = storage.save_rule_step.call_args[0][1]
        assert step_data["when"]["type"] == "expression"
        assert step_data["when"]["expression"] == "entity.status == 'ACTIVE'"

    # =========================================================================
    # import_from_yaml - Legacy Format Tests
    # =========================================================================

    LEGACY_YAML = """
rule_definitions:
  - name: "RD003_legacy_rule"
    description: "Legacy format rule"
    type: "decision"
    priority: 50

    applies_to:
      fact_objects:
        - "Supplier"
      categories:
        industry_type:
          - "RETAIL"

    inputs:
      - name: "score"
        type: "numeric"

    outputs:
      - name: "decision"
        type: "string"

rule_logics:
  - name: "RD003_legacy_rule_logic"
    rule_definition: "RD003_legacy_rule"
    steps:
      - id: "step-1"
        name: "Legacy Step"
        when:
          type: "expression"
          expression: "entity.score >= 60"
        then:
          operator: "APPROVE"
          params:
            decision: "APPROVED"
"""

    @pytest.mark.asyncio
    async def test_import_from_yaml_legacy_format(self, service, storage):
        """Test importing legacy YAML format."""
        saved_rg_data = None

        async def capture_save_rg(data, schema_id=None):
            nonlocal saved_rg_data
            saved_rg_data = data

        async def get_rule_group_after_save(name, schema_id=None):
            return saved_rg_data

        storage.save_rule_group.side_effect = capture_save_rg
        storage.get_rule_group.side_effect = get_rule_group_after_save

        result = await service.import_from_yaml(self.LEGACY_YAML, schema_id="test-schema")

        assert result.name == "RD003_legacy_rule"
        assert result.description == "Legacy format rule"
        assert result.type == "decision"
        assert result.priority == 50
        assert result.applies_to.fact_objects == ["Supplier"]

    @pytest.mark.asyncio
    async def test_import_from_yaml_legacy_saves_steps(self, service, storage):
        """Test that legacy import saves rule steps."""
        saved_steps = []
        saved_rg_data = None

        async def capture_save_step(name, data):
            saved_steps.append(data)

        async def capture_save_rg(data, schema_id=None):
            nonlocal saved_rg_data
            saved_rg_data = data

        async def get_rule_group_after_save(name, schema_id=None):
            return saved_rg_data

        storage.save_rule_step.side_effect = capture_save_step
        storage.save_rule_group.side_effect = capture_save_rg
        storage.get_rule_group.side_effect = get_rule_group_after_save

        result = await service.import_from_yaml(self.LEGACY_YAML, schema_id="test-schema")

        assert len(saved_steps) == 1
        assert saved_steps[0]["id"] == "step-1"
        assert saved_steps[0]["step_order"] == 0  # Legacy uses order from enumerate

    # =========================================================================
    # import_from_yaml - Error Handling Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_import_from_yaml_missing_schema_id(self, service):
        """Test that missing schema_id raises error."""
        with pytest.raises(RuleServiceError, match="schema_id is required"):
            await service.import_from_yaml(self.PHASE2_YAML, schema_id=None)

    @pytest.mark.asyncio
    async def test_import_from_yaml_invalid_yaml(self, service):
        """Test that invalid YAML raises error."""
        with pytest.raises(RuleServiceError, match="Invalid YAML"):
            await service.import_from_yaml("invalid: yaml: content:", schema_id="test-schema")

    @pytest.mark.asyncio
    async def test_import_from_yaml_missing_rule_group_and_definitions(self, service):
        """Test that missing both formats raises error."""
        yaml_content = """
some_other_key:
  - item: "value"
"""
        with pytest.raises(RuleServiceError, match="No valid rule format found"):
            await service.import_from_yaml(yaml_content, schema_id="test-schema")

    @pytest.mark.asyncio
    async def test_import_from_yaml_phase2_missing_name(self, service):
        """Test that Phase 2 format without name raises error."""
        yaml_content = """
rule_group:
  description: "Missing name"
  applies_to:
    fact_objects: []
rule_steps: []
"""
        with pytest.raises(RuleServiceError, match="must have a name"):
            await service.import_from_yaml(yaml_content, schema_id="test-schema")

    @pytest.mark.asyncio
    async def test_import_from_yaml_duplicate_rule_group(self, service, storage):
        """Test that importing duplicate rule group raises error."""
        storage.get_rule_group = AsyncMock(return_value={"name": "RD001_basic_eligibility"})

        with pytest.raises(RuleServiceError, match="already exists"):
            await service.import_from_yaml(self.PHASE2_YAML, schema_id="test-schema")

    # =========================================================================
    # validate_yaml Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_validate_yaml_phase2_valid(self, service):
        """Test validating valid Phase 2 YAML."""
        is_valid, errors = await service.validate_yaml(self.PHASE2_YAML)
        assert is_valid is True
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_yaml_legacy_valid(self, service):
        """Test validating valid legacy YAML."""
        is_valid, errors = await service.validate_yaml(self.LEGACY_YAML)
        assert is_valid is True
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_validate_yaml_invalid_syntax(self, service):
        """Test validating invalid YAML syntax."""
        is_valid, errors = await service.validate_yaml("invalid: yaml: content:")
        assert is_valid is False
        assert "Invalid YAML syntax" in errors[0]

    @pytest.mark.asyncio
    async def test_validate_yaml_phase2_missing_name(self, service):
        """Test validating Phase 2 YAML without name."""
        yaml_content = """
rule_group:
  description: "Missing name"
  applies_to:
    fact_objects: []
rule_steps: []
"""
        is_valid, errors = await service.validate_yaml(yaml_content)
        assert is_valid is False
        assert any("must have a name" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_yaml_phase2_step_missing_when(self, service):
        """Test validating Phase 2 YAML with step missing when clause."""
        yaml_content = """
rule_group:
  name: "RD_test"
  applies_to:
    fact_objects: []
rule_steps:
  - id: "step-1"
    name: "Step without when"
"""
        is_valid, errors = await service.validate_yaml(yaml_content)
        assert is_valid is False
        assert any("must have when clause" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_yaml_legacy_missing_name(self, service):
        """Test validating legacy YAML without name."""
        yaml_content = """
rule_definitions:
  - description: "Missing name"
rule_logics: []
"""
        is_valid, errors = await service.validate_yaml(yaml_content)
        assert is_valid is False
        assert any("must have a name" in e for e in errors)

    @pytest.mark.asyncio
    async def test_validate_yaml_no_format(self, service):
        """Test validating YAML with no recognized format."""
        yaml_content = """
some_key: "some_value"
"""
        is_valid, errors = await service.validate_yaml(yaml_content)
        assert is_valid is False
        assert any("No valid rule format" in e for e in errors)

    # =========================================================================
    # Helper Method Tests
    # =========================================================================

    def test_normalize_applies_to_with_list_fact_objects(self, service):
        """Test normalizing applies_to with fact_objects as list."""
        raw = {
            "fact_objects": ["Supplier", "Manufacturer"],
            "categories": {"industry_type": ["MANUFACTURING"]},
        }
        result = service._normalize_applies_to(raw)
        assert result.fact_objects == ["Supplier", "Manufacturer"]
        assert result.categories == {"industry_type": ["MANUFACTURING"]}

    def test_normalize_applies_to_with_string_fact_object(self, service):
        """Test normalizing applies_to with fact_objects as single string."""
        raw = {
            "fact_objects": "Supplier",
            "categories": {},
        }
        result = service._normalize_applies_to(raw)
        assert result.fact_objects == ["Supplier"]

    def test_normalize_applies_to_with_empty_categories(self, service):
        """Test normalizing applies_to with empty categories."""
        raw = {"fact_objects": ["Supplier"], "categories": []}
        result = service._normalize_applies_to(raw)
        assert result.categories == {}

    def test_normalize_io_elements(self, service):
        """Test normalizing IO elements."""
        elements = [
            {"name": "is_eligible", "type": "flag", "metric": "is_eligible"},
            {"name": "score", "type": "numeric", "attribute": "credit_score"},
        ]
        result = service._normalize_io_elements(elements)
        assert len(result) == 2
        assert result[0]["name"] == "is_eligible"
        assert result[1]["attribute"] == "credit_score"

    def test_normalize_when_expression_type(self, service):
        """Test normalizing when clause with expression type."""
        raw = {"type": "expression", "expression": "entity.status == 'ACTIVE'"}
        result = service._normalize_when(raw)
        assert result["type"] == "expression"
        assert result["expression"] == "entity.status == 'ACTIVE'"
        assert result["sub_conditions"] == []

    def test_normalize_when_all_of_type(self, service):
        """Test normalizing when clause with all_of type."""
        raw = {
            "type": "all_of",
            "sub_conditions": ["cond1", "cond2"],
        }
        result = service._normalize_when(raw)
        assert result["type"] == "all_of"
        assert result["sub_conditions"] == ["cond1", "cond2"]

    def test_normalize_when_empty(self, service):
        """Test normalizing empty when clause."""
        result = service._normalize_when({})
        assert result["type"] == "expression"
        assert result["expression"] is None
        assert result["sub_conditions"] == []

    def test_normalize_action(self, service):
        """Test normalizing action/then clause."""
        raw = {
            "operator": "SET_FLAG",
            "params": {"flag_name": "is_eligible", "flag_value": True},
            "output_mapping": {},
        }
        result = service._normalize_action(raw)
        assert result["operator"] == "SET_FLAG"
        assert result["params"]["flag_name"] == "is_eligible"
        assert result["output_mapping"] == {}