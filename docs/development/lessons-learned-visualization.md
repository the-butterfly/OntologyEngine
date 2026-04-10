# 可视化系统开发经验总结

**文档版本**: v1.0  
**创建日期**: 2026-04-10  
**文档类型**: 经验沉淀 / 问题解决方案

---

## 1. G6 图谱渲染问题

### 1.1 画布重影问题

**问题描述**: 切换视图或标签页后，画布上出现"重影"，旧图实例未正确销毁

**根本原因**:
- React 严格模式下组件双重渲染
- G6 实例销毁时未清理 DOM 中的 canvas 元素
- 旧图实例残留导致视觉重影

**解决方案**:

```typescript
// 1. 使用 useId 生成唯一实例标识
const instanceId = useId();

// 2. 创建完整的清理函数
const cleanupGraph = useCallback(() => {
  isDestroyedRef.current = true;
  
  if (graphRef.current) {
    graphRef.current.destroy();
    graphRef.current = null;
  }
  
  // 关键：清理 DOM 中所有 canvas 元素
  if (containerRef.current) {
    const canvases = containerRef.current.querySelectorAll('canvas');
    canvases.forEach(canvas => canvas.remove());
    
    // 清理 G6 注入的 div 元素
    while (containerRef.current.firstChild) {
      containerRef.current.removeChild(containerRef.current.firstChild);
    }
  }
}, []);

// 3. useEffect 正确管理生命周期
useEffect(() => {
  isDestroyedRef.current = false;
  if (data && !loading) {
    renderGraph(data);
  }
  return () => cleanupGraph();
}, [data, loading, renderGraph, cleanupGraph]);
```

**关键要点**:
- 销毁 G6 实例后，必须手动清理 DOM 中的 canvas 元素
- 使用 `while (firstChild)` 确保彻底清除所有子元素
- 添加 `isDestroyedRef` 标志防止对已销毁实例的操作

---

### 1.2 多边形边重叠问题

**问题描述**: 两个节点间存在多条边时，边直接重叠在一起

**解决方案**:

```typescript
// 1. 统计同节点对之间的边数量
const edgePairCount: Map<string, number> = new Map();
const edgePairIndex: Map<string, number> = new Map();

edges.forEach(edge => {
  const pairKey = [edge.source, edge.target].sort().join('->');
  const count = edgePairCount.get(pairKey) || 0;
  edgePairCount.set(pairKey, count + 1);
  edgePairIndex.set(edge.id, count);
});

// 2. 为每条边计算 curveOffset
.map(edge => {
  const pairKey = [edge.source, edge.target].sort().join('->');
  const count = edgePairCount.get(pairKey) || 1;
  const index = edgePairIndex.get(edge.id) || 0;
  
  let curveOffset = 0;
  if (count > 1) {
    const spacing = 20;
    const totalWidth = (count - 1) * spacing;
    curveOffset = index * spacing - totalWidth / 2;
  }
  
  return {
    ...edge,
    data: {
      ...edge.data,
      curveOffset,  // 传递给 G6
    },
  };
})

// 3. G6 配置使用 cubic 边类型
edge: {
  type: 'cubic',
  style: {
    curveOffset: (d: any) => d.data?.curveOffset || 0,
  },
}
```

---

## 2. Ant Design 组件升级问题

### 2.1 Card 组件 headStyle 弃用

**问题描述**: 控制台警告 `[antd: Card] headStyle is deprecated. Please use styles.header instead.`

**解决方案**:

```typescript
// 修复前 (已弃用)
<Card 
  headStyle={{ fontSize: 12, padding: '4px 12px' }}
>

// 修复后 (新 API)
<Card 
  styles={{ header: { fontSize: 12, padding: '4px 12px' } }}
>
```

**影响文件**:
- `NodeDetailPanel.tsx` - 4 处
- `SimulationPage.tsx` - 6 处
- `StepDetailPanel.tsx` - 5 处

---

## 3. 后端序列化问题

### 3.1 自定义 dataclasses_asdict 递归错误

**问题描述**: `simulate` 接口返回 500，后端出现 `malloc: Heap corruption detected`

**根本原因**:
- 自定义 `dataclasses_asdict` 递归函数设计缺陷
- 对不可变类型（int, str, float）也进行循环引用检测，导致 `_seen` 集合急剧膨胀
- 递归深度过大触发栈溢出，进而导致 C 层内存损坏

**解决方案**:

```python
# 使用 Python 标准库 dataclasses.asdict + JSON round-trip
def dataclasses_asdict(obj: Any) -> Any:
    """Convert dataclasses to dicts for JSON serialization."""
    if obj is None:
        return None
    
    # 基本类型直接返回
    if isinstance(obj, (str, int, bool)):
        return obj
    
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    
    # 处理 datetime
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    # 处理 Decimal
    if isinstance(obj, Decimal):
        return float(obj)
    
    # 使用标准库 asdict + JSON 安全编码
    if is_dataclass(obj) and not isinstance(obj, type):
        try:
            d = asdict(obj)
            return json.loads(json.dumps(d, cls=JSONSafeEncoder))
        except (TypeError, ValueError, RecursionError):
            return str(obj)
    
    # 其他类型
    if isinstance(obj, (list, tuple, set)):
        return [dataclasses_asdict(item) for item in obj]
    
    if isinstance(obj, dict):
        return {str(k): dataclasses_asdict(v) for k, v in obj.items()}
    
    return str(obj)


class JSONSafeEncoder(json.JSONEncoder):
    """JSON encoder that handles common non-serializable types."""
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        if isinstance(obj, set):
            return list(obj)
        return str(obj)
```

**关键要点**:
- 使用标准库 `dataclasses.asdict` 而非自定义递归
- 使用 JSON round-trip 确保所有数据都可序列化
- 不要对基本类型进行循环引用检测

---

### 3.2 DuckDB 异步 cursor 问题

**问题描述**: `duckdb.duckdb.InvalidInputException: Invalid Input Error: No open result set`

**根本原因**:
- DuckDB 的 cursor 对象不是线程安全的
- `asyncio.to_thread()` 在线程 A 中执行 `execute()` 创建 cursor
- 回到主线程后调用 `fetchone()`，此时 cursor 的 result set 已关闭

**解决方案**:

```python
# 修复前 (错误)
cursor = await asyncio.to_thread(
    self._conn.execute,
    "SELECT ...",
    [param]
)
result = cursor.fetchone()  # 错误：跨线程访问 cursor

# 修复后 (正确)
def _fetch():
    cursor = self._conn.execute("SELECT ...", [param])
    return cursor.fetchone()  # 同一线程执行

result = await asyncio.to_thread(_fetch)
```

**需要修复的方法**:
- `get_entity()`
- `query_entities()`
- `get_relations()`
- `get_metric()`
- `get_neighbors()`
- `get_category_tags()`

---

## 4. 数据流与 API 设计

### 4.1 边过滤策略

**问题描述**: 切换视图时，边可能引用不存在的节点，导致 G6 报错

**解决方案** - 双层过滤:

```python
# 后端过滤 (builders.py)
node_ids = {n.id for n in nodes}
unique_edges = [
    edge for edge in edges 
    if edge.source in node_ids and edge.target in node_ids
]

# 前端二次过滤 (SchemaGraph.tsx)
const nodeIds = new Set(nodes.map(n => n.id));
const validEdges = edges.filter(edge => 
  nodeIds.has(edge.source) && nodeIds.has(edge.target)
);
```

---

## 5. 调试技巧

### 5.1 日志记录最佳实践

```python
import logging
import traceback

logger = logging.getLogger(__name__)

# 关键步骤记录
logger.info(f"Finding entity: {entity_id}")
logger.debug(f"Processing rule {step}: {rule.id}")

# 错误时记录完整堆栈
try:
    result = await operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    logger.error(traceback.format_exc())
    raise
```

### 5.2 启动参数

```bash
# 启用 debug 日志
uvicorn ontology_engine.api.server:app --reload --log-level debug
```

---

## 6. 设计决策记录

### 6.1 规则流边生成策略

**决策**: 在 `rule_overview` 视图中添加规则执行顺序边

**实现**:
1. 按优先级排序规则
2. 添加已知的数据流依赖边 (R001→R002, R002→R004 等)
3. 为无依赖的连续规则添加顺序边

**代码位置**: `builders.py:_build_rule_execution_flow_edges()`

### 6.2 图导出实现策略

**决策**: 使用 G6 内置 `toDataURL()` 而非直接获取 DOM canvas

**原因**:
- G6 使用多层 canvas (主图层、交互层等)
- 直接获取 DOM canvas 只能拿到空白层
- G6 的 `toDataURL()` 会正确合并所有图层

**代码位置**: `SchemaGraph.tsx:exportImage()`

---

## 7. 相关文档索引

| 文档 | 说明 |
|------|------|
| `docs/09-frontend-architecture.md` | 前端架构完整说明 |
| `docs/08-visualization-system.md` | 可视化系统设计 |
| `docs/06-module-detailed-design/` | 模块详细设计 (10个模块) |

---

*文档结束*
