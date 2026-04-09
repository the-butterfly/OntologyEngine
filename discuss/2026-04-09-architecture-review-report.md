# OntologyEngine 文档体系深度评审报告

> **评审时间**: 2026-04-09
> **评审视角**: 软件工程管理与产品战略
> **分析范围**: docs/ 目录下所有设计文档

---

## 一、文档结构分析

### 1.1 当前目录结构

```
docs/
├── 01-overview/          # 概要设计 (7个文档)
│   ├── 01-vision.md
│   ├── 02-motivation.md
│   ├── 03-goals.md
│   ├── 04-modules.md
│   ├── 05-concepts.md
│   ├── 06-tech-stack.md
│   └── 07-project-structure.md
│
├── 02-design/           # 详细设计 (6个文档)
│   ├── 01-schema-spec.md
│   ├── 02-api-design.md
│   ├── 03-storage-design.md
│   ├── 04-rule-engine-design.md
│   ├── 05-services-design.md
│   └── 06-formula-spec.md
│
├── 03-rfc/              # RFC 过程文档 (3个)
│   ├── RFC-001-kgml.md
│   ├── RFC-002-storage-strategy.md
│   └── RFC-003-rule-execution-model.md
│
├── 04-testing/          # 测试指南 (1个)
│   └── 01-testing-guide.md
│
├── 05-schema-v2/        # Schema v2 (5个)
│   ├── 00-overview.md
│   ├── 01-fact-objects.md
│   ├── 02-categorization.md
│   ├── 03-analytical-elements.md
│   ├── 04-business-logic.md
│   └── 05-complete-example.md
│
├── development/         # 开发指南 (6个)
│   ├── storage-adapter.md
│   ├── operator.md
│   ├── code-style.md
│   ├── communication.md
│   ├── api-design.md
│   └── schema-spec.md
│
├── archive/             # 归档文档
│
├── 07-agent-interface.md   # 独立文档 (新)
└── 08-knowledge-retrieval.md  # 独立文档 (新)
```

### 1.2 目录结构评审

| 维度 | 评估 | 问题/建议 |
|------|------|----------|
| **层次清晰度** | ⭐⭐⭐⭐⭐ | 四层设计（概览→设计→RFC→开发）逻辑清晰 |
| **分组合理性** | ⭐⭐⭐⭐ | RFC 与正式设计分离是好实践 |
| **文档位置** | ⭐⭐⭐ | Agent 接口文档应归入 02-design 或新建 06-agent-interface/ |
| **命名一致性** | ⭐⭐⭐⭐ | `01-overview/`, `02-design/` 前缀统一 |
| **内容重复** | ⭐⭐ | architecture.md, concepts.md 等旧文档未清理，与新文档内容重叠 |

### 1.3 建议的目录重组

```
docs/
├── 01-vision-and-overview/      # 愿景与概览
│   ├── 01-vision.md
│   ├── 02-motivation.md
│   ├── 03-goals.md
│   └── 04-glossary.md           # 新增：术语表
│
├── 02-architecture/             # 架构 (合并现有)
│   ├── 01-system-overview.md    # 从 04-modules 改写
│   ├── 02-tech-stack.md         # 从 06-tech-stack 迁移
│   └── 03-project-structure.md  # 从 07-project-structure 迁移
│
├── 03-schema/                   # Schema 设计 (合并 v1/v2)
│   ├── 01-schema-spec.md        # v1 规范
│   ├── 02-schema-v2/            # v2 四层设计
│   │   ├── 00-overview.md
│   │   ├── 01-fact-objects.md
│   │   ├── ...
│   └── 03-migration-guide.md    # 新增：v1→v2 迁移指南
│
├── 04-engine/                   # 引擎设计
│   ├── 01-rule-engine.md
│   ├── 02-metric-engine.md      # 新增：L3 指标引擎
│   ├── 03-vector-engine.md      # 新增：向量引擎
│   └── 04-formula-spec.md
│
├── 05-api/                      # API 设计
│   ├── 01-rest-api.md
│   ├── 02-agent-api.md          # 从 07-agent-interface 迁移
│   └── 03-knowledge-retrieval.md # 从 08-knowledge-retrieval 迁移
│
├── 06-platform/                 # 平台化设计 (新增)
│   ├── 01-storage-extensions.md
│   ├── 02-audit-system.md
│   └── 03-schema-versioning.md
│
├── 07-development/              # 开发指南 (重组)
│   ├── testing.md
│   ├── storage-adapter.md
│   ├── operator.md
│   ├── code-style.md
│   └── communication.md
│
├── 08-rfc/                      # RFC 过程
│   └── *.md
│
├── 09-reference/                 # 参考资料 (新增)
│   ├── examples.md
│   └── faq.md
│
└── README.md                    # 导航文档
```

---

## 二、愿景与目标分析

### 2.1 愿景评审

**当前愿景**:
> "面向 AI Agent 的下一代知识库系统 —— 让机器像专家一样理解业务语义。"

**评审意见**:

| 维度 | 评估 | 问题 |
|------|------|------|
| **清晰度** | ⭐⭐⭐⭐ | "下一代知识库"定位清晰 |
| **差异化** | ⭐⭐⭐ | "像专家一样理解"较抽象，未突出技术壁垒 |
| **可衡量性** | ⭐⭐⭐ | 缺乏可量化的成功标准 |

**辩论点 1**: 愿景是否过于宏大？

当前 MVP 仅覆盖"供应链金融场景规则"，但愿景暗示"通用业务理解能力"。这是常见的 startup pitch 问题——愿景大，落地小。

**建议修正**:
> "面向 AI Agent 的结构化知识推理引擎 —— 将专家业务规则转化为可执行、可追溯、可组合的知识网络。"

### 2.2 目标分解评审

**Phase 0-3 目标评审**:

| Phase | 当前目标 | 评审意见 |
|-------|----------|----------|
| MVP | Schema 可定义、规则可执行 | ✅ 合理，与愿景一致 |
| Phase 1 | 百万节点、P99<200ms | ⚠️ DuckDB 单机难以保证 200ms |
| Phase 2 | Agent 集成、MCP 支持 | ✅ 明确 |
| Phase 3 | 反馈闭环、分布式 | ⚠️ 分布式方案未设计 |

**辩论点 2**: Phase 1 性能目标是否务实？

DuckDB 在百万节点场景下：
- 简单查询: ~50-100ms ✅
- 复杂图遍历: ~500ms-2s ❌
- 建议: P99 目标设为 **500ms** 更务实

---

## 三、核心设计点辩论

### 3.1 Schema 设计的演进 (v1 → v2)

**v1 问题** (已识别):
1. 概念混杂 —— attributes 既存事实又存分析结果
2. 规则与数据绑定 —— 硬编码 entity_type
3. 维度理解混乱
4. 缺乏分层

**v2 四层设计** (合理):
```
L1 事实对象 → L2 归类分析 → L3 分析要素 → L4 业务逻辑
```

**辩论点 3**: L3/L4 边界仍有模糊

根据讨论文档，**已决策**: L3 包含 optional `default_formula`。

**我的补充质疑**:
- L3 的 `default_formula` 与 L4 的 `formula` 冲突时，谁优先？
- L2 归类规则是否也需要 engine 执行？与 L4 规则引擎是复用还是独立？

**建议**: 在 `05-schema-v2/04-business-logic.md` 中明确：
```yaml
# L3: 通用指标定义
elements:
  - name: asset_liability_ratio
    default_formula: "total_liabilities / total_assets"  # 默认公式
    overridable: true  # 是否允许 L4 覆盖

# L4: 业务场景覆盖
logic:
  - name: BankCreditCalculation
    overrides:
      asset_liability_ratio:  # 可选：覆盖 L3 定义
        formula: "(total_liabilities + contingent_liabilities) / total_assets"
        reason: "银行需考虑或有负债"
```

### 3.2 存储策略评审

**当前设计**:
- DuckDB (主存储) + Faiss (向量) + NetworkX (按需图算法)

**辩论点 4**: DuckDB 作为主图存储的局限性

| 场景 | DuckDB 表现 | 评估 |
|------|-------------|------|
| 百万实体存储 | ✅ | 单文件，支持 JSON，查询快 |
| 图遍历 (2-3度) | ⚠️ | 需 JOIN，效率低于原生图数据库 |
| 路径查询 | ❌ | 无 Cypher 支持，只能 filter-based |
| 担保圈检测 | ⚠️ | 需 NetworkX 全量加载 |

**设计决策**: MVP 接受 filter-based 查询

**我的质疑**: 这个决策是正确的，但文档中应明确说明：
1. 哪些场景可以用 filter-based 模拟
2. 哪些场景必须等待 Neo4j 集成
3. 如何在本地优雅降级

### 3.3 规则引擎 DAG 模型评审

**当前设计**: DAG 拓扑执行 + 回滚机制

**优势**:
- 依赖关系显式化
- 支持并行优化
- 可解释性强

**辩论点 5**: DAG 模型对复杂业务规则是否足够？

当前设计的 DAG 是**规则级别**的，但实际业务中：
- 可能存在**规则内部的循环** (如迭代收敛的评分模型)
- **动态规则** (运行时添加新规则)

**建议**: Phase 2 考虑增加：
1. 循环检测 → 迭代执行支持
2. 规则热更新 → 增量 DAG 重构

---

## 四、Agent 接口设计评审 (重点)

### 4.1 接口形态选择

**当前设计**: MCP + CLI + REST + 云端/本地混合

**评审意见** ⭐⭐⭐⭐⭐: 设计非常完善，覆盖了：
- Schema 加载/同步
- 实体操作
- 规则执行 + 可解释性
- 知识检索 (向量+图混合)
- 反馈闭环 + 回退机制

### 4.2 知识检索服务评审

**Query 匹配** (08-knowledge-retrieval.md):

| 特性 | 实现状态 | 评审 |
|------|----------|------|
| 向量语义搜索 | ✅ | 完整实现 |
| 图 Schema 匹配 | ✅ | 完整实现 |
| 混合融合 | ✅ | 分数加权方案合理 |
| 路径模式 | ⚠️ | 设计了但未详细实现 |

**辩论点 6**: hybrid 模式权重分配策略

当前设计:
```yaml
weights:
  semantic: 0.6
  graph: 0.4
```

**问题**:
1. 固定权重是否适合所有场景？
2. 不同查询意图应使用不同权重
3. 是否需要自适应权重？

**建议增强**:
```yaml
# 动态权重策略
match_strategy:
  type: "adaptive" | "fixed" | "semantic_first" | "graph_first"
  fixed_weights:
    semantic: 0.6
    graph: 0.4
  # 或基于查询类型的策略
  query_type_weights:
    entity_lookup: { semantic: 0.3, graph: 0.7 }     # 查找特定实体
    semantic_search: { semantic: 0.8, graph: 0.2 }   # 语义理解
    relationship_query: { semantic: 0.2, graph: 0.8 } # 关系查询
```

### 4.3 规则追溯链路评审

**trace_mode 设计** ⭐⭐⭐⭐⭐: 非常完善

```
categorization → rule → dependency → full
```

**唯一缺失**: 追溯的**性能指标**未定义

**建议补充**:
```yaml
trace_performance:
  max_entities: 1000           # 最大追溯实体数
  max_dependency_depth: 10    # 最大依赖深度
  timeout_seconds: 5           # 超时限制
  cache_ttl_seconds: 3600     # 追溯结果缓存
```

### 4.4 反馈闭环评审

**当前设计** (08-knowledge-retrieval.md §5):

| 功能 | 实现状态 | 评审 |
|------|----------|------|
| 反馈类型 | ✅ | correction/rejection/suggestion |
| 操作历史 | ✅ | 完整的过滤和分页 |
| 回退机制 | ✅ | 影响分析 + 确认机制 |
| **缺失**: 自动闭环 | ❌ | 仅有 feedback 提交，无自动处理 |

**辩论点 7**: 反馈如何驱动知识更新？

当前设计只记录反馈，**没有**说明：
1. 如何触发 Schema/规则的自动更新？
2. 反馈如何影响向量索引？
3. 人工 review 流程是什么？

**建议补充**:
```yaml
# 反馈处理流程
feedback_processing:
  auto_apply_threshold: 3    # 同一反馈出现N次后自动处理
  human_review_threshold: 5   # 需要人工 review
  
  rules:
    - trigger:
        feedback_type: "correction"
        frequency: "high"  # > 10 次/月
      action: "create_rule_change_proposal"
      notify: ["rule_owner", "admin"]
    
    - trigger:
        feedback_type: "suggestion"
        frequency: "medium"  # 3-10 次/月
      action: "add_to_backlog"
      notify: ["rule_owner"]
```

---

## 五、平台化扩展评审 (重点)

### 5.1 用户需求分析

用户提出的扩展需求:

> 1. **配置为核心 + 平台化部署** —— 引入中间件(数据库等)作为扩展，进行中间态管理和 Schema 历史审计
> 2. **Agent 接口设计** —— MCP/CLI，已覆盖
> 3. **知识检索服务** —— 向量+图匹配，已覆盖
> 4. **反馈闭环** —— 部分覆盖，需增强

### 5.2 中间件扩展评审

**当前设计**: DuckDB 本地优先，预留 Neo4j/pgvector 接口

**缺失内容**:
1. **Schema 版本审计系统** (未设计)
2. **操作历史存储** (未设计)
3. **多环境部署** (dev/staging/prod)

**建议补充**: `docs/06-platform/02-audit-system.md`

```yaml
# 审计系统设计
audit:
  storage:
    # 本地模式 (MVP)
    local:
      enabled: true
      path: "data/audit/"
    
    # 外部数据库 (Phase 3)
    external:
      enabled: false
      type: "postgresql"  # postgresql | mysql
      dsn: "${AUDIT_DB_DSN}"
  
  # Schema 历史记录
  schema_versions:
    table: "schema_history"
    retention_days: 365
    
    columns:
      - id
      - schema_id
      - version
      - changes (JSONB)
      - diff (JSONB)
      - created_by
      - created_at
      - reason
  
  # 操作审计
  operations:
    table: "operation_log"
    retention_days: 90
    
    columns:
      - id
      - operation_id (UUID)
      - operation_type
      - entity_id
      - inputs (JSONB)
      - outputs (JSONB)
      - status
      - executed_by
      - executed_at
      - duration_ms

# Schema 变更审批
schema_change_workflow:
  enabled: true
  
  stages:
    - draft:      # 草稿
        allowed_transition: [review]
    - review:     # 评审中
        required_approvers: 1
        allowed_transition: [approved, rejected]
    - approved:   # 已批准
        allowed_transition: [deployed]
    - rejected:  # 已拒绝
        allowed_transition: []
    - deployed:  # 已部署
        allowed_transition: []
```

### 5.3 Schema 版本管理评审

**需求**: 热更新 + 回滚 + 影响分析

**当前状态**: 仅在讨论文档中提及，未正式设计

**建议设计**:

```yaml
# Schema 版本管理 API
POST /v1/schema/version

{
  "action": "publish",    # publish | rollback | diff
  "schema_id": "credit@v2.0",
  
  # 发布
  "content": { /* 新 Schema 内容 */ },
  "reason": "优化额度计算",
  "impact_analysis": {
    "affected_entities": 1523,
    "affected_rules": ["R001", "R002"],
    "breaking_changes": false
  },
  
  # 或回滚
  "rollback_to": "v1.9"
}

# 影响分析 API
GET /v1/schema/impact?from=v2.0&to=v2.1

{
  "impact_summary": {
    "entities_affected": 1523,
    "rules_affected": 5,
    "metrics_affected": 3,
    "breaking_changes": false
  },
  
  "breaking_changes": [
    {
      "type": "attribute_removed",
      "path": "Supplier.credit_limit",
      "impact": "将导致历史规则无法执行"
    }
  ],
  
  "regression_required": true,
  "estimated_downtime_seconds": 30
}
```

---

## 六、综合评分与建议

### 6.1 各维度评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **愿景清晰度** | ⭐⭐⭐ | 定位清晰但过于宏大，需收敛 |
| **目标一致性** | ⭐⭐⭐⭐ | 与愿景基本一致 |
| **技术可行性** | ⭐⭐⭐⭐ | 架构合理，技术选型得当 |
| **文档完整性** | ⭐⭐⭐⭐ | 核心设计完整 |
| **文档组织** | ⭐⭐⭐ | 结构清晰但需重组 |
| **Agent 接口** | ⭐⭐⭐⭐⭐ | MCP + CLI 设计完善 |
| **平台化扩展** | ⭐⭐ | 预留接口但未详细设计 |
| **审计与回滚** | ⭐⭐⭐ | 规则层面有回滚，Schema 层面缺失 |

### 6.2 关键设计辩论总结

| # | 辩论点 | 当前决策 | 我的建议 |
|---|--------|----------|----------|
| 1 | 愿景范围 | "下一代知识库" | 收窄为"结构化知识推理引擎" |
| 2 | Phase 1 性能目标 | P99 < 200ms | 建议 P99 < 500ms |
| 3 | L3/L4 边界 | L3 有 default_formula | 需明确覆盖机制 |
| 4 | Hybrid 权重 | 固定 0.6/0.4 | 考虑动态权重策略 |
| 5 | 反馈闭环 | 仅记录反馈 | 增加自动处理流程 |
| 6 | Schema 版本 | 未设计 | 需补充完整方案 |

### 6.3 优先行动项

**P0 (必须处理)**:
1. [ ] 清理 archive/ 和根目录的旧文档
2. [ ] 补充 Schema 版本管理设计
3. [ ] 明确 L3/L4 边界 + 覆盖机制

**P1 (建议处理)**:
4. [ ] 调整 Phase 1 性能目标为 500ms
5. [ ] 增加反馈自动处理流程
6. [ ] 设计 Hybrid 模式动态权重策略
7. [ ] 补充操作审计表结构

**P2 (可选)**:
8. [ ] 重组 docs/ 目录结构
9. [ ] 增加 Schema v1→v2 迁移指南
10. [ ] 补充术语表 (glossary)

---

## 七、附录：设计模式参考

### A. 配置驱动架构

```yaml
# config.yaml - 分层配置
ontology_engine:
  # 核心配置
  core:
    schema_dir: "./schemas"
    data_dir: "./data"
    
  # 存储配置 (可切换)
  storage:
    primary:
      type: "duckdb"           # duckdb | postgresql | mysql
      path: "./data/ontology.db"
    vector:
      type: "faiss"            # faiss | pgvector | qdrant
      path: "./data/vectors"
    cache:
      type: "diskcache"        # diskcache | redis
      ttl: 3600
    audit:
      type: "duckdb"           # duckdb | postgresql
      path: "./data/audit.db"
  
  # 引擎配置
  engines:
    rule:
      max_execution_depth: 100
      timeout_seconds: 30
    metric:
      cache_enabled: true
      cache_ttl: 3600
    vector:
      default_dimension: 1536
      top_k: 10
  
  # Agent 配置
  agent:
    mcp:
      enabled: true
      port: 8765
    cli:
      enabled: true
```

### B. 扩展点注册模式

```python
# extensions/registry.py
class ExtensionRegistry:
    """扩展点注册表"""
    
    _extensions: dict[str, Extension] = {}
    
    @classmethod
    def register(cls, name: str, ext: Extension):
        cls._extensions[name] = ext
    
    @classmethod
    def get(cls, name: str) -> Extension | None:
        return cls._extensions.get(name)
    
    @classmethod
    def enabled_extensions(cls) -> list[str]:
        return [name for name, ext in cls._extensions.items() if ext.enabled]

# 扩展类型
class Extension(Protocol):
    name: str
    enabled: bool
    version: str
    
    async def initialize(self, config: dict) -> None: ...
    async def shutdown(self) -> None: ...
```

---

**报告结束**

*评审人: AI Architecture Reviewer*
*评审日期: 2026-04-09*
