# 语义空间消费面/管理层分离架构 - 关键经验

## 2026-04-12

## 1. API 路径设计

### 经验
管理面和消费面使用不同的 API 前缀和 ID 系统：
- 管理面: `/v1/management/spaces/{spaceId}` - 使用 `space_` 前缀
- 消费面: `/v1/consumption/views/{viewId}` - 使用 `view_` 前缀

消费视图通过 `view_id` 字段与管理空间关联，而不是嵌套在管理空间的响应中。

### 教训
1. **不要混用 ID 前缀** - view_id 存在时应该能直接访问消费视图
2. **消费视图应该独立存在** - 不是管理空间的子资源，而是通过 view_id 引用

## 2. 空间激活与数据同步

### 经验
激活管理空间时会同步数据到消费视图：
1. 复制 L1-L4 层定义
2. 复制实体实例
3. 消费视图状态跟随管理空间

### 教训
1. **视图不存在时自动重建** - 如果 view_id 指向的视图文件被删除，激活时应该自动重建
2. **数据同步时机** - 激活时同步比创建时同步更合理，确保管理空间数据完整

## 3. 删除级联

### 经验
删除管理空间时应该同时删除关联的消费视图，避免孤立文件。

### 实现
```python
@router.delete("/spaces/{space_id}")
async def delete_space(space_id: str):
    space = await storage.load(space_id)
    if space.metadata.view_id:
        await storage.delete(space.metadata.view_id)
    await storage.delete(space_id)
```

## 4. 前端消费面路由

### 经验
消费视图需要独立页面 `/consumption/:viewId`，而不是嵌套在管理空间菜单下。

### 实现
1. 创建 `ConsumptionViewPage` 组件
2. 添加路由 `/consumption/:viewId`
3. 顶部导航添加「消费面」链接到 `/consumption`

## 5. G6 可视化组件复用

### 经验
现有的 SchemaGraph、RuleChainDAG 等组件可以直接用于消费面。

### 实现
消费面 `SchemaVisualizationPage` 引用管理面相同的组件：
```tsx
import SchemaGraph from '../../components/schema/SchemaGraph';
import NodeDetailPanel from '../../components/schema/NodeDetailPanel';
```

## 6. 存储层注意事项

### 经验
文件存储时 space_id 和 view_id 必须一致对应，否则会出现 404。

### 教训
1. 创建视图后必须更新管理空间的 `view_id` 字段
2. 激活时检查视图存在性，不存在则重建
3. 测试时删除文件要确认没有其他引用

## 7. 类型定义

### 经验
消费面 API 返回格式可能与预期不同，需要灵活的类型定义。

### 教训
```typescript
// 消费面返回 view_id 而非 schema_id
export interface SchemaGraphData {
  view_id?: string;
  schema_id?: string;
  // ...
}
```

## 总结

1. **管理面/消费面分离** - 通过 view_id 引用关联，不是嵌套
2. **激活时数据同步** - 确保消费视图数据完整
3. **级联删除** - 删除管理空间时清理消费视图
4. **独立路由** - 消费面有自己的页面和导航入口
5. **组件复用** - 利用现有的 G6 可视化组件
