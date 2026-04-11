# 2026-04-11 前端真实数据接入与构建收口记录

**会话时间**: 2026-04-11 17:08 - 17:20  
**分支**: dev

---

## 背景

本轮工作承接上一阶段的架构整改，目标是完成可视化前端的最后收口：

1. 去掉 `MetricScorecard` 中的 mock 指标展示
2. 去掉 `RuleChainPage` 中硬编码实体 ID
3. 修复 G6/TypeScript 兼容性问题，使 `ontology-engine-ui` 可以重新构建通过
4. 将最新实现同步到架构文档与会话记录

---

## 本轮关键决策

### 1. 评分卡必须直接消费真实指标快照

- 不再依赖前端 mock 值或页面本地拼装数据
- 使用后端新增接口 `GET /v1/visualize/metrics/{entity_id}`
- `MetricScorecard` 通过 `entityId` 与 `dimension` 拉取真实快照，统一展示：
  - 当前值
  - 授信评分
  - 授信等级
  - 雷达图
  - 权重贡献

**原因**:
- 避免前端展示与后端规则执行结果脱节
- 让 Schema 页面的指标详情与 Simulation/RuleChain 结果保持一致

### 2. 规则链页面必须动态拉取实体，而不是硬编码 ID

- 不再使用 `SUP_2024_001` 之类的固定实体
- 使用后端新增接口 `GET /v1/visualize/entities`
- `RuleChainPage` 与 `SchemaPage` 都基于实体下拉框切换当前上下文

**原因**:
- 演示数据可以扩展
- 页面行为更符合真实产品使用方式
- 降低实例数据变动时的脆弱性

### 3. G6 相关兼容问题按“最小修复面”收敛

本轮没有改视觉设计，而是只修构建与运行稳定性：

- `RuleChainDAG.tsx`
  - `addNodeOverlays()` 显式接收 `containerRef.current`
  - 不再调用不存在的 `graph.getContainer()`
  - overlay 清理改为 `querySelectorAll<HTMLElement>()`
- `SchemaGraph.tsx`
  - 高亮逻辑改为 `Record<string, string | string[]>` 形式传给 `setElementState`
- `MetricScorecard.tsx`
  - `weights` 明确约束为 `Record<string, number>`，消除 `Object.entries()` 的 `unknown` 推断

**原因**:
- 直接对准当前 TypeScript/G6 报错
- 尽量避免扩大改动面，引入新的渲染回归

---

## 影响文件

### 前端代码

- `ontology-engine-ui/src/components/rule/RuleChainDAG.tsx`
- `ontology-engine-ui/src/components/schema/SchemaGraph.tsx`
- `ontology-engine-ui/src/components/schema/MetricScorecard.tsx`
- `ontology-engine-ui/src/pages/RuleChainPage.tsx`
- `ontology-engine-ui/src/pages/SchemaPage.tsx`
- `ontology-engine-ui/src/api/visualization.ts`
- `ontology-engine-ui/src/types/visualization.ts`

### 后端接口与服务

- `ontology_engine/api/routes/visualization.py`
- `ontology_engine/services/visualization_service.py`
- `ontology_engine/visualization/models.py`

### 文档

- `docs/09-frontend-architecture.md`
- `discuss/2026-04-11-frontend-real-data-integration.md`

---

## 验证结果

### 前端构建

已执行：

```bash
cd /Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology-engine-ui && npm run build
```

结果：**构建通过**。

构建输出保留一条非阻塞告警：
- bundle chunk 超过 500 kB
- 当前不影响功能正确性，后续可考虑 `manualChunks` 或按页面拆包

### 本轮修复前的主要报错

- `RuleChainDAG.tsx`: 参数签名不一致、`graph.getContainer()` 不存在、隐式 `any`
- `MetricScorecard.tsx`: `weight is of type 'unknown'`
- `SchemaGraph.tsx`: `setElementState` 调用签名不匹配

### 本轮修复后的状态

- 上述报错全部消失
- 三个已修改组件的 IDE lint 诊断均为 0

---

## 仍需关注

1. 前端构建虽然通过，但产物体积偏大
2. 后续如继续扩展可视化页面，优先保持：
   - 实体来源统一走 `/v1/visualize/entities`
   - 指标展示统一走 `/v1/visualize/metrics/{entity_id}`
   - 不要重新引入硬编码实体 ID 或 mock 指标

---

*记录结束*
