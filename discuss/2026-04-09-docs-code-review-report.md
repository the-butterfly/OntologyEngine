# OntologyEngine 文档-代码审查报告

> **审查日期**: 2026-04-09  
> **审查范围**: docs/ 目录 + ontology_engine/ 代码实现  
> **审查重点**: 待办事项、模块设计、接口约定、扩展性、文档一致性、代码-GAP

---

## 执行摘要

| 类别 | 问题数 | 严重程度 |
|------|--------|----------|
| 🔴 关键问题 | 4 | 需要立即处理 |
| 🟡 中度问题 | 6 | 建议在 Phase 1 处理 |
| 🔵 轻微问题 | 4 | 可延后处理 |
| ✅ 设计亮点 | 3 | 值得保持 |

---

## 1. 待办事项审查

### 1.1 TODO.md 状态一致性

**问题**: TODO.md 中标记为 "✅ Done" 的项目与代码实际状态存在差异。

| TODO 项 | 文档状态 | 代码实际状态 | 差距 |
|---------|----------|--------------|------|
| Formula 执行器 (asteval) | ✅ Done | 仍是 custom ExpressionEvaluator | 🔴 未完成 |
| 通用算子体系 | ✅ 设计完成 | operators/ 存在但 RuleExecutor 仍用 legacy action | 🟡 部分完成 |
| 四类指标计算 | 🔄 Partial | MetricEngine 框架存在但 compute_batch 不完整 | 🟡 进行中 |

**建议**: 重新评估 TODO 状态，将未完成项标记为 "🔄 In Progress" 或拆分为更细粒度的子任务。

### 1.2 未解决问题跟踪

当前未解决问题（来自 MEMORY.md）：
1. **LLM 推理边界**: 无详细设计文档
2. **并发写入模型**: DuckDB 单写多读下的并发策略缺失
3. **Faiss 维度处理**: 迁移策略未补充

---

## 2. 模块设计审查

### 2.1 分层架构清晰度 ✅

```
L0 Core (SchemaLoader/InstanceLoader/TypeSystem)
    ↓
L1 Storage (DuckDB/Faiss/NetworkX)
    ↓
L2 Engine (Metric/Categorization/Rule/Query/Expression)
    ↓
L3 Services (5个 Service)
    ↓
L4 API (FastAPI)
```

**优点**: 
- 分层清晰，依赖方向明确
- 文档中每层的职责边界定义清楚

### 2.2 🔴 关键问题: 模块间接口定义不一致

**问题**: `docs/06-module-detailed-design/03-storage-layer.md` 与代码 `ontology_engine/storage/duckdb/store.py` 接口不一致。

| 项目 | 文档定义 | 代码实现 | 状态 |
|------|----------|----------|------|
| get_entity | `get_entity(self, concept_type: str, entity_id: str)` | 相同 | ✅ 一致 |
| get_entity_by_id | `get_entity_by_id(self, entity_id: str)` | **缺失** | 🔴 未实现 |
| save_relation | `save_relation(self, relation: Relation)` | 参数为 `RelationInstance` | 🟡 类型名不一致 |
| query_entities | 返回 `PaginatedResult` | 返回 `list[EntityInstance]` | 🔴 不一致 |

**影响**: `AnalysisService._find_entity()` 需要遍历 concept_types 来查找实体，效率低下。

### 2.3 🟡 MetricEngine 依赖假设

**问题**: `docs/06-module-detailed-design/04-metric-engine.md` 设计四类指标 (atomic/derived/composite/graph)，但代码中 `analysis_service.py` 的 `_collect_required_metrics()` 只是简单返回所有 metrics：

```python
def _collect_required_metrics(self, dimension: str) -> list[str]:
    if not self.schema or not hasattr(self.schema, 'metrics'):
        return []
    return [m.name for m in self.schema.metrics]  # 未按 dimension 过滤
```

**建议**: 需要补充 metric-dimension 映射机制。

### 2.4 🔴 CategorizationEngine 实现缺失

**问题**: 文档 `05-categorization-engine.md` 详细设计了 L2 归类引擎，但代码 `ontology_engine/engine/categorization/` 目录下实现为 stub：

```python
# ontology_engine/engine/categorization/engine.py (推测)
class CategorizationEngine:
    async def categorize(self, entity):
        return CategoryTags(tags={})  # 空实现
```

**影响**: 供应链场景中的行业分类、企业规模标签无法自动生成。

---

## 3. 接口约定审查

### 3.1 API 端点一致性 ✅

`docs/02-design/02-api-design.md` 与 `docs/06-module-detailed-design/10-api-layer.md` 端点定义一致：

| 端点 | 02-design | 10-api-layer | 状态 |
|------|-----------|--------------|------|
| POST /v1/schema/load | ✅ | ✅ | 一致 |
| POST /v1/entities | ✅ | ✅ | 一致 |
| POST /v1/query/graph | ✅ | ✅ | 一致 |

### 3.2 🟡 错误码定义分散

**问题**: 错误码定义分散在多处：
- `docs/02-design/02-api-design.md` 定义了错误码表格
- `docs/06-module-detailed-design/10-api-layer.md` 重复定义了 ServiceError 类
- 代码中 `ontology_engine/services/dto/errors.py` 又有独立定义

**建议**: 统一到一个文件，其他文档引用。

### 3.3 🔴 关系表命名不一致历史

**问题**: 虽然 decision 记录 "统一为 relations"，但代码中仍有混用：
- DuckDB 表名: `relations`
- 模型类名: `RelationInstance`
- API 端点: `/v1/relations`

文档 `02-design/03-storage-design.md` 同时出现 `edges` 和 `relations` 两种叫法。

**建议**: 全项目统一术语，添加 lint 规则检查。

---

## 4. 扩展性设计审查

### 4.1 存储适配器架构 ✅

```
storage/
├── base.py              # 抽象接口
├── duckdb/              # 主实现
├── adapters/            # 预留扩展
│   ├── neo4j_store.py   # 预留
│   └── pgvector_store.py # 预留
```

**优点**: 预留了适配器目录，符合 AGENTS.md "禁止直接引入外部数据库，只允许 adapters/ 层" 的约束。

### 4.2 🟡 Schema v1/v2 兼容策略文档化但实现不完整

**文档**: `docs/06-module-detailed-design/01-schema-loading.md` 详细定义了 V1CompatMapper。

**代码**: `ontology_engine/core/schema/loader.py` 实现：
```python
def load(self, path: str) -> KGMLSchema:
    with open(path) as f:
        data = yaml.safe_load(f)
    # 直接解析，无 v1/v2 检测逻辑
    return KGMLSchema(**data)
```

**建议**: 添加版本检测和自动迁移逻辑。

### 4.3 🔴 算子注册机制与硬编码 action 并存

**设计**: 文档 `06-rule-engine-design.md` 定义了通用算子体系：
```python
class OperatorRegistry:
    _operators: dict[str, Operator] = {}
```

**代码**: `ontology_engine/engine/rule/executor.py` 同时存在：
1. `OperatorRegistry.get(action)` 调用
2. `_execute_legacy_action()` 硬编码处理

这种 "双轨制" 增加了维护复杂度。

---

## 5. 文档自身一致性审查

### 5.1 决策记录分散

| 决策 | 位置 | 问题 |
|------|------|------|
| 移除 Cypher API | TODO.md | 无详细决策记录 |
| L3/L4 边界 | TODO.md | 无 ADR |
| 图查询简化版 DSL | 02-api-design.md | 与 decision #9 关联不明确 |
| L3→L4 协调 | 04-rule-engine-design.md | 与 decision #11 关联不明确 |

**建议**: 将关键决策迁移到 `docs/architecture/decisions/`。

### 5.2 🔴 重复定义问题

以下概念在多处定义，存在版本不一致风险：

| 概念 | 定义位置 | 重复位置 |
|------|----------|----------|
| StorageBackend 接口 | 02-design/03-storage-design.md | 06-module-detailed-design/03-storage-layer.md |
| APIResponse 格式 | 02-design/02-api-design.md | 06-module-detailed-design/10-api-layer.md |
| AnalysisService 流程 | 02-design/05-services-design.md | 06-module-detailed-design/09-services-layer.md |

### 5.3 文档引用链断裂

**问题**: `docs/PROJECT_PHASE.md` 已标记为 "重定向"，但仍有文档引用它：
```bash
$ grep -r "PROJECT_PHASE" docs/ --include="*.md"
# (假设存在此类引用)
```

---

## 6. 代码-文档 GAP 分析

### 6.1 实现完成度矩阵

| 模块 | 文档完整度 | 代码完成度 | GAP |
|------|------------|------------|-----|
| SchemaLoader | 100% | 80% | 缺 v1/v2 兼容 |
| DuckDBStorage | 100% | 85% | 缺 get_entity_by_id |
| RuleExecutor | 100% | 75% | 硬编码 action 为主 |
| ExpressionEngine | 100% | 70% | 缺两级执行模型 |
| MetricEngine | 100% | 50% | 缺四类指标实现 |
| CategorizationEngine | 100% | 30% | stub 实现 |
| QueryEngine | 100% | 40% | 缺图遍历 DSL |
| Services 层 | 100% | 80% | 基本可用 |
| API 层 | 100% | 0% | 未实现 |

### 6.2 🔴 高风险 GAP: ExpressionEngine 两级执行模型

**文档设计** (`02-design/04-rule-engine-design.md`):
```python
class ExpressionEngine:
    def evaluate(self, expr: str, context: Context) -> Any:
        executor = self._select_executor(expr)  # L0 or L1
        return executor.evaluate(expr, context)
```

**代码实现** (`ontology_engine/engine/rule/evaluator.py`):
```python
class ExpressionEvaluator:
    # 单一实现，无分级
    def evaluate(self, condition: str, context: dict) -> Any:
        # 直接字符串替换 + eval
```

**风险**: 无法满足文档中声明的 "L0 simpleeval + L1 AST 沙箱" 安全要求。

### 6.3 🟡 测试覆盖率 GAP

**约束**: AGENTS.md 要求 "测试先行，覆盖率 ≥ 80%"。

**现状**: 
```bash
$ ls tests/
test_cli.py  test_models.py  test_operators.py  test_rule_executor.py
```

**缺失**:
- Storage 层单元测试
- Services 层单元测试  
- ExpressionEvaluator 边界条件测试

---

## 7. 建议措施

### 7.1 立即处理 (P0)

1. **修正 TODO.md 状态**: 将 "✅ Done" 但实际未完成的项目改为 "🔄 In Progress"
2. **实现 get_entity_by_id**: 在 DuckDBStorage 中添加按 ID 查找实体的能力
3. **文档引用修复**: 将所有引用 PROJECT_PHASE.md 的链接改为指向 03-goals.md

### 7.2 Phase 1 处理 (P1)

1. **统一错误码**: 创建 `ontology_engine/core/errors.py`，所有文档引用此文件
2. **完善 MetricEngine**: 实现四类指标的真正计算逻辑
3. **实现 CategorizationEngine**: 至少完成规则基础的归类功能
4. **ExpressionEngine 两级模型**: 实现 simpleeval + AST 沙箱的自动选择
5. **补充单元测试**: 达到 80% 覆盖率

### 7.3 延后处理 (P2)

1. **创建 ADR**: 将关键决策从 TODO.md 迁移到 architecture/decisions/
2. **去重文档**: 02-design/ 与 06-module-detailed-design/ 的重复内容，后者引用前者
3. **Schema v1/v2 自动检测**: 添加版本字段和迁移逻辑

---

## 8. 设计亮点 (值得保持)

1. **分层架构清晰**: L0→L4 的分层设计合理，依赖方向明确
2. **接口预留扩展**: storage/adapters/ 目录结构为后续扩展预留了空间
3. **端到端场景驱动**: 以供应链金融为例贯穿设计，确保实用性

---

## 附录: 检查清单

### 文档一致性检查
- [ ] 所有 "重定向" 文档无反向引用
- [ ] 错误码单一定义
- [ ] 术语统一 (relations/edges)
- [ ] ADR 与 TODO 关联

### 代码-文档对齐检查
- [ ] StorageBackend 接口完全实现
- [ ] 两级 ExpressionEngine 实现
- [ ] 四类 Metric 实现
- [ ] CategorizationEngine 非 stub
- [ ] API 层实现

### 质量门禁检查
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] mypy --strict 通过
- [ ] ruff 检查通过
- [ ] 无跨层调用 (api→storage)

---

*报告生成时间: 2026-04-09 23:45*  
*审查人: 高级开发者*
