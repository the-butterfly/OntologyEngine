# OntologyEngine 前端交互设计：知识库全生命周期

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/10-kb-process.md` + `docs/02-design/agent-memory/` | **last_verified**: 2026-04-30

---

## 0. 文档定位

本文档定义 OntologyEngine 前端在**知识库构建、管理（矛盾检测）、消费检索**三个阶段的交互设计，面向两类用户：

| 用户类型 | 核心诉求 | 交互风格 |
|---------|---------|---------|
| **知识管理员（人）** | 管控知识质量、审批矛盾、维护Schema | 表格+表单+审批流 |
| **Agent** | 记忆/检索/反思 | 3动词API（remember/recall/reflect） |

**关键原则**：Agent 通过 API 交互，人通过 UI 交互。UI 的核心价值是**让知识管理员看见 Agent 在做什么，并做出治理决策**。

---

## 1. 体验点总览

### 1.1 三阶段体验地图

```
┌─────────────────────────────────────────────────────────────────────────┐
│  构建（Build）                                                           │
│                                                                         │
│  Agent: remember(content, space_id)                                     │
│    → 双通道提取（Schema引导+开放提取）                                    │
│    → CognitiveNode 创建（belief_status=accepted/pending_review）         │
│                                                                         │
│  人: 导入文档 → 查看提取结果 → 确认/修正待审记忆                          │
│    → 体验点: 提取进度可视化、待审区队列、Schema对齐度评分                   │
├─────────────────────────────────────────────────────────────────────────┤
│  管理（Manage）                                                          │
│                                                                         │
│  Agent: reflect → 矛盾检测 → 信念修正 → 更正传播                         │
│    → 自动处理轨道B矛盾，轨道A矛盾进待审区                                  │
│                                                                         │
│  人: 审批待审区记忆 → 确认/拒绝/修改 → 查看更正历史 → 治理仪表盘          │
│    → 体验点: 矛盾看板、审批流、更正时间线、信念状态机可视化                 │
├─────────────────────────────────────────────────────────────────────────┤
│  消费（Consume）                                                         │
│                                                                         │
│  Agent: recall(query, space_id)                                         │
│    → 分层漏斗检索 → 场景感知短路 → 证据展开                              │
│                                                                         │
│  人: 搜索知识 → 查看分层结果 → 展开证据链 → 查看溯源                      │
│    → 体验点: 分层结果卡片、证据链展开、溯源高亮、Disposition调节器          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 体验点清单

| # | 阶段 | 体验点 | 面向 | 优先级 | 现有UI |
|---|------|--------|------|--------|--------|
| E1 | 构建 | 文档导入与提取进度 | 人 | P0 | ✅ InstanceDataPage |
| E2 | 构建 | 待审区队列 | 人 | P0 | ❌ 新增 |
| E3 | 构建 | Schema对齐度评分 | 人 | P1 | ❌ 新增 |
| E4 | 构建 | 双通道提取结果对比 | 人 | P2 | ❌ 新增 |
| E5 | 管理 | 矛盾看板 | 人 | P0 | ❌ 新增 |
| E6 | 管理 | 记忆审批流 | 人 | P0 | ❌ 新增 |
| E7 | 管理 | 更正时间线 | 人 | P1 | ❌ 新增 |
| E8 | 管理 | 信念状态机可视化 | 人 | P2 | ❌ 新增 |
| E9 | 管理 | 治理仪表盘 | 人 | P1 | ❌ 新增 |
| E10 | 管理 | 信念修正规则配置 | 人 | P2 | ❌ 新增 |
| E11 | 消费 | 分层结果卡片 | 人+Agent | P0 | ❌ 新增 |
| E12 | 消费 | 证据链展开 | 人 | P0 | ❌ 新增 |
| E13 | 消费 | 溯源高亮 | 人 | P1 | ❌ 新增 |
| E14 | 消费 | Disposition调节器 | 人 | P2 | ❌ 新增 |
| E15 | 消费 | 记忆可见性管理 | 人 | P1 | ❌ 新增 |
| E16 | 全流程 | Agent活动日志 | 人 | P1 | ❌ 新增 |

---

## 2. 页面路由结构（重写）

### 2.1 新路由

```
/spaces/:spaceId
├── /spaces/:spaceId/knowledge           # [新增] 知识库总览
│   ├── Tab: 构建                        #   文档导入+提取进度+待审区
│   ├── Tab: 管理                        #   矛盾看板+审批流+更正时间线
│   └── Tab: 检索                        #   分层检索+证据展开+溯源
│
├── /spaces/:spaceId/schema              # [保留] Schema 声明 (L1-L4)
├── /spaces/:spaceId/rules              # [保留] 规则管理
├── /spaces/:spaceId/instances          # [保留] 数据实例管理
├── /spaces/:spaceId/versions           # [保留] 版本历史
├── /spaces/:spaceId/visualize          # [保留] Schema 可视化
├── /spaces/:spaceId/execute            # [保留] 规则执行
└── /spaces/:spaceId/simulate           # [保留] What-If 模拟
```

### 2.2 路由变更说明

| 变更 | 原路由 | 新路由 | 原因 |
|------|--------|--------|------|
| 新增 | — | `/knowledge` | 知识库全生命周期管理是核心功能，需要独立入口 |
| 保留 | `/schema` | `/schema` | Schema管理不变 |
| 保留 | `/rules` | `/rules` | 规则管理不变 |
| 保留 | `/instances` | `/instances` | 实例管理不变，但增加CognitiveNode视图 |

---

## 3. 知识库构建页面

### 3.1 页面结构

```
┌──────────────────────────────────────────────────────────────────┐
│  知识库 → 构建                                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  📥 导入文档                                              │    │
│  │  [拖拽上传] [选择文件] [粘贴文本]                          │    │
│  │  导入配置: 切片大小 [800▼]  重叠 [100▼]  管道 [fast▼]     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  📊 提取进度                                              │    │
│  │                                                            │    │
│  │  文档: 征信报告_华为_2024Q4.pdf                            │    │
│  │  ████████████████░░░░ 80% (16/20 fragments extracted)     │    │
│  │                                                            │    │
│  │  通道A (Schema引导): 12 entities, 3 observations           │    │
│  │  通道B (开放提取):   2 observations [待审]                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  🔍 待审区 (3)                                            │    │
│  │  ┌───────────────────────────────────────────────────┐  │    │
│  │  │ observation: "华为存在关联担保风险"                    │  │    │
│  │  │ 来源: 通道B开放提取 | confidence: 0.72 | 4分钟前     │  │    │
│  │  │ [✅ 确认晋升] [❌ 拒绝] [✏️ 修改后确认]              │  │    │
│  │  └───────────────────────────────────────────────────┘  │    │
│  │  ┌───────────────────────────────────────────────────┐  │    │
│  │  │ opinion: "供应链集中度风险较高"                       │  │    │
│  │  │ 来源: Agent反思 | confidence: 0.65 | 1小时前        │  │    │
│  │  │ [✅ 确认晋升] [❌ 拒绝] [✏️ 修改后确认]              │  │    │
│  │  └───────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 交互细节

#### E1: 文档导入与提取进度

| 交互 | 说明 |
|------|------|
| 拖拽上传 | 支持PDF/TXT/CSV/JSON，拖入后自动开始切片 |
| 进度条 | 实时显示fragment数量和提取状态 |
| 通道区分 | 通道A（Schema引导）和通道B（开放提取）的结果分开展示 |
| 错误提示 | 提取失败的fragment标红，点击查看错误原因 |

**API调用**：
```
POST /v1/management/{spaceId}/ingestion/document
GET  /v1/management/{spaceId}/ingestion/status/{job_id}
```

#### E2: 待审区队列

| 交互 | 说明 |
|------|------|
| 列表展示 | belief_status=pending_review 的 CognitiveNode 列表 |
| 状态标签 | 🟡待审 / 🟢已确认 / 🔴已拒绝 |
| 批量操作 | 全选→批量确认/拒绝 |
| 筛选 | 按来源（通道A/B/Agent反思）、memory_type、时间范围 |
| 排序 | 按confidence降序、时间升序 |

**审批操作**：

| 按钮 | API | 效果 |
|------|-----|------|
| ✅ 确认晋升 | `POST /v1/management/{spaceId}/knowledge/{nodeId}/approve` | belief_status→accepted, confidence→1.0 |
| ❌ 拒绝 | `POST /v1/management/{spaceId}/knowledge/{nodeId}/reject` | belief_status→rejected |
| ✏️ 修改后确认 | `POST /v1/management/{spaceId}/knowledge/{nodeId}/approve` + body修改 | belief_status→accepted, 属性更新 |

#### E3: Schema对齐度评分

| 交互 | 说明 |
|------|------|
| 评分展示 | 每个CognitiveNode的schema_alignment_score（0-1） |
| 颜色编码 | 🟢>0.8 / 🟡0.5-0.8 / 🔴<0.5 |
| 低分原因 | 点击低分节点查看缺失字段列表 |
| 批量修复 | 选择多个低分节点→触发重新提取 |

---

## 4. 知识库管理页面

### 4.1 页面结构

```
┌──────────────────────────────────────────────────────────────────┐
│  知识库 → 管理                                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  📊 治理仪表盘                                            │    │
│  │                                                            │    │
│  │  总记忆: 12,450  │  待审: 23  │  矛盾: 5  │  过期: 120    │    │
│  │  轨道A: 8,200    │  轨道B: 4,250                          │    │
│  │                                                            │    │
│  │  [编译成本: 今日 2.3M tokens / 预算 5M]                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  ⚡ 矛盾看板 (5)                                          │    │
│  │                                                            │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐                  │    │
│  │  │ 待处理(3)│  │ 已解决(1)│  │ 已忽略(1)│                  │    │
│  │  └────┬────┘  └─────────┘  └─────────┘                  │    │
│  │       │                                                    │    │
│  │  ┌────▼────────────────────────────────────────────┐     │    │
│  │  │ factual矛盾: debt_ratio                          │     │    │
│  │  │ 旧值: 0.45 (来源: 年报)  新值: 0.65 (来源: 征信)  │     │    │
│  │  │ 实体: 华为  │  矛盾类型: factual                  │     │    │
│  │  │ [采纳新值] [保留旧值] [修改后采纳] [忽略]          │     │    │
│  │  └─────────────────────────────────────────────────┘     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  📜 更正时间线                                            │    │
│  │                                                            │    │
│  │  Day 20 ── 用户更正"诉讼已撤诉"                            │    │
│  │    │  SUPERSEDES: obs_018 → obs_007                       │    │
│  │    │  影响: mental_model_003 (已标记stale)                 │    │
│  │    │  级联: 3个下游节点受影响                               │    │
│  │    │                                                      │    │
│  │  Day 15 ── 征信报告导入                                    │    │
│  │    │  debt_ratio: 0.45 → 0.65                             │    │
│  │    │  影响: risk_grade: B → C                             │    │
│  │    ▼                                                      │    │
│  │  Day 10 ── 初始导入                                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 交互细节

#### E5: 矛盾看板

| 交互 | 说明 |
|------|------|
| 看板布局 | 三列：待处理/已解决/已忽略 |
| 矛盾卡片 | 显示contradiction_type、旧值→新值、来源、实体 |
| 解决操作 | 采纳新值/保留旧值/修改后采纳/忽略 |
| 自动解决 | 轨道B的矛盾由规则引擎自动解决，显示解决理由 |
| 筛选 | 按contradiction_type（factual/temporal/semantic）、轨道、时间 |

**API调用**：
```
GET  /v1/management/{spaceId}/knowledge/contradictions?status=pending
POST /v1/management/{spaceId}/knowledge/contradictions/{id}/resolve
```

#### E6: 记忆审批流

| 交互 | 说明 |
|------|------|
| 审批队列 | belief_status=pending_review 的记忆列表 |
| 审批详情 | 点击卡片展开完整内容、来源、confidence、proof_count |
| 审批操作 | 确认晋升/拒绝/修改后确认 |
| 审批历史 | 每条记忆的审批记录（谁、何时、什么操作） |
| 自动晋升 | confidence>0.9 + proof_count≥3 的记忆自动晋升，显示"自动晋升"标签 |

#### E7: 更正时间线

| 交互 | 说明 |
|------|------|
| 时间线布局 | 垂直时间线，按recorded_at排序 |
| 更正节点 | 显示更正内容、SUPERSEDES链、级联影响 |
| 影响展开 | 点击更正节点→展开受影响的下游节点列表 |
| 回退操作 | 点击已更正节点→"撤销更正"→SUPERSEDED→ACTIVE |
| 双时序显示 | 同时显示recorded_at（系统时间）和occurred_at（事件时间） |

**API调用**：
```
GET  /v1/management/{spaceId}/knowledge/corrections?entity_name=华为
POST /v1/management/{spaceId}/knowledge/{nodeId}/revert-correction
```

#### E9: 治理仪表盘

| 指标 | 说明 | 数据源 |
|------|------|--------|
| 总记忆数 | 按cognitive_layer和memory_type分组 | CognitiveNode COUNT |
| 待审数 | belief_status=pending_review | CognitiveNode COUNT |
| 矛盾数 | CONTRADICTS边 resolution_status=pending | CONTRADICTS COUNT |
| 过期数 | valid_to < now | CognitiveNode COUNT |
| 编译成本 | 今日Token消耗 | 编译日志 |
| 轨道分布 | 轨道A/B/待审区记忆数 | CognitiveNode GROUP BY belief_status |

---

## 5. 知识库消费页面

### 5.1 页面结构

```
┌──────────────────────────────────────────────────────────────────┐
│  知识库 → 检索                                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  🔍 搜索                                                   │    │
│  │  [华为风险等级_________________________________] [搜索]     │    │
│  │                                                            │    │
│  │  Disposition: 抽象偏好 [━━━●━━━] 证据要求 [━━━━━●━]       │    │
│  │  场景: ○快速回答  ○审计合规  ●默认                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  📋 分层结果                                               │    │
│  │                                                            │    │
│  │  ┌─ opinion 层 ─────────────────────────────────────┐   │    │
│  │  │ 🧠 mental_model: "华为风险等级B，整体可控"          │   │    │
│  │  │ confidence: 0.85 | 证据: 3条 | [展开证据链 ▼]       │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                                                            │    │
│  │  ┌─ semantic 层 ─────────────────────────────────────┐   │    │
│  │  │ 📦 entity: "华为"                                   │   │    │
│  │  │ debt_ratio=0.45 | risk_grade=B | [展开证据链 ▼]     │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  │                                                            │    │
│  │  ┌─ perception 层 ───────────────────────────────────┐   │    │
│  │  │ 📄 fragment: "2024年报：资产负债率45%..."            │   │    │
│  │  │ 来源: 年报_华为_2024.pdf 第12页 | [查看原文 ▼]       │   │    │
│  │  └──────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  🔗 证据链 (展开后)                                        │    │
│  │                                                            │    │
│  │  mental_model "华为风险等级B"                               │    │
│  │    └── entity "华为" (debt_ratio=0.45)                     │    │
│  │        ├── observation "debt_ratio连续3季度上升"            │    │
│  │        │   └── fragment "2024年报：资产负债率45%..."        │    │
│  │        └── observation "经营现金流为正"                     │    │
│  │            └── fragment "2024年报：经营现金流+120亿..."     │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 交互细节

#### E11: 分层结果卡片

| 交互 | 说明 |
|------|------|
| 分层展示 | 按cognitive_layer分组：opinion→semantic→procedure→perception |
| 层级折叠 | 每层可折叠/展开，opinion层默认展开 |
| 短路标记 | 如果检索短路，显示"⚡快速返回"标记 |
| 置信度条 | 每条结果左侧显示confidence色条 |
| 信念状态 | 🟢accepted / 🟡pending_review（附注"待确认"） |

**API调用**：
```
GET /v1/management/{spaceId}/knowledge/recall?query=华为风险等级&max_results=10
```

#### E12: 证据链展开

| 交互 | 说明 |
|------|------|
| 展开按钮 | 点击"展开证据链"→树形展示从mental_model到fragment的完整路径 |
| 节点点击 | 点击证据链中的节点→跳转到该记忆的详情页 |
| 高亮路径 | 当前展开的证据链路径高亮显示 |
| 深度控制 | 默认展开2层，可手动展开更多 |

**API调用**：
```
GET /v1/management/{spaceId}/knowledge/{nodeId}/evidence?depth=2
```

#### E13: 溯源高亮

| 交互 | 说明 |
|------|------|
| 溯源按钮 | 点击fragment的"查看原文"→跳转到原文档页面 |
| 高亮标记 | 原文中提取该fragment的段落高亮显示 |
| 边信息 | 显示COG_EXTRACTED_FROM边的confidence和offset |

#### E14: Disposition调节器

| 交互 | 说明 |
|------|------|
| 滑块 | 5个维度各有滑块，范围[0.2, 0.9] |
| 预设 | 快速回答/审计合规/默认 三种预设 |
| 实时反馈 | 调整滑块后重新检索，结果实时更新 |
| 安全边界 | 滑块范围受安全边界约束，不可超出 |

---

## 6. Agent活动日志页面

### 6.1 页面结构

```
┌──────────────────────────────────────────────────────────────────┐
│  知识库 → Agent活动                                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  📋 活动流                                                │    │
│  │                                                            │    │
│  │  10:23  Agent-001  remember  创建 observation "华为涉诉"   │    │
│  │                       → belief_status=pending_review      │    │
│  │                       → 通道B开放提取 | confidence=0.72    │    │
│  │                                                            │    │
│  │  10:20  Agent-001  reflect   检测到矛盾: debt_ratio        │    │
│  │                       → 创建 CONTRADICTS 边               │    │
│  │                       → 轨道B自动解决: 采纳新值             │    │
│  │                                                            │    │
│  │  10:15  Agent-002  recall    查询"华为风险等级"             │    │
│  │                       → 分层漏斗: opinion层命中             │    │
│  │                       → 短路返回 | 异步验证通过             │    │
│  │                                                            │    │
│  │  10:10  Agent-001  remember  创建 entity "华为"            │    │
│  │                       → 通道A Schema引导 | confidence=0.95  │    │
│  │                       → 自动晋升 (confidence>0.9)          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  筛选: [Agent▼] [操作类型▼] [时间范围▼] [belief_status▼]         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 交互细节

| 交互 | 说明 |
|------|------|
| 活动流 | 按时间倒序展示Agent的remember/recall/reflect操作 |
| 操作类型筛选 | remember/recall/reflect 三种 |
| Agent筛选 | 按Agent ID筛选 |
| 详情展开 | 点击活动→展开完整输入输出 |
| 关联跳转 | 点击node_id→跳转到记忆详情页 |

---

## 7. API端点清单（新增）

### 7.1 知识库构建

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/v1/management/{spaceId}/ingestion/document` | 文档导入 |
| GET | `/v1/management/{spaceId}/ingestion/status/{job_id}` | 提取进度 |
| GET | `/v1/management/{spaceId}/knowledge/pending-review` | 待审区列表 |
| POST | `/v1/management/{spaceId}/knowledge/{nodeId}/approve` | 确认晋升 |
| POST | `/v1/management/{spaceId}/knowledge/{nodeId}/reject` | 拒绝记忆 |
| GET | `/v1/management/{spaceId}/knowledge/{nodeId}/alignment` | Schema对齐度 |

### 7.2 知识库管理

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/v1/management/{spaceId}/knowledge/contradictions` | 矛盾列表 |
| POST | `/v1/management/{spaceId}/knowledge/contradictions/{id}/resolve` | 解决矛盾 |
| GET | `/v1/management/{spaceId}/knowledge/corrections` | 更正时间线 |
| POST | `/v1/management/{spaceId}/knowledge/{nodeId}/revert-correction` | 撤销更正 |
| GET | `/v1/management/{spaceId}/knowledge/dashboard` | 治理仪表盘 |
| GET | `/v1/management/{spaceId}/knowledge/belief-rules` | 信念修正规则 |
| PUT | `/v1/management/{spaceId}/knowledge/belief-rules/{ruleId}` | 更新规则 |

### 7.3 知识库消费

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/v1/management/{spaceId}/knowledge/recall` | 分层检索 |
| GET | `/v1/management/{spaceId}/knowledge/{nodeId}/evidence` | 证据链展开 |
| GET | `/v1/management/{spaceId}/knowledge/{nodeId}/provenance` | 溯源信息 |
| GET | `/v1/management/{spaceId}/knowledge/disposition` | Disposition配置 |
| PUT | `/v1/management/{spaceId}/knowledge/disposition` | 更新Disposition |

### 7.4 Agent活动

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/v1/management/{spaceId}/knowledge/agent-activities` | Agent活动日志 |
| GET | `/v1/management/{spaceId}/knowledge/agent-activities/{activityId}` | 活动详情 |

---

## 8. 组件设计

### 8.1 新增组件

| 组件 | 路径 | 说明 |
|------|------|------|
| `KnowledgeBuildPage` | `pages/spaces/KnowledgeBuildPage.tsx` | 构建页面 |
| `KnowledgeManagePage` | `pages/spaces/KnowledgeManagePage.tsx` | 管理页面 |
| `KnowledgeConsumePage` | `pages/spaces/KnowledgeConsumePage.tsx` | 消费页面 |
| `AgentActivityPage` | `pages/spaces/AgentActivityPage.tsx` | Agent活动日志 |
| `PendingReviewQueue` | `components/knowledge/PendingReviewQueue.tsx` | 待审区队列 |
| `ContradictionBoard` | `components/knowledge/ContradictionBoard.tsx` | 矛盾看板 |
| `CorrectionTimeline` | `components/knowledge/CorrectionTimeline.tsx` | 更正时间线 |
| `LayeredResultCards` | `components/knowledge/LayeredResultCards.tsx` | 分层结果卡片 |
| `EvidenceChainTree` | `components/knowledge/EvidenceChainTree.tsx` | 证据链树 |
| `DispositionSlider` | `components/knowledge/DispositionSlider.tsx` | Disposition调节器 |
| `GovernanceDashboard` | `components/knowledge/GovernanceDashboard.tsx` | 治理仪表盘 |
| `BeliefStateMachine` | `components/knowledge/BeliefStateMachine.tsx` | 信念状态机可视化 |

### 8.2 组件依赖关系

```
KnowledgeBuildPage
├── DocumentUploader (复用Ant Design Upload)
├── ExtractionProgress (新增)
├── PendingReviewQueue (新增)
│   └── MemoryCard (新增)
└── AlignmentScoreBar (新增)

KnowledgeManagePage
├── GovernanceDashboard (新增)
│   ├── StatCard (复用Ant Design Statistic)
│   └── CostMonitor (新增)
├── ContradictionBoard (新增)
│   └── ContradictionCard (新增)
├── CorrectionTimeline (新增)
│   └── CorrectionNode (新增)
└── BeliefStateMachine (新增)

KnowledgeConsumePage
├── SearchBar (复用Ant Design Input.Search)
├── DispositionSlider (新增)
├── LayeredResultCards (新增)
│   └── MemoryCard (复用)
└── EvidenceChainTree (新增)
    └── TreeNode (复用Ant Design Tree)
```

---

## 9. 与现有页面的关系

### 9.1 保留页面（不变）

| 页面 | 原因 |
|------|------|
| SchemaDeclarationPage | Schema L1-L4声明管理，与知识库构建互补 |
| RuleDeclarationsPage | 规则声明管理，属于Schema管理范畴 |
| RuleLogicsPage | 规则逻辑管理，属于Schema管理范畴 |
| SchemaVisualizationPage | Schema可视化，属于消费面 |
| RuleExecutionPage | 规则执行，属于消费面 |
| SimulationPage | What-If模拟，属于消费面 |

### 9.2 需要增强的页面

| 页面 | 增强内容 |
|------|---------|
| InstanceDataPage | 增加CognitiveNode视图（当前只有EntityNode视图） |
| VersionHistoryPage | 增加SUPERSEDES/CONTRADICTS边的版本历史 |
| SpaceDetailPage | 侧边栏增加"知识库"菜单项 |

### 9.3 废弃页面

无。所有现有页面保留，新增知识库相关页面。

---

## 10. 与底层设计的对齐

| 底层设计 | UI体现 | 对齐状态 |
|---------|--------|---------|
| CognitiveNode统一模型 | 所有记忆页面基于CognitiveNode展示 | ✅ |
| 双通道提取（Schema引导+开放提取） | 构建页面的通道A/B结果展示 | ✅ |
| 三区模型（轨道A/B/待审区） | 待审区队列+审批流+治理仪表盘 | ✅ |
| 分层漏斗检索 | 消费页面的分层结果卡片 | ✅ |
| DispositionProfile | DispositionSlider组件 | ✅ |
| 场景感知短路 | 搜索结果中的"⚡快速返回"标记 | ✅ |
| 证据链展开 | EvidenceChainTree组件 | ✅ |
| 双时序模型 | 更正时间线同时显示recorded_at和occurred_at | ✅ |
| SUPERSEDES/CONTRADICTS边 | 矛盾看板+更正时间线 | ✅ |
| 信念修正规则引擎 | 信念修正规则配置页面 | ✅ |
| 编译层 | 治理仪表盘的编译成本监控 | ✅ |
| 记忆可见性 | 记忆详情中的visibility标签 | ✅ |
| OCC并发控制 | UI层乐观锁提示（版本冲突时提示用户） | ✅ |

---

## 11. 实施优先级

| Phase | 页面/组件 | 体验点 | 依赖 |
|-------|----------|--------|------|
| **Phase 1** | KnowledgeBuildPage + PendingReviewQueue | E1, E2 | CognitiveNode API |
| **Phase 1** | KnowledgeManagePage + ContradictionBoard | E5, E6 | CONTRADICTS API |
| **Phase 1** | KnowledgeConsumePage + LayeredResultCards | E11, E12 | recall API |
| **Phase 2** | CorrectionTimeline + GovernanceDashboard | E7, E9 | SUPERSEDES API |
| **Phase 2** | AgentActivityPage | E16 | Agent日志API |
| **Phase 2** | DispositionSlider + AlignmentScoreBar | E3, E14 | Disposition API |
| **Phase 3** | BeliefStateMachine + 双通道对比 | E4, E8, E10 | 规则引擎API |
