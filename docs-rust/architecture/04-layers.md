# 分层架构设计

> **状态**: 设计中  
> **级别**: L0 - 架构层  
> **目标读者**: 架构师、开发者

## 分层总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ L4: 应用层 (Application Layer)                                               │
│ 业务系统、AI Agent、管理界面、监控平台                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ L3: 服务层 (Service Layer)                                                   │
│ API 网关、查询服务、规则服务、推理服务、Memory 服务                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ L2: 引擎层 (Engine Layer)                                                    │
│ 查询引擎、规则引擎、推理引擎、指标计算引擎、向量引擎                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ L1: 存储层 (Storage Layer)                                                   │
│ 图存储、向量存储、关系型存储、缓存、索引                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│ L0: 基础层 (Foundation Layer)                                                │
│ Schema 管理、数据接入、事件总线、配置管理                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## L0: 基础层 (Foundation Layer)

### 职责
- Schema 定义与版本管理
- 数据接入与格式转换
- 事件发布与订阅
- 系统配置管理

### 核心组件

```rust
// Schema 管理
pub struct SchemaManager {
    registry: SchemaRegistry,
    validator: SchemaValidator,
    version_control: VersionControl,
}

// 数据接入
pub struct DataIngestionService {
    parsers: Vec<Box<dyn DataParser>>,
    transformers: Vec<Box<dyn DataTransformer>>,
    loaders: Vec<Box<dyn DataLoader>>,
}

// 事件总线
pub struct EventBus {
    publishers: Vec<Box<dyn EventPublisher>>,
    subscribers: Vec<Box<dyn EventSubscriber>>,
}
```

### 接口定义

```rust
pub trait SchemaManager: Send + Sync {
    /// 注册 Schema
    async fn register(&self, schema: Schema) -> Result<SchemaId>;
    
    /// 获取 Schema
    async fn get(&self, id: &SchemaId) -> Result<Schema>;
    
    /// 验证数据
    async fn validate(&self, data: &Data, schema_id: &SchemaId) -> Result<ValidationResult>;
    
    /// 版本对比
    async fn diff(&self, v1: &SchemaId, v2: &SchemaId) -> Result<SchemaDiff>;
}

pub trait DataIngestion: Send + Sync {
    /// 导入数据
    async fn ingest(&self, source: DataSource, config: IngestConfig) -> Result<IngestResult>;
    
    /// 实时流接入
    async fn subscribe(&self, source: DataSource, handler: Box<dyn StreamHandler>);
}
```

## L1: 存储层 (Storage Layer)

### 职责
- 多模态数据持久化
- 索引管理
- 事务支持
- 数据分片与复制

### 存储架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      存储抽象层 (Storage Abstraction)            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  GraphStore  │  │ VectorStore  │  │  Relational  │          │
│  │   接口       │  │   接口       │  │   接口       │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼──────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │   Neo4j     │  │  pgvector    │  │ PostgreSQL   │
  │  /TuGraph   │  │  /Milvus     │  │              │
  └──────────────┘  └──────────────┘  └──────────────┘
```

### 核心接口

```rust
// 图存储接口
pub trait GraphStore: Send + Sync {
    /// 创建节点
    async fn create_node(&self, node: Node) -> Result<NodeId>;
    
    /// 创建边
    async fn create_edge(&self, edge: Edge) -> Result<EdgeId>;
    
    /// 执行查询
    async fn query(&self, query: &str, params: Params) -> Result<QueryResult>;
    
    /// 事务支持
    async fn transaction(&self) -> Result<Box<dyn GraphTransaction>>;
}

// 向量存储接口
pub trait VectorStore: Send + Sync {
    /// 插入向量
    async fn insert(&self, id: &str, vector: &[f32], metadata: Metadata) -> Result<()>;
    
    /// 相似度搜索
    async fn search(&self, query: &[f32], top_k: usize) -> Result<Vec<SearchResult>>;
    
    /// 混合搜索
    async fn hybrid_search(&self, query: HybridQuery) -> Result<Vec<SearchResult>>;
}

// 关系型存储接口
pub trait RelationalStore: Send + Sync {
    /// 执行 SQL
    async fn execute(&self, sql: &str, params: Params) -> Result<RowSet>;
    
    /// 批量插入
    async fn batch_insert(&self, table: &str, rows: Vec<Row>) -> Result<()>;
}
```

## L2: 引擎层 (Engine Layer)

### 职责
- 查询解析与优化
- 规则执行
- 推理计算
- 指标计算

### 引擎架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        引擎调度器 (Engine Dispatcher)            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ QueryEngine  │  │  RuleEngine  │  │InferenceEng- │          │
│  │              │  │              │  │   ine        │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
├─────────┼─────────────────┼─────────────────┼──────────────────┤
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐          │
│  │Query Parser  │  │Dependency    │  │Reasoning     │          │
│  │Optimizer     │  │  Resolver   │  │  Engine      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 查询引擎

```rust
pub struct QueryEngine {
    parser: QueryParser,
    optimizer: QueryOptimizer,
    executor: QueryExecutor,
}

impl QueryEngine {
    /// 执行查询
    pub async fn execute(&self, query: &str) -> Result<QueryResult> {
        // 1. 解析查询
        let ast = self.parser.parse(query)?;
        
        // 2. 优化查询计划
        let plan = self.optimizer.optimize(ast)?;
        
        // 3. 执行查询
        self.executor.execute(plan).await
    }
}
```

### 规则引擎

```rust
pub struct RuleEngine {
    registry: RuleRegistry,
    dependency_resolver: DependencyResolver,
    executor: RuleExecutor,
    operator_registry: OperatorRegistry,
}

impl RuleEngine {
    /// 执行规则链
    pub async fn execute(&self, context: ExecutionContext) -> Result<ExecutionResult> {
        // 1. 解析依赖
        let graph = self.dependency_resolver.resolve(&context)?;
        
        // 2. 拓扑排序
        let order = graph.topological_sort()?;
        
        // 3. 按序执行
        self.executor.execute(order, context).await
    }
}
```

### 推理引擎

```rust
pub struct InferenceEngine {
    symbolic_engine: SymbolicReasoner,
    neural_engine: NeuralReasoner,
    hybrid_engine: HybridReasoner,
}

pub trait Reasoner: Send + Sync {
    /// 推理
    async fn infer(&self, query: InferenceQuery) -> Result<InferenceResult>;
}
```

## L3: 服务层 (Service Layer)

### 职责
- API 暴露
- 请求路由
- 服务编排
- 限流熔断

### 服务架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         API 网关                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │    REST      │  │   GraphQL    │  │    gRPC      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────────┤
│                         服务层                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │QueryService  │  │ RuleService  │  │MemoryService │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │SchemaService │  │IngestService │  │AgentService  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 服务接口示例

```rust
// gRPC 服务定义
trait KnowledgeService {
    /// 知识查询
    async fn query(&self, request: QueryRequest) -> Result<QueryResponse>;
    
    /// 语义检索
    async fn semantic_search(&self, request: SearchRequest) -> Result<SearchResponse>;
    
    /// 实体详情
    async fn get_entity(&self, request: GetEntityRequest) -> Result<Entity>;
}

trait RuleService {
    /// 执行规则
    async fn execute_rules(&self, request: ExecuteRequest) -> Result<ExecuteResponse>;
    
    /// 计算指标
    async fn compute_metrics(&self, request: ComputeRequest) -> Result<ComputeResponse>;
}

trait MemoryService {
    /// 存储记忆
    async fn store(&self, request: StoreRequest) -> Result<()>;
    
    /// 检索记忆
    async fn retrieve(&self, request: RetrieveRequest) -> Result<Vec<Memory>>;
    
    /// 摘要生成
    async fn summarize(&self, request: SummarizeRequest) -> Result<String>;
}
```

## L4: 应用层 (Application Layer)

### 职责
- 业务逻辑实现
- 用户界面
- Agent 集成
- 监控与运维

### 应用场景

| 应用 | 描述 | 集成方式 |
|------|------|----------|
| 风控系统 | 交易对手风险评估 | REST API |
| 合规检查 | 规则合规验证 | GraphQL |
| 智能问答 | 知识库问答 | gRPC |
| AI Agent | 知识增强 Agent | Memory API |

## 层间依赖规则

```
L4: 应用层
    │ 依赖
    ▼
L3: 服务层
    │ 依赖
    ▼
L2: 引擎层
    │ 依赖
    ▼
L1: 存储层
    │ 依赖
    ▼
L0: 基础层
```

**重要原则**:
- 上层可以调用下层
- 下层不能调用上层
- 同层组件通过接口松耦合
- 依赖注入实现可测试性

## 数据流转

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Input  │───▶│ Parse   │───▶│Validate │───▶│Transform│───▶│  Store  │
│  Data   │    │         │    │         │    │         │    │         │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └────┬────┘
                                                                   │
                              ┌────────────────────────────────────┘
                              ▼
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Output  │◀───│ Format  │◀───│ Execute │◀───│  Plan   │◀───│  Query  │
│ Result  │    │         │    │         │    │         │    │         │
└─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
```

## 💬 待讨论问题

1. **存储抽象**: 是否需要统一的存储抽象层，还是各自独立？
2. **事务边界**: 跨存储的事务如何保证一致性？
3. **缓存策略**: 各层的缓存策略如何协调？
4. **错误处理**: 层间错误如何传播和处理？

## 下一步

- [技术栈选型](./05-tech-stack.md) - 具体技术选型
- [Schema 设计](../design/schema/) - 详细 Schema 设计
