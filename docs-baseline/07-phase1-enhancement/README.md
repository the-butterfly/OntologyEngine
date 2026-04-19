# 07-phase1-enhancement: Phase 1 增强设计

> **角色**: Gap 驱动的增强设计
> **状态**: draft
> **Phase**: phase1
> **基于**: 代码功能检视 Gap 分析报告 (2026-04-13)

## 这个目录回答什么

本目录基于代码功能检视（2026-04-13）识别出的 Gap 和用户新增需求，制定 Phase 1 增强的完整设计文档。覆盖以下五大增强方向：

| 编号 | 文档 | 核心内容 | 对应 Gap/需求 |
|------|------|----------|---------------|
| 01 | [存储层图数据库扩展](./01-graph-storage-extension.md) | Kuzu 嵌入式图库 + 适配器模式 + Neo4j 扩展路径 | 用户新需求 #1 |
| 02 | [规则算子与值域体系](./02-operator-and-value-domain.md) | 分箱/评分卡/决策树/LLM Judge 算子 + 全要素值域声明 | 用户新需求 #2 |
| 03 | [分类 Category 完善](./03-categorization-enhancement.md) | 值域/同义词/描述/多选 + 对象关联 + 规则适用场景 | 用户新需求 #3 |
| 04 | [数据集 Dataset 管理](./04-dataset-management.md) | Dataset 模型 / CRUD / 同步映射 / 版本快照 | P0 Gap-1 |
| 05 | [增量数据更新机制](./05-incremental-data-update.md) | 变更追踪 / 差异比对 / 增量导入 / 影响传播 | P1 Gap-2 |

## 与其他文档的关系

| 已有文档 | 本设计的处理 |
|----------|-------------|
| `06-module-detailed-design/03-storage-layer.md` | 继承存储接口，扩展 GraphStoreBackend，增加 Kuzu 实现 |
| `05-schema-v2/01-fact-objects.md` | L1 属性定义增加 value_domain 字段 |
| `05-schema-v2/02-categorization.md` | 大幅扩充 L2 分类维度定义 |
| `05-schema-v2/03-analytical-elements.md` | L3 要素增加完整值域和单位体系 |
| `05-schema-v2/04-business-logic.md` | L4 算子类型枚举与实际算子实现对接 |
| `05-schema-v2/06-dataset-and-sync.md` | Dataset 从概念设计落实到详细设计 |
| `development/storage-adapter.md` | 图存储适配器遵循相同注册模式 |
| `development/operator.md` | 更新算子开发模板，覆盖新算子类型 |

## 设计原则

1. **渐进增强** —— 每个增强可独立交付，不阻塞其他模块
2. **向后兼容** —— 新功能通过扩展字段/接口实现，不破坏已有 Schema v1/v2 加载
3. **适配器优先** —— 存储层新增能力先定义抽象接口，再提供具体实现
4. **Schema 驱动** —— 所有业务逻辑可通过 YAML 声明，代码只实现通用执行
5. **测试先行** —— 每个增强点附验收场景，基于 examples 跑通

## 文档元数据格式

所有文档统一使用以下头部：

```yaml
---
status: draft
phase: phase1
source_of_truth: false   # 或 true（如果是某主题的唯一规范）
last_verified: 2026-04-13
verified_against: docs-only  # 或具体文件路径
related_docs:
  - ../06-module-detailed-design/XX-xxx.md
  - ../05-schema-v2/XX-xxx.md
related_adrs:
  - architecture/decisions/XXX.md
---
```
