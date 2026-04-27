# OntologyEngine 使用场景案例计划 — 竞争力视角深度分析

> **status**: proposed | **phase**: phase1-2 | **last_verified**: 2026-04-24
> **参与视角**: 产品分析 / 技术架构 / 业务场景 三方辩论
> **实施计划**: `docs/plans/2026-04-25-examples-case-optimization.md`（面向 `examples/` 的落地补强方案）

---

## 一、用户视角体验亮点拆解

站在知识引擎用户的视角，OntologyEngine 最关键的 **6 个体验亮点**如下：

### 亮点 1：规则秒级热更新 — "改了就能用，不用等发版"

| 维度 | 内容 |
|------|------|
| **用户感知** | 修改一条 YAML 规则，847ms 后立即对新数据生效——传统需要 2-4 周发版周期 |
| **对标反差** | 传统规则引擎（Drools）需编译→打包→测试→发版→灰度→全量 |
| **竞品对比** | Drools：需重载 KJAR；Neo4j：无规则引擎；RAG：无规则概念 |
| **案例覆盖** | ✅ Case 1 核心演示（规则热更新 847ms） |
| **竞争力** | ★★★ 核心 — 金融合规场景 48 小时改造的硬需求 |

**辩论焦点**：产品视角认为这是杀手级体验；技术视角指出当前仅覆盖"加载新规则"，缺少"规则版本回退+影响分析"的完整闭环体验。**结论**：案例需补充版本回退+影响分析步骤。

### 亮点 2：决策全链路溯源 — "每个结论都有出处，审计不再人肉"

| 维度 | 内容 |
|------|------|
| **用户感知** | 点击任意决策结果，立即看到：哪条规则→什么条件→什么数据→来源哪个文档哪一段 |
| **对标反差** | 传统系统需人工翻阅多个系统（CRM+ERP+规则文档）拼接证据链 |
| **竞品对比** | GraphRAG：有来源但无推理链；Drools：无证据链；RAG：段落级引用无结构化链路 |
| **案例覆盖** | ✅ Case 1 部分演示（trace_to + extracted_from 证据链） |
| **竞争力** | ★★★ 核心 — 金融审计、合规检查的刚需 |

**辩论焦点**：产品视角认为互索引四关系是差异化核心；技术视角指出当前案例仅演示 extracted_from + trace_to，缺少 defined_in（规则定义来源）和 supported_by（碎片支撑实体）的端到端展示。**结论**：新案例需覆盖四种互索引关系的完整闭环。

### 亮点 3：What-If 干运行仿真 — "先试后做，不污染生产数据"

| 维度 | 内容 |
|------|------|
| **用户感知** | 调整参数→立刻看到结果变化→多方案对比→选最优→不写入数据库 |
| **对标反差** | 传统方案需搭建测试环境+复制生产数据+跑批+手动对比 |
| **竞品对比** | 无竞品提供结构化知识引擎级 What-If；Excel 场景分析无规则引擎支撑 |
| **案例覆盖** | ✅ Case 3 核心演示（三方案对比） |
| **竞争力** | ★★ 重要 — 战略决策场景强需求 |

**辩论焦点**：业务视角认为税务仿真吸引力高但受众窄；产品视角认为可泛化为"策略沙盘"能力。**结论**：保留税务案例，但补充更通用的策略仿真案例（如风控策略调整）。

### 亮点 4：Layer-R/S 双层认知 — "既找到原文，又算出结论"

| 维度 | 内容 |
|------|------|
| **用户感知** | 问一个复杂问题，系统既返回相关文档片段，又给出推理结论和证据链 |
| **对标反差** | 传统 RAG 只返回文档片段（广度层）；传统规则引擎只给出结论（深度层） |
| **竞品对比** | GraphRAG：有图+文档但无推理执行；KAG：有推理但无原文回溯闭环 |
| **案例覆盖** | ❌ 完全未覆盖 — 无案例演示 Layer-R 向量检索 + Layer-S 推理执行的协同 |
| **竞争力** | ★★★ 核心 — 这是 OntologyEngine 最核心的差异化能力 |

**辩论焦点**：三方一致认为这是**最大案例缺口**。产品视角：没有这个案例，Agent 用户无法理解"为什么比纯 RAG 更强"；技术视角：QueryEngine 实现本身还在 0%，需要分阶段推进；业务视角：BI 问数 Agent 场景是最自然的演示入口。**结论**：必须新增案例，优先级最高。

### 亮点 5：知识沉淀闭环 — "经验自动变规则，人不走知识不走"

| 维度 | 内容 |
|------|------|
| **用户感知** | 风控专家多次标记"此供应商可疑"，系统自动提示"是否升级为组织规则" |
| **对标反差** | 传统系统专家经验只在脑子里/Excel里，人走知识走 |
| **竞品对比** | 无竞品提供"个人→候选→评审→发布"的结构化知识沉淀链路 |
| **案例覆盖** | ❌ 完全未覆盖 |
| **竞争力** | ★★ 重要 — 解决组织知识传承痛点 |

**辩论焦点**：产品视角认为这是最有情感共鸣的卖点（"知识不随人走"）；技术视角指出实现完整闭环需要 Phase 2 的反馈闭环机制；业务视角认为合规/风控场景的专家经验沉淀最有商业价值。**结论**：案例可先演示半自动版本（Agent标记→人工确认→规则发布），后续补充全自动。

### 亮点 6：语义空间隔离 + 跨域协同 — "数据隔离但知识可联动"

| 维度 | 内容 |
|------|------|
| **用户感知** | 风控域和供应链域数据各自隔离，但查询"华为"时自动关联两个域的知识 |
| **对标反差** | 传统系统要么全混（风险），要么全隔（孤岛） |
| **竞品对比** | 无竞品提供"逻辑隔离+物理隔离+跨域对齐"三模式 |
| **案例覆盖** | ❌ 完全未覆盖 |
| **竞争力** | ★★ 重要 — 多域场景的架构差异化 |

**辩论焦点**：技术视角认为 same_entity_as 跨域对齐是独特设计；产品视角认为对用户而言"跨域查询自动扩展"是可见体验；业务视角认为集团型企业（多事业部）最有需求。**结论**：案例可用"集团风控+供应链双域"场景。

---

## 二、技术能力覆盖缺口矩阵

| 技术能力 | 案例覆盖度 | 用户体验关键性 | 竞争力损失 | 推荐案例方向 |
|----------|:----------:|:------------:|:----------:|------------|
| Layer-R/S 双层协同检索 | **0%** | ★★★ 极高 | 极高 — 核心差异化无法演示 | BI 问数 Agent / 知识问答 |
| 查询路由（5种类型） | **0%** | ★★ 高 | 高 — 智能路由无法展示 | 知识检索场景 |
| 互索引四关系完整闭环 | **25%** | ★★★ 极高 | 高 — 4 种关系仅演示 2 种 | 合规溯源 / 定义溯源 |
| 时序建模（as_of/历史） | **0%** | ★★ 高 | 中 — 时序查询是差异化 | 历史风险回溯 |
| 矛盾检测 | **0%** | ★★ 高 | 中 — 知识质量差异化 | 多源数据冲突 |
| 知识沉淀闭环 | **0%** | ★★ 高 | 中高 — 独特价值 | 专家经验规则化 |
| 语义空间隔离 | **0%** | ★ 辅助 | 低 | 多域企业场景 |
| 增量更新+影响分析 | **0%** | ★ 辅助 | 低 | 规则变更影响 |
| 三通道提取 | **0%** | ★ 辅助 | 低 | 文档→知识编译 |
| Bundle Search | **0%** | ★★ 高 | 中高 | 多跳推理查询 |

**关键发现**：10 项核心技术能力中，7 项案例覆盖度为 0%。最大缺口是 **Layer-R/S 双层协同**。

---

## 三、三方辩论记录

### 辩论 1：优先做哪个案例？

| 视角 | 立场 | 论据 |
|------|------|------|
| **产品** | Layer-R/S 协同检索案例 | 这是用户理解"比 RAG 强在哪"的入口，没有它其他能力都是空中楼阁 |
| **技术** | 同意，但分阶段 | QueryEngine 实现 0%，Phase 2 才能完整交付；建议先做半自动版 |
| **业务** | BI 问数 Agent 最自然 | 用户问"毛利率怎么算"，既返回定义文档又算出数值，比纯 RAG 直观 |

**决议**：✅ 新增 Case 4 — BI 问数 Agent，优先级 P0

### 辩论 2：知识沉淀闭环是否值得做案例？

| 视角 | 立场 | 论据 |
|------|------|------|
| **产品** | 必须做，最有情感共鸣 | "知识不随人走"比任何技术指标都打动决策者 |
| **技术** | 当前实现不足 | 完全自动需 Phase 2 反馈闭环，但半自动版（Agent标记→确认→发布）可现做 |
| **业务** | 风控场景最合适 | 风控专家经验结构化是金融行业刚需 |

**决议**：✅ 新增 Case 5 — 专家经验规则化，优先级 P1，半自动版

### 辩论 3：时序/矛盾检测是否独立案例？

| 视角 | 立场 | 论据 |
|------|------|------|
| **产品** | 应作为现有案例的扩展 | Case 1 加入时序回溯（"去年合规结论是什么"），Case 4 加入矛盾检测 |
| **技术** | 倾向独立小案例 | 时序和矛盾检测各自独立，混入大案例增加复杂度 |
| **业务** | 折中：时序扩展现有案例，矛盾检测独立 | 时序是现有场景的自然延伸；矛盾检测是全新场景 |

**决议**：✅ 时序扩展到 Case 1/Case 4；矛盾检测作为 Case 6 独立小案例，优先级 P2

### 辩论 4：语义空间隔离是否值得做案例？

| 视角 | 立场 | 论据 |
|------|------|------|
| **产品** | 优先级低 | 对终端用户而言，隔离是运维概念不是体验概念 |
| **技术** | 架构差异化重要 | 但确实不直接影响用户日常体验 |
| **业务** | 集团型企业有需求 | 但可以合入其他案例，不独立 |

**决议**：⚠️ 不独立做案例，合入 Case 4 或 Case 5 的跨域查询步骤

---

## 四、案例计划

### 案例优先级排序

| 优先级 | 案例 | 核心体验亮点 | 覆盖能力缺口 | 状态 |
|:------:|------|------------|------------|------|
| **P0** | Case 4: BI 智能问数 Agent | Layer-R/S 双层认知 + 查询路由 | Layer-R/S 协同、查询路由、互索引完整闭环 | 🆕 新增 |
| **P1** | Case 5: 风控专家经验规则化 | 知识沉淀闭环 + 规则版本管理 | 知识沉淀、defined_in、规则生命周期 | 🆕 新增 |
| **P1** | Case 1 扩展: 时序回溯 | 时序建模 + as_of 查询 | 时序建模、版本对比 | 📝 扩展现有 |
| **P2** | Case 6: 多源数据矛盾检测 | 矛盾检测 + 知识质量管理 | 矛盾检测、增量更新、质量检测 | 🆕 新增 |
| **P2** | Case 3 扩展: 策略沙盘 | 通用 What-If 泛化 | 模拟对比增强 | 📝 扩展现有 |
| **P3** | Case 7: 文档→知识编译 | 三通道提取 + 知识编译 | 三通道提取、知识编译 | 🆕 新增 |

---

### Case 4: BI 智能问数 Agent（P0）

**位置**: `examples/case4_bi_query_agent/`

**核心体验亮点**: Layer-R/S 双层认知协同 + 查询路由 + 互索引完整闭环

**业务场景**: 某集团财务分析师通过自然语言查询经营指标，系统既返回相关文档段落，又自动计算指标值并给出推理链。

**目标用户**: 集团财务分析师 / BI Agent 用户

**核心痛点**: IT↔组织断裂 — 数据表结构与指标定义脱节，RAG 只能找文档不能算指标

**用户旅程**:

```
Step 1: 创建分析语义空间
  ontology-cli space create --name bi_query_demo

Step 2: 加载经营分析 Schema
  ontology-cli schema load --space space.bi_query --file schema.yaml

Step 3: 导入企业实体 + 注册文档数据集
  ontology-cli entities batch-import --space space.bi_query --file instances.yaml
  ontology-cli datasets register --space space.bi_query --source-type file --uri ./docs/

Step 4: Layer-R 语义检索（"查找毛利率相关资料"）
  POST /v1/query/search
  {"text": "毛利率计算方法", "space_id": "space.bi_query", "top_k": 5}

Step 5: Layer-S 结构化推理（"计算深圳恒通的毛利率"）
  POST /v1/actions/credit_assessment/execute
  {"space_id": "space.bi_query", "entity_id": "SUP_C1"}

Step 6: 混合检索（"哪些供应商的风险等级和毛利率不匹配？"）
  POST /v1/query/hybrid
  {"query": "高风险低毛利率供应商", "space_id": "space.bi_query", "fusion": "rrf"}

Step 7: 互索引溯源（查看推理证据链）
  GET /v1/query/trace/SUP_C1
  → extracted_from: 毛利率定义 → 年报PDF第12页
  → defined_in: 评分规则 → 风控政策v2.1第3节
  → supported_by: 财务数据 → 担保合同GR_001
  → trace_to: 决策步骤 → 信用评分文档
```

**验证点**:
- [ ] Layer-R 向量检索返回相关文档碎片
- [ ] extracted_from 扩展到 Layer-S 实体
- [ ] Layer-S 执行推理计算指标值
- [ ] trace_to 回溯到原文证据
- [ ] 四种互索引关系全部可展示
- [ ] 查询路由自动选择 factual/multi-hop/analytical

---

### Case 5: 风控专家经验规则化（P1）

**位置**: `examples/case5_expert_knowledge_crystallization/`

**核心体验亮点**: 知识沉淀闭环 + 规则版本管理 + defined_in 溯源

**业务场景**: 资深风控专家的"这个圈可疑"直觉，通过 Agent 反复标记，系统自动提示升级为组织规则，经专家评审后全团队共享。

**目标用户**: 风控专家 / 知识管理员

**核心痛点**: 个人↔组织断裂 — 专家经验无法传承，退休后规则成谜

**用户旅程**:

```
Step 1: 创建风控知识空间
  ontology-cli space create --name risk_knowledge --domain risk_control

Step 2: 加载风控 Schema + 已有组织规则
  ontology-cli schema load --space space.risk_knowledge --file schema.yaml

Step 3: 专家标记个人归类规则（"担保链深度>3层=高风险"）
  POST /v1/spaces/space.risk_knowledge/schema/L2/categorizations
  {"dimension": "risk_assessment", "owner": "expert_001", "rule": "guarantee_chain_depth > 3 → HIGH_RISK"}

Step 4: 执行分析验证个人规则
  POST /v1/actions/risk_assessment/execute
  {"space_id": "space.risk_knowledge", "entity_id": "SUP_C4"}

Step 5: 系统检测使用次数达标，自动提示升级
  GET /v1/spaces/space.risk_knowledge/schema/L4/rules?candidate_for_organization=true
  → [{"rule_id": "expert_001_guarantee_chain", "usage_count": 25, "confidence": 0.85}]

Step 6: 专家评审并发布为组织规则
  POST /v1/spaces/space.risk_knowledge/schema/L4/rules
  {"name": "guarantee_chain_risk", "source": "expert_001", "status": "active", "version": 2}
  → 系统自动创建 supersedes 边链接旧版本

Step 7: 验证组织规则对所有用户生效
  POST /v1/actions/risk_assessment/execute
  {"space_id": "space.risk_knowledge", "entity_id": "SUP_C5"}
  → 规则应用了组织规则 v2，决策包含 defined_in 溯源到专家原始标记
```

**验证点**:
- [ ] 个人归类规则可创建并执行
- [ ] 使用次数累积自动标记候选
- [ ] 专家评审后发布为组织规则
- [ ] supersedes 边链接新旧版本
- [ ] defined_in 溯源到专家原始标记
- [ ] 全用户可使用新发布的组织规则

---

### Case 1 扩展: 时序回溯（P1）

**扩展内容**: 在现有合规检查案例中加入时序维度

**新增步骤**:

```
Step 7: 查询历史时点的合规结论（"SUP_C4 去年Q4的合规状态是什么？"）
  GET /v1/query/trace/SUP_C4?as_of=2025-12-31
  → 返回 2025 年底的合规结论（当时担保金额仅500万，状态为PASSED）

Step 8: 对比历史版本变化
  GET /v1/spaces/space.supply_chain_finance/instances/entities/SUP_C4?include_history=true
  → 返回所有历史版本，展示担保金额从500万→1500万的变化链
```

**验证点**:
- [ ] as_of 参数返回指定时点状态
- [ ] include_history 返回所有版本
- [ ] PRECEDES/SUCCEEDS 时序边可遍历

---

### Case 6: 多源数据矛盾检测（P2）

**位置**: `examples/case6_contradiction_detection/`

**核心体验亮点**: 矛盾检测 + 知识质量管理 + 人工介入点

**业务场景**: CRM 和 ERP 系统中同一客户地址不一致，Ingest 时自动检测矛盾并弹出确认。

**目标用户**: 数据管理员 / 知识管理员

**核心痛点**: IT↔组织断裂 — 多源数据冲突无人发现，决策基于错误数据

**用户旅程**:

```
Step 1: 创建客户知识空间
  ontology-cli space create --name customer_knowledge

Step 2: 加载客户 Schema + CRM 数据
  ontology-cli schema load --space space.customer --file schema.yaml
  ontology-cli entities batch-import --space space.customer --file crm_instances.yaml

Step 3: 导入 ERP 数据（触发矛盾检测）
  ontology-cli entities batch-import --space space.customer --file erp_instances.yaml
  → 系统检测到客户"华为技术"地址冲突：
    CRM: "深圳市龙岗区坂田街道"
    ERP: "深圳市龙岗区坂田华为基地"
  → 输出: {"contradiction_warnings": [...], "requires_confirmation": true}

Step 4: 人工确认解决矛盾
  POST /v1/spaces/space.customer/instances/entities/HW001/resolve-contradiction
  {"field": "address", "action": "accept_new", "reason": "ERP为最新注册地址"}

Step 5: 查询时返回矛盾警告
  GET /v1/views/view.customer/entities/HW001
  → 正常结果 + contradiction_warnings 标记

Step 6: 异步扫描检测潜在矛盾
  POST /v1/spaces/space.customer/scan-contradictions
  → 全量扫描，返回 Graph-Aware 检测结果（孤立社区、脆弱桥等）
```

---

### Case 3 扩展: 策略沙盘泛化（P2）

**扩展内容**: 在现有税务仿真案例中加入通用策略调整场景

**新增步骤**:

```
Step 8: 风控策略 What-If（"如果将信用评分阈值从700降到650会怎样？"）
  POST /v1/actions/credit_assessment/simulate
  {"space_id": "space.supply_chain_finance", "entity_data": {...}, "context_overrides": {"credit_score_threshold": 650}}

Step 9: 对比策略变更影响
  ontology-cli simulation compare --baseline current --scenario threshold_650
  → 显示：通过率从20%升至45%，但风险暴露增加30%
```

---

### Case 7: 文档→知识编译（P3）

**位置**: `examples/case7_knowledge_compilation/`

**核心体验亮点**: 三通道提取 + 知识编译 + 增量更新

**业务场景**: 将企业制度文档自动编译为结构化知识，SHA256 缓存实现增量处理。

**目标用户**: 知识工程师 / 文档管理员

**用户旅程**:

```
Step 1: 注册文档数据集
  ontology-cli datasets register --space space.policy --source-type file --uri ./policies/

Step 2: 执行知识编译（Ingest）
  POST /v1/ingestion/ingest
  {"space_id": "space.policy", "dataset_id": "ds_policies"}
  → Pass 1: AST确定性提取（文档结构、标题、表格）
  → Pass 2: LLM语义提取（概念、关系、规则）
  → 输出: {entities_extracted: 15, relations_extracted: 23, fragments_created: 45}

Step 3: 查看编译结果
  GET /v1/views/view.policy/entities
  → 新增的实体和关系，带 extracted_from 溯源链接

Step 4: 增量更新（仅修改的文档）
  POST /v1/incremental/import
  {"space_id": "space.policy", "dataset_id": "ds_policies", "mode": "incremental"}
  → SHA256 比对：仅 2 个文件变化，重处理 2 个文件
  → 输出: {files_processed: 2, files_unchanged: 13, entities_updated: 3}

Step 5: 影响分析
  POST /v1/incremental/impact
  {"space_id": "space.policy", "dataset_id": "ds_policies"}
  → 返回：受影响实体、受影响规则、潜在矛盾
```

---

## 五、竞争力提升路径

### 当前案例覆盖 vs 目标覆盖

| 竞争力维度 | 当前覆盖 | 新增后覆盖 | 提升 |
|-----------|:--------:|:---------:|:----:|
| Layer-R/S 双层协同 | 0% | 80% | +80% |
| 互索引完整闭环 | 25% | 90% | +65% |
| 查询路由 | 0% | 70% | +70% |
| 时序建模 | 0% | 60% | +60% |
| 矛盾检测 | 0% | 70% | +70% |
| 知识沉淀 | 0% | 60% | +60% |
| 三通道提取 | 0% | 50% | +50% |
| Bundle Search | 0% | 30% | +30% |
| 语义空间隔离 | 0% | 20% | +20% |

### 竞品对标差距缩小

| 竞品 | 当前可展示差距 | 新增后差距 |
|------|:------------:|:---------:|
| GraphRAG | 仅图+文档，无推理执行 | 仍有推理执行优势 |
| KAG | 有推理但无原文回溯闭环 | 消除回溯闭环差距 |
| Drools | 规则执行+热更新 | 热更新差距缩小 |
| 纯 RAG | 仅文档检索 | 完全展示"检索+执行+仿真"升级 |
| Neo4j | 图存储无推理 | 仍有推理+规则优势 |

---

## 六、实施路线图

```
Phase 1 (当前MVP→Phase1) ─────────────────────────────
  ├─ P0: Case 4 BI 智能问数 Agent（依赖 QueryEngine Phase 1 基础实现）
  └─ P1: Case 1 扩展时序回溯（依赖 as_of 参数实现）

Phase 2 (Phase 2 协同期) ──────────────────────────────
  ├─ P1: Case 5 专家经验规则化（依赖反馈闭环基础）
  ├─ P2: Case 3 扩展策略沙盘（增强模拟对比能力）
  └─ P2: Case 6 矛盾检测（依赖 IngestionService 矛盾检测）

Phase 3 (Phase 3 规模期) ──────────────────────────────
  └─ P3: Case 7 文档→知识编译（依赖 ExtractionPipeline）
```

---

## 七、关键讨论点（待决策）

### 🔴 讨论点 1：Case 4 是否需要等 QueryEngine 完整实现？

**选项 A**：等 Phase 2 QueryEngine 完整实现后再做 Case 4（技术完善度高）
**选项 B**：先做半自动版 Case 4（Layer-R 向量检索 + Layer-S 直接实体查询，不经过查询路由），Phase 2 补全路由能力

**倾向**：选项 B — 半自动版仍能展示 Layer-R/S 协同的核心差异化，且不阻塞案例开发

### 🟡 讨论点 2：知识沉淀案例的自动化程度

**选项 A**：全自动（usage_count≥20 自动升级）— 需要 Phase 2 反馈闭环
**选项 B**：半自动（Agent 标记→人工确认→规则发布）— 当前可实现
**选项 C**：纯手动（专家手动创建规则→系统自动创建溯源链接）— 最简实现

**倾向**：选项 B — 平衡体验完整度和实现复杂度

### 🟢 讨论点 3：案例编号规范

当前：case1 / case3（缺少 case2）
建议：
- 保持现有编号不变（case1/case3 已有引用）
- 新增案例按 case4/case5/case6/case7 编号
- 不补 case2 编号

---

*本文档由三方辩论（产品/技术/业务）综合生成，待团队评审确认后进入实施。*
