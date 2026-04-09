# OntologyEngine 软件工程分析评审报告

**分析日期**: 2026-04-08  
**分析范围**: `./docs` 目录下全部文档  
**评审视角**: 软件工程管理、架构设计、技术选型  

---

## 一、执行摘要

### 总体评价

OntologyEngine 项目展现了一个**架构清晰、目标明确、文档完善**的知识库系统设计。从软件工程管理视角看，该项目具有以下突出特点：

1. **文档体系完整**: 采用分层文档结构，从愿景到实现细节覆盖全面
2. **技术决策理性**: 基于明确约束（本地优先、零依赖）做出合理取舍
3. **演进路线清晰**: 从 MVP 到 Phase 3 的阶段目标与验收标准明确
4. **架构约束严格**: 模块边界、调用关系、质量门禁定义清晰

### 关键风险点

| 风险等级 | 问题 | 影响 |
|---------|------|------|
| 🔴 高 | v2 Schema L3/L4 边界模糊 | 指标计算逻辑归属不清 |
| 🔴 高 | Formula 单行限制与 simpleeval 矛盾 | 复杂表达式无法表达 |
| 🟡 中 | Services 层职责与 Engine 重叠 | 可能导致架构腐化 |
| 🟡 中 | Cypher API 设计但底层不支持 | API 与实现脱节 |
| 🟢 低 | 目录结构重组遗留重定向文件 | 维护负担 |

---

## 二、愿景与动机分析

### 2.1 愿景清晰度: ⭐⭐⭐⭐⭐

**一句话定义**: "面向 AI Agent 的下一代知识库系统 —— 让机器像专家一样理解业务语义"

**评价**:
- ✅ 定位精准：明确区分于传统知识库（"回答'意味着什么'"）
- ✅ 目标用户清晰：AI Agent 开发者
- ✅ 价值主张明确：三层跃迁（事实→分析→决策）

**建议**: 愿景表述优秀，无需修改。

### 2.2 动机充分性: ⭐⭐⭐⭐⭐

**痛点矩阵** 构建完整，四个痛点（规则散落、数据知识割裂、AI不懂业务、专家经验流失）切中行业要害。

**竞品盲区分析** 展现了良好的市场认知：

| 方案 | 盲区 | OntologyEngine 解法 |
|------|------|---------------------|
| 传统规则引擎(Drools) | 无图计算，无向量检索 | +NetworkX +Faiss |
| 图数据库(Neo4j) | 无规则引擎，重度依赖 | 本地 DuckDB + 声明式规则 |
| 向量数据库 | 无语义推理，黑盒相似 | +规则引擎 +可解释 |
| LLM 微调 | 无法解释，更新成本高 | 规则热更新 + 可解释 |

**评价**: 动机论证充分，差异化定位清晰。

### 2.3 愿景与方案匹配度: ⭐⭐⭐⭐☆

**匹配点**:
- 愿景中的"AI Native" → Schema v2 的 LLM_INFERENCE 算子
- 愿景中的"Schema 即代码" → KGML YAML DSL
- 愿景中的"本地优先" → DuckDB + Faiss 技术栈

**不匹配点**:
- 愿景强调"让机器像专家一样理解"，但当前设计缺乏**专家知识捕获机制**（如规则推导过程的显式记录）
- "AI Native" 的 Memory 接口设计在文档中提及但未详细展开

**建议**: 补充专家知识捕获和 Memory 接口的详细设计文档。

---

## 三、目标与阶段规划分析

### 3.1 阶段目标合理性: ⭐⭐⭐⭐☆

| 阶段 | 目标 | 验收标准 | 评价 |
|------|------|----------|------|
| Phase 0 (MVP) | Schema 可定义、规则可执行 | 5条规则跑通 | ✅ 合理 |
| Phase 1 | 查询高性能、规则热更新 | P99 < 200ms | ⚠️ 需明确数据规模 |
| Phase 2 | Agent 集成、可视化 | MCP 协议支持 | ✅ 合理 |
| Phase 3 | 反馈闭环、分布式 | 自动更新知识 | ⚠️ 过于宏大，需拆分 |

**问题**: 
1. Phase 1 的"百万级节点 P99 < 200ms"未说明查询类型（点查/范围/图遍历）
2. Phase 3 "用户反馈驱动知识自动更新"是一个研究级问题，作为工程目标风险高

**建议**:
- Phase 1 按查询类型设定不同 SLA
- Phase 3 拆分为：3a) 反馈收集与标注、3b) 规则优化建议、3c) 自动更新（可选）

### 3.2 技术指标可行性: ⭐⭐⭐⭐☆

| 指标 | MVP | Phase 1 | Phase 2 | 评价 |
|------|-----|---------|---------|------|
| 节点数 | 1K | 1M | 10M | ⚠️ DuckDB 单机 10M 需验证 |
| 查询P99 | 1s | 200ms | 100ms | ✅ 合理 |
| 规则数 | 10 | 100 | 1000 | ✅ 合理 |
| 部署依赖 | 0 | 0 | 可选 | ✅ 符合本地优先 |

**风险**: DuckDB 单机处理 10M 节点 + 向量检索 + 图算法的性能需基准测试验证。

---

## 四、模块架构分析

### 4.1 分层架构合理性: ⭐⭐⭐⭐⭐

```
L3: API 层 (FastAPI/GraphQL/gRPC/MCP)
L2: 引擎层 (Query/Rule/Metric/Vector)
L1: 存储层 (DuckDB/Faiss/NetworkX)
L0: 核心层 (SchemaLoader/OperatorRegistry/ExpressionEngine)
```

**优点**:
1. 依赖方向清晰（只能向下）
2. 每层职责单一
3. 存储层抽象良好（base.py 接口 + local/ + adapters/）

**约束严格**:
- 上层只能调用 `storage/base.py` 接口 ✅
- `engine/` 禁止直接调 `storage/local/` ✅
- 无循环依赖 ✅

### 4.2 模块边界清晰度: ⭐⭐⭐⭐☆

**清晰边界**:
- Storage: GraphStore / VectorStore / MetaStore 抽象 ✅
- Engine: 四大引擎职责分离 ✅
- Core: Schema/Operator/Expression 三大核心 ✅

**模糊边界**:
- **Services 层 vs Engine 层**: `AnalysisService.execute_analysis()` 与 `RuleEngine.execute()` 职责重叠
  - Services: "协调 MetricEngine + RuleEngine"
  - 但 RuleEngine 内部也有 DAG 执行协调
  - 问题：跨引擎协调应该在哪里？

**建议**: 明确 Services 层仅做"用例编排"，所有计算逻辑下沉到 Engine。

### 4.3 扩展性设计: ⭐⭐⭐⭐⭐

**存储适配器模式**:
```python
# storage/base.py - 抽象接口
class GraphStore(ABC): ...

# storage/local/duckdb/ - 本地实现
class DuckDBStorage(GraphStore): ...

# storage/adapters/ - 外部存储
class Neo4jGraphStore(GraphStore): ...  # 预留
```

**优点**:
- 符合开闭原则
- 本地/外部存储切换无需改代码
- Phase 3 的分布式目标已预留接口

---

## 五、Schema 设计深度分析

### 5.1 Schema v1 vs v2 演进: ⭐⭐⭐⭐⭐

**v1 问题识别准确**:
1. 概念混杂（attributes 既存事实又存分析结果）✅
2. 规则与数据绑定（硬编码 entity_type）✅
3. 维度理解混乱（dimension_attributes 误用）✅
4. 缺乏分层 ✅

**v2 四层分离设计**:
```
L1 事实对象 ──▶ 定义实体/关系/属性（客观数据）
L2 归类分析 ──▶ 行业/规模/风险标签（分类维度）
L3 分析要素 ──▶ 指标定义（WHAT: 计算什么）
L4 业务逻辑 ──▶ Formula/算子/规则（HOW: 如何计算）
```

**评价**: 四层分离是核心架构改进，体现了良好的领域建模能力。

### 5.2 v2 设计的核心争议点

#### 争议 1: L3 与 L4 的边界

**当前设计**:
- L3: 仅定义指标存在和依赖，**不包含 formula**
- L4: 统一承载 formula 和算子

**问题**:
```yaml
# L3: 仅声明指标
analytical_elements:
  metrics:
    - name: asset_liability_ratio
      type: derived
      dependencies: [total_assets, total_liabilities]
      # formula 在哪里？

# L4: 规则中才定义计算
business_logic:
  rule_groups:
    - name: credit_assessment
      rules:
        - action:
            type: compute
            output: asset_liability_ratio
            formula: "total_liabilities / total_assets"  # ← 在这里
```

**矛盾**:
1. L3 说"定义 WHAT"，但资产负债率这个指标的计算方式是客观定义，不是业务逻辑
2. 同一指标在不同规则组中可能重复定义 formula，导致不一致

**建议方案**:
```yaml
# L3: 指标定义包含默认计算方式
analytical_elements:
  metrics:
    - name: asset_liability_ratio
      type: derived
      formula: "total_liabilities / total_assets"  # ← 默认计算
      
# L4: 可覆盖，但不强制
business_logic:
  rules:
    - action:
        type: compute
        metric: asset_liability_ratio
        # 不指定 formula，使用 L3 默认
```

#### 争议 2: Formula 单行限制

**当前设计**:
- Formula 必须为单行表达式
- 复杂逻辑使用结构化算子（SWITCH/BINNING/SCORECARD）

**问题**:
```yaml
# 这是多行需求，但被迫拆分成算子
condition:
  and:
    - "credit_score >= 60"
    - "guarantee_exposure < registered_capital * 2"
    - "asset_liability_ratio < 0.7"
    - "years_in_business >= 3"
```

实际上这是一个简单的 AND 组合，但 YAML 结构使其复杂化。

**与 simpleeval 的矛盾**:
- 文档说使用 simpleeval（仅支持单行）
- 但 L4 的算子体系（SCORECARD/DECISION_TABLE）实际上需要多行配置

**建议**:
1. Formula 支持多行（改用 asteval 或自定义 AST）
2. 算子用于真正的复杂结构（图遍历、模型调用）
3. 简单条件组合保持 formula 表达

### 5.3 算子体系设计: ⭐⭐⭐⭐⭐

**算子类型覆盖全面**:

| 算子 | 用途 | 复杂度 |
|------|------|--------|
| FORMULA | 简单表达式 | ⭐ |
| SWITCH | 多分支条件 | ⭐⭐ |
| BINNING | 数值分箱 | ⭐⭐ |
| SCORECARD | 评分卡模型 | ⭐⭐⭐ |
| DECISION_TABLE | 决策表 | ⭐⭐ |
| DECISION_TREE | 决策树 | ⭐⭐⭐ |
| GRAPH | 图检索计算 | ⭐⭐⭐⭐ |
| MODEL_INFERENCE | 外部模型 | ⭐⭐⭐ |
| LLM_INFERENCE | 大模型推理 | ⭐⭐⭐⭐ |

**评价**: 算子设计体现了对风控业务场景的深入理解，从简单计算到 AI 推理全覆盖。

---

## 六、API 设计分析

### 6.1 REST API 设计: ⭐⭐⭐⭐☆

**端点覆盖完整**:
- Schema 管理: `POST /v1/schema/load`, `GET /v1/schema`
- 实体管理: `POST /v1/entities`, `GET /v1/entities/{id}`, `POST /v1/entities/query`
- 关系管理: `POST /v1/edges`, `GET /v1/entities/{id}/neighbors`
- 规则执行: `POST /v1/rules/execute`, `GET /v1/rules`
- 向量检索: `POST /v1/query/vector`

**响应格式统一**:
```json
{
  "success": true,
  "data": { },
  "error": null,
  "meta": { "request_id": "uuid", "timestamp": "..." }
}
```

**问题**: `POST /v1/query/graph` 接受 Cypher，但底层 DuckDB 不支持 Cypher

**建议**: MVP 阶段移除 Cypher 接口，改为 filter-based 查询（已在 API 文档中注明推迟到 Phase 3）

### 6.2 Python API 设计: ⭐⭐⭐⭐☆

**核心类设计**:
```python
class OntologyEngine:
    @classmethod
    def from_config(cls, schema_path: str) -> "OntologyEngine"
    async def load_instances(self, instances_path: str) -> None
    async def analyze(self, entity_id: str, dimension: str) -> AnalysisResult
    async def query(self, concept: str, filters: dict | None = None) -> list[Entity]
```

**评价**: 接口简洁，符合 Python 习惯。

**缺失**:
- 缺少流式响应接口（文档中标记为 Future）
- 缺少批量操作接口（批量分析多个实体）

---

## 七、存储设计分析

### 7.1 技术选型: ⭐⭐⭐⭐⭐

**DuckDB + NetworkX + Faiss 组合**:

| 数据类型 | 技术 | 评价 |
|----------|------|------|
| 主存储 | DuckDB | ✅ OLAP 优化，单文件，零配置 |
| 图算法 | NetworkX | ✅ 按需加载，内存计算 |
| 向量索引 | Faiss | ✅ 本地文件，高性能 |
| 缓存 | diskcache | ✅ LRU + 持久化 |

**对比外部数据库**:

| 方面 | 本地存储 | 外部数据库 |
|------|----------|------------|
| 部署 | 零依赖 | 需额外部署 |
| 性能 | 单节点优秀 | 可水平扩展 |
| 容量 | 受单机限制 | 可扩展 |
| 并发 | 适合低频写入 | 高并发优化 |

**评价**: 在"本地优先"约束下，这是最优选择。

### 7.2 表结构设计: ⭐⭐⭐⭐☆

**DuckDB Schema**:
```sql
-- 实体表
CREATE TABLE entities (
    id VARCHAR PRIMARY KEY,
    concept_type VARCHAR NOT NULL,
    attributes JSON,
    created_at TIMESTAMP
);

-- 关系表
CREATE TABLE edges (
    id VARCHAR PRIMARY KEY,
    from_id VARCHAR REFERENCES entities(id),
    to_id VARCHAR REFERENCES entities(id),
    relation_type VARCHAR,
    attributes JSON
);
```

**优点**:
- JSON 存储灵活属性
- 外键约束保证一致性
- 索引覆盖常用查询

**风险**:
- JSON 字段无法直接建索引（DuckDB 支持 JSON 索引但性能不如原生列）
- 大规模数据下 JSON 解析开销

**建议**: 高频查询字段（如 status、risk_level）考虑物化为独立列。

### 7.3 NetworkX 按需加载: ⭐⭐⭐⭐⭐

**设计**:
```python
class NetworkXGraph:
    def load_from_duckdb(self, center_id: str, depth: int = 2) -> nx.DiGraph
    def find_path(self, source: str, target: str) -> list[str] | None
    def calculate_centrality(self, node_id: str, method: str) -> float
```

**评价**: 
- 避免全图加载内存爆炸
- 子图范围可控（center + depth）
- 图算法与存储解耦

---

## 八、规则引擎设计分析

### 8.1 DAG 执行模型: ⭐⭐⭐⭐⭐

**设计**:
```
Schema.yaml ──▶ Parser ──▶ DAG ──▶ Executor ──▶ Results
```

**执行流程**:
1. 筛选适用规则（by scope）
2. 构建依赖图（DAGBuilder）
3. 拓扑排序（networkx.topological_sort）
4. 顺序执行
5. 回滚机制（事务）

**评价**: DAG 模型平衡了复杂度和可解释性。

**对比其他方案**:
| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| Rete 算法 | 大量事实匹配高效 | 实现复杂，内存占用高 | Drools |
| 顺序执行 | 简单 | 无法处理依赖 | 简单规则 |
| **DAG** | 支持依赖，可解释 | 需显式声明依赖 | **本项目** |

### 8.2 表达式引擎: ⭐⭐⭐☆☆

**当前方案**: simpleeval（单行表达式）

**限制**:
- 仅支持单行
- 复杂逻辑需拆分到算子
- 与 v2 的 formula 多行需求矛盾

**建议演进**:
```
Phase 1: simpleeval（单行）
Phase 2: asteval（多行，AST 白名单）
Phase 3: 自定义 AST（完全控制）
```

### 8.3 跨引擎协调: ⭐⭐⭐☆☆

**当前设计**:
```python
class AnalysisService:
    async def _compute_l3_inputs(self, inputs: list, entity: Entity) -> dict:
        """跨引擎协调: 按需计算 L3 指标"""
        for inp in inputs:
            value = await self.metric_engine.compute(inp.metric, entity)
            results[inp.metric] = value
        return results
```

**问题**:
- L3 MetricEngine 与 L4 RuleEngine 的协调机制在文档中描述不够详细
- 缓存失效策略未明确
- 并发计算优化（并行计算无依赖指标）未展开

**建议**: 补充 ExecutionOrchestrator 的详细设计文档。

---

## 九、目录结构分析

### 9.1 当前结构评价: ⭐⭐⭐⭐☆

```
docs/
├── 01-overview/          # 概要设计（愿景、动机、目标、模块、概念、技术栈、结构）
├── 02-design/            # 详细设计（Schema、API、存储、规则引擎、Services、Formula）
├── 03-rfc/               # RFC 过程文档
├── 04-testing/           # 测试规范
├── 05-schema-v2/         # Schema v2 设计（四层分离）
├── development/          # 开发指南
├── architecture.md       # 重定向
├── concepts.md           # 重定向
├── ...
```

**优点**:
- 数字前缀保证顺序
- 分层清晰（概要→详细→RFC→测试）
- Schema v2 独立目录体现其重要性

**问题**:
1. **重定向文件过多**: architecture.md、concepts.md、project-structure.md 等均为重定向
2. **development/ 与 02-design/ 边界模糊**: api-design.md 在 development/，但 02-api-design.md 在 02-design/
3. **archive/ 未清理**: 历史文档未归档

### 9.2 建议的目录优化

```
docs/
├── 00-index.md           # 合并 README.md，统一入口
├── 01-overview/          # 保持
├── 02-design/            # 保持
├── 03-rfc/               # 保持
├── 04-testing/           # 保持
├── 05-schema-v2/         # 保持
├── 06-development/       # 重命名 development/ → 06-development/
│   ├── api-design.md     # 合并 02-design/02-api-design.md（去重）
│   ├── schema-spec.md
│   ├── storage-adapter.md
│   ├── operator.md
│   ├── code-style.md
│   └── testing.md        # 重定向到 04-testing/
├── archive/              # 清理旧文档
└── _redirects/           # 所有重定向文件移入（或删除）
    ├── architecture.md
    ├── concepts.md
    └── ...
```

---

## 十、核心设计点辩论

### 辩论 1: 是否应该自研规则引擎？

**反方观点（使用 Drools/Easy Rules）**:
- Drools 成熟稳定，RETE 算法高效
- Easy Rules 轻量，学习成本低
- 自研引擎维护成本高

**正方观点（自研）**:
- 需要图计算 + 向量检索集成，现有引擎不支持
- 需要 YAML 声明式配置，Drools 是 DRL
- 需要 AI 算子（LLM_INFERENCE），需扩展

**评审结论**: ✅ **自研合理**。理由：
1. 项目核心差异化是"图+规则+向量"融合，无现成方案
2. DAG 模型比 RETE 更适合本项目（规则数量级不大，但依赖复杂）
3. YAML 配置是产品化关键，DRL 对非技术用户不友好

### 辩论 2: Schema v2 四层分离是否过度设计？

**反方观点**:
- 四层增加了概念复杂度
- L2 归类分析是否必要？（行业/规模可直接作为属性）
- L3/L4 分离导致 formula 位置争议

**正方观点**:
- 四层对应不同变更频率（L1 稳定，L4 频繁变更）
- 归类分析支持多维度叠加（同一企业可同时是"制造业"+"中型"+"低风险"）
- 分离后规则复用性更强（同一规则可适用于多个 entity_type）

**评审结论**: ✅ **设计合理**。理由：
1. 分层是领域驱动设计（DDD）的自然结果
2. 归类分析（L2）是风控业务的核心需求（不同行业/规模政策不同）
3. 复用性提升是长期收益

**建议**: 优化 L3/L4 边界（见 5.2 节）。

### 辩论 3: DuckDB 能否支撑 Phase 2 目标？

**反方观点**:
- 10M 节点 + 向量检索 + 图算法，单机性能存疑
- DuckDB 是 OLAP 引擎，非图数据库
- 复杂图查询（多跳邻居）性能可能不达标

**正方观点**:
- DuckDB 性能优秀（TPC-H 基准测试领先）
- NetworkX 按需加载子图，避免全图遍历
- Phase 2 目标可降级（如 5M 节点）

**评审结论**: ⚠️ **需验证**。建议：
1. Phase 1 结束前做基准测试（10M 节点，典型查询场景）
2. 准备 Plan B：Neo4j 适配器提前实现
3. 明确 Phase 2 的查询类型 SLA（点查/邻居/路径）

---

## 十一、竞品对比与技术趋势

### 11.1 与主流方案对比

| 维度 | OntologyEngine | Neo4j + GDS | TigerGraph | Dgraph |
|------|----------------|-------------|------------|--------|
| 部署复杂度 | 低（零依赖） | 高 | 高 | 中 |
| 规则引擎 | 内置 | 需集成 | 需集成 | 需集成 |
| 向量检索 | 内置 | 5.11+支持 | 需集成 | 需集成 |
| 声明式配置 | KGML YAML | Cypher | GSQL | GraphQL+- |
| 本地优先 | ✅ | ❌ | ❌ | ❌ |
| 开源 | ✅ | 社区版 | 部分 | ✅ |

**差异化优势**: "本地优先 + 声明式规则 + 图+向量融合"

### 11.2 AI Agent Memory 趋势

根据检索到的资料，AI Agent Memory 系统的发展趋势：

1. **长短期记忆分离**: LlamaIndex 的 memory 设计区分 working memory 和 long-term memory
2. **知识图谱增强**: LangChain 的 GraphRAG 结合向量检索和图遍历
3. **可解释性要求**: Agent 需要解释"为什么记得这个"

**OntologyEngine 的契合度**:
- ✅ 图存储天然支持关联记忆
- ✅ 规则引擎提供可解释性
- ⚠️ 需补充 Memory 接口设计（如上下文窗口管理）

---

## 十二、补充与修正建议

### 12.1 高优先级（P0）

#### 建议 1: 明确 L3/L4 边界

**问题**: 指标计算逻辑归属不清

**方案**:
```yaml
# L3: 定义指标 + 默认计算方式
analytical_elements:
  metrics:
    - name: asset_liability_ratio
      type: derived
      default_formula: "total_liabilities / total_assets"  # 默认计算
      
# L4: 可覆盖，也可直接使用
business_logic:
  rules:
    - action:
        type: compute
        metric: asset_liability_ratio
        # 不指定 formula，使用 L3 默认
        # 或指定 override_formula 覆盖
```

#### 建议 2: Formula 支持多行

**问题**: 单行限制与 simpleeval 矛盾

**方案**:
- Phase 1: 使用 asteval 替代 simpleeval（支持多行，AST 白名单）
- Phase 2: 自定义 AST 解析（完全控制语法）

#### 建议 3: 移除 Cypher API（MVP）

**问题**: API 设计与底层实现脱节

**方案**:
- MVP 阶段移除 `POST /v1/query/graph`（Cypher）
- 仅保留 filter-based 查询
- Phase 3 实现 Neo4j 适配器后再开放

### 12.2 中优先级（P1）

#### 建议 4: 补充 Services 层详细设计

**缺失内容**:
- 跨引擎协调的详细时序图
- 缓存失效策略
- 并发控制机制

#### 建议 5: 明确图查询 SLA

**问题**: Phase 1 的"P99 < 200ms"未区分查询类型

**方案**:
| 查询类型 | 示例 | Phase 1 SLA |
|----------|------|-------------|
| 点查 | 获取单个实体 | P99 < 50ms |
| 邻居查询 | 获取一度邻居 | P99 < 100ms |
| 路径查询 | 最短路径（depth=3） | P99 < 200ms |
| 全图算法 | 中心性计算 | P99 < 1s |

#### 建议 6: 清理目录结构

**行动**:
1. 删除或归档重定向文件
2. 合并重复的 api-design.md
3. 统一 development/ 命名

### 12.3 低优先级（P2）

#### 建议 7: 补充专家知识捕获机制

**愿景匹配**: "让机器像专家一样理解"

**方案**:
- 规则执行过程记录（推导链）
- 专家反馈接口（"这个评分不合理"）
- 规则版本对比（A/B 测试）

#### 建议 8: 补充 Memory 接口设计

**愿景匹配**: "AI Native —— 为 Agent 设计 Memory 接口"

**方案**:
```python
class MemoryInterface:
    async def remember(self, entity_id: str, fact: Fact) -> None
    async def recall(self, context: Context, query: str) -> list[Memory]
    async def associate(self, entity_id: str, relation: str) -> list[Entity]
```

---

## 十三、总结

### 13.1 优势

1. **架构清晰**: 四层分离、模块边界、调用约束定义明确
2. **技术选型理性**: 在"本地优先"约束下做出最优选择
3. **文档完善**: 从愿景到实现细节覆盖全面
4. **演进路线清晰**: 阶段目标与验收标准明确
5. **差异化定位**: "图+规则+向量"融合，本地优先

### 13.2 风险

1. **L3/L4 边界模糊**: 可能导致实现混乱
2. **Formula 单行限制**: 与 simpleeval 矛盾
3. **性能未验证**: DuckDB 10M 节点性能需基准测试
4. **Services 层职责**: 与 Engine 层可能存在重叠

### 13.3 建议优先级

| 优先级 | 建议 | 预期收益 |
|--------|------|----------|
| P0 | 明确 L3/L4 边界 | 避免实现混乱 |
| P0 | Formula 支持多行 | 提升表达能力 |
| P0 | 移除 Cypher API（MVP） | 避免 API 与实现脱节 |
| P1 | 补充 Services 详细设计 | 明确跨引擎协调 |
| P1 | 明确图查询 SLA | 可验证的性能目标 |
| P1 | 清理目录结构 | 降低维护成本 |
| P2 | 补充专家知识捕获 | 匹配愿景 |
| P2 | 补充 Memory 接口 | 匹配 AI Native 定位 |

### 13.4 总体评价

**软件工程成熟度**: ⭐⭐⭐⭐☆ (4/5)

OntologyEngine 是一个**设计精良、文档完善、目标明确**的项目。核心架构（四层分离、DAG 规则引擎、本地优先存储）体现了良好的软件工程实践。主要风险在于实现细节（L3/L4 边界、Formula 限制）和性能验证。建议在 Phase 1 启动前解决 P0 级问题，确保架构稳定。

---

**报告完成时间**: 2026-04-08  
**报告作者**: AI Assistant  
**评审方法**: 文档分析 + 外部资料检索 + 设计辩论
