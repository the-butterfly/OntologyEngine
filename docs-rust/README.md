# OntologyEngine 设计文档

> **版本**: 0.1.0  
> **状态**: 设计中  
> **最后更新**: 2026-04-07

## 项目愿景

构建下一代知识库系统，面向未来的 Agent 提供分层的事实描述、规则管理和执行以及 Memory 能力，支持快速构建和更新图谱的 Schema 和数据，提供给 Agent 的知识检索服务，同时在 Agent 使用过程中实现用户反馈的实时回流。

## 文档组织结构

本文档采用**自顶向下、逐层细化**的方式组织，从架构概览逐步深入到具体实现细节。

```
docs/
├── README.md                    # 本文档 - 总览与导航
├── architecture/               # 架构设计（粗粒度）
│   ├── 01-overview.md          # 系统整体架构
│   ├── 02-requirements.md      # 需求分析
│   ├── 03-concepts.md          # 核心概念定义
│   ├── 04-layers.md            # 分层架构设计
│   └── 05-tech-stack.md        # 技术栈选型
├── design/                     # 详细设计（中粒度）
│   ├── schema/                 # Schema 与本体设计
│   ├── storage/                # 存储层设计
│   ├── query/                  # 查询与检索设计
│   ├── inference/              # 推理引擎设计
│   ├── rules/                  # 规则引擎设计
│   └── agent/                  # Agent 集成设计
├── implementation/             # 实现细节（细粒度）
│   ├── project-structure.md    # 项目结构
│   ├── crate-design.md         # Crate 划分
│   ├── data-structures.md      # 核心数据结构
│   ├── algorithms.md           # 关键算法
│   └── interfaces.md           # 接口定义
├── api/                        # API 文档
│   └── public-api.md           # 公开 API
├── development/                # 开发计划
│   ├── roadmap.md              # 路线图
│   └── milestones.md           # 里程碑
└── reference/                  # 参考资料
    ├── glossary.md             # 术语表
    └── decisions/              # 架构决策记录(ADR)
```

## 快速导航

### 如果你是架构师
1. 从 [架构概览](./architecture/01-overview.md) 开始
2. 阅读 [分层架构](./architecture/04-layers.md)
3. 查看 [技术栈选型](./architecture/05-tech-stack.md)

### 如果你是开发者
1. 查看 [项目结构](./implementation/project-structure.md)
2. 阅读 [Crate 设计](./implementation/crate-design.md)
3. 参考 [接口定义](./implementation/interfaces.md)

### 如果你是产品经理
1. 从 [需求分析](./architecture/02-requirements.md) 开始
2. 查看 [路线图](./development/roadmap.md)

## 核心特性

| 特性 | 描述 | 状态 |
|------|------|------|
| 声明式 Schema | 使用 YAML/JSON 定义本体、类型、规则 | 设计中 |
| 分层知识表示 | 支持 L0-L2 三层本体结构 | 设计中 |
| 多模态存储 | 属性图 + 向量 + 关系型混合存储 | 设计中 |
| 规则引擎 | 支持符号推理、图推理、LLM 推理 | 设计中 |
| 指标计算 | 声明式指标定义与多策略计算 | 设计中 |
| Agent 集成 | 为 Agent 提供知识检索与 Memory | 规划中 |
| 实时反馈 | 用户反馈回流到知识库 | 规划中 |

## 参与讨论

本文档仍处于设计阶段，每个设计点都需要通过讨论来细化。请通过以下方式参与：

1. 阅读具体设计文档，查看标记为 **💬 待讨论** 的部分
2. 在相应文档中提出问题和建议
3. 参考 [架构决策记录](./reference/decisions/) 了解已做出的决策

## 变更日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-04-07 | 0.1.0 | 初始文档结构创建 |
