# 前端 Agent Memory UI 一致性审查报告

> **status**: draft | **phase**: Phase 2 | **source_of_truth**: `.trae/documents/agent-memory-frontend-ui-design.md` + `ontology-engine-ui/src/` | **last_verified**: 2026-05-06 | **verified_against**: localhost:8000 API

---

## 1. 审查目的

对 Agent Memory 前端交互界面实现与设计文档进行一致性审查，确认已实现内容、识别缺失功能、记录后端依赖问题。

---

## 2. 审查范围

| 维度 | 内容 |
|------|------|
| 设计文档 | `.trae/documents/agent-memory-frontend-ui-design.md` |
| 前端代码 | `ontology-engine-ui/src/pages/spaces/memory/*.tsx` |
| 前端组件 | `ontology-engine-ui/src/components/memory/*.tsx` |
| 前端服务 | `ontology-engine-ui/src/services/memoryApi.ts` |
| 后端 API | `localhost:8000` 实际端点 |

---

## 3. 已实现且一致的内容

| 设计项 | 实现文件 | 状态 |
|--------|----------|------|
| 路由结构 `/spaces/:spaceId/memory/*` | `App.tsx` | ✅ |
| MemoryOverviewPage 记忆图谱 Tab | `MemoryOverviewPage.tsx` | ✅ |
| MemoryOverviewPage Agent 活动 Tab | `MemoryOverviewPage.tsx` | ✅ |
| MemoryOverviewPage 验证演示 Tab（占位） | `MemoryOverviewPage.tsx` | ⚠️ 仅占位 |
| MemoryGraphView (G6 力导向图) | `MemoryGraphView.tsx` | ✅ |
| MemoryDetailDrawer | `MemoryDetailDrawer.tsx` | ✅ |
| MemoryBuildPage 记忆创建 | `MemoryBuildPage.tsx` | ✅ |
| MemoryBuildPage 待审区队列 | `MemoryBuildPage.tsx` | ✅ |
| MemoryConsumePage 分层检索 | `MemoryConsumePage.tsx` | ✅ |
| MemoryConsumePage Disposition 滑块 | `MemoryConsumePage.tsx` | ✅ |
| ReflectCenterPage 发起反思 | `ReflectCenterPage.tsx` | ✅ |
| ReflectCenterPage 任务列表+报告 | `ReflectCenterPage.tsx` | ✅ |
| MemoryManagePage 统计+更正历史 | `MemoryManagePage.tsx` | ✅ |
| 颜色编码系统（认知层/信念状态） | 多文件 | ✅ |

---

## 4. 设计 → 实现 GAP 分析

### 4.1 完全缺失的功能

| 设计项 | 设计位置 | 影响页面 | 缺失原因 |
|--------|----------|----------|----------|
| 记忆强度热力图 | 4.1.1 | MemoryOverviewPage | 后端无 `/heatmap` 端点 |
| Agent 活动筛选器 | 4.1.2 | MemoryOverviewPage | 未实现 |
| 活动统计（延迟/错误率） | 4.1.2 | MemoryOverviewPage | 后端 `audit` 字段不全 |
| 验证演示面板 | 4.1.3 | MemoryOverviewPage | 后端无 `/validation` 端点 |
| 文档导入（拖拽/粘贴/选择） | 4.2.1 | MemoryBuildPage | 后端无文档上传端点 |
| 双通道提取进度 | 4.2.1 | MemoryBuildPage | 未实现 |
| Schema 对齐度评分 | 4.2.1 | MemoryBuildPage | 后端无对齐度接口 |
| 矛盾看板 | 4.3.1 | MemoryManagePage | 前端未实现 |
| 信念状态机可视化 | 4.3.1 | MemoryManagePage | 未实现 |
| 治理仪表盘 | 4.3.1 | MemoryManagePage | 后端无 `/dashboard` 端点 |
| 证据链树形展开 | 4.4.1 | MemoryConsumePage | 未实现 |
| 短路返回标记 | 4.4.1 | MemoryConsumePage | 未实现 |
| Reflect 任务阶段进度 | 4.5.1 | ReflectCenterPage | 后端返回简化状态 |

### 4.2 部分实现的功能

| 设计项 | 设计规格 | 当前实现 | GAP |
|--------|----------|----------|-----|
| 验证演示 Tab | case5-case14 全覆盖+步骤可视化+结果对比 | 仅占位卡片 | ❌ 完全缺失 |
| Agent 活动流 | WebSocket/轮询实时更新+操作延迟统计 | 静态列表，无实时更新 | ⚠️ 部分缺失 |
| 记忆管理-矛盾看板 | 矛盾分类+裁决操作 | 仅展示更正历史 | ❌ 完全缺失 |
| 记忆消费-证据链 | 树形展开+贡献度标注 | 未实现 | ❌ 完全缺失 |

---

## 5. 后端 API 实际支持情况

### 5.1 已确认存在的端点

| 方法 | 端点 | 状态 | 说明 |
|------|------|------|------|
| POST | `/v1/spaces/{space_id}/memory/remember` | ✅ 正常 | 创建记忆 |
| POST | `/v1/spaces/{space_id}/memory/recall` | ⚠️ 有BUG | `query="*"` 返回空结果 |
| POST | `/v1/spaces/{space_id}/memory/reflect` | ✅ 正常 | 返回 reflection_id |
| POST | `/v1/spaces/{space_id}/memory/approve` | ✅ 正常 | 审批操作 |
| POST | `/v1/spaces/{space_id}/memory/consolidate` | ✅ 正常 | 手动触发整合 |
| POST | `/v1/spaces/{space_id}/memory/forget` | ✅ 正常 | 手动触发遗忘 |
| GET | `/v1/spaces/{space_id}/memory/stats` | ✅ 正常 | 返回完整统计 |
| GET | `/v1/spaces/{space_id}/memory/types` | ✅ 正常 | 返回类型分布 |
| GET | `/v1/spaces/{space_id}/memory/audit` | ✅ 正常 | 返回活动日志 |
| GET | `/v1/spaces/{space_id}/memory/contradictions` | ✅ 正常 | 返回矛盾列表（当前为空） |
| GET | `/v1/spaces/{space_id}/memory/corrections` | ✅ 正常 | 返回更正列表（当前为空） |
| GET | `/v1/spaces/{space_id}/memory/{node_id}/evidence` | ❌ **报错** | `'confirmation_count'` 错误 |
| GET | `/v1/spaces/{space_id}/memory/{node_id}` | ❌ **报错** | `'confirmation_count'` 错误 |
| PATCH | `/v1/spaces/{space_id}/memory/{node_id}/correct` | ✅ 正常 | 更正节点 |
| DELETE | `/v1/spaces/{space_id}/memory/{node_id}` | ✅ 正常 | 删除节点 |

### 5.2 确认不存在的端点

| 端点 | 说明 | 影响 |
|------|------|------|
| `GET /heatmap` | 记忆强度热力图数据 | 热力图无法展示 |
| `GET /dashboard` | 治理仪表盘聚合数据 | 治理仪表盘无法展示 |
| `POST /validation/{case_id}` | 验证案例执行 | 验证演示无法自动化 |
| `GET /validation/cases` | 验证案例列表 | 验证演示无法选择案例 |
| `GET /disposition` | Disposition 配置读取 | Disposition 预设无法加载 |
| `PUT /disposition` | Disposition 配置更新 | Disposition 调节无法保存 |
| `GET /reflect-tasks` | Reflect 任务列表查询 | 只能展示当前会话任务 |
| `GET /reflect/{reflection_id}` | Reflect 状态/结果查询 | 无法轮询任务进度 |

---

## 6. 关键后端问题

### 6.1 🔴 recall 返回空结果

**现象**：
```bash
POST /recall {"query":"*","max_results":5}
→ {"results": [], "total": 0}
```

**影响**：记忆图谱、记忆列表、待审区均无法展示数据。

**根因**：后端 `recall` 对 `*` 通配符处理逻辑有误，或向量检索未命中。

**建议**：
- 前端临时改用 `GET /stats` + `GET /audit` 展示数据
- 后端修复 `recall` 的通配符查询逻辑

### 6.2 🔴 `confirmation_count` 字段错误

**现象**：
```bash
GET /{node_id}/evidence → {"error": {"code": "EVIDENCE_ERROR", "message": "'confirmation_count'"}}
GET /{node_id} → {"error": {"code": "GET_NODE_ERROR", "message": "'confirmation_count'"}}
```

**影响**：记忆详情抽屉、证据链展开功能完全不可用。

**根因**：后端 Kuzu 存储查询中引用了不存在的 `confirmation_count` 字段。

**建议**：
- 后端移除 `confirmation_count` 字段引用
- 或在前端 `memoryApi.ts` 中改用 `recall` 模拟节点查询

### 6.3 🟡 audit 返回字段不完整

**当前返回**：
```json
{
  "id": "...",
  "memory_type": "opinion",
  "content": "...",
  "belief_status": "rejected",
  "superseded_by": null,
  "updated_at": null
}
```

**设计期望**：
- `agent_name`: Agent 标识
- `activity_type`: remember/recall/reflect
- `timestamp`: 操作时间
- `operation`: 具体操作描述
- `result`: 操作结果摘要

**影响**：Agent 活动流无法展示操作类型和延迟统计。

---

## 7. 前端 → 后端依赖清单

| 前端功能 | 依赖后端端点 | 当前状态 | 优先级 |
|----------|-------------|----------|--------|
| 记忆详情抽屉 | `GET /{node_id}` | ❌ 报错 | P0 |
| 证据链展开 | `GET /{node_id}/evidence` | ❌ 报错 | P0 |
| 记忆列表展示 | `POST /recall` | ⚠️ 返回空 | P0 |
| 验证演示 | `POST /validation/{case_id}` | ❌ 不存在 | P1 |
| 治理仪表盘 | `GET /dashboard` | ❌ 不存在 | P1 |
| 记忆强度热力图 | `GET /heatmap` | ❌ 不存在 | P2 |
| Disposition 预设 | `GET/PUT /disposition` | ❌ 不存在 | P2 |
| Reflect 任务轮询 | `GET /reflect/{id}` | ❌ 不存在 | P2 |
| Agent 活动统计 | `GET /audit` 字段扩展 | ⚠️ 字段不全 | P2 |

---

## 8. 建议实施优先级

### Phase 1: 修复阻塞性问题（P0）

1. **修复后端 `confirmation_count` 错误**
   - 影响：详情抽屉、证据链完全不可用
   - 文件：`ontology_engine/storage/local/kuzu_store.py` 或相关查询

2. **修复后端 `recall` 返回空结果**
   - 影响：所有列表展示为空
   - 文件：`ontology_engine/engine/cognitive/memory_api.py`

### Phase 2: 补全缺失页面（P1）

3. **实现矛盾看板**
   - 依赖：`GET /contradictions`（已存在，当前为空）
   - 文件：`MemoryManagePage.tsx`

4. **实现验证演示框架**
   - 方案：前端调用现有 remember/recall/reflect 模拟验证步骤
   - 文件：`MemoryOverviewPage.tsx` 验证 Tab

5. **实现治理仪表盘（简化版）**
   - 方案：用 `/stats` + `/audit` 聚合展示
   - 文件：`MemoryManagePage.tsx`

### Phase 3: 增强体验（P2）

6. **实现证据链树形展开**
   - 依赖：`GET /{node_id}/evidence`（需先修复）
   - 文件：`MemoryConsumePage.tsx`

7. **实现记忆强度热力图（简化版）**
   - 方案：用 `/stats` + `/types` 数据模拟
   - 文件：`MemoryOverviewPage.tsx`

8. **Agent 活动实时轮询**
   - 方案：5秒轮询 `/audit`
   - 文件：`MemoryOverviewPage.tsx`

---

## 9. 文档引用

| 文档 | 路径 | 作用 |
|------|------|------|
| 前端设计文档 | `.trae/documents/agent-memory-frontend-ui-design.md` | UI 设计唯一事实源 |
| 后端 API 设计 | `docs/02-design/agent-memory/memory-api.md` | API 设计规范 |
| 前端代码 | `ontology-engine-ui/src/` | 实现代码 |
| 后端路由 | `ontology_engine/api/routes/memory.py` | 实际端点定义 |

---

## 10. 审查结论

| 维度 | 评分 | 说明 |
|------|------|------|
| 核心页面框架 | ✅ 80% | 5个页面均已创建，基础功能可用 |
| 设计一致性 | ⚠️ 60% | 核心功能对齐，高级功能缺失 |
| 后端 API 覆盖 | ⚠️ 65% | 基础 CRUD 可用，聚合/验证端点缺失 |
| 数据流完整性 | ❌ 40% | `recall` 返回空 + `evidence` 报错导致数据展示受阻 |

**总体结论**：前端页面框架已完成，但受后端 API 问题影响，实际数据展示能力受限。建议优先修复后端 `confirmation_count` 和 `recall` 问题，再补全前端缺失功能。
