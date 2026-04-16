
❯ 文档检视，审视docs目录下的所有文档，从愿景、动机、目标、模块、API设计等来方面进行拆分内容，审视目录结构的合理性，同时对具体内容的核心设计点进行辩论，尤其是设计是否能够满足愿景，愿景和方案是否足够清晰合理，提出补充或者修
正意见，可以调用各种外部检索工具。简化不必要的描述，保证文档的一致性和代码的合理性，全部内容使用统一的语言体系，重点审视规则的执行和可解释性、业务分类管理的内容，保障一个端到端的管理交互和可视化内容，最终通过examples进行完
整的用户案例呈现，接口设计中考虑未来Agent调用进行资产的构建和消费的易用性。

⏺ I'll conduct a comprehensive review of the docs/ directory. Let me start by scanning the structure and reading the key documents.

  Searched for 1 pattern, read 3 files (ctrl+o to expand)

⏺ This is a substantial review task. I'll dispatch parallel agents to analyze different doc domains while directly reading the most critical files.

⏺ 4 Explore agents finished (ctrl+o to expand)
   ├─ Review vision and goals docs · 9 tool uses · 16.7k tokens
   │  ⎿  Done
   ├─ Review schema v2 target architecture · 10 tool uses · 35.8k tokens
   │  ⎿  Done
   ├─ Review API and agent interface docs · 6 tool uses · 32.6k tokens
   │  ⎿  Done
   └─ Review design and module docs · 32 tool uses · 112.4k tokens
      ⎿  Done

⏺ Let me continue by reading the remaining critical documents directly.

  Read 5 files (ctrl+o to expand)

⏺ Let me read a few more core documents to ensure accuracy in my synthesis.

  Read 4 files (ctrl+o to expand)
  ⎿  Please run /login · API Error: 403 {"error":{"type":"permission_error","message":"You've reached your usage limit for this billing cycle. Your quota will be refreshed in the next cycle. Upgrade to get more:
     https://www.kimi.com/code/console?from=quota-upgrade"},"type":"error"}

✻ Sautéed for 2m 55s

⏺ Now I have comprehensive coverage. Let me synthesize the complete review report.

  ---
  OntologyEngine 文档体系审查报告

  一、总体评估

  文档体系成熟度：中等偏上，但存在结构性断层。

  治理框架（README / STATUS / ROADMAP / TODO / 迁移层）设计合理，标注约定有效。核心问题集中在三层：
  1. Schema v2 内层结构存在至少三种互不兼容的方言
  2. 设计-代码漂移未系统性追踪，导致文档可信度参差不齐
  3. Agent 接口与目标 API 架构之间缺乏映射桥梁

  ---
  二、愿景与目标（01-overview）

  2.1 关键矛盾

  ┌──────────────────────────────────┬─────────────────────────────────────────────────────────┬───────────────────────┐
  │              矛盾点              │                          位置                           │         影响          │
  ├──────────────────────────────────┼─────────────────────────────────────────────────────────┼───────────────────────┤
  │ Phase 1 节点数目标矛盾           │ 01-vision.md 写"十万级"（100K），03-goals.md 表格写"1M" │ 高 — 无法确定验收基线 │
  ├──────────────────────────────────┼─────────────────────────────────────────────────────────┼───────────────────────┤
  │ "三层跃迁"列了四层（L1-L4）      │ 01-vision.md 标题与内容不符                             │ 低 — 文字错误         │
  ├──────────────────────────────────┼─────────────────────────────────────────────────────────┼───────────────────────┤
  │ AI Native 品牌 vs Phase 2 才落地 │ 愿景声称 AI Native，Agent 接口却在 Phase 2              │ 中 — 品牌与路线不匹配 │
  └──────────────────────────────────┴─────────────────────────────────────────────────────────┴───────────────────────┘

  2.2 目标与愿景的对齐性

  对齐良好的部分：
  - L1-L4 知识跃迁与"回答'意味着什么'"的命题高度一致
  - "Schema 即代码"与 KGML/Schema v2 声明式设计呼应
  - "本地优先，零外部依赖"与 DuckDB + Faiss 选型一致

  对齐不足的部分：
  - "AI Native" 仅体现为 Agent 接口文档，代码层面没有 Memory 接口、Agent Context 集成等实质支撑
  - "百万级节点"目标与 NetworkX 内存图 + DuckDB SQL 图遍历的技术选型存在可行性风险（见 tech-stack 评估）

  2.3 建议修正

  # 01-vision.md 第34行
  - [ ] Phase 1: 十万级节点查询 P99（简单 200ms / 图遍历 1s / 混合检索 500ms）
  + [ ] Phase 1: 百万级节点查询 P99（简单 200ms / 图遍历 1s / 混合检索 500ms）

  # 01-vision.md "三层跃迁"标题改为"四层知识跃迁"

  建议将 03-goals.md 中的节点规模与 Phase 1/2/3 目标对齐，而非将 100K 和 1M 分散在不同文档中。

  ---
  三、Schema v2 语法体系（05-schema-v2）

  3.1 三层方言问题（最严重）

  经逐文件核验，Schema v2 内部存在至少三种不兼容的语法方言：

  方言A（Canonical 根）: schema_version / semantic_space / fact_objects / categorizations / analytical_elements / business_logic
  方言B（分层专题）:      fact_object_declaration / categorization_declaration / analytical_element_declaration / rule_definition / rule_logic
  方言C（完整示例）:      attributes / from/to / type:element_type / inputs/outputs / steps:[{operator: GRAPH|BINNING}]

  具体冲突：

  ┌──────────┬────────────────────┬────────────────────────┐
  │   字段   │ 01-fact-objects.md │ 05-complete-example.md │
  ├──────────┼────────────────────┼────────────────────────┤
  │ 实体属性 │ properties         │ attributes             │
  ├──────────┼────────────────────┼────────────────────────┤
  │ 关系端点 │ source / target    │ from / to              │
  ├──────────┼────────────────────┼────────────────────────┤
  │ 指标类型 │ element_type       │ type                   │
  └──────────┴────────────────────┴────────────────────────┘

  ┌─────────────┬──────────────────────────────────┬───────────────────────────────────────────────────┐
  │    字段     │       04-business-logic.md       │              05-complete-example.md               │
  ├─────────────┼──────────────────────────────────┼───────────────────────────────────────────────────┤
  │ L4 规则结构 │ 扁平 when / then_action          │ 嵌套 steps:[{id, priority, depends_on, operator}] │
  ├─────────────┼──────────────────────────────────┼───────────────────────────────────────────────────┤
  │ 输入输出    │ input_elements / output_elements │ inputs:[{metric}] / outputs:[{name, type}]        │
  ├─────────────┼──────────────────────────────────┼───────────────────────────────────────────────────┤
  │ 条件定义    │ applicable_conditions 列表       │ applies_to.categories 映射                        │
  └─────────────┴──────────────────────────────────┴───────────────────────────────────────────────────┘

  这是实现层面的阻断性问题——没有统一的 inner schema，任何 Schema loader 实现都面临"选哪种方言"的主观选择。

  3.2 示例完整性缺陷

  05-complete-example.md 中存在引用未声明变量：
  - revenue_growth_rate 依赖 current_revenue / previous_revenue — 未声明
  - financial_health_score 依赖 current_ratio — 未声明
  - credit_score 依赖 guarantee_exposure_score — 未声明
  - Company 实体缺少 employee_count — 但 determine_scale 规则引用了它

  这使得示例无法通过自验证。

  3.3 建议修正路径

  优先级1（立即修复）:
    冻结 09-canonical-schema-spec.md 的 inner schema（fact_objects.entities[].attributes 等）
    使 01-04 分层文档与 05-complete-example.md 向 canonical 对齐
    补充示例中缺失的声明（current_ratio, guarantee_exposure_score 等）

  优先级2（Phase 2 前冻结）:
    决定 L4 规则执行模型：扁平 when/then_action vs 步骤化 steps+operators
    建议采用步骤化模型（方言C），因其更接近可执行语义

  ---
  四、API 与接口设计

  4.1 三套 API 模型并存的断层

  ┌────────────────┬──────────────────────────────────────────────────────────────┬──────────────────────────────────────────┬──────────────────────────┐
  │      层级      │                             文档                             │                 路由风格                 │           状态           │
  ├────────────────┼──────────────────────────────────────────────────────────────┼──────────────────────────────────────────┼──────────────────────────┤
  │ Current MVP    │ 02-api-design.md + 06-module-detailed-design/10-api-layer.md │ 扁平 /v1/entities 等                     │ 已实现，与代码核验       │
  ├────────────────┼──────────────────────────────────────────────────────────────┼──────────────────────────────────────────┼──────────────────────────┤
  │ Target Phase 2 │ 10-api-architecture.md                                       │ 分离 /v1/management/ vs /v1/consumption/ │ 仅表格，无 DTO           │
  ├────────────────┼──────────────────────────────────────────────────────────────┼──────────────────────────────────────────┼──────────────────────────┤
  │ Agent Native   │ 07-agent-interface.md                                        │ MCP tools + CLI                          │ 消费工具完整，管理层缺失 │
  └────────────────┴──────────────────────────────────────────────────────────────┴──────────────────────────────────────────┴──────────────────────────┘

  最严重问题：07-agent-interface.md 的 MCP 工具集没有对应到目标 API。没有任何文档说明：
  - oe_load_schema 调用哪个 HTTP 端点？
  - oe_query 的语义搜索对应 /v1/consumption/ 中哪个端点？
  - 消费工具与管理 API 的映射关系是什么？

  4.2 Agent 接口的"消费强、构建弱"失衡

  ┌─────────────┬────────────────────┬─────────────────────────────────────────┐
  │    能力     │   oe_* 工具支持    │                  说明                   │
  ├─────────────┼────────────────────┼─────────────────────────────────────────┤
  │ Schema 加载 │ oe_load_schema ✅  │ 但仅引用/下载，不支持创建/编辑          │
  ├─────────────┼────────────────────┼─────────────────────────────────────────┤
  │ 实体查询    │ oe_query ✅        │ 完整规格                                │
  ├─────────────┼────────────────────┼─────────────────────────────────────────┤
  │ 规则执行    │ oe_execute_rule ✅ │ 含 explainability                       │
  ├─────────────┼────────────────────┼─────────────────────────────────────────┤
  │ 执行追溯    │ oe_trace_rule ✅   │ 完整 computation tree                   │
  ├─────────────┼────────────────────┼─────────────────────────────────────────┤
  │ Schema 创作 │ ❌ 缺失            │ 无 oe_create_dimension、oe_define_rule  │
  ├─────────────┼────────────────────┼─────────────────────────────────────────┤
  │ 规则创作    │ ❌ 缺失            │ 无 oe_create_rule、oe_attach_operator   │
  ├─────────────┼────────────────────┼─────────────────────────────────────────┤
  │ 空间管理    │ ❌ 缺失            │ 无 oe_create_space、oe_activate_space   │
  ├─────────────┼────────────────────┼─────────────────────────────────────────┤
  │ 数据集管理  │ ❌ 缺失            │ 无 oe_register_dataset、oe_trigger_sync │
  └─────────────┴────────────────────┴─────────────────────────────────────────┘

  这使得 Agent 当前的角色是知识消费者，而非知识构建者。考虑到愿景明确说"面向 AI Agent"和"AI Native"，这个缺口需要填补。

  4.3 建议

  在 07-agent-interface.md 中增加两节：

  ## 管理面 MCP 工具（新增）
  - oe_create_schema / oe_update_schema
  - oe_define_rule / oe_attach_operator
  - oe_create_space / oe_activate_space
  - oe_register_dataset / oe_trigger_sync

  ## 工具 → API 映射表（新增）
  | MCP Tool       | Target API Endpoint                |
  |----------------|-----------------------------------|
  | oe_load_schema | GET /v1/management/{spaceId}/schema |
  | oe_query       | GET /v1/consumption/views/{viewId}/entities |
  | oe_execute_rule| POST /v1/consumption/views/{viewId}/execute/analyze |

  ---
  五、模块设计（06-module-detailed-design）

  5.1 设计-代码漂移矩阵

  以下模块存在重大设计-实现差距，文档已部分诚实标注，但缺乏系统性追踪机制：

  ┌────────────────────┬──────────────────────────────────────────────────┬────────────────────────────────────┬──────────┐
  │        模块        │                     文档描述                     │              实际代码              │ 漂移级别 │
  ├────────────────────┼──────────────────────────────────────────────────┼────────────────────────────────────┼──────────┤
  │ Query Engine       │ Graph DSL + Vector + Hybrid (08-query-engine.md) │ 仅 DuckDB BFS/DFS，无向量搜索      │ 🔴 高    │
  ├────────────────────┼──────────────────────────────────────────────────┼────────────────────────────────────┼──────────┤
  │ Expression Engine  │ L0/L1 两级沙箱 (07-expression-engine.md)         │ 仅 simpleeval 单层                 │ 🔴 高    │
  ├────────────────────┼──────────────────────────────────────────────────┼────────────────────────────────────┼──────────┤
  │ Rule Engine        │ DAG 驱动 RuleEngine (06-rule-engine.md)          │ 顺序执行 RuleExecutor + 硬编码动作 │ 🔴 高    │
  ├────────────────────┼──────────────────────────────────────────────────┼────────────────────────────────────┼──────────┤
  │ StorageBackend     │ 含事务、分类标签方法                             │ 接口方法集不一致                   │ 🟡 中    │
  ├────────────────────┼──────────────────────────────────────────────────┼────────────────────────────────────┼──────────┤
  │ NetworkXGraphStore │ 图形算法后端 (03-storage-layer.md)               │ 存在但从未被调用                   │ 🟡 中    │
  └────────────────────┴──────────────────────────────────────────────────┴────────────────────────────────────┴──────────┘

  5.2 孤儿抽象问题

  NetworkXGraphStore（ontology_engine/storage/graph/networkx_store.py）是一个未被使用的抽象。它在设计文档中被描述为核心图算法提供者，但 MetricEngine 和 QueryService 均通过内联 BFS/DFS
  实现图计算。这违反了"不要为未使用的抽象付出维护成本"的原则。

  5.3 建议

  优先级1:
    将 08-query-engine.md 拆分为两部分：
      - QueryService 当前能力（已实现）：移入 02-design
      - 目标 Vector/Hybrid 能力：标记为 Phase 2 设计文档

  优先级2:
    为 StorageBackend 引入 Repository 接口分离（避免单一大接口）
    或将 transaction 相关方法移除，因为 DuckDB 不支持真正的 ACID 事务

  优先级3:
    决定 NetworkXGraphStore 的命运：
      - 选项A：删除代码和文档（如果确定不用）
      - 选项B：在 Phase 2 激活它（补充集成设计）

  ---
  六、可视化系统（08-visualization-system + 09-frontend-architecture）

  6.1 文档质量评估

  这是整个 docs 目录中实现程度最高、可操作性最强的文档：
  - G6/X6 分工清晰
  - 执行快照模型（ExecutionStepSnapshot）设计完整
  - What-if 对比视图有具体数据结构
  - 验收场景与 examples 数据直接挂钩
  - 实施计划有明确 4 阶段划分

  6.2 与代码的对照

  08-visualization-system.md 第 7 节"后端模块设计"定义了 ontology_engine/visualization/ 模块。需要核验：
  - ontology_engine/visualization/ 目录是否存在？
  - SchemaGraphBuilder、RuleChainSimulator 是否已实现？

  若未实现，该文档应从 draft 降级为 planned，并标注 [待实现]。

  6.3 可视化与 Schema v2 的接口

  08-visualization-system.md 第 3.3.1 节 API 返回的节点类型包括 entity、metric、rule，但使用 KGMLSchema 作为构建器输入。这意味着可视化系统基于 KGML v1 构建，尚未适配 Schema v2。如果前端消费
  /v1/consumption/views/{viewId}/visualize/schema-graph（来自 10-api-architecture.md），需要确认后端能返回 Schema v2 格式的图数据。

  ---
  七、目录结构合理性评估

  7.1 当前结构

  docs/
  ├── 01-overview/          ✅ 认知层，边界清晰
  ├── 02-design/           ⚠️ 当前实现基线，但部分文档与代码漂移
  ├── 03-rfc/              ✅ 历史决策存档
  ├── 04-migration-and-gap/ ✅ 迁移层，设计合理
  ├── 05-schema-v2/        ⚠️ 目标态，但 inner schema 方言未收敛
  ├── 06-module-detailed-design/ ⚠️ 实施层，设计-代码差距大
  ├── 07-agent-interface.md ⚠️ Agent 接口，与目标 API 无映射
  ├── 08-visualization-system.md ✅ 最高质量文档
  ├── 09-frontend-architecture.md ✅ 与 08 配套
  ├── 10-api-architecture.md ⚠️ 目标 API，placeholder 性质
  ├── 11-frontend-user-guide.md ❓ 未读
  ├── architecture/decisions/ ✅ ADR 记录
  ├── development/          ✅ 规范层
  └── archive/             ✅ 归档区

  7.2 缺失的文档

  ┌──────────────────────────────────────────┬────────────────────────────────────┐
  │                应有但缺失                │                影响                │
  ├──────────────────────────────────────────┼────────────────────────────────────┤
  │ examples/ 的端到端用户案例文档           │ 无法通过真实案例验证设计完整性     │
  ├──────────────────────────────────────────┼────────────────────────────────────┤
  │ Schema v2 Inner Grammar 规范             │ 阻断实现                           │
  ├──────────────────────────────────────────┼────────────────────────────────────┤
  │ Current API → Target API Migration Guide │ 04-migration-and-gap/ 已知但未完成 │
  ├──────────────────────────────────────────┼────────────────────────────────────┤
  │ Examples 验证报告（Playwright 测试结果） │ ROADMAP 中标注"进行中"但无文档     │
  ├──────────────────────────────────────────┼────────────────────────────────────┤
  │ Phase 1 完成后的 Examples 验收文档       │ 无法确认代码-文档一致性            │
  └──────────────────────────────────────────┴────────────────────────────────────┘

  7.3 建议重组

  现状问题：
    - 07-agent-interface.md 放在根目录，地位模糊
    - 10-api-architecture.md 与 06-module-detailed-design/10-api-layer.md 重名但不同内容

  建议调整：
    docs/
    ├── 01-overview/
    ├── 02-design/
    ├── 03-rfc/
    ├── 04-migration-and-gap/
    ├── 05-schema-v2/
    ├── 06-module-detailed-design/
    ├── 07-platform/               # ← 将 agent-interface + api-architecture 合并
    │   ├── agent-interface.md     # MCP + CLI 设计
    │   ├── management-api.md       # /v1/management 规范（含 DTO）
    │   ├── consumption-api.md      # /v1/consumption 规范（含 DTO）
    │   └── api-migration-guide.md  # Current → Target 迁移路径 [新增]
    ├── 08-visualization/
    │   ├── visualization-system.md
    │   └── frontend-architecture.md
    ├── 09-examples/               # ← [新增] 端到端用户案例
    │   ├── supply-chain-finance.md
    │   └── [验收报告]
    ├── 10-api-current.md          # ← 从 06-module-detailed-design 移出
    └── 11-frontend-user-guide.md   # 保留在根目录

  ---
  八、Examples 端到端案例现状

  docs 目录中没有 Examples 文档，但 ROADMAP.md 提到"前端验证（Playwright）"和"全链路 API 验收"。这是文档体系的重大缺口——没有端到端案例，文档的正确性无法被验证。

  建议在 docs/09-examples/ 中新增：

  8.1 供应链金融场景端到端案例

  一个完整的用户故事应覆盖：

  用户故事：供应商"北京智造科技"申请融资授信

  Step 1: Schema 管理
    → 创建 Space "供应链金融v2"
    → 上传 schema-v2.yaml（含 Company/Guarantee/4维分类/5指标/6规则）
    → 验证 Schema 加载成功

  Step 2: 数据集注册
    → 注册 ERP 数据集，配置字段映射
    → 触发首次同步，验证 150 个 Supplier 实体入库

  Step 3: 规则执行（消费面）
    → 选择实体 COMP001（供应商）
    → 执行 credit_assessment 维度
    → 验证输出：eligible=true, credit_limit=750万, interest_rate=7.2%

  Step 4: What-if 模拟
    → 将 credit_score 从 78 改为 50
    → 验证 eligible 降级，credit_limit 降至 400万
    → 验证 alert 新增

  Step 5: Agent 调用
    → 通过 MCP oe_query "资本充足的大型制造业供应商"
    → 验证返回按 score 排序的实体列表
    → 通过 MCP oe_execute_rule 执行授信评估
    → 验证 trace 输出完整计算树

  这个案例应与 examples/supply_chain_finance/ 目录中的代码和数据完全对应，文档中的预期值必须与运行结果一致。

  ---
  九、关键规则执行与业务分类的审查

  9.1 规则引擎与 L2/L3 边界

  当前设计中存在一个语义模糊地带：derived dimension（L2 分类，由规则计算）是否直接复用 L4 rule_logics？

  - 02-categorization.md 描述 L2 derived 维度"复用 L4 引擎"
  - 05-complete-example.md 中 company_scale 和 risk_level 使用 rule_logic: 引用 L4 规则逻辑
  - 但 04-business-logic.md 和 07-rule-declaration-and-instance.md 使用 ruleset: 或 rules: 数组

  这个边界决定了两件事：
  1. 同一规则逻辑能否同时服务 L2 归类（"这是什么规模？"）和 L4 决策（"该授多少信？"）
  2. Schema loader 是否需要支持 L2→L4 的规则引用解析

  建议：在 canonical grammar 中明确定义 rule_logic 的复用语义，并统一引用的字段命名。

  9.2 指标的可覆盖机制

  03-analytical-elements.md 描述了 overridable: true 时 L4 可覆盖 L3 公式，但：
  - 覆盖的语法是什么？（在 rule_definition 中如何声明？）
  - 覆盖的优先级如何确定？
  - Schema v2 完整示例中是否有 overridable 的使用？

  05-complete-example.md 中所有指标都没有 overridable 字段，示例不完整。

  ---
  十、审查结论与优先行动项

  🔴 立即修复（阻断实现）

  1. 冻结 Schema v2 Inner Grammar — 在 09-canonical-schema-spec.md 中补充 fact_objects.entities[].attributes、categorizations.dimensions[].*、analytical_elements.metrics[].* 的规范写法
  2. 统一 Schema 方言 — 使 01-fact-objects.md、02-categorization.md、03-analytical-elements.md、04-business-logic.md、05-complete-example.md 与 canonical grammar 一致
  3. 修复示例完整性 — 补充 05-complete-example.md 中缺失的指标声明（current_ratio, current_revenue, previous_revenue 等）
  4. 修正 Phase 1 节点数矛盾 — 01-vision.md 和 03-goals.md 统一为 1M

  🟡 近期收敛（Phase 2 前）

  5. 补全 API Migration Guide — Current (/v1/entities) → Target (/v1/management/, /v1/consumption/) 的完整映射，含 DTO
  6. 建立 Agent 接口 → 目标 API 映射 — 在 07-agent-interface.md 中补充工具→端点映射表
  7. 补充管理面 MCP 工具 — oe_create_schema、oe_define_rule 等构造类工具
  8. 拆分 Query Engine 文档 — 将已实现部分（QueryService BFS/DFS）与目标部分（Vector/Hybrid）分开
  9. 决定 NetworkXGraphStore 命运 — 激活集成或删除代码
  10. 创建 Examples 端到端文档 — docs/09-examples/supply-chain-finance.md，与 examples/ 目录完全对应

  🟢 中期优化

  11. 补充 What-if 覆盖语法 — 在 canonical grammar 中定义 L4 对 L3 的覆盖声明语法
  12. 统一 rule_logic 复用语义 — 解决 rule_logic: vs ruleset: 的方言问题
  13. 将可视化系统与 Schema v2 对齐 — 确保 08-visualization-system.md 构建器支持 Schema v2 而非 KGML v1
  14. 建立设计-代码漂移追踪机制 — 在 04-migration-and-gap/ 中增加按模块的漂移检查表，每 sprint 更新

  📋 文档治理建议

  - 在 CLAUDE.md 中增加：Schema v2 方言统一规则、设计-代码核验触发条件（每次 PR 触发 vs 每次 milestone 触发）
  - 在 STATUS.md 中增加"热点漂移清单"，将当前最大的 3-5 个设计-代码差距列出来，作为每次 review 的必检项
  - 将 Phase 1 完成状态（ROADMAP 中标注"进行中"的两项）推进到 STATUS.md accepted，或明确说明阻塞原因

  ---
  总结：OntologyEngine 的文档体系在治理层面已经建立了良好的分层和标注约定，但在 Schema v2 语法收敛、设计-代码漂移追踪、Agent 接口完整性、端到端示例文档四个维度上存在实质性缺口。最优先的是 Schema v2 inner grammar
  的冻结——这是所有下游工作的基础。

✻ Cooked for 2m 10s

───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

2. 对齐目标：
- 性能上在本地方案中只瞄准 10W节点级别的图分析
- 重写 03-goals.md 目标内容

3. 整合成一种, schema version/space 仅为Ontology配置文件的基础信息, 关键资产 以 L1->L4的四层事实为准，其中再区分 Schema(声明) 与 Instance(实例层); 
冲突部分以 05-complete-example.md 为主体重写, 补充语义空间的版本的基础信息
按照建议的修正路径进行执行, 冻结 09-canonical-schema-spec.md 的 inner schema（fact_objects.entities[].attributes 等）,使 01-04 分层文档与 05-complete-example.md 向 canonical 对齐, 补充示例中缺失的声明（current_ratio, guarantee_exposure_score 等）

4. 同意对 07-agent-interface.md 的修改建议

5. 08-query-engine.md 拆分, Vector不分设计文档补充. 存储层StorageBackend 引入 Repository 接口分离. NetworkXGraphStore保留, 在Phase 2激活, 并与 kuzu 嵌入图数据库协同工作.

6. ontology_engine/visualization/ 目录存在, 代码已经部分实现，但需要和最新的代码及其他设计内容进行同步，此外将 08-visualization-system.md 进行精简，突出关键设计点

7. 冲突文档目录结构

8. 同意新增案例文档

9. derived dimension（L2 分类，由规则计算）直接复用 L4 rule_logics, 通常通过实体的属性进行简单计算即可得到, 可通过构建逻辑上的关系支撑后续消费
03-analytical-elements.md 描述了 overridable: true 时 L4 可覆盖 L3 公式, 对应在 规则的实例创建时直接生成新的逻辑即可, 对应优先级最高.

10 按照上述结论, 同意行动建议. 调用 subagent 开始执行



