# 02-design 交叉对比分析：过时设计点与扩展需求

> **日期**: 2026-04-30 | **审查基准**: 2026-04-30-adversarial-review + 10-kb-process.md
> **定位**: 过程文档——02-design文档与审查结论的交叉对比，识别过时/需扩展设计点

---

## 一、GAP矩阵：02-design文档 vs 审查结论

### 1.1 总览

| 02-design文档 | 当前设计 | 审查要求 | GAP等级 | 影响范围 |
|--------------|---------|---------|---------|---------|
| **kuzudb-schema.md** | EntityNode + 4辅助节点表 | 统一CognitiveNode + cognitive_layer分区 | 🔴重大 | 存储层+所有上层 |
| **memory-hierarchy.md** | MemoryUnitNode + MAPPED_TO影子节点 | 统一CognitiveNode消除影子节点 | 🔴重大 | 记忆层次+检索 |
| **temporal-modeling.md** | valid_from/valid_to 单时序 | 双时序(+recorded_at T') | 🟡中等 | 时序查询+更正传播 |
| **query-routing.md** | 5种查询类型+RRF融合 | 分层漏斗+Disposition动态权重 | 🔴重大 | 检索全流程 |
| **ingestion-service.md** | 快/慢双通道+单轨矛盾检测 | Schema-Aware提取+双轨矛盾+待审区 | 🟡中等 | 构建+加工流程 |
| **memory-lifecycle.md** | 巩固/遗忘/反思 | +待审区+规则引擎+编译层 | 🟡中等 | 管理+更新流程 |
| **memory-api.md** | 3动词API | +L1/L2/L3分层+异步reflect | 🟢轻度 | 消费流程 |
| **01-schema-spec.md** | L1-L4声明层 | +Schema变更门禁+版本锁定 | 🟢轻度 | Schema治理 |

### 1.2 按全流程分类

```
构建（Build）:
  ingestion-service.md → 🔴缺Schema-Aware提取通道B
                       → 🟡缺双轨矛盾+待审区
                       → 🟢缺编译层触发

加工（Process）:
  memory-hierarchy.md → 🔴影子节点需消除
  memory-lifecycle.md → 🟡缺编译层+规则引擎
  temporal-modeling.md → 🟡缺双时序

消费（Consume）:
  query-routing.md → 🔴缺分层漏斗+Disposition
  memory-api.md → 🟢缺L1/L2/L3分层+异步reflect

更新（Update）:
  memory-lifecycle.md → 🟡缺更正传播+级联更新
  temporal-modeling.md → 🟡缺SUPERSEDES→ACTIVE回退
  01-schema-spec.md → 🟢缺Schema变更门禁
```

---

## 二、逐文档详细分析

### 2.1 kuzudb-schema.md —— 🔴重大GAP

**过时设计点**：

| # | 当前设计 | 问题 | 审查要求 |
|---|---------|------|---------|
| 1 | 5个独立节点表（EntityNode, RuleDefinitionNode, KnowledgeFragmentNode, CategoryTagNode, MetricValueNode） | 与CognitiveNode统一节点设计冲突 | 统一CognitiveNode + cognitive_layer分区 |
| 2 | EntityNode.attributes MAP(STRING, STRING) | 全JSON无强类型列，查询性能风险 | 保留核心字段为强类型列 |
| 3 | 无version字段 | 无法支持乐观并发控制(OCC) | 增加version INT64 |
| 4 | 无recorded_at字段 | 无法支持双时序 | 增加recorded_at DATETIME |
| 5 | 无cognitive_layer字段 | 无法支持认知分层查询 | 增加cognitive_layer STRING |
| 6 | 无belief_status字段 | 无法支持信念状态（accepted/rejected/pending） | 增加belief_status STRING |
| 7 | 无visibility字段 | 无法支持记忆隐私边界 | 增加visibility STRING |
| 8 | 无compiled_at字段 | 无法支持编译产物一致性标记 | 增加compiled_at DATETIME |
| 9 | 无superseded_by字段 | 无法支持SUPERSEDES链 | 增加superseded_by STRING |
| 10 | 边表缺SUPERSEDES/CONTRADICTS | 无法支持矛盾链和版本链 | 增加SUPERSEDES/CONTRADICTS边 |

**典型案例**：并发更新华为debt_ratio

```
当前设计：EntityNode.attributes MAP(STRING, STRING)
  Agent A写入 debt_ratio=0.65 → 覆盖整个attributes
  Agent B写入 revenue=8000亿 → 覆盖整个attributes（debt_ratio丢失）

需要：字段级OCC
  CognitiveNode增加version字段
  attributes更新采用merge而非replace
```

### 2.2 memory-hierarchy.md —— 🔴重大GAP

**过时设计点**：

| # | 当前设计 | 问题 | 审查要求 |
|---|---------|------|---------|
| 1 | MemoryUnitNode + EntityNode通过MAPPED_TO影子节点关联 | 同步开销+数据不一致风险 | 统一CognitiveNode消除影子节点 |
| 2 | memory_type: entity/observation/mental_model/episode/procedure/rule | 缺opinion类型（与observation区分） | 增加opinion类型 |
| 3 | 类型权重静态（mental_model=3.0, entity=2.0...） | 无Disposition动态调整 | DispositionProfile驱动动态权重 |
| 4 | ChromaDB统一memory_unit_text集合 | 无cognitive_layer过滤 | 按cognitive_layer分区或metadata过滤 |
| 5 | 巩固=类型升级（fragment→observation→entity→mental_model） | 缺编译层概念（Entity Page/Topic Page） | 增加Compiled Page作为巩固产物 |

**关键辩论**：影子节点是否应该立即消除？

```
正方（立即消除）：
  - MAPPED_TO同步开销真实存在
  - 双节点数据不一致风险高
  - 统一CognitiveNode简化所有上层逻辑

反方（渐进消除）：
  - EntityNode有Schema约束的强类型属性
  - 立即消除需要重写大量上层代码
  - JSON attributes的类型安全丧失

调和（审查结论）：
  Phase 1a: CognitiveNode保留核心字段为强类型列
  Phase 1b: 验证JSON查询性能后逐步迁移
```

### 2.3 temporal-modeling.md —— 🟡中等GAP

**过时设计点**：

| # | 当前设计 | 问题 | 审查要求 |
|---|---------|------|---------|
| 1 | 只有valid_from/valid_to | 无法区分"事件何时发生"与"系统何时知晓" | 增加recorded_at (T') |
| 2 | 版本限制策略：删除最老版本 | 被淘汰版本如果被引用，处理不完整 | 先归档再删除+引用检查 |
| 3 | 无SUPERSEDES边语义 | 更正传播无法在图中表达 | 增加SUPERSEDES/CONTRADICTS边 |
| 4 | 时序查询只有4种模式 | 缺"更正历史"查询（基于recorded_at） | 增加correction_history查询 |

**典型案例**：Day 20用户更正"诉讼已撤诉"

```
当前设计：
  旧observation(valid_from=Day10, valid_to=Day20) → 设置valid_to=Day20
  新observation(valid_from=Day20, valid_to=null) 创建

问题：
  - 无法表达"系统在Day20收到更正，但撤诉实际发生在Day18"
  - recorded_at=Day20, occurred_at=Day18 两者不同
  - 级联更新应基于occurred_at而非recorded_at

需要：
  双时序：valid_from/valid_to(事实有效时间) + recorded_at(系统记录时间)
  SUPERSEDES边：新observation →[SUPERSEDES]→ 旧observation
```

### 2.4 query-routing.md —— 🔴重大GAP

**过时设计点**：

| # | 当前设计 | 问题 | 审查要求 |
|---|---------|------|---------|
| 1 | 5种查询类型（factual/multi-hop/temporal/analytical/mixed） | 无分层漏斗概念 | 分层漏斗：mental_model→entity→observation→fragment |
| 2 | 特征词匹配O(1) | 无法利用Schema结构引导检索 | Schema-Aware检索路由 |
| 3 | 静态RRF权重 | 无Disposition动态调整 | DispositionProfile驱动权重 |
| 4 | 降级链（单路失败→备选路径） | 无短路机制+异步验证 | 场景感知短路+降级策略 |
| 5 | 无EvidenceExpander | 短路返回后无法展开证据 | 多层证据展开 |

**关键辩论**：5种查询类型 vs 分层漏斗是否互斥？

```
分析：两者不互斥，而是不同维度的路由策略

5种查询类型 → 决定"用什么方式检索"（向量/图遍历/时序/规则/协同）
分层漏斗 → 决定"按什么顺序返回"（mental_model优先→fragment兜底）

融合设计：
  1. 查询类型识别 → 决定检索路径和边权重
  2. 分层漏斗 → 决定结果排序和短路策略
  3. DispositionProfile → 动态调整类型权重和短路阈值
  4. 场景感知 → 审计场景禁止短路，快速场景允许短路
```

### 2.5 ingestion-service.md —— 🟡中等GAP

**过时设计点**：

| # | 当前设计 | 问题 | 审查要求 |
|---|---------|------|---------|
| 1 | 快速通道写入EntityNode | 应写入CognitiveNode | 统一CognitiveNode |
| 2 | 慢速通道因果推断+实体边 | 缺Schema-Aware提取 | 双通道提取（Schema引导+开放提取） |
| 3 | 单轨矛盾检测（人工确认） | 缺双轨（企业+Agent自治） | 双轨矛盾治理 |
| 4 | 矛盾检测只有Ingest时+后台扫描 | 缺待审区 | Agent生成记忆默认进待审区 |
| 5 | Fragment生命周期缺STALE→ACTIVE回退 | 状态机不完整 | 补充回退路径 |

**典型案例**：Agent发现风险信号

```
当前设计：
  Agent生成observation → 需要人工确认（contradiction_report）
  → 在确认前，observation不可被检索

审查要求：
  Agent生成observation → 默认进入待审区（belief_status=pending_review）
  → 待审区记忆可被检索但带pending_review标记
  → 人工确认后晋升到轨道A或降级到轨道B

关键区别：
  当前：矛盾=阻塞（阻止写入）
  审查：矛盾=分流（待审区缓冲，不阻塞Agent工作流）
```

### 2.6 memory-lifecycle.md —— 🟡中等GAP

**过时设计点**：

| # | 当前设计 | 问题 | 审查要求 |
|---|---------|------|---------|
| 1 | 巩固=类型升级 | 缺编译层（Entity Page/Topic Page） | 编译层作为巩固的高级产物 |
| 2 | 遗忘=强度衰减 | 缺更正传播机制 | CorrectionPropagation |
| 3 | 反思=检索+LLM分析 | 缺异步编排 | reflect返回reflection_id |
| 4 | 无信念修正规则引擎 | 矛盾处理逻辑硬编码 | 可配置规则引擎+优先级 |
| 5 | 梦境循环未分析资源消耗 | 全量扫描不可行 | 采样策略 |
| 6 | 无DispositionProfile初始化 | 新space无默认性格 | 行业模板+行为学习 |

### 2.7 memory-api.md —— 🟢轻度GAP

**过时设计点**：

| # | 当前设计 | 问题 | 审查要求 |
|---|---------|------|---------|
| 1 | 3动词API（remember/recall/reflect） | 参数膨胀风险 | L1/L2/L3分层抽象 |
| 2 | reflect同步返回 | 内部编排复杂度高 | 异步编排+reflection_id |
| 3 | recall无场景感知 | 审计场景需要全层检索 | 场景感知参数 |
| 4 | 无记忆可见性控制 | 多用户隐私问题 | visibility参数 |

### 2.8 01-schema-spec.md —— 🟢轻度GAP

**过时设计点**：

| # | 当前设计 | 问题 | 审查要求 |
|---|---------|------|---------|
| 1 | Schema只有L1-L4声明 | 缺Schema变更影响分析 | SchemaMigrationImpactAnalyzer |
| 2 | 无Schema版本锁定 | 新增必填字段后存量记忆alignment下降 | 版本锁定+惰性重算 |
| 3 | 无alignment_score定义 | Schema-Memory对齐度无法量化 | alignment_score计算规则 |

---

## 三、全流程视角：构建-加工-消费-更新

### 3.1 构建流程（Build）

```
当前02-design覆盖：
  ingestion-service.md: 快/慢双通道 ✅
  kuzudb-schema.md: EntityNode写入 ✅

缺失：
  ❌ Schema-Aware提取（双通道：Schema引导+开放提取）
  ❌ CognitiveNode统一写入（替代EntityNode+MemoryUnitNode）
  ❌ 双时序写入（recorded_at同步写入）
  ❌ 待审区分流（Agent生成记忆默认pending_review）
  ❌ OCC写入（version检查）
```

### 3.2 加工流程（Process）

```
当前02-design覆盖：
  memory-lifecycle.md: 巩固/遗忘/反思 ✅
  memory-hierarchy.md: 类型升级路径 ✅

缺失：
  ❌ 编译层（Entity Page/Topic Page生成）
  ❌ 编译产物一致性标记（compiled_at vs updated_at）
  ❌ 成本感知编译策略（高频预编译+低频按需编译）
  ❌ 编译防抖策略
  ❌ 信念修正规则引擎
```

### 3.3 消费流程（Consume）

```
当前02-design覆盖：
  query-routing.md: 5种查询类型+降级链 ✅
  memory-api.md: 3动词API ✅

缺失：
  ❌ 分层漏斗检索（mental_model→entity→observation→fragment）
  ❌ DispositionProfile动态权重
  ❌ 场景感知短路策略
  ❌ 短路后异步验证
  ❌ EvidenceExpander多层证据展开
  ❌ 冷启动降级策略
  ❌ API L1/L2/L3分层
  ❌ reflect异步编排
```

### 3.4 更新流程（Update）

```
当前02-design覆盖：
  temporal-modeling.md: valid_from/valid_to版本管理 ✅
  memory-lifecycle.md: 遗忘衰减 ✅

缺失：
  ❌ 双时序（recorded_at T'）
  ❌ SUPERSEDES/CONTRADICTS边
  ❌ 更正传播（CorrectionPropagation）
  ❌ 状态机回退路径（SUPERSEDED→ACTIVE, STALE→ACTIVE）
  ❌ Schema变更门禁
  ❌ Schema版本锁定+惰性重算
  ❌ 级联更新防风暴
```

---

## 四、Agent与人协作：当前02-design的盲区

### 4.1 当前设计中的协作模型

| 文档 | 协作设计 | 覆盖程度 |
|------|---------|---------|
| ingestion-service.md | 矛盾检测→人工确认 | 仅构建阶段 |
| memory-lifecycle.md | 反思→矛盾报告 | 仅发现阶段 |
| memory-api.md | 无协作API | ❌ |

### 4.2 缺失的协作场景

| 场景 | 当前状态 | 需要的设计 |
|------|---------|-----------|
| Agent发现风险→人工确认是否影响企业知识 | 无 | 待审区+晋升审批流 |
| 人工更正Agent结论→更正传播到下游 | 无 | CorrectionPropagation+审批流 |
| Agent建议Schema扩展→人工审批 | 无 | SchemaMigrationImpactAnalyzer+审批流 |
| 多Agent协作→冲突解决 | 无 | 冲突检测+优先级排序 |
| 人工设置记忆保护→Agent不可遗忘 | feedback_weight≥0.9 | 已有但缺显式API |
| Agent反思结果→人工审核 | 无 | reflect结果审核流 |

### 4.3 协作流程设计建议

```
Agent自治区（轨道B）          待审区              企业治理区（轨道A）
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│ Agent自动     │    │ belief_status=    │    │ 人工确认的    │
│ 生成/更新记忆 │───▶│ pending_review    │───▶│ 正式知识      │
│               │    │                   │    │               │
│ 可自由检索    │    │ 可检索但带标记    │    │ 可自由检索    │
│ 可自由遗忘    │    │ 不可遗忘          │    │ 不可自由遗忘  │
│ confidence自评│    │ 等待人工决策      │    │ confidence=1.0│
└──────────────┘    └──────────────────┘    └──────────────┘
       │                    │                       │
       │ 自动晋升            │ 人工审批               │ 降级
       │ (confidence>0.9    │ (approve/reject/       │ (人工标记
       │  + alignment>0.9)  │  modify)               │  过时)
       └────────────────────┴───────────────────────┘
```

---

## 五、需要讨论的关键决策点

### 决策1：CognitiveNode迁移策略

**选项A**：立即重写kuzudb-schema.md，5表合一为CognitiveNode
- 优点：设计一致性最高，无技术债
- 风险：上层代码全部需要重写，MVP功能回归风险高

**选项B**：CognitiveNode作为视图层，底层保留EntityNode等5表
- 优点：底层不变，上层通过视图访问
- 风险：KuzuDB不支持视图，需要应用层实现

**选项C**：渐进式迁移——Phase 1增加CognitiveNode表+核心强类型列，Phase 2逐步合并
- 优点：风险可控，可验证性能
- 风险：过渡期双表并存

### 决策2：分层漏斗与5种查询类型的融合方式

**选项A**：分层漏斗替代5种查询类型
- 优点：设计简洁
- 风险：丧失查询类型差异化能力

**选项B**：5种查询类型决定检索路径，分层漏斗决定结果排序
- 优点：两个维度独立，可组合
- 风险：复杂度增加

**选项C**：分层漏斗为主，查询类型作为漏斗内部的检索策略参数
- 优点：分层漏斗是主流程，查询类型是内部实现细节
- 风险：查询类型的差异化可能被漏斗的短路机制削弱

### 决策3：Agent与人协作的审批粒度

**选项A**：粗粒度——只区分轨道A/B，晋升/降级是唯一审批点
- 优点：实现简单
- 风险：无法处理细粒度场景（如"只确认部分属性"）

**选项B**：中粒度——区分轨道A/B/待审区，支持字段级审批
- 优点：灵活
- 风险：字段级审批实现复杂

**选项C**：细粒度——每个记忆变更都有审批流，支持部分确认+条件确认
- 优点：最灵活
- 风险：审批流过于复杂，可能成为瓶颈
