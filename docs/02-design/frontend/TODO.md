## Schema 可视化改进状态

### 已完成 ✅

| 功能点 | 状态 | 说明 |
|--------|------|------|
| LAYER_CONFIG 分层配置 | ✅ | entity/category/metric/rule 各自独立样式 |
| 胶囊形态实体 | ✅ | L1 事实对象使用全圆角 (radius=28) |
| 菱形分类节点 | ✅ | L2 分类体系旋转45度显示 |
| 圆形指标节点 | ✅ | L3 分析要素保持圆形 (radius=26) |
| 矩形规则节点 | ✅ | L4 业务逻辑使用矩形 (radius=6) |
| 边类型着色 | ✅ | relation/dependency/rule_input/data_dependency 不同颜色 |
| 方向箭头 | ✅ | 所有边（包括 relation）都显示箭头 |
| 关系名称标签 | ✅ | relation 边显示关系名（supplies_to等） |
| 图例面板 | ✅ | 右上角展示层级图例和边类型 |
| 并行边处理 | ✅ | curveOffset 防止多条边重叠 |
| NodeDetailPanel 属性列表 | ✅ | 实体显示完整属性定义 |
| Category 详情面板 | ✅ | L2 分类体系详情支持 |

### 待解决 - 后端问题

**问题: schema-graph API 缺少 L4→L4 规则依赖边**

GET /v1/consumption/views/{view_id}/visualize/schema-graph
返回: 43条边 (relation:5, dependency:15, component:5, rule_input:18)
缺少: L4规则之间的 data_dependency 边 (3条存在于 /rules/dependency-graph)

**根本原因:** 后端 get_schema_graph() 只添加 L3→L4 的 rule_input 边，不添加 L4→L4 规则间的 data_dependency 边。

**解决方案:** 后端需要修改 consumption.py 的 get_schema_graph() 函数，在返回前合并来自 _build_rule_dependency_graph() 的 L4→L4 边。

待办: Task #9 - Backend: Add rule-to-rule edges to schema-graph API

---

## 本次提交 (2026-04-15)

| Commit | 描述 |
|--------|------|
| `93a8bdf` | 详情面板增强：属性列表 + category 类型 |
| `b4c8e00` | 关系边添加方向箭头和关系名称标签 |
| `d7d5234` | Schema 可视化重设计：分层样式、图例、并线处理 |

---

## 辅助文件

| 文件 | 说明 |
|------|------|
| `explore_ui.py` | Playwright 探索脚本 v1 |
| `explore_ui2.py` | Playwright 探索脚本 v2 |
| `test_user_journey.py` | 用户旅程测试脚本 |
| `debug_tags.py` | 调试标签工具 |
