# tests/unit/services/test_rule_service.py
"""Tests for RuleService."""

import pytest
from unittest.mock import AsyncMock

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

    # =========================================================================
    # export_rule_group_to_yaml Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_export_rule_group_to_yaml_phase2_format(self, service, storage):
        """Test exporting rule group to Phase 2 YAML format."""
        storage.get_rule_group = AsyncMock(
            return_value={
                "id": "rg-uuid-123",
                "name": "RD001_basic_eligibility",
                "description": "供应商融资申请的基础资质门槛校验",
                "type": "constraint",
                "priority": 100,
                "enabled": True,
                "applies_to": {
                    "fact_objects": ["Supplier"],
                    "categories": {"industry_type": ["MANUFACTURING"]},
                },
                "preconditions": [
                    {
                        "expression": "entity.status == 'ACTIVE'",
                        "fail": {"action": "reject", "reason": "企业经营状态异常"},
                    }
                ],
                "inputs": [{"name": "is_eligible", "type": "flag", "metric": "is_eligible"}],
                "outputs": [{"name": "is_eligible", "type": "flag"}],
                "schema_id": "test-schema",
            }
        )
        storage.list_rule_steps = AsyncMock(
            return_value=[
                {
                    "id": "step-1",
                    "name": "注册资本与成立年限检查",
                    "step_order": 1,
                    "enabled": True,
                    "description": "校验注册资本≥100万且成立≥1年",
                    "tags": ["eligibility"],
                    "when": {
                        "type": "all_of",
                        "sub_conditions": [
                            "entity.registered_capital_value >= 1000000",
                            "days_since(entity.establishment_date) >= 365",
                        ],
                    },
                    "then": {
                        "operator": "SET_FLAG",
                        "params": {"flag_name": "is_eligible", "flag_value": True},
                        "output_mapping": {},
                    },
                }
            ]
        )

        result = await service.export_rule_group_to_yaml("RD001_basic_eligibility", schema_id="test-schema")

        assert "rule_group:" in result
        assert "RD001_basic_eligibility" in result
        assert "rule_steps:" in result
        assert "step-1" in result
        assert "注册资本与成立年限检查" in result
        assert "order: 1" in result
        assert "tags:" in result
        assert "eligibility" in result
        # Verify legacy keys are NOT present
        assert "rule_definitions:" not in result
        assert "rule_logics:" not in result

    @pytest.mark.asyncio
    async def test_export_rule_group_to_yaml_not_found(self, service, storage):
        """Test export raises error when rule group not found."""
        storage.get_rule_group = AsyncMock(return_value=None)

        with pytest.raises(RuleServiceError, match="not found"):
            await service.export_rule_group_to_yaml("NONEXISTENT", schema_id="test-schema")

    @pytest.mark.asyncio
    async def test_export_rule_group_to_yaml_roundtrip(self, service, storage):
        """Test that exported YAML can be imported back (round-trip)."""
        # Setup: existing rule group data
        storage.get_rule_group = AsyncMock(
            return_value={
                "id": "rg-uuid-123",
                "name": "RD001_basic_eligibility",
                "description": "供应商融资申请的基础资质门槛校验",
                "type": "constraint",
                "priority": 100,
                "enabled": True,
                "applies_to": {
                    "fact_objects": ["Supplier"],
                    "categories": {"industry_type": ["MANUFACTURING"]},
                },
                "preconditions": [
                    {
                        "expression": "entity.status == 'ACTIVE'",
                        "fail": {"action": "reject", "reason": "企业经营状态异常"},
                    }
                ],
                "inputs": [{"name": "is_eligible", "type": "flag", "metric": "is_eligible"}],
                "outputs": [{"name": "is_eligible", "type": "flag"}],
                "schema_id": "test-schema",
            }
        )
        storage.list_rule_steps = AsyncMock(
            return_value=[
                {
                    "id": "step-1",
                    "name": "注册资本与成立年限检查",
                    "step_order": 1,
                    "enabled": True,
                    "description": "校验注册资本≥100万且成立≥1年",
                    "tags": ["eligibility"],
                    "when": {
                        "type": "all_of",
                        "sub_conditions": [
                            "entity.registered_capital_value >= 1000000",
                            "days_since(entity.establishment_date) >= 365",
                        ],
                    },
                    "then": {
                        "operator": "SET_FLAG",
                        "params": {"flag_name": "is_eligible", "flag_value": True},
                        "output_mapping": {},
                    },
                }
            ]
        )

        # Export
        exported_yaml = await service.export_rule_group_to_yaml("RD001_basic_eligibility", schema_id="test-schema")

        # Re-import: capture what gets saved
        saved_rg_data = None

        async def capture_save_rg(data, schema_id=None):
            nonlocal saved_rg_data
            saved_rg_data = data

        async def get_rule_group_after_save(name, schema_id=None):
            return saved_rg_data

        storage.save_rule_group.side_effect = capture_save_rg
        storage.get_rule_group.side_effect = get_rule_group_after_save

        result = await service.import_from_yaml(exported_yaml, schema_id="test-schema")

        # Verify round-trip: imported rule group has correct data
        assert result.name == "RD001_basic_eligibility"
        assert result.description == "供应商融资申请的基础资质门槛校验"
        assert result.type == "constraint"
        assert result.priority == 100
        assert result.enabled is True
        assert result.applies_to.fact_objects == ["Supplier"]
        assert result.applies_to.categories == {"industry_type": ["MANUFACTURING"]}
        assert len(result.preconditions) == 1
        assert result.preconditions[0].expression == "entity.status == 'ACTIVE'"
        assert len(result.inputs) == 1
        assert result.inputs[0].name == "is_eligible"
        assert len(result.outputs) == 1
        assert result.outputs[0].name == "is_eligible"

    # =========================================================================
    # import_from_l4_schema_yaml Tests (L4 Legacy Format)
    # =========================================================================

    L4_SCHEMA_YAML = """
semantic_space:
  id: "space.supply_chain_finance"
  name: "供应链金融授信评估语义空间"

  business_logic:
    rule_definitions:
      - id: RD001_basic_eligibility
        name: "基础准入检查"
        description: "供应商融资申请的基础资质门槛校验"
        rule_type: constraint
        priority: 100
        applies_to: [Supplier]
        applicable_categorizations: [credit_assessment]
        inputs:
          - { id: status, name: "经营状态", type: attribute }
          - { id: registered_capital, name: "注册资本", type: attribute }
        outputs:
          - { id: is_eligible, name: "是否准入", type: flag }
          - { id: rejection_reason, name: "拒绝原因", type: computed_value }
        logic_ids: [RL001_eligibility_standard]
        enabled: true

      - id: RD002_credit_score_compute
        name: "信用评分计算"
        description: "驱动 L3 credit_score 指标体系计算"
        rule_type: inference
        priority: 90
        applies_to: [Supplier]
        inputs:
          - { id: is_eligible, name: "是否准入", type: flag }
        outputs:
          - { id: credit_score, name: "综合信用评分", type: computed_value }
        logic_ids: [RL002_score_standard]
        enabled: true

    rule_logics:
      - id: RL001_eligibility_standard
        definition_id: RD001_basic_eligibility
        name: "标准准入检查"
        description: "注册资本≥100万、成立≥1年、近90天交易额≥50万"
        when:
          expression: |
            status == 'ACTIVE'
            AND registered_capital_value >= 1000000
        then_action:
          action_type: set_flag
          output:
            is_eligible: true
        else_action:
          action_type: set_flag
          output:
            is_eligible: false
            rejection_reason: "不满足基础准入条件"

      - id: RL002_score_standard
        definition_id: RD002_credit_score_compute
        name: "标准信用评分计算"
        when:
          expression: "is_eligible == true"
        then_action:
          action_type: compute
          output:
            credit_score: "$metric:credit_score"
"""

    @pytest.mark.asyncio
    async def test_import_from_l4_schema_yaml_basic(self, service, storage):
        """Test importing L4 schema.yaml format."""
        saved_rg_data = None
        saved_rg_names = set()

        async def capture_save_rg(data, schema_id=None):
            nonlocal saved_rg_data
            saved_rg_data = data
            saved_rg_names.add(data["name"])

        async def get_rule_group_after_save(name, schema_id=None):
            if name in saved_rg_names:
                return saved_rg_data
            return None

        storage.save_rule_group.side_effect = capture_save_rg
        storage.get_rule_group.side_effect = get_rule_group_after_save

        result = await service.import_from_l4_schema_yaml(self.L4_SCHEMA_YAML, schema_id="test-schema")

        assert len(result) == 2
        # First rule group
        assert result[0].name == "基础准入检查"
        assert result[0].description == "供应商融资申请的基础资质门槛校验"
        assert result[0].type == "constraint"
        assert result[0].priority == 100
        assert result[0].schema_id == "test-schema"
        assert result[0].applies_to.fact_objects == ["Supplier"]
        assert result[0].applies_to.categories == {}

        # Second rule group
        assert result[1].name == "信用评分计算"
        assert result[1].type == "inference"
        assert result[1].priority == 90

    @pytest.mark.asyncio
    async def test_import_from_l4_schema_yaml_inputs_outputs(self, service, storage):
        """Test that L4 inputs/outputs are correctly mapped (id -> name)."""
        saved_rg_data = None
        saved_rg_names = set()

        async def capture_save_rg(data, schema_id=None):
            nonlocal saved_rg_data
            saved_rg_data = data
            saved_rg_names.add(data["name"])

        async def get_rule_group_after_save(name, schema_id=None):
            if name in saved_rg_names:
                return saved_rg_data
            return None

        storage.save_rule_group.side_effect = capture_save_rg
        storage.get_rule_group.side_effect = get_rule_group_after_save

        result = await service.import_from_l4_schema_yaml(self.L4_SCHEMA_YAML, schema_id="test-schema")

        # Check first rule group's inputs/outputs
        rg = result[0]
        assert len(rg.inputs) == 2
        assert rg.inputs[0].name == "status"
        assert rg.inputs[1].name == "registered_capital"
        assert len(rg.outputs) == 2
        assert rg.outputs[0].name == "is_eligible"
        assert rg.outputs[1].name == "rejection_reason"

    @pytest.mark.asyncio
    async def test_import_from_l4_schema_yaml_saves_steps(self, service, storage):
        """Test that L4 import saves rule steps correctly."""
        saved_steps = []
        saved_rg_data = None
        saved_rg_names = set()

        async def capture_save_step(name, data):
            saved_steps.append(data)

        async def capture_save_rg(data, schema_id=None):
            nonlocal saved_rg_data
            saved_rg_data = data
            saved_rg_names.add(data["name"])

        async def get_rule_group_after_save(name, schema_id=None):
            if name in saved_rg_names:
                return saved_rg_data
            return None

        storage.save_rule_step.side_effect = capture_save_step
        storage.save_rule_group.side_effect = capture_save_rg
        storage.get_rule_group.side_effect = get_rule_group_after_save

        result = await service.import_from_l4_schema_yaml(self.L4_SCHEMA_YAML, schema_id="test-schema")

        # RL001 logic for RD001 rule
        rl001_steps = [s for s in saved_steps if s["id"] == "RL001_eligibility_standard"]
        assert len(rl001_steps) == 1
        step = rl001_steps[0]
        assert step["name"] == "标准准入检查"
        assert step["when"]["type"] == "expression"
        assert "status == 'ACTIVE'" in step["when"]["expression"]
        assert "registered_capital_value >= 1000000" in step["when"]["expression"]
        assert step["then"]["operator"] == "SET_FLAG"
        assert step["then"]["params"]["flag_name"] == "is_eligible"
        assert step["then"]["params"]["flag_value"] is True
        # else_action should also be set
        assert step["else"] is not None
        assert step["else"]["operator"] == "SET_FLAG"
        assert step["else"]["params"]["flag_name"] == "is_eligible"
        assert step["else"]["params"]["flag_value"] is False

    @pytest.mark.asyncio
    async def test_import_from_l4_schema_yaml_compute_action(self, service, storage):
        """Test L4 compute action is correctly converted."""
        saved_steps = []
        saved_rg_data = None
        saved_rg_names = set()

        async def capture_save_step(name, data):
            saved_steps.append(data)

        async def capture_save_rg(data, schema_id=None):
            nonlocal saved_rg_data
            saved_rg_data = data
            saved_rg_names.add(data["name"])

        async def get_rule_group_after_save(name, schema_id=None):
            if name in saved_rg_names:
                return saved_rg_data
            return None

        storage.save_rule_step.side_effect = capture_save_step
        storage.save_rule_group.side_effect = capture_save_rg
        storage.get_rule_group.side_effect = get_rule_group_after_save

        result = await service.import_from_l4_schema_yaml(self.L4_SCHEMA_YAML, schema_id="test-schema")

        # RL002 logic for RD002 rule (compute action)
        rl002_steps = [s for s in saved_steps if s["id"] == "RL002_score_standard"]
        assert len(rl002_steps) == 1
        step = rl002_steps[0]
        assert step["then"]["operator"] == "COMPUTE"
        assert "computations" in step["then"]["params"]
        assert step["then"]["params"]["computations"]["credit_score"] == "$metric:credit_score"

    @pytest.mark.asyncio
    async def test_import_from_l4_schema_yaml_missing_schema_id(self, service):
        """Test that missing schema_id raises error."""
        with pytest.raises(RuleServiceError, match="schema_id is required"):
            await service.import_from_l4_schema_yaml(self.L4_SCHEMA_YAML, schema_id=None)

    @pytest.mark.asyncio
    async def test_import_from_l4_schema_yaml_invalid_yaml(self, service):
        """Test that invalid YAML raises error."""
        with pytest.raises(RuleServiceError, match="Invalid YAML"):
            await service.import_from_l4_schema_yaml("invalid: yaml: content:", schema_id="test-schema")

    @pytest.mark.asyncio
    async def test_import_from_l4_schema_yaml_no_rule_definitions(self, service):
        """Test that missing rule_definitions raises error."""
        yaml_content = """
semantic_space:
  business_logic:
    rule_logics: []
"""
        with pytest.raises(RuleServiceError, match="No rule_definitions found"):
            await service.import_from_l4_schema_yaml(yaml_content, schema_id="test-schema")

    @pytest.mark.asyncio
    async def test_import_from_l4_schema_yaml_duplicate_rule_group(self, service, storage):
        """Test that importing duplicate rule group raises error."""
        storage.get_rule_group = AsyncMock(return_value={"name": "基础准入检查"})

        with pytest.raises(RuleServiceError, match="already exists"):
            await service.import_from_l4_schema_yaml(self.L4_SCHEMA_YAML, schema_id="test-schema")

    # =========================================================================
    # Helper Method Tests for L4 Conversion
    # =========================================================================

    def test_normalize_l4_when_expression(self, service):
        """Test normalizing L4 when with expression string."""
        raw = {"expression": "status == 'ACTIVE'"}
        result = service._normalize_l4_when(raw)
        assert result["type"] == "expression"
        assert result["expression"] == "status == 'ACTIVE'"
        assert result["sub_conditions"] == []

    def test_normalize_l4_when_multiline_expression(self, service):
        """Test normalizing L4 when with multiline expression."""
        raw = {
            "expression": """status == 'ACTIVE'
            AND registered_capital_value >= 1000000"""
        }
        result = service._normalize_l4_when(raw)
        assert result["type"] == "expression"
        assert "status == 'ACTIVE'" in result["expression"]
        assert "registered_capital_value >= 1000000" in result["expression"]

    def test_normalize_l4_when_all_of(self, service):
        """Test normalizing L4 when with allOf."""
        raw = {"allOf": ["cond1", "cond2"]}
        result = service._normalize_l4_when(raw)
        assert result["type"] == "all_of"
        assert result["sub_conditions"] == ["cond1", "cond2"]

    def test_normalize_l4_when_any_of(self, service):
        """Test normalizing L4 when with anyOf."""
        raw = {"anyOf": ["cond1", "cond2"]}
        result = service._normalize_l4_when(raw)
        assert result["type"] == "any_of"
        assert result["sub_conditions"] == ["cond1", "cond2"]

    def test_normalize_l4_action_set_flag(self, service):
        """Test normalizing L4 set_flag action."""
        raw = {
            "action_type": "set_flag",
            "output": {"is_eligible": True},
        }
        result = service._normalize_l4_action(raw)
        assert result["operator"] == "SET_FLAG"
        assert result["params"]["flag_name"] == "is_eligible"
        assert result["params"]["flag_value"] is True

    def test_normalize_l4_action_set_flag_with_extra_output(self, service):
        """Test normalizing L4 set_flag action with extra output fields."""
        raw = {
            "action_type": "set_flag",
            "output": {
                "is_eligible": False,
                "rejection_reason": "Not eligible",
            },
        }
        result = service._normalize_l4_action(raw)
        assert result["operator"] == "SET_FLAG"
        assert result["params"]["flag_name"] == "is_eligible"
        assert result["params"]["flag_value"] is False
        assert "rejection_reason" in result["output_mapping"]

    def test_normalize_l4_action_compute(self, service):
        """Test normalizing L4 compute action."""
        raw = {
            "action_type": "compute",
            "output": {"credit_score": "$metric:credit_score"},
        }
        result = service._normalize_l4_action(raw)
        assert result["operator"] == "COMPUTE"
        assert "computations" in result["params"]
        assert result["params"]["computations"]["credit_score"] == "$metric:credit_score"

    def test_normalize_l4_action_alert(self, service):
        """Test normalizing L4 alert action."""
        raw = {
            "action_type": "alert",
            "output": {"level": "HIGH", "message": "Risk detected"},
        }
        result = service._normalize_l4_action(raw)
        assert result["operator"] == "ALERT"
        assert result["params"]["alert_data"]["level"] == "HIGH"

    def test_normalize_l4_action_empty(self, service):
        """Test normalizing empty L4 action."""
        result = service._normalize_l4_action(None)
        assert result["operator"] == ""
        assert result["params"] == {}
        assert result["output_mapping"] == {}

    def test_map_l4_action_type(self, service):
        """Test mapping L4 action types to Phase 2 operators."""
        assert service._map_l4_action_type("set_flag") == "SET_FLAG"
        assert service._map_l4_action_type("compute") == "COMPUTE"
        assert service._map_l4_action_type("alert") == "ALERT"
        assert service._map_l4_action_type("approve") == "APPROVE"
        assert service._map_l4_action_type("reject") == "REJECT"
        assert service._map_l4_action_type("set_value") == "SET_VALUE"
        assert service._map_l4_action_type("unknown") == "UNKNOWN"