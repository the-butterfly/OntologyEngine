# OntologyEngine Examples 改造详细计划

> 状态：计划中  
> 来源：基于 `examples/` 现状分析报告的改进方案  
> 关键决策确认日期：2026-04-14

## 一、背景与目标

### 1.1 背景
`examples/` 目录下的两个案例（`supply_chain_finance/` 与 `consumer_credit/`）是 OntologyEngine Schema v2 的核心验收场。当前存在以下阻塞性问题：
- **Demo 与实例数据 ID 不一致**：`supply_chain_finance/demo.py` 引用的实体 ID 与 `instances.yaml` 中实际定义的数据不匹配，导致 Demo 无法直接运行。
- **数据完整性缺陷**：`consumer_credit/instances.yaml` 中还款记录数据量与测试用例断言不符。
- **Schema 语法漂移**：YAML 中混用 Python f-string、原生 `if-else` 块、以及 `$metric:` 引用，增加跨语言移植难度。
- **引擎层未对齐**：`composite` 指标存在 `components` 与 `dependencies` 重复声明；图指标的 `algorithm` 字段为字符串，缺少结构化参数能力。

### 1.2 目标
- **P0**：修复数据与 ID 对齐问题，使 `demo.py` 与全部 `testcases.yaml` 可一键运行。
- **P1**：完成 Schema 语法标准化（去除 f-string、composite 依赖自动推导、表达式沙箱增强）。
- **P2**：图指标 `algorithm` 结构化增强，并同步改造引擎层的 `SchemaLoader` 与 `MetricEngine`。

---

## 二、关键决策摘要（已确认）

| 议题 | 已确认方案 | 影响范围 |
|------|-----------|---------|
| 表达式标准化 | **中等改造**：去除 f-string + 引入 `simpleeval` 沙箱限制 | `schema.yaml` + `ExpressionEngine` |
| Demo 案例数量 | **补充数据**：保留 10 个案例，在 `instances.yaml` 中新增缺失的 7 个实体数据 | `instances.yaml` + `demo.py` + `testcases.yaml` |
| composite 依赖去重 | **方案 A**：删除 `composite.dependencies`，由引擎自动从 `components` 推导 | `schema.yaml` + `SchemaLoader` |
| 图指标 algorithm | **结构化对象**：`algorithm` 从 `str` 改为 `{name, params}`，引擎层新增解析与执行能力 | `schema.yaml` + `SchemaLoader` + `MetricEngine` |

---

## 三、P0：数据完整性与 ID 对齐

### 任务 3.1：供应链金融 instances.yaml 数据补全

**目标**：补全 Demo 所需的 10 个案例的完整事实数据，建立统一的 ID 命名规范。

**ID 映射规范**：

| Demo 旧 ID | 新统一 ID | 场景定位 | 数据状态 |
|-----------|----------|---------|---------|
| `SUP_2024_001` | `SUP_A` | 优质供应商（制造业） | ✅ 已存在 |
| `SUP_2024_003` | `SUP_B` | 高风险贸易公司 | ✅ 已存在 |
| `SUP_2024_A` | `SUP_C_A` | 担保圈供应商 A | ✅ 已存在 |
| `SUP_2024_NEW` | `SUP_D_NEW` | 新供应商（成立<1年） | ❌ 需新增 |
| `SUP_2024_NEG` | `SUP_E_NEG` | 负面舆情供应商 | ❌ 需新增 |
| `SUP_2024_EXC` | `SUP_F_EXC` | 优秀供应商（完美记录） | ❌ 需新增 |
| `SUP_2024_MULTI` | `SUP_G_MULTI` | 多核心企业供应商 | ❌ 需新增 |
| `SUP_2024_TRADE` | `SUP_H_TRADE` | 小型贸易商 | ❌ 需新增 |
| `SUP_2024_MFG` | `SUP_I_MFG` | 大型制造（主力） | ❌ 需新增 |
| `SUP_2024_PARTIAL` | `SUP_J_PARTIAL` | 部分担保背书 | ❌ 需新增 |

**新增数据设计原则**：
- 每个新实体必须包含：基础属性（`supplier_id`, `company_name`, `unified_credit_code`, `registered_capital`, `establishment_date`, `industry_type`, `status`）+ 外部原子指标（`tax_compliance_score`, `negative_news_count_90d`）+ 关联事实（`Invoice`, `Contract`, `GuaranteeRelation`）。
- `unified_credit_code` 使用虚拟但符合 `^[A-Z0-9]{18}$` 格式的字符串。
- 发票和合同数据需与 Demo 中打印的 `credit_score`、`credit_grade` 预期输出逻辑自洽。

**涉及文件**：
- `examples/supply_chain_finance/instances.yaml`
- `examples/supply_chain_finance/testcases.yaml`（新增对应验收用例）
- `examples/supply_chain_finance/demo.py`（替换 ID）

**引擎层配合**：无。

**验收标准**：
- `python -m examples.supply_chain_finance.demo` 运行成功，无 `EntityNotFound`。
- `query_service.run_testcases()` 对新旧案例全部通过。

---

### 任务 3.2：个人消费信贷 instances.yaml 还款记录补全

**目标**：补充 `BRW_P` 和 `BRW_M` 的完整还款记录，使 graph_traversal 指标的计算结果与 `testcases.yaml` 的断言一致。

**具体修改**：
- `BRW_P`：补充 22 条还款记录，覆盖 `2024-04` 至 `2026-03` 的 24 个月周期，`days_overdue=0`。
- `BRW_M`：补充 22 条还款记录，其中 1 条 `days_overdue=7`（已存在），其余 23 条 `days_overdue=0`。

**涉及文件**：
- `examples/consumer_credit/instances.yaml`

**验收标准**：
- `pytest` 执行 `TC-C01` 时，`repayment_on_time_count=24`、`total_repayment_count=24`、`repayment_rate_24m=1.0` 由引擎实际计算得出，不再依赖“注释断言”。
- `TC-C03` 中 `repayment_rate_24m=0.958`（23/24）由实际数据计算。

---

## 四、P1：Schema 语法标准化与引擎层配合

### 任务 4.1：去除 f-string 与 message 模板化

**目标**：将所有 `rule_logics` 中 `output.message` 里的 Python f-string 语法（如 `{co_borrower_risk_count}`）替换为纯字符串模板，由引擎在渲染阶段做变量替换。

**改造示例**：

```yaml
# 修改前（consumer_credit/schema.yaml）
message: "关联共借人/担保人中存在{co_borrower_risk_count}人当前逾期..."

# 修改后
message_template: "关联共借人/担保人中存在 {co_borrower_risk_count} 人当前逾期，风险评分 {network_risk_score}，建议人工核查关系网络"
```

同理改造 `supply_chain_finance/schema.yaml` 中所有含 `{}` 插值的 `message` 字段。

**涉及文件**：
- `examples/consumer_credit/schema.yaml`
- `examples/supply_chain_finance/schema.yaml`

**引擎层配合**：
- `ontology_engine/core/schema/models.py`：`RuleAction` 和 `RuleStep` 新增可选字段 `message_template: str | None`。
- `ontology_engine/engine/rule/operators/alert.py` 或其他渲染层：在执行 alert 动作时，若检测到 `message_template`，使用上下文做 `str.format(**context)` 渲染，回退到原 `message` 字段。
- `ontology_engine/engine/expression/engine.py`：`ExpressionEngine._resolve_fields` 需确保不对 `message_template` 内容进行字段预解析（因为模板渲染发生在规则执行阶段，而非表达式求值阶段）。

**验收标准**：
- `grep -r 'message:.*{' examples/*/schema.yaml` 不再命中任何 f-string 语法。
- 运行 `TC-C05`（网络风险预警）时，alert 消息正确渲染出 `1人当前逾期`。

---

### 任务 4.2：表达式引擎沙箱增强

**目标**：在现有 `ExpressionEngine`（基于 `simpleeval`）基础上，增加安全限制与函数扩展。

**当前状态**：`ExpressionEngine` 已经使用 `simpleeval`，但缺少以下能力：
- 不支持 `days_since`（schema 中大量使用）。
- 不支持多行 `if-elif-else` Python 语句块（simpleeval 只支持单行表达式）。
- 没有显式禁用 `__import__` 等危险操作的黑名单。

**改造方案**：

1. **扩展函数注册表**
   在 `ExpressionEngine.__init__` 中注册：
   - `days_since(date_str) -> int`：`days_between(date_str, today())` 的别名。
   - `clamp(value, min_val, max_val) -> float`

2. **多行公式预处理**
   对于 `derived` / `composite` 指标中的多行 Python 块（如 `score = 50; if ...: ...`），在 `ExpressionEngine.evaluate` 中增加一个 **Mini-Transformer**：
   - 若表达式包含换行符，先尝试用正则将其转换为 `simpleeval` 可接受的单行形式，或回退到安全的 `asteval` 解释器。
   - **建议落地方式**：引入 `asteval` 库（MIT 许可）作为多行表达式的安全回退执行器。`asteval` 基于 AST 白名单，默认禁止 `import`、`class`、`def`、`lambda` 等危险节点。

3. **安全加固**
   - 在 `simpleeval` 中清空 `operators` 中的位运算（`<<`, `>>`, `&`, `|`, `^`）和字符串格式化（`%`），防止侧信道攻击。
   - 在 `asteval` 中设置 `max_time=1.0`（若支持）或限制循环次数。

**涉及文件**：
- `ontology_engine/engine/expression/engine.py`
- `pyproject.toml`（新增 `asteval` 依赖）

**验收标准**：
- `pytest tests/unit/engine/expression/` 通过新增的安全测试用例（如尝试 `__import__('os')` 应抛出异常）。
- `TC-01` 中的 `days_since(establishment_date) >= 365` 在 `simpleeval` 或 `asteval` 沙箱中正确求值。
- 多行公式（如 `business_stability_score` 的计算块）在沙箱中正确求值。

---

### 任务 4.3：composite 指标 dependencies 自动推导（方案 A）

**目标**：删除 `schema.yaml` 中所有 `type: composite` 指标的 `dependencies` 字段，由 `SchemaLoader` 在加载时自动从 `components[].metric` 推导。

**涉及文件（Schema 侧）**：
- `examples/consumer_credit/schema.yaml`
- `examples/supply_chain_finance/schema.yaml`

**引擎层配合**：
- `ontology_engine/core/schema/loader.py`：在 `_parse_analytical_elements` 中，解析 `MetricDefinitionV2` 后，若 `type == "composite"` 且未显式提供 `dependencies`，则自动填充为 `components` 中所有 `metric` 的集合。
- `ontology_engine/core/schema/models.py`：`MetricDefinitionV2` 的 `dependencies` 字段保持可选（`default_factory=list`），但增加 `@model_validator` 校验：当 `type == "composite"` 且 `components` 非空时，若 `dependencies` 非空，则必须严格等于 `components` 中的 metric ID 集合；否则自动推导并覆盖。
- `ontology_engine/engine/metric/dag.py`：确认 `MetricDAG` 的依赖解析逻辑使用 `metric.dependencies`，无需额外修改。

**验收标准**：
- `grep -B2 'type: composite' examples/*/schema.yaml | grep 'dependencies:'` 不再命中任何结果（即 composite 指标不再显式声明 dependencies）。
- `SchemaLoader.load()` 加载两个 schema 后，所有 composite 指标的 `dependencies` 非空且与 `components` 一致。
- 现有 testcases 全部通过，DAG 拓扑排序无异常。

---

## 五、P2：图指标 algorithm 结构化与引擎层配合

### 任务 5.1：Schema 语法升级

**目标**：将 `graph` 类型指标的 `algorithm` 从字符串改为结构化对象。

**改造示例**：

```yaml
# 修改前（supply_chain_finance/schema.yaml）
- id: guarantee_chain_depth
  type: graph
  algorithm: longest_path
  traversal:
    entity: Supplier
    edge: GuaranteeRelation
    direction: both
    max_hops: 10

# 修改后
- id: guarantee_chain_depth
  type: graph
  algorithm:
    name: longest_path
    params:
      direction: both
      weighted: false
      allow_revisit: false
      max_hops: 10
  traversal:
    entity: Supplier
    edge: GuaranteeRelation
    direction: both
    max_hops: 10
```

同理改造所有 `graph` 指标：
- `supply_chain_finance`：`guarantee_chain_depth`、`has_guarantee_cycle`
- `consumer_credit`：`co_borrower_risk_count`、`network_risk_score`

**涉及文件**：
- `examples/supply_chain_finance/schema.yaml`
- `examples/consumer_credit/schema.yaml`

---

### 任务 5.2：引擎模型与加载层改造

**引擎层配合**：

1. **新增模型**：`ontology_engine/core/schema/models.py`
   新增 `GraphAlgorithmDefinition`：
   ```python
   class GraphAlgorithmDefinition(BaseModel):
       name: str
       params: dict[str, Any] = Field(default_factory=dict)
   ```

2. **修改 `MetricDefinitionV2`**：
   ```python
   algorithm: GraphAlgorithmDefinition | str | None = None
   ```
   增加 `@model_validator` 向后兼容：若传入字符串，自动包装为 `GraphAlgorithmDefinition(name=原字符串)`。

3. **修改 `SchemaLoader`**：`ontology_engine/core/schema/loader.py`
   在 `_parse_analytical_elements` 中，解析 `algorithm` 字段时：
   - 若值为字符串，构造 `GraphAlgorithmDefinition(name=value)`。
   - 若值为字典，构造 `GraphAlgorithmDefinition(name=value[       name=value["name"], params=value.get("params", {}))`。

4. **修改 `MetricEngine`**：`ontology_engine/engine/metric/engine.py`
   - `_compute_graph` 方法不再直接 `if algorithm == "longest_path"`，而是读取 `algorithm.name` 和 `algorithm.params`。
   - 将现有的硬编码图算法逻辑（`longest_path`、`cycle_detection`、`page_rank`、`betweenness`）抽取到独立的图算子函数或类中。
   - 新增 `GraphOperatorRegistry`（可放在 `ontology_engine/engine/metric/graph_operators.py`）：
     ```python
     class GraphOperatorRegistry:
         _operators: dict[str, Callable] = {}
         
         @classmethod
         def register(cls, name: str, func: Callable):
             cls._operators[name] = func
             
         @classmethod
         def execute(cls, name: str, entity, storage, params: dict, traversal: dict):
             op = cls._operators.get(name)
             if not op:
                 raise MetricError(f"Unknown graph algorithm: {name}")
             return op(entity, storage, params, traversal)
     ```
   - 现有的 `longest_path` 和 `cycle_detection` 逻辑包装为注册函数：
     ```python
     @GraphOperatorRegistry.register("longest_path")
     async def _op_longest_path(entity, storage, params, traversal):
         max_hops = params.get("max_hops", traversal.get("max_hops", 10))
         direction = params.get("direction", traversal.get("direction", "both"))
         # ... 复用现有 BFS 逻辑
     ```

**涉及文件**：
- `ontology_engine/core/schema/models.py`
- `ontology_engine/core/schema/loader.py`
- `ontology_engine/engine/metric/engine.py`
- `ontology_engine/engine/metric/graph_operators.py`（新增）

**验收标准**：
- `SchemaLoader.load()` 成功加载改造后的两个 `schema.yaml`，`algorithm` 字段解析为 `GraphAlgorithmDefinition` 对象。
- `MetricEngine.compute("guarantee_chain_depth", ...)` 和 `compute("has_guarantee_cycle", ...)` 在结构化 `algorithm` 配置下返回正确结果。
- 旧版字符串形式的 `algorithm`（如外部用户的 schema）仍能通过向后兼容包装正常加载。

---

### 任务 5.3：消费信贷图指标算法结构化适配

**目标**：将 `consumer_credit/schema.yaml` 中的图指标同步改造为结构化 `algorithm`，并在引擎层支持 `neighbor_attribute_count` 算法的参数化。

**改造示例**：

```yaml
# 修改前
- id: co_borrower_risk_count
  type: graph
  algorithm: neighbor_attribute_count
  traversal:
    entity: Borrower
    edge: BorrowerRelation
    direction: both
    max_hops: 2

# 修改后
- id: co_borrower_risk_count
  type: graph
  algorithm:
    name: neighbor_attribute_count
    params:
      direction: both
      max_hops: 2
      deduplicate_neighbors: true
  traversal:
    entity: Borrower
    edge: BorrowerRelation
    direction: both
    max_hops: 2
```

**引擎层配合**：
- 在 `graph_operators.py` 中实现 `neighbor_attribute_count` 算子：
  - 根据 `traversal.edge` 和 `params.direction` / `params.max_hops` 获取邻居集合。
  - 应用 `metric.neighbor_filter`（已存在字段）过滤邻居。
  - 若 `params.deduplicate_neighbors` 为 `true`，在多跳遍历中去重。
  - 返回满足条件的邻居数量。

**验收标准**：
- `TC-C05` 中 `co_borrower_risk_count=1` 由结构化算法配置正确计算。
- `network_risk_score=20`（`1 * 20`）正确输出。

---

## 六、测试与验收总览

### 6.1 新增/修改的测试文件

| 测试文件 | 测试目标 |
|---------|---------|
| `tests/unit/engine/expression/test_expression_engine.py` | `days_since`、`clamp`、asteval 多行公式、安全黑名单 |
| `tests/unit/core/schema/test_schema_loader.py` | composite 依赖自动推导、algorithm 结构化解析、向后兼容 |
| `tests/unit/engine/metric/test_graph_operators.py` | `longest_path`、`cycle_detection`、`neighbor_attribute_count` 结构化参数执行 |
| `tests/integration/examples/test_supply_chain_finance.py` | Demo 可运行、testcases 全通过 |
| `tests/integration/examples/test_consumer_credit.py` | Demo 可运行、testcases 全通过 |

### 6.2 质量门禁

实施完成后必须执行：
```bash
mypy ontology_engine/ --strict
ruff check ontology_engine/
pytest tests/unit/ -v --cov=ontology_engine --cov-report=term-missing
```

---

## 七、实施顺序与里程碑

### 阶段 1：P0 修复（预计 1-2 天）
1. 补全 `consumer_credit/instances.yaml` 还款记录。
2. 补全 `supply_chain_finance/instances.yaml` 缺失的 7 个案例数据。
3. 修改 `supply_chain_finance/demo.py` 统一实体 ID。
4. 运行 `demo.py` 和 `testcases.yaml` 验证 P0 通过。

### 阶段 2：P1 Schema 标准化（预计 2-3 天）
1. 改造两个 `schema.yaml`：去除 f-string、`message` 改 `message_template`。
2. 引擎层：`RuleAction` / `RuleStep` 模型新增 `message_template`，alert 渲染层适配。
3. 表达式引擎沙箱增强：`days_since`、`asteval` 引入、安全加固。
4. 删除 composite 的 `dependencies`，引擎层自动推导逻辑 + 校验。
5. 跑通全部 unit / integration 测试。

### 阶段 3：P2 图指标结构化（预计 3-4 天）
1. 新增 `GraphAlgorithmDefinition` 模型，`SchemaLoader` 解析适配。
2. 改造两个 `schema.yaml` 的 graph 指标 `algorithm` 为结构化对象。
3. 抽取 `MetricEngine._compute_graph` 硬编码逻辑到 `graph_operators.py`。
4. 实现 `neighbor_attribute_count` 参数化算子（支持 `deduplicate_neighbors`）。
5. 新增 graph operator 单元测试，跑通全部 testcases。

---

## 八、风险与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| `asteval` 对复杂 Python 语法（如 f-string、walrus 运算符）支持不完整 | P1 表达式改造 | 在 `ExpressionEngine` 中增加前置过滤器，将不支持的语法转换为 `asteval` 可接受形式；若无法转换则抛出清晰的 `ExpressionSyntaxError` |
| `supply_chain_finance` 新增 7 个案例的数据设计工作量大 | P0 进度延迟 | 优先保证 Demo 可运行的最小数据集（3-4 个核心案例），其余案例可分批补充 |
| 图指标 `algorithm` 结构化改造涉及 `MetricEngine` 核心计算路径 | P2 可能引入回归缺陷 | 为所有现有 graph 指标（包括 canonical spec 中定义的）增加完整的单元测试，确保改造前后输出一致 |
| `message_template` 的变量替换与现有 `ExpressionEngine._resolve_fields` 冲突 | P1 | 明确区分两类字段：`message_template` 不走 `_resolve_fields`，仅在规则执行后的 alert 构造阶段做 `str.format(**context)` |

---

## 九、产出物清单

完成全部改造后，预期变更的文件清单：

**Schema / Example 文件**：
- `examples/consumer_credit/instances.yaml`
- `examples/consumer_credit/schema.yaml`
- `examples/consumer_credit/testcases.yaml`（若新增案例则修改）
- `examples/supply_chain_finance/instances.yaml`
- `examples/supply_chain_finance/schema.yaml`
- `examples/supply_chain_finance/testcases.yaml`
- `examples/supply_chain_finance/demo.py`

**引擎层文件**：
- `ontology_engine/core/schema/models.py`
- `ontology_engine/core/schema/loader.py`
- `ontology_engine/engine/expression/engine.py`
- `ontology_engine/engine/metric/engine.py`
- `ontology_engine/engine/metric/graph_operators.py`（新增）
- `ontology_engine/engine/rule/operators/alert.py`

**项目配置**：
- `pyproject.toml`（新增 `asteval` 依赖）

**测试文件**：
- `tests/unit/engine/expression/test_expression_engine.py`
- `tests/unit/core/schema/test_schema_loader.py`
- `tests/unit/engine/metric/test_graph_operators.py`
- `tests/integration/examples/test_supply_chain_finance.py`
- `tests/integration/examples/test_consumer_credit.py`

---

**结论**：本计划从 `examples/` 的阻塞性问题出发，逐层延伸到 Schema 语法标准化和引擎层架构改造。建议按 **P0 → P1 → P2** 的顺序分阶段实施，每阶段完成后执行完整的 unit + integration 测试，确保改造可控、风险可收敛。
