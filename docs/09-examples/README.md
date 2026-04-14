# 用户案例

> 端到端用户故事与验收场景

## 供应链金融（当前验证场景）

- **[supply_chain_finance.md](./supply_chain_finance.md)**: 端到端用户故事
  - 场景：供应商"北京智造科技"申请融资授信
  - 验证路径：管理空间 → Schema → 数据集 → 规则执行 → 可视化 → Agent 调用
  - 覆盖：6 个 Step，覆盖全部主要 API 和 MCP 工具

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

每个案例应包含：

- [ ] 至少 4 个 Step
- [ ] 覆盖管理面 API (Space/Schema/Dataset)
- [ ] 覆盖消费面 API (Execute/Visualize)
- [ ] 覆盖至少 2 个 MCP 工具
- [ ] 包含 What-if 或模拟场景
- [ ] 末尾有验证清单

---

## 相关文档

- **Schema 规范**: [`05-schema-v2/09-canonical-schema-spec.md`](../05-schema-v2/09-canonical-schema-spec.md)
- **案例审视报告**: [`REVIEW_REPORT.md`](./REVIEW_REPORT.md)
- **文档状态**: [`STATUS.md`](../STATUS.md)
