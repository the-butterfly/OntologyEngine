# Agent 接口设计

> **接口形态**: MCP + CLI + 云端/本地混合部署
> **核心特性**: 组织级资产共享 + 本地知识刷新

## 一、架构概览

### 1.1 部署模式

```
┌─────────────────────────────────────────────────────────────┐
│                     云端 (Cloud)                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Organization Asset Repository               │   │
│  │  ├── Shared Schemas (共享 Schema 库)               │   │
│  │  ├── Canonical Rules (权威规则库)                   │   │
│  │  ├── Model Registry (模型仓库)                      │   │
│  │  └── Knowledge Graph (组织知识图谱)                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │ ↑
                          │ │ 同步刷新
                          │ ↓
┌─────────────────────────────────────────────────────────────┐
│                     本地 (Local)                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Local Instance                           │   │
│  │  ├── Local Schemas (本地 Schema 实例化)              │   │
│  │  ├── Instance Data (实体/关系数据)                   │   │
│  │  ├── Local Cache (热点缓存)                          │   │
│  │  └── Personal Config (个人配置)                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Agent Interface Layer                    │   │
│  │  ├── MCP Server (Claude Agent 调用)                  │   │
│  │  ├── CLI Tool (命令行工具)                          │   │
│  │  └── REST API (外部集成)                             │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 资产类型与同步策略

| 资产类型 | 云端权威 | 本地可编辑 | 同步方向 | 冲突策略 |
|----------|----------|------------|----------|----------|
| Schema 模板 | ✅ | ❌ | 云→本地 | 云端优先 |
| 规则定义 | ✅ | 可覆盖（本地可实例化覆盖） | 云→本地 | 覆盖/保留 |
| 实例数据 | ❌ | ✅ | 本地私有 | - |
| 个人配置 | ❌ | ✅ | 本地私有 | - |
| 向量索引 | ❌ | 本地构建 | - | - |

---

## 二、MCP 接口设计

### 2.1 MCP Server 架构

```python
# agent/mcp_server.py
from mcp.server import Server
from mcp.types import Tool, Resource

class OntologyEngineMCPServer:
    """OntologyEngine MCP Server"""

    def __init__(
        self,
        local_config: LocalConfig,
        cloud_config: CloudConfig | None = None
    ):
        self.local = LocalEngine(local_config)
        self.cloud = CloudSync(cloud_config) if cloud_config else None
        self.tools = self._register_tools()

    def _register_tools(self) -> list[Tool]:
        return [
            # === 消费面工具 ===
            # Schema 操作
            Tool(
                name="oe_load_schema",
                description="加载 Schema 到本地",
                input_schema=LoadSchemaInput,
                handler=self.load_schema
            ),
            Tool(
                name="oe_sync_assets",
                description="从云端同步组织资产",
                input_schema=SyncAssetsInput,
                handler=self.sync_assets
            ),

            # 实体操作
            Tool(
                name="oe_create_entity",
                description="创建实体",
                input_schema=CreateEntityInput,
                handler=self.create_entity
            ),

            # 规则执行
            Tool(
                name="oe_execute_rule",
                description="执行规则并返回可解释结果",
                input_schema=ExecuteRuleInput,
                handler=self.execute_rule
            ),

            # 检索
            Tool(
                name="oe_query",
                description="知识检索 (向量+图语义)",
                input_schema=QueryInput,
                handler=self.query
            ),

            # 追溯
            Tool(
                name="oe_trace_rule",
                description="从实例追溯到完整计算树",
                input_schema=TraceRuleInput,
                handler=self.trace_rule
            ),

            # === 管理面工具 ===
            # Space 管理
            Tool(
                name="oe_create_space",
                description="创建管理空间",
                input_schema=CreateSpaceInput,
                handler=self.create_space
            ),
            Tool(
                name="oe_activate_space",
                description="激活管理空间",
                input_schema=SpaceIdInput,
                handler=self.activate_space
            ),
            Tool(
                name="oe_archive_space",
                description="归档管理空间",
                input_schema=SpaceIdInput,
                handler=self.archive_space
            ),

            # Schema 管理
            Tool(
                name="oe_create_schema",
                description="在 Space 中创建/更新完整 Schema",
                input_schema=CreateSchemaInput,
                handler=self.create_schema
            ),
            Tool(
                name="oe_update_schema",
                description="部分更新 Schema",
                input_schema=UpdateSchemaInput,
                handler=self.update_schema
            ),
            Tool(
                name="oe_publish_schema",
                description="发布 Schema 版本快照",
                input_schema=PublishSchemaInput,
                handler=self.publish_schema
            ),

            # 规则创作
            Tool(
                name="oe_define_rule",
                description="在 Schema 中新增规则声明",
                input_schema=DefineRuleInput,
                handler=self.define_rule
            ),
            Tool(
                name="oe_attach_rule_logic",
                description="为规则添加实例逻辑（steps/算子）",
                input_schema=AttachRuleLogicInput,
                handler=self.attach_rule_logic
            ),

            # 数据集管理
            Tool(
                name="oe_register_dataset",
                description="注册外部数据集",
                input_schema=RegisterDatasetInput,
                handler=self.register_dataset
            ),
            Tool(
                name="oe_trigger_sync",
                description="触发数据同步",
                input_schema=TriggerSyncInput,
                handler=self.trigger_sync
            ),
            Tool(
                name="oe_get_sync_status",
                description="获取同步状态",
                input_schema=DatasetIdInput,
                handler=self.get_sync_status
            ),

            # 视图管理
            Tool(
                name="oe_create_view",
                description="创建消费视图",
                input_schema=CreateViewInput,
                handler=self.create_view
            ),
            Tool(
                name="oe_authorize_view",
                description="配置视图授权",
                input_schema=AuthorizeViewInput,
                handler=self.authorize_view
            ),

            # 版本管理
            Tool(
                name="oe_snapshot",
                description="创建版本快照",
                input_schema=SnapshotInput,
                handler=self.snapshot
            ),
            Tool(
                name="oe_rollback",
                description="回滚到指定版本",
                input_schema=RollbackInput,
                handler=self.rollback
            ),
        ]
```

### 2.2 核心 Tool 定义

#### 2.2.1 Schema 加载

```yaml
tool: oe_load_schema
description: "加载 Schema 到本地实例"

input:
  schema_id: string          # Schema 标识
                          # 格式: org_id/schema_name@version
                          # 示例: acme/credit_assessment@v2.1
  mode: enum               # 加载模式
    - reference: 仅引用，不下载
    - local: 下载到本地，可离线使用
    - cached: 使用本地缓存

output:
  schema_info:
    id: string
    version: string
    loaded_at: timestamp
    entity_count: number
    rule_count: number
```

#### 2.2.2 资产同步

```yaml
tool: oe_sync_assets
description: "从云端同步组织资产到本地"

input:
  asset_types: list[enum]
    - schemas: Schema 模板
    - rules: 规则定义
    - models: 模型配置
    - all: 全部
  strategy: enum
    - pull: 云端→本地 (默认)
    - push: 本地→云端 (需权限)
    - merge: 合并 (冲突时提示)
  force: boolean            # 强制覆盖本地

output:
  sync_result:
    pulled: list[AssetSummary]   # 从云端拉取的
    pushed: list[AssetSummary]   # 推送到云端的
    conflicts: list[Conflict]     # 冲突项
    errors: list[Error]
```

#### 2.2.3 知识检索

```yaml
tool: oe_query
description: "混合检索: 向量语义 + 图Schema匹配"

input:
  query: string            # 自然语言查询
  match_mode: enum
    - semantic: 仅向量相似
    - graph: 仅图关系匹配
    - hybrid: 加权融合 (默认)
    - path: 路径模式
  top_k: number = 10
  filters:                  # 结构化过滤
    concept_types: list[string]
    attributes: dict
    relation_types: list[string]
  weights:                 # hybrid 模式权重
    semantic: number = 0.5
    graph: number = 0.5

output:
  results:
    - entity_id: string
      concept_type: string
      relevance_score: number   # 0-1
      match_details:
        semantic_score: number
        graph_score: number
        matched_path: list[string]  # 匹配的关系路径
      attributes: dict            # 关键属性摘要
```

#### 2.2.4 规则追溯

```yaml
tool: oe_trace_rule
description: "从实例追溯完整计算链路"

input:
  entity_id: string
  trace_mode: enum
    - categorization: 仅归类分析
    - rules: 仅适用规则
    - dependency: 规则依赖树
    - full: 完整链路 (默认)
  rule_group: string | null   # 指定规则组，为空则全部

output:
  trace:
    entity:
      id: string
      concept_type: string
      key_attributes: dict

    categorization:
      industry: string
      company_scale: string
      risk_level: string
      tags: list[string]

    rule_groups:
      - name: string
        matched: boolean
        reason: string

    computation_tree:
      # 完整 DAG 结构
      nodes:
        - rule_id: string
          name: string
          type: enum[precondition, compute, decision]
          inputs:
            - name: string
              source: enum[fact, metric, rule_output]
              source_id: string
              value: any  # 已计算的值
          formula: string
          output:
            name: string
            value: any

      edges:
        - from: string
          to: string
          label: string  # "depends_on"

    atomic_metrics:
      - id: string
        name: string
        value: any
        source: string  # 来自 L1 事实
```

#### 2.2.5 规则执行

```yaml
tool: oe_execute_rule
description: "执行规则并返回可解释结果"

input:
  entity_id: string
  rule_group: string
  explain_level: enum
    - minimal: 仅最终结果
    - intermediate: 结果 + 中间规则
    - full: 完整计算过程 + 数据来源
  dry_run: boolean = false   # 仅预览，不执行

output:
  execution:
    entity_id: string
    rule_group: string
    executed_at: timestamp
    duration_ms: number

  final_output:
    # 规则定义的 outputs
    eligible: boolean
    credit_limit:
      value: number
      currency: string
    interest_rate: number

  explain:
    rules_executed:
      - rule_id: string
        name: string
        condition_evaluated: string  # 实际求值的条件
        condition_result: boolean
        action_taken: string
        computation_detail:
          formula: string
          inputs: dict
          calculation: string  # "min(5000000*0.5,10000000)*0.78 = 1950000"
          result: any

    data_sources:
      - field: string
        layer: enum[L1_fact, L2_category, L3_metric]
        instance_id: string
        computed: boolean
        value: any

    warnings: list[string]   # 潜在问题提示
    suggestions: list[string]  # 优化建议
```

---

## 三、CLI 工具设计

### 3.1 命令结构

```bash
# 主体结构
ontologyengine <command> <subcommand> [options]

# 命令分组
ontologyengine schema   # Schema 管理
ontologyengine entity   # 实体操作
ontologyengine rule     # 规则管理
ontologyengine query    # 知识检索
ontologyengine sync     # 云端同步
ontologyengine agent    # Agent 交互
```

### 3.2 核心命令

#### Schema 管理

```bash
# 加载 Schema
ontologyengine schema load <schema_id>

# 列出可用 Schema
ontologyengine schema list --source cloud

# 比较 Schema 版本
ontologyengine schema diff org/schema@v1.0 org/schema@v2.0

# Schema 版本切换
ontologyengine schema switch <schema_id> --to-version v2.1
```

#### 实体操作

```bash
# 创建实体
ontologyengine entity create --type Supplier --data '{"name": "公司A"}'

# 批量导入
ontologyengine entity import --file entities.csv --schema schema_id

# 查询实体
ontologyengine entity query --type Supplier --filter 'status=ACTIVE'
```

#### 规则执行

```bash
# 执行规则
ontologyengine rule execute <entity_id> --group credit_assessment

# 执行并解释
ontologyengine rule execute <entity_id> --group credit_assessment --explain full

# 预览 (dry run)
ontologyengine rule execute <entity_id> --group credit_assessment --dry-run
```

#### 知识检索

```bash
# 自然语言检索
ontologyengine query "提供芯片的供应商"

# 指定模式检索
ontologyengine query "提供芯片的供应商" --mode hybrid --top-k 20

# 检索并追溯
ontologyengine query "供应商A" --trace full
```

#### 云端同步

```bash
# 同步所有资产
ontologyengine sync pull --all

# 同步指定类型
ontologyengine sync pull --schemas --rules

# 查看同步状态
ontologyengine sync status

# 解决冲突
ontologyengine sync resolve --conflict <id> --strategy keep-local
```

---

## 四、云端/本地混合架构

### 4.1 资产分层

```
Organization Layer (组织层)
├── Canonical Schemas     # 权威 Schema
├── Shared Rules         # 共享规则
├── Model Registry       # 模型仓库
└── Asset Catalog        # 资产目录

Team Layer (团队层)
├── Team Schemas         # 团队定制
├── Team Rules           # 团队规则
└── Instance Data       # 实例数据

Personal Layer (个人层)
├── Local Overrides      # 个人覆盖
└── Cache               # 本地缓存
```

### 4.2 同步机制

```python
class AssetSync:
    """资产同步引擎"""

    async def pull(
        self,
        asset_types: list[str],
        strategy: SyncStrategy = SyncStrategy.CLOUD_FIRST
    ) -> SyncResult:
        """
        从云端拉取资产到本地
        """
        # 1. 获取云端资产清单
        cloud_assets = await self.cloud.list_assets(asset_types)

        # 2. 获取本地资产状态
        local_assets = await self.local.get_asset_status(asset_types)

        # 3. 计算差异
        diff = self._compute_diff(cloud_assets, local_assets)

        # 4. 执行同步
        result = SyncResult()
        for asset in diff.to_pull:
            # 下载资产
            content = await self.cloud.download(asset)
            # 应用本地覆盖 (如果有)
            if local_override := local_assets.get(asset.id):
                content = self._merge(asset, local_override)
            # 保存本地
            await self.local.save(asset.id, content)
            result.pulled.append(asset)

        # 5. 记录同步历史
        await self._record_sync_history(result)

        return result

    async def push(
        self,
        assets: list[Asset],
        mode: PushMode
    ) -> PushResult:
        """
        推送本地资产到云端
        """
        # 需要权限检查
        for asset in assets:
            if not self._can_push(asset):
                raise PermissionError(f"无权限推送 {asset.id}")
            await self.cloud.upload(asset)
```

### 4.3 冲突处理

```python
class ConflictResolver:
    """冲突解决策略"""

    def resolve(
        self,
        local: Asset,
        remote: Asset,
        strategy: ConflictStrategy
    ) -> Asset:
        """
        解决本地与云端冲突

        策略:
        - cloud_wins: 云端优先
        - local_wins: 本地优先
        - manual: 手动解决
        - merge: 智能合并
        """
        if strategy == ConflictStrategy.CLOUD_WINS:
            return remote

        elif strategy == ConflictStrategy.LOCAL_WINS:
            return local

        elif strategy == ConflictStrategy.MANUAL:
            # 返回冲突信息，等待用户决定
            raise ConflictDetected(local=local, remote=remote)

        elif strategy == ConflictStrategy.MERGE:
            # 智能合并 (Schema 字段级别合并)
            return self._smart_merge(local, remote)
```

### 4.4 配置示例

```yaml
# ~/.ontologyengine/config.yaml
ontologyengine:
  mode: hybrid  # local | cloud | hybrid

  local:
    data_dir: ~/.ontologyengine/data
    cache_size: 1000

  cloud:
    endpoint: https://api.ontologyengine.io
    org_id: acme
    api_key: ${ONTOLOGYENGINE_API_KEY}

  sync:
    auto_sync: true
    sync_interval: 300  # 5分钟
    conflict_strategy: manual  # cloud_wins | local_wins | manual | merge

  mcp:
    enabled: true
    port: 8765
```

---

## 五、数据模型

### 5.1 资产标识

```python
@dataclass
class AssetId:
    """资产唯一标识"""
    org_id: str           # 组织 ID
    asset_type: str       # schema | rule | model | config
    name: str             # 资产名
    version: str          # 版本号 (语义化)

    def __str__(self) -> str:
        return f"{self.org_id}/{self.asset_type}/{self.name}@{self.version}"

    @classmethod
    def parse(cls, s: str) -> "AssetId":
        # "acme/schema/credit@v2.0" → AssetId
        org, asset_type, name_version = s.split("/", 2)
        name, version = name_version.rsplit("@", 1)
        return cls(org_id=org, asset_type=asset_type, name=name, version=version)
```

### 5.2 资产元数据

```python
@dataclass
class AssetMetadata:
    id: AssetId
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    status: AssetStatus  # draft | published | deprecated
    tags: list[str]
    dependencies: list[AssetId]
    checksum: str         # 内容校验
```

### 5.3 同步历史

```python
@dataclass
class SyncRecord:
    id: str
    sync_type: SyncType  # pull | push
    asset_type: str
    asset_id: str
    direction: str       # cloud_to_local | local_to_cloud
    status: SyncStatus  # success | failed | partial
    details: dict
    timestamp: datetime
    error: str | None
```

---

## 六、管理面工具输入 Schema

### 6.1 Space 管理工具

```yaml
tool: oe_create_space
description: "创建管理空间"
input:
  space_id: string              # 格式: space.{name}
  name: string                  # 人类可读名称
  description: string?
output:
  space_id: string
  status: DRAFT

tool: oe_activate_space
description: "激活管理空间"
input:
  space_id: string
output:
  space_id: string
  status: ACTIVE

tool: oe_archive_space
description: "归档管理空间"
input:
  space_id: string
output:
  space_id: string
  status: ARCHIVED
```

### 6.2 Schema 管理工具

```yaml
tool: oe_create_schema
description: "在 Space 中创建/更新完整 Schema"
input:
  space_id: string
  schema: object               # 完整 schema 对象（schema_version/semantic_space/L1-L4）
output:
  schema_id: string
  version: string
  loaded_at: timestamp

tool: oe_update_schema
description: "部分更新 Schema（增量修改）"
input:
  space_id: string
  layer: enum[L1,L2,L3,L4]
  operations: list             # [{op: add|update|delete, path, value}]
output:
  schema_id: string
  version: string

tool: oe_publish_schema
description: "发布 Schema 版本快照"
input:
  space_id: string
output:
  version: string
  snapshot_id: string
```

### 6.3 规则创作工具

```yaml
tool: oe_define_rule
description: "在 Schema 中新增规则声明"
input:
  space_id: string
  rule_definition: object      # applies_to, inputs, outputs, preconditions
output:
  rule_id: string
  status: draft

tool: oe_attach_rule_logic
description: "为规则添加实例逻辑（steps / 算子）"
input:
  space_id: string
  rule_name: string            # 规则定义名
  rule_logic: object           # steps[], type, description
output:
  rule_logic_id: string
  rule_logic_name: string
```

### 6.4 数据集与视图管理工具

```yaml
tool: oe_register_dataset
description: "注册外部数据集"
input:
  space_id: string
  name: string
  type: enum[PostgreSQL,MySQL,CSV,JSON]
  connection: object           # 连接配置
output:
  dataset_id: string
  status: REGISTERED

tool: oe_trigger_sync
description: "触发数据同步"
input:
  space_id: string
  dataset_id: string
  mode: enum[full, incremental]
output:
  sync_id: string
  status: RUNNING

tool: oe_create_view
description: "创建消费视图"
input:
  space_id: string
  name: string
  description: string?
output:
  view_id: string
  status: draft

tool: oe_snapshot
description: "创建版本快照"
input:
  space_id: string
  layer: enum[L1,L2,L3,L4,ALL]
output:
  version: integer
  snapshot_id: string

tool: oe_rollback
description: "回滚到指定版本"
input:
  space_id: string
  layer: string
  version: integer
output:
  success: boolean
  rollback_to: integer
```

---

## 七、工具 → API 端点映射

| MCP Tool | Target API Endpoint | 权限 | 说明 |
|----------|-------------------|------|------|
| **消费面工具** | | | |
| `oe_load_schema` | `GET /v1/management/{spaceId}/schema` | `management:read` | 获取完整 Schema |
| `oe_sync_assets` | `POST /v1/management/{spaceId}/datasets/{id}/sync` | `management:write` | 触发资产同步 |
| `oe_create_entity` | `POST /v1/management/{spaceId}/instances/entities` | `management:write` | 创建实体 |
| `oe_query` | `GET /v1/consumption/views/{viewId}/entities` | `consumption:read` | 查询实体 |
| `oe_execute_rule` | `POST /v1/consumption/views/{viewId}/execute/analyze` | `consumption:execute` | 执行规则分析 |
| `oe_trace_rule` | `GET /v1/consumption/views/{viewId}/execute/history` | `consumption:read` | 查询执行历史 |
| **管理面工具** | | | |
| `oe_create_space` | `POST /v1/management/spaces` | `management:write` | 创建空间 |
| `oe_activate_space` | `POST /v1/management/spaces/{spaceId}/activate` | `management:write` | 激活空间 |
| `oe_archive_space` | `POST /v1/management/spaces/{spaceId}/archive` | `management:write` | 归档空间 |
| `oe_create_schema` | `PUT /v1/management/{spaceId}/schema` | `management:write` | 上传/替换 Schema |
| `oe_update_schema` | `PATCH /v1/management/{spaceId}/schema` | `management:write` | 部分更新 Schema |
| `oe_publish_schema` | `POST /v1/management/{spaceId}/publish` | `management:write` | 发布版本快照 |
| `oe_define_rule` | `POST /v1/management/{spaceId}/schema/L4/rules/definitions` | `management:write` | 新增规则声明 |
| `oe_attach_rule_logic` | `POST /v1/management/{spaceId}/schema/L4/rules/logics` | `management:write` | 添加规则实例 |
| `oe_register_dataset` | `POST /v1/management/{spaceId}/datasets` | `management:write` | 注册数据集 |
| `oe_trigger_sync` | `POST /v1/management/{spaceId}/datasets/{id}/sync` | `management:write` | 触发同步 |
| `oe_get_sync_status` | `GET /v1/management/{spaceId}/datasets/{id}/sync/history` | `management:read` | 查询同步状态 |
| `oe_create_view` | `POST /v1/consumption/views` | `management:write` | 创建消费视图 |
| `oe_authorize_view` | `POST /v1/management/{spaceId}/authorizations` | `management:write` | 授权视图 |
| `oe_snapshot` | `POST /v1/management/{spaceId}/versions/{layer}/snapshot` | `management:write` | 创建快照 |
| `oe_rollback` | `POST /v1/management/{spaceId}/versions/{layer}/{v}/rollback` | `management:write` | 版本回滚 |

### 权限层级说明

| 权限 | 可操作范围 |
|------|-----------|
| `management:read` | 读取 Space、Schema、Dataset、Version |
| `management:write` | 创建/修改/删除 Space、Schema、Dataset、Rule、View |
| `consumption:read` | 读取 View、查询 Entity |
| `consumption:execute` | 执行规则、模拟 What-if |

---

## 八、安全与权限

### 6.1 权限模型

```python
class Permission:
    """权限定义"""
    READ = "read"           # 读取资产
    WRITE = "write"         # 修改资产
    PUBLISH = "publish"     # 发布到云端
    ADMIN = "admin"         # 管理权限

# 角色定义
class Role:
    VIEWER = [Permission.READ]
    EDITOR = [Permission.READ, Permission.WRITE]
    PUBLISHER = [Permission.READ, Permission.WRITE, Permission.PUBLISH]
    ADMIN = [Permission.READ, Permission.WRITE, Permission.PUBLISH, Permission.ADMIN]
```

### 6.2 访问控制

```yaml
# Schema 访问控制示例
schema_access:
  acme/credit_assessment@v2.0:
    roles:
      - role: PUBLISHER
        users: ["admin@acme.com"]
      - role: EDITOR
        users: ["analyst@acme.com"]
      - role: VIEWER
        users: ["*"]  # 组织内所有人可读
```

---

## 九、错误处理

### 9.1 错误码

| Code | HTTP | 说明 |
|------|------|------|
| ASSET_NOT_FOUND | 404 | 资产不存在 |
| ASSET_CONFLICT | 409 | 同步冲突 |
| PERMISSION_DENIED | 403 | 无权限 |
| SYNC_FAILED | 500 | 同步失败 |
| INVALID_SCHEMA | 400 | Schema 格式错误 |
| RULE_EXECUTION_ERROR | 500 | 规则执行失败 |
| NETWORK_ERROR | 503 | 云端连接失败 |

### 9.2 降级策略

```python
class CloudClient:
    """带降级的云端客户端"""

    async def get_asset(self, asset_id: AssetId) -> Asset:
        try:
            return await self._fetch_from_cloud(asset_id)
        except NetworkError:
            # 网络失败，尝试本地缓存
            if cached := await self.local.get_cached(asset_id):
                logger.warning(f"Using cached asset: {asset_id}")
                return cached
            raise

        except CloudUnavailable:
            # 云端不可用，完全降级到本地
            logger.error("Cloud unavailable, local-only mode")
            return await self.local.get_asset(asset_id)
```
