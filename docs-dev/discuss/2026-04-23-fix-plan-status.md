# 规则模拟功能修复计划 - 执行状态 v2

> 日期: 2026-04-23
> 状态: 数据问题待修复
> 关联案例: `examples/supply_chain_finance/` 供应链金融授信评估

---

## 一、实施状态总结

### P0 代码已完成

**已修改文件**:
1. `ontology_engine/services/simulation_tree_builder.py` - 实现 `_filter_steps()` 和 `_locate_from_l4_layer()`
2. `ontology_engine/api/routes/simulation.py` - 注入 `SemanticSpaceStorage`

### API 测试结果

```bash
POST /v1/simulation/tree
{
  "schema_id": "space_supply_chain_finance",
  "target_output": "decision"
}

Response:
{
  "layers": [],
  "total_steps": 0,
  "rule_group_count": 0
}
```

**结论**: API 调用正常，但规则数据 outputs 字段为空，无法匹配

---

## 二、发现的核心问题

### 问题: L4 规则定义 `outputs` 字段为空

**API 响应**:
```bash
curl http://localhost:8000/v1/spaces/space_supply_chain_finance/schema/L4/rules/definitions
```

返回:
```json
{
  "id": "RD001_basic_eligibility",
  "outputs": [],        // ← 空！
  "inputs": [],         // ← 空！
  "logic_ids": [],      // ← 空！
  "enabled": false
}
```

**但** `examples/supply_chain_finance/schema.yaml` 中明确定义了 outputs:
```yaml
- id: RD001_basic_eligibility
  name: "基础准入检查"
  outputs:
    - { id: is_eligible, name: "是否准入", type: flag }
    - { id: rejection_reason, name: "拒绝原因", type: computed_value }
```

**根因**: Schema 导入时 `to_space_layers_dict()` 正确转换了 `outputs` 字段，但保存到 SemanticSpace 后数据丢失或被覆盖

---

## 三、两个 Semantic Space 对比

| Space ID | rule_definition_count | outputs 状态 |
|----------|------------------------|--------------|
| space_supply_chain_finance | 6 | 全部为空 |
| space_supply_chain_demo | 3 | 全部为 null 或空 |

**共同问题**: 两个 space 的 L4 规则定义 outputs 字段都是空的

---

## 四、修复方案

### 方案 1: 检查 Schema 导入流程 [P0]

**检查点**:
1. `SchemaLoader.load()` 是否正确解析 `outputs` 字段
2. `to_space_layers_dict()` 转换是否丢失数据
3. `SemanticSpaceStorage.save()` 是否正确保存 L4 数据

### 方案 2: 直接修复数据库中的数据 [P1]

如果检查后发现是历史数据问题，可以通过 API 重新保存规则定义

### 方案 3: 使用 `space_supply_chain_demo` 进行测试 [P2]

用户的 URL 是 `space_supply_chain_demo`，该 space 有 3 条规则定义

---

## 五、下一步行动

1. **检查 Schema 导入流程** - 确认数据丢失点
2. **修复数据或代码** - 根据检查结果
3. **运行前端测试** - 验证旅程完整性

---

## 六、测试命令

```bash
# 检查规则定义
curl -s http://localhost:8000/v1/spaces/space_supply_chain_demo/schema/L4/rules/definitions | python3 -c "import sys,json; [print(f\"{r.get('id')}: outputs={r.get('outputs')}\") for r in json.load(sys.stdin).get('data',[])]"

# 测试模拟树构建
curl -s -X POST http://localhost:8000/v1/simulation/tree -H "Content-Type: application/json" -d '{"schema_id":"space_supply_chain_demo","target_output":"decision"}'
```

---

## 七、相关文件索引

### 已修改
- `ontology_engine/services/simulation_tree_builder.py` - P0 实现
- `ontology_engine/api/routes/simulation.py` - 注入 storage

### 待检查
- `ontology_engine/core/schema/loader.py` - Schema 导入逻辑
- `ontology_engine/core/schema/models.py` - to_space_layers_dict()
- `ontology_engine/core/semantic_space/storage.py` - 数据存储逻辑