# Phase 2-A: 规则编排系统实施细则

> **日期**: 2026-04-15  
> **阶段**: Phase 2-A: 规则编排核心能力  
> **负责人**: 待定  
> **关联设计**: `detail/plans/2026-04-15-rule-orchestration-system-design.md`

---

## 一、实施概述

### 1.1 目标

构建规则编排系统的**核心能力**，为业务人员提供**可视化规则创建、编辑、验证**的基础平台。

**交付范围**：
1. 规则组/规则实例数据模型 + DuckDB 持久化
2. 规则CRUD API
3. 基础前端框架（列表页 + 详情页）
4. 规则组框架编辑器（四元素①②③）
5. YAML导入/导出
6. 单规则模拟执行

**非交付范围**：
- 要素DAG可视化（Phase 2-B）
- 编排画布拖拽排序（Phase 2-B）
- 复杂算子参数UI（Phase 2-B/C）
- 全量DAG构建（Phase 2-B）

### 1.2 实施前提

1. **架构约束**：需遵守 `AGENTS.md` 中的边界约束
2. **现有兼容性**：需要兼容当前 `RuleDefinitionV2` / `RuleLogic` 模型
3. **测试要求**：遵循 `docs/development/testing.md`，覆盖率≥80%
4. **文档治理**：需同步更新 `docs/STATUS.md` / `docs/TODO.md`

### 1.3 与现有系统的兼容性分析

根据代码分析，当前系统已有以下组件：

| 组件 | 位置 | 现状 | 升级策略 |
|------|------|------|----------|
| `RuleDefinitionV2` | `core/schema/models.py:436` | L4规则定义，有 `applies_to`/`inputs`/`outputs` | **扩展**：增加 `applicable_categories` + `preconditions` 增强 |
| `RuleLogic` | `core/schema/models.py:477` | 规则逻辑实例，有 `steps[]` | **复用**：映射为 `RuleStep`，但需要扩展 `operator`/`params` |
| `api/routes/rules.py` | 规则API | 基础CRUD + 执行 | **新增API**：创建新的 `rule-groups`/`rule-steps` 路由，原有逻辑保留 |
| `storage/duckdb/store.py` | 存储 | 已有8张Phase 1表 | **新增表**：`rule_groups` + `rule_steps` + `metric_extensions` |

**关键兼容决策**：
```
rule_definitions (Schema v2)    → RuleDefinitionV2 (框架，不含详细逻辑)
rule_logics.steps (Schema v2)   → RuleLogic (逻辑步骤，多个)
rule_groups (新系统)            ← RuleDefinitionV2 + 扩展字段
rule_steps (新系统)             ← RuleLogic.steps的元素 + operator/params扩展
```

---

## 二、后端实施详情

### 2.1 数据模型升级

#### 2.1.1 新数据模型（继承自有模型）

```python
# ontology_engine/core/rule/models.py ✨ 新文件

from pydantic import BaseModel, Field
from typing import Optional, Literal, Any, List, Dict

# 核心模型：扩展自 RuleDefinitionV2，增加可视化所需字段
class RuleGroup(BaseModel):  # 规则组，对应 Schema v2 的 rule_definitions
    id: str
    name: str
    description: Optional[str] = None
    rule_type: Literal["constraint", "inference", "alert", "decision"] = "constraint"
    priority: int = 100
    
    # ① 作用对象（四元素之一）
    applies_to: List[str] = Field(default_factory=list)  # 实体类型列表
    # ② 适用场景（四元素之二） - 扩展字段
    applicable_categories: Optional[Dict[str, List[str]]] = None  # {dimension: [values]}
    
    # ③ 输入输出要素（四元素之三）
    inputs: List[IOElement] = Field(default_factory=list)
    outputs: List[IOElement] = Field(default_factory=list)
    
    # 前置条件（RuleDefinitionV2已有，增强）
    preconditions: List[Precondition] = Field(default_factory=list)
    
    # 可视化/UI字段
    color: Optional[str] = None  # 十六进制颜色，如 "#1677FF"
    icon: Optional[str] = None   # 图标名称
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""
    
    # 引用现有系统的 compatibility 字段
    logic_ids: List[str] = Field(default_factory=list)  # 对 RuleLogic.id 的引用


class RuleStep(BaseModel):  # 规则实例，对应 Schema v2 的 rule_logics.steps
    id: str  # 规则实例ID，如 "R001"
    rule_group_id: str  # 所属规则组ID
    name: str
    order: int  # 执行顺序，从1开始
    
    # ④ 分析逻辑（四元素之四）
    when: ConditionClause  # 条件
    then: ActionClause     # 主动作
    else_: Optional[ActionClause] = None  # 备选动作
    
    # 算子扩展字段
    operator: Optional[str] = None  # 算子名称：BINNING/SCORECARD/WEIGHTED_SUM/DECISION_TABLE/LLM_JUDGE
    operator_params: Optional[Dict[str, Any]] = None  # 算子参数
    
    # 元信息
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""


class IOElement(BaseModel):  # 输入/输出要素
    name: str
    type: Literal["metric", "attribute", "rule_output", "variable"]
    ref: Optional[str] = None  # 引用名（metric.name / attribute.path）
    value_type: Literal["boolean", "integer", "decimal", "Money", "string", "flag"] = "string"
    description: Optional[str] = None


class Precondition(BaseModel):  # 前置条件（扩展自有模型）
    expression: str
    fail_action: FailAction = Field(default_factory=lambda: FailAction())


class ConditionClause(BaseModel):
    type: Literal["expression", "all_of", "any_of"] = "expression"
    expression: Optional[str] = None
    all_of: Optional[List[str]] = None
    any_of: Optional[List[str]] = None


class ActionClause(BaseModel):
    type: Literal["set_flag", "reject", "compute", "alert", "none"] = "compute"
    target: Optional[str] = None
    value: Optional[Any] = None
    reason: Optional[str] = None
    alert_level: Optional[Literal["LOW", "MEDIUM", "HIGH"]] = None
    alert_message: Optional[str] = None
```

### 2.2 DuckDB 表设计

在 `storage/duckdb/store.py` 中新增表：

```sql
-- 规则组表（对应 RuleGroup）
CREATE TABLE rule_groups (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    rule_type VARCHAR NOT NULL DEFAULT 'constraint',
    priority INTEGER DEFAULT 100,
    applies_to JSON NOT NULL,  -- JSON数组：["Supplier", "Invoice"]
    applicable_categorizations JSON,  -- JSON对象：{"company_scale": ["LARGE", "MEDIUM"]}
    inputs JSON NOT NULL,
    outputs JSON NOT NULL,
    preconditions JSON,
    color VARCHAR,
    icon VARCHAR,
    enabled BOOLEAN DEFAULT TRUE,
    logic_ids JSON,  -- JSON数组：["credit_assessment_1", "credit_assessment_2"]
    schema_id VARCHAR,  -- 所属Schema ID
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 规则实例表（对应 RuleStep）
CREATE TABLE rule_steps (
    id VARCHAR NOT NULL,  -- 如 "R001"
    rule_group_id VARCHAR NOT NULL REFERENCES rule_groups(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    when_clause JSON NOT NULL,
    then_clause JSON NOT NULL,
    else_clause JSON,
    operator VARCHAR,  -- 算子类型
    operator_params JSON,
    description TEXT,
    tags JSON,  -- JSON数组
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (rule_group_id, id)
);

-- 指标扩展表（值域约束+阈值）
CREATE TABLE metric_extensions (
    metric_name VARCHAR PRIMARY KEY,
    value_domain JSON,
    thresholds JSON,
    color VARCHAR,
    unit VARCHAR,
    schema_id VARCHAR,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_rule_groups_schema ON rule_groups(schema_id);
CREATE INDEX idx_rule_steps_group ON rule_steps(rule_group_id);
CREATE INDEX idx_metric_extensions_schema ON metric_extensions(schema_id);
```

### 2.3 服务层实现

#### 2.3.1 RuleService

```python
# ontology_engine/services/rule_service.py ✨ 新文件

"""
规则组/规则实例服务。

职责：
1. 规则组CRUD
2. 规则实例CRUD（绑定到规则组）
3. 规则实例排序调整
4. YAML导入/导出（Schema v2 canonical格式）
5. 与现有SchemaService/Storage的集成
"""

class RuleService:
    def __init__(self, storage_backend: StorageBackend):
        self.storage = storage_backend
        
    async def create_rule_group(self, rule_group: RuleGroup) -> RuleGroup:
        """创建规则组"""
        # 验证：确保 rule_group.id 唯一
        # 验证：输入/输出要素必须引用有效指标或属性
        # 持久化到 duckdb.rule_groups
        pass
    
    async def get_rule_group(self, rule_group_id: str) -> Optional[RuleGroup]:
        """获取规则组详情"""
        pass
    
    async def list_rule_groups(
        self, 
        schema_id: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> List[RuleGroup]:
        """规则组列表（可选过滤）"""
        pass
    
    async def update_rule_group(
        self, 
        rule_group_id: str,
        updates: Dict[str, Any]
    ) -> RuleGroup:
        """更新规则组"""
        pass
    
    async def delete_rule_group(self, rule_group_id: str) -> bool:
        """删除规则组（级联删除关联的rule_steps）"""
        pass
    
    async def add_rule_step(self, step: RuleStep) -> RuleStep:
        """添加规则实例到规则组"""
        # 验证：rule_group_id存在
        # 验证：when/then语法正确
        # 自动生成order（最大order+1）
        pass
    
    async def update_rule_step(self, step: RuleStep) -> RuleStep:
        """更新规则实例"""
        pass
    
    async def reorder_rule_steps(
        self,
        rule_group_id: str,
        new_order: List[str]  # step.id列表
    ) -> bool:
        """调整规则实例执行顺序"""
        pass
    
    async def export_to_yaml(self, rule_group_id: str) -> str:
        """导出为Schema v2 canonical YAML格式"""
        # 组合成符合 docs/05-schema-v2/09-canonical-schema-spec.md 的YAML
        pass
    
    async def import_from_yaml(
        self, 
        yaml_content: str, 
        validate: bool = True
    ) -> RuleGroup:
        """从YAML导入规则组（验证格式）"""
        pass
    
    async def validate_step_condition(self, condition: str) -> bool:
        """验证条件表达式语法"""
        pass
```

#### 2.3.2 与现有服务的集成点

```python
# 依赖注入示例
def get_rule_service(
    storage: StorageBackend = Depends(get_storage_backend),
    schema_service: SchemaService = Depends(get_schema_service)
) -> RuleService:
    return RuleService(storage, schema_service)
```

### 2.4 API路由设计

```
📁 ontology_engine/api/routes/rule_groups.py ✨ 新文件
```

```python
router = APIRouter(prefix="/v1/rule-groups", tags=["Rule Management"])

# === 规则组 CRUD ===
@router.post("")
async def create_rule_group(...): ...

@router.get("")
async def list_rule_groups(...): ...

@router.get("/{id}")
async def get_rule_group_detail(...): ...

@router.put("/{id}")
async def update_rule_group(...): ...

@router.delete("/{id}")
async def delete_rule_group(...): ...

# === 规则实例管理 ===
@router.get("/{id}/steps")
async def get_rule_steps(...): ...

@router.post("/{id}/steps")
async def add_rule_step(...): ...

@router.put("/{id}/steps/{step_id}")
async def update_rule_step(...): ...

@router.delete("/{id}/steps/{step_id}")
async def delete_rule_step(...): ...

@router.post("/{id}/steps/reorder")
async def reorder_rule_steps(...): ...

# === 模拟执行 ===
@router.post("/{id}/simulate")
async def simulate_rule(
    entity_data: Dict[str, Any],
    pre_computed: Optional[Dict[str, Any]] = None,
    step_filter: Optional[List[str]] = None
): ...

# === YAML导入/导出 ===
@router.get("/{id}/export")
async def export_rule_group_to_yaml(...): ...

@router.post("/import")
async def import_rule_group_from_yaml(
    yaml_content: str,
    validate_only: bool = False
): ...

@router.post("/validate-yaml")
async def validate_rule_yaml(...): ...
```

```
📁 ontology_engine/api/routes/operators.py ✨ 新文件
```

```python
router = APIRouter(prefix="/v1/operators", tags=["Operators"])

@router.get("")
async def list_operators():
    """获取算子列表及参数Schema"""
    return {
        "binning": binning_param_schema,
        "scorecard": scorecard_param_schema,
        "weighted_sum": weighted_sum_param_schema,
        "decision_table": decision_table_param_schema,
        "llm_judge": llm_judge_param_schema,
        # ... 其他算子
    }

@router.get("/{operator_name}/schema")
async def get_operator_schema(operator_name: str): ...

@router.post("/{operator_name}/validate")
async def validate_operator_params(
    operator_name: str,
    params: Dict[str, Any]
): ...
```

### 2.5 依赖项

| 依赖 | 版本 | 用途 |
|------|------|------|
| `pydantic^2.5.0` | 已有 | 数据验证 |
| `FastAPI^0.104.0` | 已有 | API框架 |
| `duckdb^1.0.0` | 已有 | 持久化存储 |
| `pyyaml^6.0` | 需添加 | YAML导入/导出 |
| `jsonschema^4.17.0` | 需添加 | 算子参数Schema验证 |

---

## 三、前端实施详情

### 3.1 项目结构

```
📂 ontology-engine-ui/src/
├── pages/
│   ├── rules/ ✨ 新目录
│   │   ├── RuleGroupListPage.tsx       # 规则组列表
│   │   ├── RuleGroupDetailPage.tsx     # 规则组详情（三栏布局）
│   │   └── index.ts
│   └── [...其他已有页面]
│
├── components/
│   ├── rule-editor/ ✨ 新目录（Phase 2-A）
│   │   ├── RuleGroupForm.tsx          # 规则组框架表单（四元素①②③）
│   │   ├── RuleStepList.tsx           # 规则实例列表
│   │   ├── ConditionEditor.tsx        # 条件编辑器（基础版）
│   │   ├── ActionEditor.tsx           # 动作编辑器（基础版）
│   │   └── SimulationPanel.tsx        # 模拟执行面板
│   ├── operator-params/               # ✨ Phase 2-B（暂不实现）
│   └── dag-view/                      # ✨ Phase 2-B（暂不实现）
│
├── hooks/ ✨ 新目录
│   ├── useRuleGroups.ts              # 规则组数据管理
│   ├── useRuleSteps.ts               # 规则实例数据管理
│   ├── useMetrics.ts                 # 指标数据管理（复用现有）
│   ├── useDAG.ts                     # ✨ Phase 2-B
│   └── useSimulation.ts              # 模拟执行hook
│
├── stores/ ✨ 新目录
│   ├── ruleStore.ts                  # 规则编排状态（Zustand）
│   └── dagStore.ts                   # ✨ Phase 2-B
│
├── api/
│   ├── ruleGroups.ts                 # 规则组API客户端
│   ├── ruleSteps.ts                  # 规则实例API客户端
│   ├── operators.ts                  # 算子API客户端
│   └── [...其他已有API]
│
└── types/
    ├── rule.ts                       # 规则相关类型定义
    └── operator.ts                   # 算子相关类型定义
```

### 3.2 关键组件实现详情

#### 3.2.1 RuleGroupDetailPage（三栏布局）

```tsx
// src/pages/rules/RuleGroupDetailPage.tsx
export const RuleGroupDetailPage: React.FC = () => {
  const { ruleGroupId } = useParams();
  const { ruleGroup, loading } = useRuleGroup(ruleGroupId);
  const { steps } = useRuleSteps(ruleGroupId);
  
  return (
    <PageLayout>
      <PageHeader 
        title={ruleGroup?.name}
        subTitle={ruleGroup?.description}
        backUrl="/rules"
        extra={<RuleGroupActions ruleGroup={ruleGroup} />}
      />
      
      <Row gutter={[16, 16]}>
        {/* 左侧：规则组框架配置 */}
        <Col span={8}>
          <Card title="规则框架" size="small">
            <RuleGroupForm 
              ruleGroup={ruleGroup}
              readOnly={false}
            />
          </Card>
        </Col>
        
        {/* 中间：规则实例列表 */}
        <Col span={12}>
          <Card title="规则逻辑步骤">
            <RuleStepList 
              steps={steps}
              ruleGroupId={ruleGroupId}
            />
            <div style={{ marginTop: 16 }}>
              <Button type="dashed" block>
                <PlusOutlined /> 添加规则步骤
              </Button>
            </div>
          </Card>
        </Col>
        
        {/* 右侧：模拟面板 */}
        <Col span={4}>
          <Card title="快速模拟" size="small">
            <SimulationPanel ruleGroupId={ruleGroupId} />
          </Card>
        </Col>
      </Row>
    </PageLayout>
  );
};
```

#### 3.2.2 RuleGroupForm（四元素编辑器）

```tsx
// src/components/rule-editor/RuleGroupForm.tsx
export const RuleGroupForm: React.FC<RuleGroupFormProps> = ({ ruleGroup }) => {
  return (
    <Form<RuleGroup>
      layout="vertical"
      initialValues={ruleGroup}
    >
      {/* ① 作用对象 */}
      <Card title="作用对象" size="small">
        <Form.Item
          label="作用于实体类型"
          name="applies_to"
          rules={[{ required: true }]}
        >
          <Select
            mode="multiple"
            placeholder="选择实体类型..."
            options={entityTypeOptions}
          />
        </Form.Item>
      </Card>
      
      {/* ② 适用场景 */}
      <Card title="适用场景" size="small" style={{ marginTop: 16 }}>
        <Form.Item
          label="维度分类过滤"
          name="applicable_categories"
        >
          <CategoryFilterEditor />
        </Form.Item>
        
        <Form.Item
          label="前置条件"
          name="preconditions"
        >
          <PreconditionEditor />
        </Form.Item>
      </Card>
      
      {/* ③ 输入输出要素 */}
      <Card title="输入/输出要素" size="small" style={{ marginTop: 16 }}>
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item label="输入要素" name="inputs">
              <IOElementsEditor type="input" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item label="输出要素" name="outputs">
              <IOElementsEditor type="output" />
            </Form.Item>
          </Col>
        </Row>
      </Card>
      
      {/* 基础属性 */}
      <Card title="规则属性" size="small" style={{ marginTop: 16 }}>
        <Form.Item label="规则名称" name="name" rules={[{ required: true }]}>
          <Input placeholder="输入规则组名称..." />
        </Form.Item>
        {/* ... 其他属性 */}
      </Card>
    </Form>
  );
};
```

#### 3.2.3 RuleStepList（规则实例列表）

```tsx
// src/components/rule-editor/RuleStepList.tsx
export const RuleStepList: React.FC<RuleStepListProps> = ({ steps }) => {
  const [editingStep, setEditingStep] = useState<string | null>(null);
  
  return (
    <React.Fragment>
      {steps.map((step) => (
        <div key={step.id} style={{ marginBottom: 12 }}>
          <Card 
            size="small"
            title={
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Tag color="blue">R{step.order}</Tag>
                <span>{step.name}</span>
                <div style={{ marginLeft: 'auto' }}>
                  <Space>
                    <Button 
                      size="small" 
                      icon={<EditOutlined />}
                      onClick={() => setEditingStep(step.id)}
                    />
                    <Button 
                      size="small" 
                      icon={<PlayCircleOutlined />}
                      onClick={() => simulateSingleStep(step.id)}
                    />
                  </Space>
                </div>
              </div>
            }
          >
            {/* 条件摘要 */}
            <div style={{ marginBottom: 8 }}>
              <Text strong>WHEN:</Text>{' '}
              <ConditionSummary condition={step.when} />
            </div>
            
            {/* 动作摘要 */}
            <div>
              <Text strong>THEN:</Text>{' '}
              <ActionSummary action={step.then} />
            </div>
            
            {/* 算子标签 */}
            {step.operator && (
              <div style={{ marginTop: 4 }}>
                <Tag color="green">{step.operator}</Tag>
              </div>
            )}
          </Card>
          
          {/* 编辑模态框 */}
          {editingStep === step.id && (
            <RuleStepEditorModal
              step={step}
              onClose={() => setEditingStep(null)}
            />
          )}
        </div>
      ))}
    </React.Fragment>
  );
};
```

### 3.3 API 客户端

```typescript
// src/api/ruleGroups.ts
import { RuleGroup, RuleStep } from '@/types/rule';

const API_BASE = '/api/v1';

export const ruleGroupsApi = {
  // 规则组CRUD
  list: async (params?: { schema_id?: string; entity_type?: string }) => {
    const res = await fetch(`${API_BASE}/rule-groups?${new URLSearchParams(params)}`);
    return res.json();
  },
  
  getById: async (id: string) => {
    const res = await fetch(`${API_BASE}/rule-groups/${id}`);
    return res.json();
  },
  
  create: async (ruleGroup: Partial<RuleGroup>) => {
    const res = await fetch(`${API_BASE}/rule-groups`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ruleGroup),
    });
    return res.json();
  },
  
  // 规则实例管理
  listSteps: async (ruleGroupId: string) => {
    const res = await fetch(`${API_BASE}/rule-groups/${ruleGroupId}/steps`);
    return res.json();
  },
  
  addStep: async (ruleGroupId: string, step: Partial<RuleStep>) => {
    const res = await fetch(`${API_BASE}/rule-groups/${ruleGroupId}/steps`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(step),
    });
    return res.json();
  },
  
  // 模拟执行
  simulate: async (
    ruleGroupId: string, 
    entityData: Record<string, any>,
    stepFilter?: string[]
  ) => {
    const res = await fetch(`${API_BASE}/rule-groups/${ruleGroupId}/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entity_data: entityData, step_filter: stepFilter }),
    });
    return res.json();
  },
  
  // YAML导入导出
  exportYaml: async (ruleGroupId: string) => {
    const res = await fetch(`${API_BASE}/rule-groups/${ruleGroupId}/export`);
    return res.text();  // 返回纯文本YAML
  },
  
  importYaml: async (yamlContent: string, validateOnly = false) => {
    const res = await fetch(`${API_BASE}/rule-groups/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        yaml_content: yamlContent,
        validate_only: validateOnly,
      }),
    });
    return res.json();
  },
};
```

### 3.4 状态管理（Zustand）

```typescript
// src/stores/ruleStore.ts
import { create } from 'zustand';
import { RuleGroup, RuleStep } from '@/types/rule';

interface RuleStore {
  // 状态
  currentRuleGroup: RuleGroup | null;
  ruleSteps: RuleStep[];
  loading: boolean;
  error: string | null;
  
  // Actions
  loadRuleGroup: (id: string) => Promise<void>;
  loadRuleSteps: (ruleGroupId: string) => Promise<void>;
  addRuleStep: (step: Partial<RuleStep>) => Promise<void>;
  updateRuleStep: (step: RuleStep) => Promise<void>;
  reorderRuleSteps: (newOrder: string[]) => Promise<void>;
  simulateStep: (stepId: string, testData: object) => Promise<any>;
  exportYaml: () => Promise<string>;
  
  // UI状态
  editingStepId: string | null;
  setEditingStepId: (id: string | null) => void;
  simulationResult: any | null;
  setSimulationResult: (result: any) => void;
}

export const useRuleStore = create<RuleStore>((set, get) => ({
  currentRuleGroup: null,
  ruleSteps: [],
  loading: false,
  error: null,
  editingStepId: null,
  simulationResult: null,
  
  loadRuleGroup: async (id) => {
    set({ loading: true, error: null });
    try {
      const ruleGroup = await ruleGroupsApi.getById(id);
      set({ currentRuleGroup: ruleGroup, loading: false });
    } catch (error) {
      set({ error: error.message, loading: false });
    }
  },
  
  // ... 其他action实现
}));
```

### 3.5 依赖包清单

```json
// 需要在 package.json 中添加的依赖
{
  "dependencies": {
    "@ant-design/icons": "^5.0.0",        // 已有
    "antd": "^5.0.0",                     // 已有
    "react": "^18.2.0",                   // 已有
    "react-dom": "^18.2.0",               // 已有
    "react-router-dom": "^6.8.0",         // 已有
    "zustand": "^4.4.0",                  // 状态管理（需添加）
    "immer": "^10.0.0",                   // Zustand辅助（需添加）
    "yaml": "^2.3.0",                     // YAML处理（需添加）
    "lodash-es": "^4.17.21",              // 工具函数（已有或需添加）
    "dayjs": "^1.11.0"                    // 日期处理（已有）
  },
  "devDependencies": {
    "@types/react": "^18.0.0",            // 已有
    "@types/react-dom": "^18.0.0",        // 已有
    "typescript": "^5.0.0",               // 已有
    "vite": "^5.0.0",                     // 已有
    "@vitejs/plugin-react": "^4.0.0",     // 已有
    "tailwindcss": "^3.0.0"               // CSS框架（如有）
  }
}
```

---

## 四、Phase 2-A 任务分解（按开发顺序）

### 4.1 Week 1: 数据模型 + 存储层

| Task | 模块 | 负责人 | 状态 | 验收标准 |
|------|------|--------|------|----------|
| 1.1 | 创建 `ontology_engine/core/rule/models.py` | Backend | ✅ | Pydantic模型通过验证测试 |
| 1.2 | 创建 `ontology_engine/core/rule/schemas.py` (算子参数JSON Schema) | Backend | ✅ | BINNING/SCORECARD/WEIGHTED_SUM/DT/LLM Schema定义 |
| 1.3 | 扩展 `storage/duckdb/store.py` (新增3表) | Backend | ✅ | SQL创建脚本+迁移测试 |
| 1.4 | 创建 `ontology_engine/services/rule_service.py` 骨架 | Backend | ✅ | 服务接口定义+依赖注入 |
| 1.5 | 创建 `tests/unit/core/rule/test_models.py` | Backend | ✅ | 基础模型测试通过 |

**交付物**：
- 可持久化的RuleGroup/RuleStep数据模型
- DuckDB schema升级脚本
- 基础服务接口

### 4.2 Week 2: API层实现

| Task | 模块 | 负责人 | 状态 | 验收标准 |
|------|------|--------|------|----------|
| 2.1 | 创建 `api/routes/rule_groups.py` (规则组CRUD) | Backend | ✅ | POST/GET/PUT/DELETE 端点可用 |
| 2.2 | 创建 `api/routes/operators.py` (算子Schema) | Backend | ✅ | GET /v1/operators 返回5种算子schema |
| 2.3 | 在 `api/server.py` 注册新路由 | Backend | ✅ | 启动服务，/api/v1/rule-groups 可访问 |
| 2.4 | 实现 `RuleService` (create/list/update 基础CRUD) | Backend | ✅ | 通过API测试 |
| 2.5 | 创建 `tests/unit/api/test_rule_groups.py` | Backend | ✅ | API端点测试通过 |

**交付物**：
- 完整的规则管理REST API
- 算子参数Schema API
- API测试套件

### 4.3 Week 3: YAML导入导出 + 规则验证

| Task | 模块 | 负责人 | 状态 | 验收标准 |
|------|------|--------|------|----------|
| 3.1 | 实现 `rule_service.export_to_yaml()` | Backend | | 产出符合Schema v2 canonical的YAML |
| 3.2 | 实现 `rule_service.import_from_yaml()` | Backend | | 从YAML解析+验证+创建规则组 |
| 3.3 | 实现 `ConditionParser` (表达式验证) | Backend | | 基础表达式语法验证 |
| 3.4 | 实现API端点：/export, /import, /validate-yaml | Backend | | 端点可通过 curl 测试 |
| 3.5 | 创建 `tests/unit/services/test_rule_service_yaml.py` | Backend | | YAML往返导入导出测试 |

**交付物**：
- Schema v2 YAML导入导出功能
- 表达式语法验证
- YAML验证API

### 4.4 Week 4: 前端基础框架

| Task | 模块 | 负责人 | 状态 | 验收标准 |
|------|------|--------|------|----------|
| 4.1 | 创建 TypeScript类型定义：`types/rule.ts` | Frontend | | TypeScript编译通过 |
| 4.2 | 创建API客户端：`src/api/ruleGroups.ts`等 | Frontend | | API调用封装完成 |
| 4.3 | 创建基础Hook：`useRuleGroups.ts` | Frontend | | 支持加载列表+详情 |
| 4.4 | 创建状态管理：`stores/ruleStore.ts` | Frontend | | Zustand store可用 |
| 4.5 | 创建页面骨架：`pages/rules/` 目录 | Frontend | | 路由配置完成 |

**交付物**：
- TypeScript类型系统
- 前端数据层（API+Hook+Store）
- 页面骨架

### 4.5 Week 5: 规则组列表页 + 框架编辑

| Task | 模块 | 负责人 | 状态 | 验收标准 |
|------|------|--------|------|----------|
| 5.1 | 创建 `RuleGroupListPage.tsx` | Frontend | | 列表显示+分页+过滤 |
| 5.2 | 创建 `RuleGroupForm.tsx` (四元素①②③) | Frontend | | 框架配置表单完成 |
| 5.3 | 组件：`CategoryFilterEditor`, `PreconditionEditor`等 | Frontend | | 专用编辑器组件 |
| 5.4 | 创建 `RuleGroupCreatePage.tsx` (新建) | Frontend | | 完整创建流程 |
| 5.5 | 创建 `RuleGroupDetailPage.tsx` (布局骨架) | Frontend | | 三栏布局完成 |

**交付物**：
- 规则组列表查询页面
- 规则框架编辑器（四元素①②③）
- 创建/更新完整流程

### 4.6 Week 6: 规则实例编辑 + 模拟

| Task | 模块 | 负责人 | 状态 | 验收标准 |
|------|------|--------|------|----------|
| 6.1 | 创建 `RuleStepList.tsx` | Frontend | | 步骤列表+拖拽支持 |
| 6.2 | 创建 `ConditionEditor.tsx` (基础版) | Frontend | | 表达式编辑器 |
| 6.3 | 创建 `ActionEditor.tsx` (基础版) | Frontend | | 简单动作选择器 |
| 6.4 | 创建 `RuleStepEditorModal.tsx` | Frontend | | 模态框编辑器 |
| 6.5 | 创建 `SimulationPanel.tsx` | Frontend | | 模拟面板UI |
| 6.6 | 实现API集成：模拟执行 | Frontend | | 可调用后端模拟API |

**交付物**：
- 规则实例编辑流程
- 单规则模拟执行UI
- 条件/动作基础编辑器

### 4.7 Week 7: 集成测试 + 优化

| Task | 模块 | 负责人 | 状态 | 验收标准 |
|------|------|--------|------|----------|
| 7.1 | 端到端测试：创建->编辑->模拟->导出 | QA | | E2E测试通过 |
| 7.2 | 性能测试：大数据量规则组加载 | QA | | 列表加载 < 2s |
| 7.3 | 兼容性测试：从现有系统导入 | QA | | 旧规则可迁移 |
| 7.4 | 前端验收测试 | QA | | 通过UX验收标准 |
| 7.5 | 文档更新：`docs/STATUS.md`, `docs/TODO.md` | Doc | | 文档同步更新 |

**交付物**：
- 完整可用的Phase 2-A系统
- 测试报告
- 更新的文档

---

## 五、质量门禁

### 5.1 代码质量

```bash
# 后端
mypy ontology_engine/core/rule/ --strict
ruff check ontology_engine/core/rule/
pytest tests/unit/core/rule/ -v --coverage

# 前端
npm run lint
npm run type-check
npm run test:unit
```

### 5.2 测试覆盖率要求

| 模块 | 覆盖率目标 | 关键测试点 |
|------|-----------|----------|
| `core/rule/models.py` | ≥95% | 模型验证、序列化 |
| `services/rule_service.py` | ≥85% | CRUD、YAML导入导出 |
| `api/routes/rule_groups.py` | ≥80% | 所有端点测试 |
| 前端组件 | ≥70% | 组件渲染、用户交互 |

### 5.3 性能指标

| 指标 | 目标 | 监控方法 |
|------|------|----------|
| API响应时间(95%) | <200ms | 接口性能测试 |
| 规则组列表加载 | <500ms (10个规则组) | 前端性能监控 |
| YAML导出速度 | <2s (50个步骤) | 端到端测试 |
| 内存使用 | <256MB 增量 | 内存 profiling |

---

## 六、风险与缓解

### 6.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| DuckDB schema 升级失败 | 数据丢失 | 低 | 备份现有表；提供回滚脚本 |
| 与现有 RuleDefinitionV2 不兼容 | 规则执行异常 | 中 | 创建兼容层；双模式过渡期 |
| YAML导入/导出格式错误 | 数据损坏 | 中 | 严格Schema验证；提供修复工具 |
| 前端组件性能问题 | 用户体验差 | 低 | 使用虚拟列表；组件懒加载 |

### 6.2 项目风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 任务依赖延迟 | 整体延期 | 中 | 关键路径优先；并行开发 |
| UX设计变更 | 返工 | 高 | 每周设计评审；原型验证 |
| 测试覆盖率不足 | 质量风险 | 中 | 测试驱动开发；强制覆盖率要求 |

### 6.3 迁移策略

**双模式并行过渡期（4周）**：

| 周次 | 模式 | 描述 |
|------|-------|------|
| W1-W2 | 旧系统为主 | 新系统只读展示，不可编辑 |
| W3 | 并行运行 | 新旧系统均可编辑，数据同步 |
| W4 | 新系统为主 | 关闭旧系统编辑，只留查看 |

- **迁移工具**：提供批量迁移CLI工具
- **回滚计划**：保留W1的完整数据快照
- **用户培训**：录制操作视频，提供文档

---

## 七、文档要求

所有实施必须同步更新以下文档：

### 7.1 设计文档更新

- `docs/STATUS.md`：标记Phase 2-A为进行中，添加验收标准
- `docs/TODO.md`：移除Phase 2-A完成的任务，添加Phase 2-B条目
- `docs/development/rule-engine.md`：扩展规则引擎设计说明

### 7.2 技术文档

- `ontology_engine/core/rule/README.md`：数据模型说明
- `api/docs/rule-groups-api.md`：API接口文档
- `frontend/docs/rule-management.md`：前端组件使用说明

### 7.3 用户文档

- `docs/user-guide/rule-orchestration.md`：用户操作指南
- `docs/user-guide/yaml-import-export.md`：YAML格式说明

---

## 八、验收标准

Phase 2-A完成后，必须具备以下能力：

### 8.1 必须完成（MVP）

- [ ] 业务人员可通过页面创建规则组（配置四元素①②③）
- [ ] 可在规则组中添加、编辑、删除规则实例
- [ ] 可通过模拟面板测试单条规则逻辑
- [ ] 可将规则组导出为Schema v2 canonical YAML
- [ ] 可从YAML文件导入规则组（格式验证通过）
- [ ] 规则修改自动触发影响分析提示

### 8.2 核心质量指标

- [ ] 后端API测试覆盖率 ≥80%
- [ ] 前端组件测试覆盖率 ≥70%
- [ ] 关键API P95延迟 <200ms
- [ ] YAML导入/导出往返一致性100%
- [ ] 无P1级缺陷（阻塞、崩溃、数据丢失）

### 8.3 用户体验

- [ ] 页面加载时间 <2秒
- [ ] 规则编辑过程无需页面跳转（模态框）
- [ ] 表单验证及时，错误提示清晰
- [ ] 操作回滚支持（Ctrl+Z）
- [ ] 响应式设计，支持桌面端

---

## 九、后续链路

Phase 2-A完成后，立即启动Phase 2-B：

| 时期 | 主题 | 重点 |
|------|------|------|
| 第8周 | Phase 2-B规划 | 要素DAG可视化详细设计 |
| 第9-12周 | Phase 2-B实施 | 指标依赖图 + 规则流转图 |
| 第13-14周 | Phase 2-C集成 | LLM_JUDGE完整 + 编排画布 |

**注意**：Phase 2-A实施期间，需指定1名架构师开始规划Phase 2-B的详细技术方案，确保无缝衔接。