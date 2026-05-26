# Agent Onboarding 指南

> **status**: draft | **phase**: phase2 | **source_of_truth**: 本文档 | **last_verified**: 2026-05-25
> **[单一事实源]**: Agent 接入 OntologyEngine 的唯一引导文档

---

## 目的

指导 AI Agent 快速接入 OntologyEngine，了解可用 MCP 工具清单、调用方式和典型使用场景。

---

## 快速接入

### 1. 连接 MCP Server

OntologyEngine 通过 MCP（Model Context Protocol）暴露工具接口。Agent 通过 stdio transport 连接：

```bash
# 启动 MCP Server
python -m ontology_engine.mcp.server
```

### 2. 确认连接

连接成功后，Agent 可调用 `oe_list_spaces` 验证连通性。

---

## MCP 工具清单

### 知识消费（Query & Execution）

| 工具 | 用途 | 关键参数 | 返回 |
|------|------|---------|------|
| `oe_query` | 知识检索（Layer-R/S 双路） | query, entity_id, space_id, top_k | 结果 + 证据链 + 执行快照 |
| `oe_execute_rule` | 执行规则/业务逻辑 | rule_name, entity_id, inputs | 执行结果 + 规则链 |
| `oe_simulate` | 模拟执行（不持久化） | scenario, overrides | 仿真结果 |

### 知识管理（Schema & Entity）

| 工具 | 用途 | 关键参数 | 返回 |
|------|------|---------|------|
| `oe_create_entity` | 创建实体实例 | fact_object, attributes, space_id | entity_id |
| `oe_update_relation` | 更新/创建关系边 | from_id, to_id, relation_name, attributes | relation_id |
| `oe_define_rule` | 定义业务规则 | rule_name, conditions, actions, space_id | rule_id |
| `oe_activate_space` | 激活语义空间 | space_id | status |

### 知识摄入（Ingestion）

| 工具 | 用途 | 关键参数 | 返回 |
|------|------|---------|------|
| `oe_create_space` | 创建语义空间 | name, type, description | space_id |
| `oe_list_spaces` | 列出所有空间 | — | 空间列表 |
| `oe_load_schema` | 加载空间 Schema | space_id | Schema 定义 |
| `oe_register_dataset` | 注册数据源 | source_type, source_uri, linkage_targets | dataset_id |

### Agent 记忆（Memory）

| 工具 | 用途 | 关键参数 | 返回 |
|------|------|---------|------|
| `oe_remember` | 写入记忆 | text, memory_type, space_id | node_id |
| `oe_recall` | 检索记忆 | query, memory_type, top_k | 记忆列表 + 置信度 |
| `oe_reflect` | 触发反思 | space_id, focus_area | 反思结果 |
| `oe_approve_memory` | 审批记忆晋升 | node_id, action, comment | 审批状态 |
| `oe_consolidate` | 合并重复记忆 | node_id, target_node_id | 合并结果 |
| `oe_forget` | 策略性遗忘 | node_id, reason | 状态 |
| `oe_correct_memory` | 修正记忆内容 | node_id, corrections | 修正结果 |
| `oe_delete_memory` | 删除记忆 | node_id, reason | 状态 |
| `oe_list_my_memories` | 列出当前 Agent 的记忆 | agent_name, memory_type, limit | 记忆列表 |
| `oe_record_commitment` | 记录承诺/约束 | commitment_text, deadline, priority | commitment_id |
| `oe_check_commitments` | 检查承诺状态 | agent_name, status_filter | 承诺列表 |
| `oe_memory_stats` | 记忆统计 | space_id | 统计信息 |
| `oe_get_reflection_status` | 反思状态 | space_id | 反思进度 |
| `oe_memory_types` | 可用记忆类型列表 | — | 类型列表 |
| `oe_audit_trail` | 审计日志 | node_id, limit | 操作历史 |

### 版本管理

| 工具 | 用途 | 关键参数 | 返回 |
|------|------|---------|------|
| `oe_snapshot` | 创建空间快照 | space_id, label, description | version_id |
| `oe_rollback` | 回滚到指定版本 | space_id, version_id | status |

---

## 典型使用场景

### 场景 1：快速知识查询

```python
# Agent 调用
result = oe_query(
    query="企业A 的资产负债率和信用评级",
    space_id="space.company_analysis"
)

# 返回结构
{
    "answer": "资产负债率 65%，信用评级 B+",
    "evidence": [
        {"fragment_id": "frag_001", "source": "2024年报.pdf", "confidence": 0.9},
        {"fragment_id": "frag_002", "source": "征信报告", "confidence": 0.85}
    ],
    "execution_snapshot": {
        "steps": ["retrieval", "entity_resolution", "metric_calculation"],
        "rule_chain": ["credit_scoring"]
    }
}
```

### 场景 2：写入新记忆

```python
# Agent 从对话中提取经验
node_id = oe_remember(
    text="用户倾向于在周五下午提交报销申请，建议提前审核",
    memory_type="self_experience",
    space_id="space.workflow"
)
```

### 场景 3：反思与总结

```python
# 周期性反思：从近期记忆中提炼模式
reflection = oe_reflect(
    space_id="space.workflow",
    focus_area="recurring_patterns"
)
```

### 场景 4：记忆审批（人类-Agent 协作）

```python
# Agent 发现高质量记忆，申请晋升到企业治理区
approval = oe_approve_memory(
    node_id="mem_001",
    action="approve",
    comment="该经验已被 3 次对话验证，confidence=0.92"
)
```

### 场景 5：规则执行

```python
# 执行业务规则
result = oe_execute_rule(
    rule_name="credit_limit_calculation",
    entity_id="ent_company_A",
    inputs={"override_debt_ratio": 0.55}
)
```

---

## 调用约定

### 空间隔离

所有工具调用默认在当前 `space_id` 下执行。跨空间调用需显式指定 `space_id`。

### 错误处理

工具返回统一错误格式：

```json
{
    "error": {
        "code": "ENTITY_NOT_FOUND",
        "message": "Entity ent_999 not found in space space.company_analysis",
        "details": {"entity_id": "ent_999", "space_id": "space.company_analysis"}
    }
}
```

### 置信度标签

| 标签 | 含义 | Agent 使用建议 |
|------|------|--------------|
| EXTRACTED (1.0) | 确定性提取，来源明确 | 可直接使用 |
| INFERRED (0.4-0.9) | 合理推断 | 使用但标注不确定性 |
| AMBIGUOUS (0.1-0.3) | 不确定关系 | 需人工确认 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| MCP 工具实现源码 | `ontology_engine/mcp/tools/` |
| 记忆系统详细设计 | [`docs/02-design/agent-memory/`](../02-design/agent-memory/) |
| API 端点设计 | [`docs/02-design/api/`](../02-design/api/) |
| 知识库流程 | [`docs/01-overview/10-kb-process.md`](../01-overview/10-kb-process.md) |
