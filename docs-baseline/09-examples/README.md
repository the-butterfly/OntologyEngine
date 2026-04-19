# 用户案例

> 端到端用户故事与验收场景

## 供应链金融

- **[supply_chain_finance.md](./supply_chain_finance.md)**: 端到端案例 **[deprecated]**
  - ⚠️ **状态**: 已标记为 Phase 2 设计参考，不代表当前 Phase 1 实现
  - 详见文档头部的不符点说明和 [`REVIEW_REPORT.md`](./REVIEW_REPORT.md)
  - 当前实现参考: [`examples/supply_chain_finance/schema.yaml`](../../examples/supply_chain_finance/schema.yaml)

## 案例贡献指南

### 添加新案例

1. 在 `docs/09-examples/` 目录下创建 `{domain}.md` 文件
2. 遵循以下格式要求

### 格式要求

| 元素 | 要求 |
|------|------|
| Step 编号 | 连续编号 (Step 1, Step 2, ...) |
| MCP 工具 | 每个 Step 必须标注对应 MCP 工具名 |
| HTTP 方法 | 标注 `METHOD /path` 格式 |
| 请求/响应 | JSON 格式，带语法高亮 |
| 验证点 | 每个 Step 末尾列出具体验证项 |
| 数据清单 | 末尾附示例文件清单表格 |

### 验证完整性

每个案例应包含（Phase 1）：

- [ ] 至少 4 个 Step
- [ ] 覆盖管理面 API (Space/Schema/Dataset)
- [ ] 覆盖消费面 API (Execute/Visualize)
- [ ] **Phase 2**: 覆盖 MCP 工具（当前 `ontology_engine/mcp/` 未实现）
- [ ] 包含 What-if 或模拟场景
- [ ] 末尾有验证清单

---

## 相关文档

- **Schema 规范**: [`05-schema-v2/09-canonical-schema-spec.md`](../05-schema-v2/09-canonical-schema-spec.md)
- **案例审视报告**: [`REVIEW_REPORT.md`](./REVIEW_REPORT.md) — 供应链金融与消费信贷案例一致性核验
- **MCP 工具核验**: [`TOOL_AUDIT.md`](./TOOL_AUDIT.md) — 18 个 MCP 工具定义 vs 实现状态
- **Phase 2 RFC**: [`docs/03-rfc/RFC-010-phase2-roadmap.md`](../03-rfc/RFC-010-phase2-roadmap.md)
