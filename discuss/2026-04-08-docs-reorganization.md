# 文档重组关键决策

**Date**: 2026-04-08
**Context**: MVP Demo 已跑通，需要整理设计文档并为 Schema v2 做准备

## 决策汇总

### 1. 文档分层结构

按大型项目管理规范，将文档分为五层：

```
docs/
├── 01-overview/      # 概要设计: 愿景、动机、目标、模块
├── 02-design/        # 详细设计: Schema、API、存储、规则引擎
├── 03-rfc/           # 过程文档: RFC 决策记录
├── 04-testing/       # 测试修复: 测试规范、质量门禁
└── 05-schema-v2/     # 下一步设计: 四层分离架构
```

### 2. Schema v2 核心设计

**四层分离架构**：

| 层级 | 名称 | 内容 | 稳定性 |
|------|------|------|--------|
| L1 | 事实对象 | 实体/关系定义、原始属性 | 高 |
| L2 | 归类分析 | 行业、规模、风险等级等标签 | 中 |
| L3 | 分析要素 | 指标、变量、函数 | 中 |
| L4 | 业务逻辑 | 规则、决策、流程 | 高变动 |

**关键改进**：
- 规则不再硬编码 entity_type，改为声明式 applies_to
- 事实与分析结果分离，避免 attributes 混杂
- 支持规则组作用域 (fact_objects + categories)
- 显式 inputs/outputs 声明

### 3. 术语统一

| v1 术语 | v2 术语 | 说明 |
|---------|---------|------|
| concepts | fact_objects | 更精确 |
| dimension_attributes | categorization | 消除误解 |
| metrics | analytical_elements | 扩展为包含变量/函数 |
| rules | business_logic | 包含规则组/决策/流程 |

### 4. 下一步行动

1. **当前 (MVP)**
   - 继续完善基于 v1 的实现
   - 确保 Demo 场景完全跑通
   - 补充单元测试覆盖

2. **Phase 1 启动时**
   - 评估 v2 设计可行性
   - 实现 Schema v2 Loader
   - 逐步迁移现有规则

3. **需要进一步设计**
   - v2 的 YAML 完整语法规范
   - L3 图指标的具体算法配置
   - L4 workflow 的状态机设计
   - v1 到 v2 的迁移工具

## 参考

- 详细文档: `docs/05-schema-v2/`
- 完整示例: `docs/05-schema-v2/05-complete-example.md`
