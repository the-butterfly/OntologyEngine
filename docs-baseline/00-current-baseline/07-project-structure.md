# 项目结构（当前基线）

> **status**: verified | **phase**: mvp+phase1 | **source_of_truth**: 本文件 | **last_verified**: 2026-04-19
> **[已核对代码]**: 与 `ontology_engine/` 实际目录结构逐项核验

本文档描述 OntologyEngine 的**当前实际代码结构**，与代码库逐一核验。所有路径、模块名、文件大小均基于 2026-04-19 代码库快照。

## 主包结构

```
ontology_engine/                     # 主包
├── __init__.py                      # 包入口
│
├── core/                            # 核心层 (L0)
│   ├── schema/                      # Schema 管理
│   │   ├── models.py                # Pydantic 模型 (30K+, 含 Schema v2 全量模型)
│   │   └── loader.py                # KGML YAML 加载与解析
│   ├── instances/                   # 实例加载
│   │   └── loader.py                # Entity/Relation 实例加载
│   ├── semantic_space/              # 语义空间管理
│   │   ├── models.py                # 空间模型定义
│   │   ├── rule_models.py           # 规则相关模型
│   │   ├── loader.py                # 空间配置加载
│   │   ├── state_machine.py         # 空间状态机
│   │   └── storage.py               # 空间持久化
│   ├── dataset/                     # 数据集模型
│   │   └── models.py                # Dataset/ChangeBatch 等模型
│   └── types/                       # 类型定义
│       └── __init__.py
│
├── storage/                         # 存储层 (L1)
│   ├── base.py                      # 存储抽象接口 (19K+)
│   ├── duckdb/                      # DuckDB 主存储
│   │   └── store.py                 # DuckDB 实现 (72K+, 30+ CRUD 方法)
│   ├── graph/                       # 图存储
│   │   ├── networkx_store.py        # NetworkX 图存储实现
│   │   └── kuzu_store.py            # kuzu 图存储实现 (Phase 2)
│   ├── vector/                      # 向量存储
│   │   └── local_vector_store.py    # Faiss 本地向量存储
│   ├── dual_write.py                # 图+关系双写协调器
│   └── retrieval.py                 # 混合检索 (向量+图+SQL)
│
├── engine/                          # 引擎层 (L2)
│   ├── rule/                        # 规则引擎
│   │   ├── models.py                # 规则模型 (11K+)
│   │   ├── executor.py              # 规则执行器 (18K+)
│   │   ├── evaluator.py             # 条件评估器
│   │   └── operators/               # 算子库
│   │       ├── base.py              # 算子基类
│   │       ├── registry.py          # 算子注册中心 (13K+)
│   │       ├── compute.py           # 计算算子 (BINNING 等)
│   │       ├── decision_table.py    # 决策表算子
│   │       ├── weighted_sum.py      # 加权求和算子
│   │       ├── switch.py            # 分支算子 (11K+)
│   │       ├── llm_judge.py         # LLM 定性分析算子
│   │       ├── alert.py             # 告警算子
│   │       └── set_flag.py          # 标记算子
│   ├── metric/                     # 指标引擎
│   │   ├── engine.py                # 指标计算引擎 (15K+)
│   │   ├── dag.py                   # DAG 依赖解析
│   │   ├── graph_operators.py      # 图指标算子
│   │   └── errors.py               # 指标错误定义
│   ├── categorization/             # 归类引擎
│   │   ├── engine.py               # 归类编译+执行
│   │   └── models.py               # 归类模型
│   ├── expression/                 # 表达式引擎
│   │   └── engine.py               # L0 simpleeval + L1 AST 沙箱
│   ├── query/                     # 查询引擎 (占位，Phase 2)
│   │   └── __init__.py
│   ├── validation/                 # 值域验证
│   │   └── value_domain_validator.py # 5种域类型验证
│   └── errors.py                   # 引擎层通用错误
│
├── services/                       # 服务层 (L3)
│   ├── schema_service.py           # Schema CRUD + 版本
│   ├── entity_service.py           # 实体/关系 CRUD
│   ├── analysis_service.py         # 分析编排 (指标+规则)
│   ├── query_service.py            # 查询路由 + 混合检索
│   ├── rule_service.py             # 规则管理 (41K+, 最大服务)
│   ├── ingestion_service.py        # 数据导入
│   ├── dag_service.py              # DAG 执行编排
│   ├── dataset_service.py          # 数据集管理 + diff
│   ├── incremental_update.py       # 增量更新 + 影响分析
│   ├── simulation_service.py       # dry_run + what-if 模拟
│   ├── visualization_service.py    # 可视化服务
│   └── dto/                        # 服务层数据传输对象
│       ├── requests.py
│       ├── responses.py
│       └── errors.py
│
├── api/                            # API 层 (L4)
│   ├── server.py                   # FastAPI 应用 (15K+)
│   ├── dependencies.py             # 依赖注入
│   ├── routes/                     # 14 个路由模块
│   │   ├── management.py           # 管理面 API (54K+)
│   │   ├── consumption.py          # 消费面 API (52K+)
│   │   ├── semantic_spaces.py       # 语义空间管理 (41K+)
│   │   ├── rules.py                # 规则 API
│   │   ├── query.py                # 查询 API
│   │   ├── ingestion.py            # 数据导入 API
│   │   ├── datasets.py             # 数据集 API
│   │   ├── categories.py           # 分类管理 API
│   │   ├── visualization.py        # 可视化 API
│   │   ├── entities.py             # 实体 API
│   │   ├── schema.py              # Schema API
│   │   ├── incremental.py         # 增量更新 API
│   │   ├── analysis.py            # 分析 API
│   │   └── relations.py            # 关系 API
│   └── dto/                        # API 数据传输对象
│       ├── requests.py
│       └── responses.py
│
├── mcp/                            # MCP Agent 协议层
│   ├── server.py                   # MCP 服务器
│   ├── tools/                      # 4 个 MCP 工具
│   │   ├── space.py               # 空间管理工具
│   │   ├── dataset.py              # 数据集工具
│   │   ├── query.py               # 查询工具
│   │   └── execution.py            # 执行工具
│   └── transports/
│       └── stdio.py                # STDIO 传输
│
├── visualization/                   # 可视化模块
│   ├── models.py                   # 7 个 dataclass
│   ├── builders.py                 # Schema/RuleChain 图构建 (28K+)
│   ├── explainers.py              # 条件拆解+中文解释 (21K+)
│   └── simulator.py               # dry_run/what_if 模拟 (26K+)
│
├── cli/                           # 命令行接口 (占位)
│   └── __init__.py
│
└── migrations/                     # 数据库迁移
    └── add_source_declaration_id.py
```

## 项目根目录

```
OntologyEngine/
├── ontology_engine/                # 主包 (如上)
├── ontology-engine-ui/             # 前端 (React 18 + Vite + G6 + X6)
├── examples/                       # 端到端案例
│   ├── supply_chain_finance/      # 供应链金融授信
│   └── consumer_credit/           # 个人消费信贷
├── tests/                          # 测试
│   └── unit/                      # 168+ 单元测试
├── docs/                           # 文档体系
├── docs-ui/                        # 前端文档
├── docs-rust/                      # Rust 扩展设计文档
├── detail/                         # 实施计划
├── discuss/                        # 决策记录
├── review/                         # 评审报告
├── scripts/                        # 工具脚本
├── data/                           # 本地数据 (gitignore)
├── pyproject.toml                  # 项目配置
├── AGENTS.md                       # Agent 行为指南
└── CLAUDE.md                       # Claude Code 指南
```

## 存储层实现

### 接口抽象

```python
# storage/base.py (19K+)
class StorageBackend(ABC):
    """主存储抽象接口 (DuckDB 实现)"""
    # 实体/关系/指标/规则/数据集/增量更新等 30+ 方法

class GraphStoreBackend(ABC):
    """图存储抽象接口"""
    # 节点/边/路径/邻居/图指标等

class VectorStore(ABC):
    """向量存储抽象接口"""
    # insert/search/delete
```

### 实现关系

```python
# storage/__init__.py
DuckDBStorage(StorageBackend)        # 主存储: 实体/关系/指标/审计
NetworkXGraphStore(GraphStoreBackend) # 图存储: NetworkX
KuzuGraphStore(GraphStoreBackend)     # 图存储: kuzu (Phase 2)
LocalVectorStore(VectorStore)         # 向量存储: Faiss
DualWriteCoordinator                  # 图+关系双写协调
```

## 模块依赖

```
api/ ───────▶ services/ ───────▶ engine/ ───────▶ storage/
 │                │                │                │
 │                │                │                ▼
 │                │                │           storage/base.py
 │                │                │                │
 │                │                │                ▼
 │                │                │          storage/duckdb/
 │                │                │          storage/graph/
 │                │                │          storage/vector/
 │                │                │
 │                │                ▼
 │                │           core/schema/
 │                │           core/semantic_space/
 │                │
 │                ▼
 │         visualization/
 │         mcp/tools/
 │
 ▼
examples/*/schema.yaml  ← 三类资产定义入口
```

## 关键约束（当前实现）

1. **上层依赖下层接口**，不关心具体实现
2. **默认使用本地 DuckDB + NetworkX + Faiss**
3. **通过配置切换外部存储**，无需改代码
4. **图算法 (NetworkX) 按需加载**，不作为主存储
5. **三层资产统一存储**：DuckDB 同时承载 IT 资产、组织资产和链接元数据
