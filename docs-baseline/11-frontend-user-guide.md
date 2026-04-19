# 前端用户操作指南

## 访问地址
- 前端: http://localhost:3000
- 后端 API: http://localhost:8000

## 整体架构

```
管理面 (/spaces)
  └── SpaceListPage - 空间列表
  └── SpaceDetailPage - 空间详情
        ├── Schema 声明 (L1 事实对象)
        ├── 规则声明 (L4 规则定义)
        ├── 规则逻辑 (L4 规则逻辑)
        ├── 数据实例 (实体实例)
        ├── 版本历史
        ├── Schema 可视化 ← 消费面功能
        ├── 规则执行 ← 消费面功能
        └── What-If 模拟 ← 消费面功能
```

**重要变化**: 可视化、规则执行、模拟功能现在属于**消费面**，需要先激活空间创建消费视图后才能使用。

---

## 用户旅程 1: 创建和管理空间

### 步骤 1: 进入空间列表
- URL: http://localhost:3000/spaces
- 点击任意空间名称进入空间详情

### 步骤 2: 创建新空间
- 点击右上角「创建空间」按钮
- 输入空间名称和描述
- ⚠️ **差异点**: 新建空间时 `create_default_view: true` 会自动创建一个关联的消费视图
- 空间创建后状态为 `draft`（草稿）

### 步骤 3: 激活空间
- ⚠️ **新功能**: 空间需要激活后才能使用消费视图功能
- 点击「激活」按钮（需要通过 API 调用）
- 激活后状态变为 `active`，消费视图可用

---

## 用户旅程 2: 管理面功能

### 2.1 Schema 声明 (L1 事实对象)
- **路径**: 空间详情 → Schema 声明
- **功能**: 查看已定义的 fact objects（实体类型）
- **显示内容**:
  - ID、名称、描述
  - 属性列表（名称、类型、是否必填）
  - 关系列表（关系名 → 目标对象）

**差异点**: 原来是占位页面，现在已实现为显示 L1 fact objects 的表格

### 2.2 规则声明 (L4 规则定义)
- **路径**: 空间详情 → 规则声明
- **功能**: CRUD 操作规则定义
- **显示内容**:
  - ID、名称、类型（constraint/decision/alert/inference）
  - 优先级、适用范畴
  - 输入/输出要素数量
  - 启用状态

**差异点**: 规则定义的 API 路径从 `/rules/definitions` 变为 `/schema/L4/rules/definitions`

### 2.3 规则逻辑
- **路径**: 空间详情 → 规则逻辑
- **功能**: 管理规则的逻辑实例（一个声明可以对应多个逻辑）
- **显示内容**:
  - ID、名称、关联声明
  - 版本、环境
  - 适用条件、when/then action

### 2.4 数据实例
- **路径**: 空间详情 → 数据实例
- **功能**: 查看实体实例列表

**差异点**: 原来是占位页面，现在已实现为显示实体实例的表格

### 2.5 版本历史
- **路径**: 空间详情 → 版本历史
- **功能**: 查看空间快照历史

---

## 用户旅程 3: 消费面功能

⚠️ **前提条件**: 空间必须已激活（状态为 active），且有关联的消费视图

### 3.1 Schema 可视化
- **路径**: 空间详情 → Schema 可视化
- **功能**: 以图形化方式展示语义空间结构
- **显示内容**:
  - 节点列表（实体、分类、指标、规则）
  - 边列表（关系、依赖）
  - 统计信息（各类型数量）

**差异点**:
- 使用 `view_id` 而非 `space_id` 调用 API
- API 路径: `/v1/consumption/views/{view_id}/visualize/schema-graph`

### 3.2 规则执行
- **路径**: 空间详情 → 规则执行
- **功能**: 对单个实体执行规则分析
- **操作步骤**:
  1. 选择评估维度（信用评估/风险分析）
  2. 选择实体
  3. 点击「执行分析」按钮
- **显示内容**:
  - 执行步骤表格（规则ID、类型、条件、结果、说明）
  - 最终输出
  - 决策结果（APPROVED/REJECTED/REVIEW）

**差异点**:
- 使用 `view_id` 调用 API
- 原来可能没有执行按钮，需要手动触发
- API 路径: `/v1/consumption/views/{view_id}/execute/analyze`

### 3.3 What-If 模拟
- **路径**: 空间详情 → What-If 模拟
- **功能**: 对实体进行变量覆盖模拟分析
- **操作步骤**:
  1. 选择评估实体
  2. 选择评估维度
  3. 添加变量覆盖（可选）
  4. 点击「运行模拟」
- **显示内容**:
  - 基准结果 vs 模拟结果对比
  - 差异分析
  - 影响链

**差异点**:
- 使用 `view_id` 调用 API
- API 路径: `/v1/consumption/views/{view_id}/execute/simulate`

---

## API 路径对照表

| 功能 | 旧路径 | 新路径 |
|------|--------|--------|
| 空间列表 | `/v1/spaces/` | `/v1/management/spaces` |
| 空间详情 | `/v1/spaces/{id}` | `/v1/management/spaces/{id}` |
| 事实对象 | `/v1/spaces/{id}/fact-objects` | `/v1/management/{id}/schema/L1/fact-objects` |
| 规则定义 | `/v1/spaces/{id}/rules/definitions` | `/v1/management/{id}/schema/L4/rules/definitions` |
| 规则逻辑 | `/v1/spaces/{id}/rules/logics` | `/v1/management/{id}/schema/L4/rules/logics` |
| 实体实例 | `/v1/spaces/{id}/entities` | `/v1/management/{id}/instances/entities` |
| 版本历史 | `/v1/spaces/{id}/versions` | `/v1/management/{id}/versions` |
| Schema可视化 | `/v1/spaces/{id}/execute/schema-graph` | `/v1/consumption/views/{view_id}/visualize/schema-graph` |
| 规则执行 | `/v1/spaces/{id}/execute/analyze` | `/v1/consumption/views/{view_id}/execute/analyze` |
| What-If模拟 | `/v1/spaces/{id}/execute/simulate` | `/v1/consumption/views/{view_id}/execute/simulate` |

---

## 已知限制

1. **消费视图数据为空**: 创建空间时自动创建的消费视图是空的，不包含 layers 和 instances 数据。这是后端问题，需要在激活空间时同步数据。

2. **激活空间需要 API**: 目前激活空间只能通过 API 调用:
   ```bash
   curl -X POST http://localhost:8000/v1/management/spaces/{space_id}/activate
   ```

3. **消费面功能入口**: 可视化、规则执行、模拟功能在管理面菜单中，但实际调用消费面 API，需要空间已激活。

---

## 故障排查

### Q: 点击「Schema 可视化」报错 "请先激活空间以创建消费视图"
**A**: 需要先激活空间。调用 API:
```bash
curl -X POST http://localhost:8000/v1/management/spaces/{space_id}/activate
```

### Q: 打开空间详情页空白或报错
**A**: 检查控制台是否有 404 错误，可能是 API 路径问题。确认后端运行在 8000 端口。

### Q: 消费面功能报 "Entity not found"
**A**: 这是因为消费视图没有数据（已知限制）。需要后端实现数据同步。
