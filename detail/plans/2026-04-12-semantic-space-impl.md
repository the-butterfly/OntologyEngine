# Semantic Space 架构实现计划

**日期**: 2026-04-12
**基于设计**: `docs/05-schema-v2/00b-semantic-space-architecture.md` 及相关文档

---

## 目标

实现语义空间架构的 Phase 1：
- 管理面/消费面路由分离
- 声明/实例模型分离
- Dataset 和同步基础实现
- 规则声明/实例分离
- 前端路由更新

---

## Batch 1: 核心模型和路由重构

### Task 1.1: 更新 SemanticSpace 模型
- 添加 `space_type: MANAGEMENT | CONSUMPTION`
- 添加 `status: DRAFT | ACTIVE | PUBLISHED | ARCHIVED`
- 添加 `authorizations: list[Authorization]`
- 更新 `SemanticSpaceLayers` 添加层版本信息

### Task 1.2: 重构 API 路由
- 创建 `api/routes/management.py` - 管理面路由
- 创建 `api/routes/consumption.py` - 消费面路由
- 更新 `api/server.py` 注册新路由
- 保持向后兼容，标记旧路由为 deprecated

### Task 1.3: 实现 Space CRUD
- 创建管理空间
- 激活/归档/发布空间
- 创建同名消费视图

**验证**: `python -c "from ontology_engine.api.routes import management, consumption; print('OK')"`

---

## Batch 2: Dataset 和同步

### Task 2.1: Dataset 模型
- 创建 `core/dataset/models.py`
- DatasetDeclaration, MappingRule, SyncConfig 模型
- 支持 source type, field mappings, sync mode

### Task 2.2: Dataset CRUD API
- POST/GET/PUT/DELETE `/v1/management/{spaceId}/datasets`
- Dataset 映射规则管理
- 同步配置管理

### Task 2.3: 同步执行 (简化版)
- 全量同步触发
- 增量同步触发 (时间戳字段)
- 同步历史记录

**验证**: `python -c "from ontology_engine.core.dataset import *; print('OK')"`

---

## Batch 3: 规则声明/实例分离

### Task 3.1: 更新 L4 模型
- RuleDefinition 和 RuleLogic 分离
- 添加 `applicable_conditions` 支持
- 添加 `definition_id` 关联

### Task 3.2: 规则选择逻辑
- 根据 entity 类型和分类选择规则声明
- 根据 applicable_conditions 选择匹配的规则实例
- 按 priority 排序执行

### Task 3.3: 更新执行端点
- `/v1/consumption/{viewId}/execute/analyze` - 真实执行
- `/v1/consumption/{viewId}/execute/simulate` - What-if

**验证**: `python -c "from ontology_engine.engine.rule import *; print('OK')"`

---

## Batch 4: 前端更新

### Task 4.1: 更新路由配置
- 添加 `/management/` 路由
- 添加 `/consumption/` 路由
- 创建 managementStore 和 consumptionStore

### Task 4.2: 创建管理面页面框架
- ManagementSpacesPage
- SpaceOverviewPage
- Schema 编辑页面 (L1-L4 tabs)

### Task 4.3: 更新消费面页面
- 使用新的 consumptionStore
- 集成新的 API 端点

**验证**: `cd ontology-engine-ui && npm run build`

---

## Batch 5: Demo 数据和验证

### Task 5.1: 更新示例数据
- 更新 `examples/supply_chain_finance/`
- 添加 demo space 配置

### Task 5.2: 端到端验证
- 启动后端服务
- 打开前端页面
- 验证 Schema 可视化
- 验证规则执行

---

## 预期产出

1. 新的 API 路由 `/v1/management/*` 和 `/v1/consumption/*`
2. 更新的 SemanticSpace 模型
3. Dataset 基础实现
4. 规则声明/实例分离实现
5. 更新的前端路由
6. 可运行的 demo
