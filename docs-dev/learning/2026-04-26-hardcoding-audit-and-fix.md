# 硬编码实体类型/属性问题排查与修复经验

> **日期**: 2026-04-26
> **模块**: ontology_engine 全模块
> **场景**: `__init__.py` 的 `_compute_supplier_metrics_legacy` 函数暴露出全代码库系统性硬编码问题
> **严重度**: CRITICAL — 直接阻断非供应链金融领域的新 case 接入

---

## 1. 问题全景

### 1.1 审计数据

| 严重度 | 数量 | 含义 |
|--------|------|------|
| CRITICAL | 30 | 硬编码了 Supplier/Invoice/Contract 等实体类型名，非供应链场景必定报错或静默返回空 |
| HIGH | 56 | 硬编码了关系名或 ID 字段名，新增领域必须改源码 |
| MEDIUM | 65 | 硬编码了指标名或维度名，扩展性受限 |
| LOW | 30 | 文档注释中的示例值，不影响功能 |

**涉及文件**: 28 个 Python 文件，181 处硬编码匹配

### 1.2 硬编码分布热力图

```
__init__.py              ██████████████████████████████  30 (8 CRITICAL)
engine/metric/engine.py  ██████████████████              18 (5 CRITICAL)
core/instances/loader.py ████████████████                16 (10 HIGH)
engine/rule/executor.py  ████████                         8
engine/rule/operators/   ███████                          7
engine/metric/graph_ops  ██████                           6 (4 CRITICAL)
services/analysis_svc    █████                            5
api/routes/query.py      ███                              3 (3 CRITICAL)
services/query_svc       █                                1 (1 CRITICAL)
services/entity_svc      █                                1 (1 CRITICAL)
```

---

## 2. 四大根因模式

### 根因模式 A: 领域锁定函数（Domain-Locked Function）

**典型代码**:

```python
# __init__.py — 135 行 Supplier 域锁定函数
async def _compute_supplier_metrics_legacy(self, entity, entity_id):
    invoices = await self.storage.get_neighbors(entity_id, "has_invoice", "outgoing")
    contracts = await self.storage.get_neighbors(entity_id, "has_contract", "outgoing")
    enterprises = await self.storage.get_neighbors(entity_id, "supplies_to", "outgoing")
    # ... 8 个硬编码字符串
```

**特征**:
- 函数名包含具体领域名（`supplier`, `invoice`）
- 关系名、实体类型名直接写在函数体内
- 调用入口用 `if concept == "Supplier"` 守卫

**为什么危险**:
- 新增 Store/MonthlySales 等实体 → 走不到这个函数 → 指标全部为空
- 修改关系名（如 `has_invoice` → `issues_invoice`）→ 需要全文搜索替换

**修复策略**:
- 删除整个 legacy 函数
- 改为 schema 声明驱动：从 `MetricDeclaration.source.traversal` 获取关系名和聚合方式
- 保留 v1 兼容路径：`_compute_atomic_by_convention()` 从 schema 关系声明推断

---

### 根因模式 B: 三重实现（Triple Implementation）

**典型代码**:

```
__init__.py::_compute_supplier_metrics_legacy()  → 遍历 "guaranteed_by" / "supplier_id"
engine/metric/engine.py::_compute_guarantee_chain_depth() → 同样的遍历逻辑
engine/metric/graph_operators.py::_op_guarantee_chain_depth() → 又一次
```

**特征**:
- 同一业务逻辑在 3 个文件中各实现一次
- 每次都硬编码相同的字符串
- 修一个 bug 要改三处

**为什么危险**:
- 行为不一致风险：三处实现可能产生不同结果
- 维护成本 3x

**修复策略**:
- 统一到 `graph_operators.py` 的 `_op_longest_path()`
- 参数化：`chain_field`, `id_field`, `concept`, `edge`, `max_hops` 全部从 traversal/params 获取
- `engine.py` 和 `__init__.py` 调用算子注册表，不再自己实现遍历

---

### 根因模式 C: Schema 信息未下沉（Schema Declaration Ignored）

**典型代码**:

```python
# loader.py — 13 条硬编码映射
id_fields = {
    "Supplier": "supplier_id",
    "CoreEnterprise": "enterprise_id",
    "Invoice": "invoice_no",
    "Contract": "contract_no",
    "Store": "store_id",
    "MonthlySales": "record_id",
    # ...
}
```

而 schema.yaml 中已经声明了：

```yaml
fact_objects:
  - name: Supplier
    attributes:
      - name: supplier_id
        type: string
        required: true
        unique: true     # ← 这就是 ID 字段声明！
```

**特征**:
- Schema 已经声明了 `unique: true` 的属性，但代码不读取
- 代码中维护了一份与 schema 平行的硬编码映射
- 新增实体类型时，schema 加了但代码忘了加 → ID 检测失败

**修复策略**:
- 在 `KGMLSchema` 上新增 `get_entity_id_field(concept_name)` 方法
- 优先读取 schema 声明（`unique=True` + `required=True`）
- 约定推断作为 fallback（`{concept_lower}_id` / `{concept_lower}_no`）
- 删除所有硬编码映射表

---

### 根因模式 D: 默认值污染（Default Value Pollution）

**典型代码**:

```python
# api/routes/query.py
class TraverseRequest(BaseModel):
    relation_name: str = "has_invoice"   # ← 非供应链场景无法使用

# services/entity_service.py
rn = rn or "has_invoice"                # ← 同上

# services/query_service.py
neighbors = await self.storage.get_neighbors(
    entity_id=current,
    relation_name="has_invoice",        # ← 硬编码在 DFS 内部
)
```

**特征**:
- API/Service 层将特定领域的关系名作为默认值
- 用户不传参数时，自动使用供应链金融的关系名
- 非供应链场景：要么报错，要么返回空结果

**修复策略**:
- 默认值改为空字符串 `""`
- 从 schema 获取第一个关系名作为 fallback：`schema.get_first_relation_name()`
- 函数签名新增 `relation_name` 参数，让调用方显式指定

---

## 3. 修复方案总览

### 3.1 新增 Schema 驱动基础设施

| 方法 | 位置 | 作用 |
|------|------|------|
| `get_entity_id_field(concept_name)` | `KGMLSchema` | 从 schema 声明发现 ID 字段 |
| `get_all_concept_names()` | `KGMLSchema` | 获取所有概念名（替代硬编码列表） |
| `get_relation_names_for_concept(concept)` | `KGMLSchema` | 获取概念的所有关系名 |
| `get_first_relation_name()` | `KGMLSchema` | 获取第一个关系名（替代 `"has_invoice"` 默认值） |

### 3.2 修复统计

| 文件 | 修复前硬编码 | 修复后 | 关键变更 |
|------|------------|--------|----------|
| `__init__.py` | 30 (8C) | 0 | 删除 legacy 函数，新增 schema 驱动路径 |
| `engine/metric/engine.py` | 18 (5C) | 2 (fallback) | 删除 5 个硬编码聚合，新增通用聚合 |
| `engine/metric/graph_operators.py` | 6 (4C) | 3 (fallback) | 全算子参数化 |
| `core/instances/loader.py` | 16 (10H) | 0 | 删除 13 条映射，改用 schema 驱动 |
| `services/analysis_service.py` | 5 (1C) | 0 | schema 概念名列表 + get_entity_by_id |
| `services/query_service.py` | 1 (1C) | 0 | 新增 relation_name 参数 |
| `services/entity_service.py` | 1 (1C) | 0 | schema 首关系名 fallback |
| `api/routes/query.py` | 3 (3C) | 0 | 默认值改为空字符串 |

**CRITICAL 级硬编码: 30 → 0**

---

## 4. 代码审查注意点

> 以下规则应纳入项目代码审查 checklist，防止硬编码问题复发。

### 4.1 禁止事项（RED FLAGS）

| # | 禁止模式 | 检查方式 | 替代方案 |
|---|----------|----------|----------|
| R1 | 函数名包含具体领域名（如 `_compute_supplier_*`） | `grep -r "def _.*supplier\|def _.*invoice\|def _.*contract" ontology_engine/` | 通用命名 + schema 参数驱动 |
| R2 | 函数体内硬编码关系名（如 `"has_invoice"`） | `grep -r '"has_\|"_by\|"supplies_\|"guaranteed"' ontology_engine/ --include="*.py"` | 从 schema `MetricSource.traversal` 或 `concept.relations` 获取 |
| R3 | 函数体内硬编码实体类型名（如 `"Supplier"`） | `grep -r '"Supplier"\|"Invoice"\|"Contract"\|"Store"' ontology_engine/ --include="*.py"` | 从 schema `get_all_concept_names()` 获取 |
| R4 | 硬编码 ID 字段映射表（如 `{"Supplier": "supplier_id"}`） | `grep -r '"Supplier".*:.*"supplier_id"\|"Invoice".*:.*"invoice_no"' ontology_engine/ --include="*.py"` | `schema.get_entity_id_field()` |
| R5 | API 默认值为特定领域关系名 | 检查 `BaseModel` 字段默认值和函数参数默认值 | 默认 `""` 或 `schema.get_first_relation_name()` |
| R6 | `if concept == "XXX"` 守卫分支 | `grep -r 'if concept ==\|if concept_name ==' ontology_engine/ --include="*.py"` | schema 声明驱动的多态分发 |
| R7 | 同一业务逻辑在多个文件中重复实现 | 代码审查时关注遍历/聚合逻辑 | 统一到算子注册表或 service 层 |

### 4.2 必须事项（GREEN CHECKS）

| # | 必须模式 | 检查方式 |
|---|----------|----------|
| G1 | 新增实体类型时，schema 必须声明 `unique: true` 的 ID 属性 | `grep -A5 "unique: true" schema.yaml` |
| G2 | 新增关系时，schema concept 必须声明 `relations` 条目 | `grep -A3 "relations:" schema.yaml` |
| G3 | 新增指标时，必须声明 `source.traversal` 或 `source.attribute` | `grep -A5 "source:" schema.yaml` |
| G4 | 引擎层代码必须通过 `schema.get_entity_id_field()` 获取 ID 字段 | 代码审查 |
| G5 | API 层默认值必须为空字符串或 schema 驱动 | 检查 `BaseModel` 和 `Query()` 默认值 |
| G6 | 遍历/聚合逻辑必须通过 `GraphOperatorRegistry` 注册 | `grep -r "@GraphOperatorRegistry.register" ontology_engine/` |

### 4.3 架构原则

```
Schema 是唯一事实源（Single Source of Truth）
  │
  ├── 实体 ID 字段  → schema.get_entity_id_field()
  ├── 关系名        → schema.get_relation_names_for_concept()
  ├── 指标定义      → schema.analytical_elements.metrics
  ├── 规则定义      → schema.business_logic.rule_definitions
  │
  └── 引擎层代码不得重新声明 schema 已有的信息
```

**核心原则**: 如果 schema 已经声明了某个信息，代码中不得再次硬编码该信息。代码应通过 schema API 获取，或在 schema 未提供时使用约定推断作为 fallback。

### 4.4 新增 Case 审查流程

```
1. schema.yaml 是否声明了所有实体的 ID 属性（unique: true）？
2. schema.yaml 是否声明了所有关系（relations 列表）？
3. schema.yaml 是否声明了所有指标的 source（traversal/attribute）？
4. 引擎能否仅凭 schema 声明完成指标计算？（运行 demo_case*.py 验证）
5. 是否存在任何硬编码的实体类型名/关系名/ID 字段名？
```

---

## 5. 反模式速查表

| 反模式 | 代码示例 | 正确做法 |
|--------|----------|----------|
| 领域锁定函数 | `def _compute_supplier_metrics(self, ...)` | `def _compute_entity_metrics(self, concept, ...)` |
| 硬编码关系名 | `storage.get_neighbors(id, "has_invoice", ...)` | `storage.get_neighbors(id, schema.get_relation_names(concept)[0], ...)` |
| 硬编码 ID 字段 | `data.get("supplier_id")` | `data.get(schema.get_entity_id_field(concept))` |
| 硬编码概念列表 | `["Supplier", "Invoice", "Contract"]` | `schema.get_all_concept_names()` |
| 硬编码默认关系 | `relation_name: str = "has_invoice"` | `relation_name: str = ""` |
| 重复实现 | 同一遍历逻辑在 3 个文件中 | 统一到 `GraphOperatorRegistry` |
| 概念守卫分支 | `if concept == "Supplier": ...` | schema 声明驱动的多态分发 |

---

## 6. 残留风险

| 风险项 | 位置 | 说明 | 处理建议 |
|--------|------|------|----------|
| Fallback 默认值 | `engine.py:396-397`, `graph_operators.py:68-70` | 当 schema 未声明担保关系时，fallback 到 `"guaranteed_by"`/`"supplier_id"` | Phase 2 要求所有 schema 必须声明关系，届时可移除 fallback |
| 规则执行器硬编码 | `rule/executor.py`, `rule/operators/compute.py` | 8 处硬编码指标名查找 | 需要单独的规则引擎重构（不在本次范围） |
| API 文档示例 | `ingestion.py:110`, `ingestion_service.py:108` | 文档注释中的 `"has_invoice"` 示例 | 低优先级，仅影响文档 |
