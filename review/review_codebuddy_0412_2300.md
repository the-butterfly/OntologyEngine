# OntologyEngine 文档体系审视与优化方案

> **审视范围**: `docs/README.md`、`docs/TODO.md`、`docs/01-overview/`、`docs/02-design/`、`docs/05-schema-v2/`、`docs/06-module-detailed-design/`
> **审视目标**: 从当前 Agent spec coding 约束与大型开源项目文档设计逻辑出发，评估目录结构、内容框架、一致性与可靠性
> **结论摘要**: 当前文档的核心问题不是“内容少”，而是**文档职责混叠、当前态/目标态混写、规范/实现/计划未分层、导航入口与真实内容脱节**。

---

## 一、总体判断

当前 `docs/` 实际上同时承担了 4 种完全不同的职责：

- **产品/项目认知入口**：`01-overview/`
- **MVP 当前实现基线**：`02-design/`
- **目标态架构设计**：`05-schema-v2/`
- **Phase 1 实现拆解**：`06-module-detailed-design/`

这四类文档本身都合理，但**缺少“谁是当前真相、谁是目标设计、谁是历史基线、谁是实施分解”的明确边界**。这会直接带来三个后果：

- **新读者无法建立稳定心智模型**：看完 `README.md` 仍然不知道应该先读当前实现还是目标架构。
- **实现者容易拿错文档当 source of truth**：尤其是在 Schema v2 结构、Rule 模型、API 路由、Expression 执行模型上。
- **状态文档失去可信度**：`README.md` / `TODO.md` 与 4 月 12 日更新过的 v2 文档已经明显不同步。

从大型开源项目的文档组织原则看，当前最缺的是这四件事：

- **单一入口**：一个读者地图，而不是多个平行入口。
- **单一事实源（SoT）声明**：每类主题只能有一个“规范文档”。
- **当前态 / 目标态 / 迁移态分离**：不能把 MVP、Phase 1、Schema v2 最终形态混在一个叙事层里。
- **状态与决策元数据**：每篇文档都应能快速回答“适用于哪个阶段、是否已定稿、替代了谁、谁维护”。

---

## 二、当前目录的核心结构问题

### 1. `README.md` 作为总导航已经失真

`README.md` 目前存在几个结构级问题：

- **没有把 `06-module-detailed-design/` 作为一级核心文档组展示**。
  - 但 `TODO.md` 明确把 Phase 1 实现优先级建立在 `06-module-detailed-design/` 之上。
  - 这意味着**最接近实施的文档组，没有被主入口正确曝光**。
- `README.md` 把“06”标成了**开发指南**，但真实目录里“06”是 `06-module-detailed-design/`，开发指南实际上在 `development/`。
  - 这会让编号语义失真，读者误以为模块详细设计不存在。
- `05 - Schema v2` 导航只列出前 6 个文档，没有覆盖：
  - `00b-semantic-space-architecture.md`
  - `06-dataset-and-sync.md`
  - `07-rule-declaration-and-instance.md`
  - `08-version-management.md`
- `README.md` 日期仍停在 **2026-04-09**，但 `05-schema-v2/` 多篇核心文档已更新到 **2026-04-12**。

**结论**：当前 `README.md` 不能再被视为可信的总索引，它本身已经成为不一致来源。

### 2. `TODO.md` 不是路线图，而是过期快照

`TODO.md` 的主要问题：

- **最后更新时间仍是 2026-04-09**，但其引用对象已经发生扩展。
- 它仍然在用“是否已有设计文档”来表达任务完成度，却没有更新到 4 月 12 日新增的 v2 语义空间、版本管理、数据集同步等内容。
- `TODO.md` 中“FastAPI 13 个端点”的描述，与 `06-module-detailed-design/10-api-layer.md` 中实际列出的路由数不一致，也与 `10-api-architecture.md` 的管理/消费双面 API 设计严重不一致。

**结论**：`TODO.md` 适合作为阶段任务板，但不适合作为架构状态页；应拆成 `STATUS.md` + `ROADMAP.md` / `BACKLOG.md`。

### 3. `02-design`、`05-schema-v2`、`06-module-detailed-design` 的关系没有被显式声明

目前读者必须靠猜：

- `02-design/` 是 **MVP 基线** 还是仍然有效的规范？
- `05-schema-v2/` 是 **目标架构规范** 还是已经进入实施的现行规范？
- `06-module-detailed-design/` 是对 `02-design/` 的细化，还是对 `05-schema-v2/` 的实现映射？

虽然 `06-module-detailed-design/00-overview.md` 有“继承/补充”关系说明，但它没有成为整个文档体系的显式结构规则。

**结论**：这三个目录的“层次语义”没有写在目录本身，也没有写在根导航中，导致理解成本高、误用概率大。

---

## 三、推荐的文档目录结构优化方案

这里建议采用**低风险重组**：尽量保留现有内容，但把目录语义、入口、状态页和源头规范补齐，而不是大面积重写。

### 推荐目标结构

```text
docs/
├── README.md                      # 单一入口：读者地图 + 当前阶段 + 推荐阅读路径
├── STATUS.md                      # 当前状态：已定稿/进行中/过期/替代关系
├── ROADMAP.md                     # 路线图与实施阶段（替代当前 TODO 的任务视角）
├── 01-overview/                   # 为什么做、做什么、不做什么、核心术语
├── 02-current-architecture/       # 当前实现基线（由现 02-design 演进而来）
├── 03-target-architecture/        # 目标架构（由现 05-schema-v2 演进而来）
│   ├── schema-v2/
│   ├── semantic-space/
│   ├── api/
│   └── versioning-sync/
├── 04-migration-and-gap/          # 当前态→目标态映射、兼容策略、风险与缺口
├── 05-module-design/              # Phase 1 实施拆解（由现 06-module-detailed-design 演进而来）
├── 06-development/                # 开发规范、测试、扩展指南
├── 07-rfc-adr/                    # RFC / ADR / 决策记录
└── archive/
```

### 如果希望最小改名，可采用兼容版映射

| 当前目录/文件 | 建议角色 | 处理建议 |
|---|---|---|
| `README.md` | 总入口 | 重写为读者地图，不承载详细状态表 |
| `TODO.md` | 任务板 | 拆为 `STATUS.md` + `ROADMAP.md`，原文件保留为临时 backlog |
| `01-overview/` | 项目概览 | 保留，但只放“为什么/是什么/边界/术语” |
| `02-design/` | 当前实现基线 | 明确标注为 MVP / current baseline |
| `05-schema-v2/` | 目标架构规范 | 明确标注为 target architecture / schema spec |
| `06-module-detailed-design/` | 实施设计 | 明确标注为 Phase 1 module design |
| `development/` | 开发规范 | 从 `README.md` 中独立为规范区 |
| `03-rfc/` | 决策记录 | 建议升级为 `07-rfc-adr/`，按 ADR/RFC 统一 |

---

## 四、每类文档建议采用的内容框架

### 1. 根入口 `README.md`

建议只做 5 件事：

- **项目当前所处阶段**：MVP / Phase 1 / Phase 2
- **读者分流**：新读者、实现者、评审者、Agent
- **推荐阅读路径**
- **目录语义说明**
- **当前 source of truth 列表**

推荐结构：

1. 你现在在看什么项目
2. 当前阶段与一句话状态
3. 我应该从哪开始读
4. 文档地图（按角色）
5. Source of Truth 索引
6. 最近变更 / 已知过期区

### 2. `01-overview/` 的内容边界

只保留以下内容：

- 业务愿景
- 问题动机
- 项目目标与非目标
- 核心术语表
- 模块边界总览
- 技术路线原则

**不要在这一层放**：

- 详细 API 路由
- Schema 细节字段
- 规则 DSL 具体语法
- 未来空间/消费视图的实现细节

### 3. `02-current-architecture/` 的内容框架

每篇都应回答“今天代码库实际采用了什么”。

建议模板：

- **状态**：Current / Deprecated / Transitional
- **适用范围**：MVP 还是 Phase 1
- **核心模型**
- **关键接口**
- **运行路径**
- **已知限制**
- **被哪个目标文档替代/演进**

### 4. `03-target-architecture/` 的内容框架

每篇都应回答“我们希望未来收敛成什么规范”。

建议模板：

- **Status**：Draft / Proposed / Accepted / Frozen
- **Source of Truth**：本篇是否是该主题的唯一规范
- **Problem / Goal / Non-goals**
- **Canonical data model**
- **Lifecycle / execution flow**
- **API / storage / consistency contract**
- **Compatibility and migration**
- **Open questions**

### 5. `05-module-design/` 的内容框架

每篇都应回答“目标架构如何变成可实现模块”。

建议模板：

- 模块职责
- 输入/输出契约
- 与上游/下游关系
- 关键数据结构
- 执行流程
- 错误处理/失败模式
- 与当前代码的映射
- 测试要点
- 未决问题

### 6. 每篇文档统一元数据

建议所有核心设计文档顶部统一加入：

```yaml
status: draft | proposed | accepted | frozen | deprecated
phase: mvp | phase1 | phase2
audience: overview | implementer | reviewer | agent
source_of_truth: true | false
supersedes: [old-doc]
related_docs: [x, y, z]
last_verified: 2026-04-12
verified_against: docs-only | code-and-docs
owner: architecture
```

这是当前最值得补的一层“文档治理元数据”。

---

## 五、关键一致性与可靠性问题清单

下面按严重度列出目前最需要处理的问题。

### A. 高严重度问题

| 问题 | 证据 | 影响 | 建议 |
|---|---|---|---|
| `README.md` 导航与真实目录失配 | `README.md` 把“06”写成开发指南，但真实核心目录是 `06-module-detailed-design/`；且未完整列出 `05-schema-v2` 文档 | 主入口失真，读者会错过最关键实施文档 | 立即重写根导航，明确“当前态 / 目标态 / 实施态” |
| Schema v2 顶层 YAML 形状漂移 | `05-schema-v2/00-overview.md` 用 `fact_objects / categorizations / analytical_elements / rule_definitions`；`05-complete-example.md` 用 `fact_objects.entities / categorization.dimensions / business_logic.rule_groups`；`01-fact-objects.md` 又用 `fact_object_declaration` 单文档结构 | 无法判断 canonical schema grammar，后续实现和示例都可能分叉 | 指定一个“唯一 canonical schema 形状”，其余文档显式标记为“局部声明示意”或“完整文件示例” |
| Rule 模型前后不统一 | `05-schema-v2/04-business-logic.md` 和 `07-rule-declaration-and-instance.md` 定义 `rule_definition + rule_logic`；`05-complete-example.md` 却用 `business_logic.rule_groups`; `06-module-detailed-design/01-schema-loading.md` 内部模型仍偏旧式 `scope/when/then` | 规则引擎、SchemaLoader、示例 YAML 难以对齐 | 明确 Rule 的 canonical model，并给出从旧 `rule_group` 写法到新模型的迁移表 |
| 当前 API 与目标 API 混写 | `02-design/02-api-design.md` 和 `06-module-detailed-design/10-api-layer.md` 是 `/v1/schema`、`/v1/entities`；`10-api-architecture.md` 和 `05-schema-v2/*` 是 `/v1/management` + `/v1/consumption` | 实现者不知道现在该实现哪套接口 | 将 API 文档拆成 **Current API** 与 **Target Space API** 两套 |
| Formula / Expression 执行模型冲突 | `02-design/06-formula-spec.md` 写 Phase 1 只用 `simpleeval`，Phase 2 再做自定义 AST；`02-design/04-rule-engine-design.md` 与 `06-module-detailed-design/07-expression-engine.md` 却写 Phase 1 已是双层执行 | 公式能力、语法边界、安全模型无法稳定落地 | 指定一个唯一执行模型文档，并把其他文档改为引用而不是重复定义 |

### B. 中严重度问题

| 问题 | 证据 | 影响 | 建议 |
|---|---|---|---|
| L3/L4 边界仍未真正收敛 | `05-schema-v2/03-analytical-elements.md` 一边说“只声明依赖，formula 在 L4”，一边又允许 `overridable: false` 时 `formula` 留在 L3；`00-overview.md` 示例也把公式放在 L3 | 指标逻辑到底归属 L3 还是 L4，不同读者理解不同 | 增加“L3/L4 决策矩阵”：哪些逻辑必须在 L4、哪些可在 L3 固定声明 |
| 状态机表述不一致 | `00-overview.md` 表格写状态为 `DRAFT/ACTIVE/ARCHIVED`，但状态图与 `00b-semantic-space-architecture.md`、`08-version-management.md` 明确存在 `PUBLISHED` | 生命周期语义不闭合 | 统一空间状态机，并将 `PUBLISHED` 明确为状态还是快照事件 |
| 引擎拆分口径漂移 | `01-overview/04-modules.md` 有独立 `VectorEngine`；`02-design/05-services-design.md` 的 `AnalysisService` 依赖 `VectorEngine`；`06-module-detailed-design/00-overview.md` 则把向量能力并入 `QueryEngine` | 模块边界不稳定，服务依赖图不可靠 | 明确 Vector 是独立引擎还是 QueryEngine 子能力 |
| “本地优先”与平台/外部依赖叙事冲突 | `01-overview/01-vision.md`、`06-tech-stack.md` 强调零外部依赖；`02-design/03-storage-design.md`、`05-schema-v2/06-dataset-and-sync.md`、`10-api-architecture.md` 又大量引入 PostgreSQL / MySQL / S3 / 管理面 / JWT 等平台设定 | 评审时难判断哪些是当前约束，哪些是远期能力 | 采用能力矩阵：`current / optional / future` 三栏明确归位 |
| `README.md` / `TODO.md` 状态过期 | 根文档停留 4 月 9 日，v2 核心文档已到 4 月 12 日 | 状态页不可信 | 让 `STATUS.md` 成为唯一状态页，并由变更时强制同步 |

### C. 低到中严重度问题（但应尽快清理）

| 问题 | 证据 | 影响 | 建议 |
|---|---|---|---|
| `TODO.md` 的“13 个端点”与详细设计不一致 | `10-api-layer.md` 中可检出的路由装饰器已达 14 个，而且 `10-api-architecture.md` 描述的是更大的一整套 API 面 | 任务板不可信 | 改成“API 层完成基于哪份规范”，不要写不稳定数字 |
| `07-expression-engine.md` 的伪实现可靠性不足 | 文中写依赖 `asteval`，但示例却用 `exec`；还出现 Python 3 中不存在的 `ast.Exec` | 误导实现，安全设计可信度不足 | 把此类代码改成“伪代码”或“约束描述”，并标注未验证 |
| 术语多套并行 | `Concept / Entity / Fact Object`，`Categorization / Category / Dimension / Tag`，`RuleGroup / RuleDefinition / RuleLogic / Ruleset` 并存 | 新读者学习成本高 | 在 `01-overview/05-concepts.md` 增加术语对照表并强制统一用词 |

---

## 六、当前设计中最值得优先收敛的 8 个冲突点

### 1. 目录编号语义冲突

- `README.md` 中的“06”是开发指南
- 实际目录中的“06”是 `06-module-detailed-design/`
- 开发指南在 `development/`

**建议**：不要再让编号承担分类含义；要么取消数字前缀，要么保证数字与目录一一对应。

### 2. `05-schema-v2` 内部有三套 Schema 展示口径

- **单声明示意**：`fact_object_declaration` / `analytical_element_declaration`
- **总览简写**：`fact_objects` / `categorizations` / `rule_definitions`
- **完整示例**：`fact_objects.entities` / `categorization.dimensions` / `business_logic.rule_groups`

**问题本质**：没有定义哪一套才是“真实文件格式”。

### 3. 规则模型存在“双轨叙事”

- 一条轨道：`rule_definition + rule_logic`
- 另一条轨道：`rule_group + applies_to + rules`

**问题本质**：概念模型还没最后收敛，但文档却以“定稿口吻”同时发布了两套模型。

### 4. L3 是否允许携带计算逻辑没有决议闭环

现状至少有三种表达：

- L3 只声明依赖，逻辑都在 L4
- L3 可以保留标准公式，L4 仅在 `overridable=true` 时覆盖
- 示例里 L3 直接有 `formula`

**建议**：增加一篇非常短的 ADR，标题可为：`ADR-00x-l3-l4-computation-boundary.md`。

### 5. API 面设计存在“当前接口”和“空间接口”混线

- 一套是当前工程导向的 FastAPI（`/v1/schema`、`/v1/entities`）
- 一套是平台化空间接口（`/v1/management`、`/v1/consumption`）

**建议**：明确：

- `02-current-architecture/api.md`：当前可实现接口
- `03-target-architecture/api-space.md`：未来空间接口
- `04-migration-and-gap/api-migration.md`：映射关系

### 6. 平台化内容越界到基础设计，缺少能力边界声明

像以下内容都属于高成本平台能力：

- JWT / 权限模型
- 管理空间 / 消费视图
- 外部数据库同步
- 计划任务 / cron 同步
- 跨空间授权聚合

这些内容本身可以设计，但需要在文档上标清：

- **Current**：不实现 / 只占位
- **Phase 1**：最小实现
- **Future**：仅目标态设计

### 7. 设计文档的示例代码缺少“可实现性校验”标记

现在许多代码块在语义上更像“说明性伪代码”，但样式写得像可直接落地的实现。

**建议**：统一分三类：

- `Pseudo-code`
- `Proposed interface`
- `Verified against current code`

### 8. 缺少“迁移文档”这一层

当前最缺的不是再加一篇规范，而是补一篇：

- 从 `02-design`（当前态）
- 到 `05-schema-v2`（目标态）
- 再到 `06-module-detailed-design`（实施态）

之间的**一对一映射表**。

这篇文档会直接降低 50% 的理解成本。

---

## 七、建议新增的 4 个关键文档

### 1. `docs/STATUS.md`

作用：统一表达“哪些文档已定稿、哪些已过期、哪些仍在 proposal”。

建议字段：

- 文档路径
- 角色（overview/current/target/module/reference）
- 状态（draft/proposed/accepted/deprecated）
- phase
- source_of_truth
- last_verified

### 2. `docs/04-migration-and-gap/README.md`

作用：集中回答“当前代码和目标设计之间还差什么”。

建议内容：

- 当前实现 vs 目标设计矩阵
- 关键不兼容点
- 优先级与风险
- 每个模块的迁移入口

### 3. `docs/03-target-architecture/schema-canonical-spec.md`

作用：定义**唯一 canonical Schema v2 文件格式**。

必须明确：

- 根对象结构
- L1/L2/L3/L4 顶层键
- rule declaration / logic 的最终形状
- 允许的兼容别名
- 示例文件与声明示意的关系

### 4. `docs/07-rfc-adr/ADR-l3-l4-boundary.md`

作用：一次性冻结最容易反复争论的问题：

- L3 是否可带标准 formula
- L4 何时可覆盖 L3
- 哪些 operator 属于 L4 专属
- 是否允许 rule_group 作为 authoring sugar

---

## 八、建议的重写优先级

### P0：必须先做

- 重写 `README.md`
- 将 `TODO.md` 拆为 `STATUS.md` + `ROADMAP.md`
- 明确 `02-design` / `05-schema-v2` / `06-module-detailed-design` 三者关系
- 指定 canonical Schema v2 grammar

### P1：紧接着做

- 收敛 Rule 模型
- 收敛 L3/L4 边界
- 拆开 current API 和 target API
- 统一术语表

### P2：随后做

- 清理伪代码可靠性问题
- 给每篇核心文档补元数据
- 为模块设计增加“映射到当前代码”与“测试要点”章节

---

## 九、最终建议（可直接执行）

如果只做最小必要动作，我建议这 6 步：

1. **先把 `README.md` 改成真正的读者地图**，不要再放过期状态表。
2. **新增 `STATUS.md`**，让“当前有效规范”有唯一落点。
3. **给 `02-design` 打上 current baseline 标签**，给 `05-schema-v2` 打上 target architecture 标签，给 `06-module-detailed-design` 打上 implementation design 标签。
4. **补一篇 canonical schema spec**，冻结顶层结构和 Rule 模型。
5. **补一篇 migration & gap 文档**，明确从当前代码到目标架构的映射。
6. **停止在多个文档里重复定义公式执行模型、API 路由、Rule 结构**，改为“一个规范文档 + 多处引用”。

---

## 十、结论

当前文档体系的主要矛盾，不是“写得不够多”，而是**没有明确区分“认知入口、当前真相、目标规范、实施设计、任务状态”五种文档职责**。一旦把这五层分开，现有内容大部分都能被保留，只需要重建入口、冻结 source of truth、补齐迁移层，就能显著提升可读性和可实施性。

从工程收益看，**最重要的不是继续新增设计，而是先做信息架构收敛**。否则接下来每新增一篇文档，都会继续扩大口径漂移。
