# OntologyEngine 类分析报告

**日期**: 2026-04-09
**分析对象**: `ontology_engine/__init__.py` 中的 `OntologyEngine` 类

---

## 1. 类架构总览

```
OntologyEngine
├── schema: KGMLSchema (SchemaLoader 加载)
├── storage: DuckDBStorage (DuckDB 内存数据库)
└── rule_executor: RuleExecutor (规则执行器)
```

### 核心流程

```
Schema.yaml → SchemaLoader → KGMLSchema
                                 ↓
                              RuleExecutor
                                 ↓
instances.yaml → InstanceLoader → entities/relations
                                           ↓
                              DuckDBStorage (持久化)
                                           ↓
                              OntologyEngine.analyze()
                                           ↓
                                    AnalysisResult
```

---

## 2. 核心方法分析

### 2.1 `from_config()` - 工厂方法

```python
@classmethod
def from_config(cls, schema_path: str) -> "OntologyEngine"
```

**功能**: 从 Schema 配置文件创建引擎实例

**流程**:
1. `SchemaLoader.load()` → 加载并解析 KGML Schema
2. `loader.validate()` → 验证 Schema 合法性
3. `DuckDBStorage(":memory:")` → 创建内存数据库
4. `RuleExecutor(schema)` → 创建规则执行器

**优点**:
- ✅ 一行代码初始化完整引擎
- ✅ Schema 验证 + 警告机制
- ✅ 依赖注入，便于测试

**问题**:
- ⚠️ `:memory:` 数据库意味着每次重启数据丢失
- ⚠️ 没有提供持久化存储的配置选项

---

### 2.2 `initialize()` - 异步初始化

```python
async def initialize(self) -> None
```

**功能**: 初始化存储层

**问题**:
- ⚠️ Demo 中没有调用此方法
- ⚠️ 可能导致异步操作失败

---

### 2.3 `load_instances()` - 实例加载

```python
async def load_instances(self, instances_path: str) -> None
```

**功能**: 从 YAML 加载实体和关系数据

**流程**:
```
instances.yaml
     ↓
InstanceLoader.load()
     ↓
entities[] → storage.save_entity()
relations[] → storage.save_relation()
```

**问题**:
- ⚠️ 没有批量插入优化
- ⚠️ 没有事务保护
- ⚠️ 错误处理不完善（一个失败全部回滚？）

---

### 2.4 `analyze()` - 核心分析入口

```python
async def analyze(
    self,
    entity_id: str,
    dimension: str,
    concept: str = "Supplier"
) -> AnalysisResult
```

**流程图**:

```
analyze(entity_id, dimension)
        ↓
   get_entity() ──不存在?──→ return AnalysisResult(error)
        ↓ 存在
   _compute_entity_metrics()
        ↓
   rule_executor.execute_dimension()
        ↓
   return AnalysisResult
```

**设计亮点**:
- ✅ 清晰的关注点分离
- ✅ 支持不同 Concept 类型
- ✅ 错误情况优雅返回

---

### 2.5 `_compute_entity_metrics()` - 指标计算

**功能**: 计算实体的派生指标

#### Supplier 指标计算逻辑:

| 指标 | 计算方式 | 来源 |
|------|----------|------|
| `total_invoice_amount_90d` | SUM(amount) where issue_date >= 90天前 | Invoice 关系 |
| `invoice_count_90d` | COUNT(issue_date >= 90天前) | Invoice 关系 |
| `overdue_invoice_amount` | SUM(amount) where status == "OVERDUE" | Invoice 关系 |
| `overdue_invoice_ratio` | overdue / total * 100 | 计算派生 |
| `total_contract_amount` | SUM(contract_amount) | Contract 关系 |
| `guarantee_chain_depth` | 图遍历担保链深度 | guaranteed_by 关系 |
| `has_guarantee_circle` | depth >= 3 | 启发式规则 |

**亮点**:
- ✅ 90天滚动窗口计算
- ✅ 基于关系链的图遍历
- ✅ 担保圈检测（循环检测）

**问题**:
- ⚠️ 硬编码 90 天常量
- ⚠️ `has_guarantee_circle` 阈值 3 是 magic number
- ⚠️ 图遍历没有深度限制说明
- ⚠️ 只支持 Supplier 概念

---

## 3. RuleExecutor 执行模型

### 3.1 执行流程

```python
execute_dimension(dimension, entity_id, entity_data)
        ↓
   创建 ExecutionContext
        ↓
   获取 dimension 对应的规则
        ↓
   按 priority 降序排序
        ↓
   遍历执行每个规则
        ↓
   根据结果生成 decision
```

### 3.2 规则执行

```python
execute_rule(rule, context)
        ↓
   检查 when 条件
        ↓ 条件满足
   执行 then.action
        ↓ then.computation?
   计算 formula 表达式
        ↓
   通过 OperatorRegistry 执行 action
        ↓
   返回 RuleResult
```

### 3.3 OperatorRegistry 算子体系

| 算子 | 用途 |
|------|------|
| `set_flag` | 设置实体标志 |
| `approve_eligibility` | 批准准入 |
| `reject_eligibility` | 拒绝准入 |
| `trigger_alert` | 触发预警 |
| `compute_formula` | 公式计算 |
| `calculate_credit_score` | 计算信用分 |
| `calculate_credit_limit` | 计算授信额度 |
| `determine_interest_rate` | 确定利率 |
| `graph_traversal` | 图遍历聚合 |
| `switch` | 多分支选择 |
| `binning` | 分箱离散化 |
| `scorecard` | 计分卡计算 |

---

## 4. 与 Demo 的对比分析

### Demo (`mvp_demo.py`) vs OntologyEngine

| 维度 | Demo | OntologyEngine |
|------|------|----------------|
| 指标计算 | 硬编码 Python | Schema 驱动 |
| 规则执行 | 硬编码 if-else | KGML DSL |
| 数据加载 | 内存对象 | DuckDB Storage |
| 图遍历 | 单跳属性 | 多跳遍历算子 |
| 预警机制 | 内置函数调用 | Alert 算子 |

### 关键差异

**Demo 的优势**:
1. 代码直观，易于调试
2. 逻辑清晰，可单步执行
3. 无额外依赖

**OntologyEngine 的优势**:
1. Schema 可配置，无需改代码
2. 支持复杂图遍历
3. 可持久化存储
4. 算子可复用

**OntologyEngine 的问题**:
1. 过度设计（对于简单场景）
2. 性能开销（异步 I/O + DSL 解析）
3. 调试困难（隐藏的执行流程）

---

## 5. 问题汇总

### P0 - Critical

1. **Demo 未使用 OntologyEngine**
   - `mvp_demo.py` 定义了自己的 `MetricEngine` 和 `RuleEngine`
   - 没有导入或使用 `OntologyEngine`

### P1 - High

2. **异步方法未被调用**
   - `initialize()` 和 `load_instances()` 在 Demo 中未调用
   - 可能导致数据未正确初始化

3. **内存数据库**
   - `:memory:` 数据库无法持久化
   - 每次重启数据丢失

### P2 - Medium

4. **Magic Numbers**
   - 90 天窗口期硬编码
   - 担保圈阈值 3 硬编码

5. **错误处理不完善**
   - `get_entity` 返回 None 时的处理过于简单
   - 图遍历中的异常未捕获

6. **只支持 Supplier 概念**
   - `_compute_entity_metrics` 只处理 Supplier
   - 扩展性差

---

## 6. 改进建议

### 6.1 短期 (P1)

```python
# 1. 修改 Demo 使用 OntologyEngine
from ontology_engine import OntologyEngine

async def main():
    engine = OntologyEngine.from_config("schema.yaml")
    await engine.initialize()
    await engine.load_instances("instances.yaml")

    result = await engine.analyze(
        entity_id="SUP_2024_001",
        dimension="credit_assessment"
    )
    print(result)
```

### 6.2 中期 (P2)

```python
# 1. 配置化常量
GUARANTEE_CIRCLE_THRESHOLD = 3  # 从 Schema 读取
INVOICE_WINDOW_DAYS = 90        # 从 Schema 读取

# 2. 扩展指标计算
def compute_metrics(entity: dict, concept: str) -> dict:
    COMPUTE_STRATEGIES = {
        "Supplier": compute_supplier_metrics,
        "Enterprise": compute_enterprise_metrics,
        "Invoice": compute_invoice_metrics,
    }
    return COMPUTE_STRATEGIES.get(concept, compute_default_metrics)(entity)
```

### 6.3 长期 (P3)

1. 实现 Schema 驱动的完整工作流
2. 添加性能监控
3. 实现缓存层
4. 支持插件化算子

---

## 7. 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        OntologyEngine                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │   KGMLSchema  │  │ DuckDBStorage│  │   RuleExecutor   │      │
│  │              │  │              │  │                  │      │
│  │ - metadata   │  │ - entities   │  │ - OperatorReg   │      │
│  │ - types      │  │ - relations   │  │ - execute_rule   │      │
│  │ - rules      │  │ - query()     │  │ - execute_dim    │      │
│  │ - metrics    │  │ - save()      │  │                  │      │
│  └──────────────┘  └──────────────┘  └──────────────────┘      │
│          ↑                 ↑                    ↑              │
│          │                 │                    │              │
│  SchemaLoader         InstanceLoader     OperatorRegistry      │
│          │                 │                    │              │
│  ┌───────┴─────────────────┴────────────────────┴────────┐     │
│  │                    operators/                          │     │
│  │  compute_formula | trigger_alert | calculate_*       │     │
│  │  set_flag | graph_traversal | switch | binning       │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. 总结

**OntologyEngine** 是一个设计良好的知识推理引擎核心类，具有：

✅ **优点**:
- 清晰的关注点分离
- Schema 驱动的灵活性
- 完善的算子体系
- 异步 I/O 支持

⚠️ **待改进**:
- Demo 未使用（核心问题）
- 配置化不足（magic numbers）
- 错误处理需加强
- 文档需补充

**下一步**: 重构 `mvp_demo.py` 使用 `OntologyEngine`，实现真正的 Schema 驱动执行。
