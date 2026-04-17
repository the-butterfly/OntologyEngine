# API 重构实施记录

> **日期**: 2026-04-17
> **任务**: 执行 `02-api-redesign-proposal.md` 的 API 重构
> **状态**: ✅ 完成

---

## 实施策略

### 1. 变更范围确认

根据提案文档，核心变更包括：

| 类别 | 旧前缀 | 新前缀 | 影响文件 |
|------|--------|--------|----------|
| Space 管理 | `/v1/management` | `/v1` | management.py, spaceApi.ts |
| Consumption | `/v1/consumption` | `/v1` | consumption.py, spaceApi.ts |
| Visualization | `/v1/visualize` | 整合到 views | visualization.py (deprecated) |
| Schema | `/v1/schema` | - | schema.py (deprecated) |
| Entities | `/v1/entities` | - | entities.py (deprecated) |

### 2. 执行顺序

```
Phase 1: 后端路由修改
├── Step 1: management.py - prefix + 嵌套路径
├── Step 2: consumption.py - prefix + 路径整合
└── Step 3: deprecation headers 更新

Phase 2: 前端 API 客户端修改
├── Step 1: spaceApi.ts - BASE_URL + 路径替换
└── Step 2: 页面文件 - 硬编码路径修复

Phase 3: 验证
├── Backend API 测试
└── Playwright 前端测试
```

---

## 遇到的问题

### 问题 1: 重复路由导致部分 Edit 失败

**现象**: 使用 `replace_all` 时遇到多个匹配项，无法唯一确定位置

**原因**: `management.py` 中存在重复的路由定义（如 `/{space_id}/schema/L2/categorizations` 有两个 GET 端点）

**解决**:
- 分批执行 Edit，每次提供更多上下文
- 使用 `replace_all: false` 并提供唯一上下文

### 问题 2: replace_all 意外替换了部分不应替换的路径

**现象**: `${BASE_URL}/${spaceId}/` 被全局替换，但有些地方应该用 `'/v1/views'` 而不是 `${BASE_URL}/spaces/${spaceId}/`

**解决**:
- 分阶段执行替换
- 先替换模板字符串中的路径
- 再单独处理硬编码的视图路径

### 问题 3: 遗漏的 /v1/consumption/views 路径

**现象**: 第一轮替换后，spaceApi.ts 中仍有多处 `/v1/consumption/views`

**原因**: 使用 `${BASE_URL}/spaces/${spaceId}/` 的替换模式无法匹配硬编码的 `/v1/consumption/views`

**解决**:
- 使用 Grep 全面搜索 `v1/consumption` 模式
- 逐个修复遗留路径

### 问题 4: schema/overview 路径映射错误

**现象**: 前端调用 `/schema/overview`，后端已改为 `/schema`

**解决**:
- 发现问题后立即修正前端路径

### 问题 5: load-from-yaml vs load-yaml

**现象**: 前端调用 `load-from-yaml`，后端已改为 `load-yaml`（连字符改下划线）

**解决**:
- 检查后端实际路径
- 更新前端调用

---

## 经验总结

### 1. API 重构检查清单

```
□ Backend 路由 prefix 变更
□ Backend 嵌套路径修正（/{space_id} → /spaces/{space_id}）
□ Frontend BASE_URL 修正
□ Frontend 模板字符串路径修正
□ Frontend 硬编码路径修正（特别是 /v1/consumption, /v1/views）
□ load-from-yaml 等特殊路径映射
□ schema/overview → schema
□ deprecation headers 指向正确的新路径
```

### 2. 验证方法

**Backend 验证**:
```bash
curl http://localhost:8000/openapi.json | python -c "..."
```
- 检查路径是否按预期变更
- 确认无残留的旧路径

**前端验证**:
```bash
grep -r "/v1/management\|/v1/consumption" src/
```
- 确认无残留的旧 API 路径（注释除外）

**Playwright 端到端测试**:
- 启动前端服务器
- 测试关键页面加载
- 验证 API 调用成功

### 3. 代码组织建议

**API 路径常量化**: 将 API 路径提取为常量，避免散落在各处
```typescript
const API_PATHS = {
  SPACES: '/v1/spaces',
  VIEWS: '/v1/views',
  // ...
}
```

**替换操作的执行顺序**:
1. 先执行精确匹配的单次替换
2. 再执行批量替换
3. 最后验证残留模式

---

## 变更文件清单

### Backend (5 文件)
- `ontology_engine/api/routes/management.py` - prefix + 嵌套路径
- `ontology_engine/api/routes/consumption.py` - prefix + schema-graph 路径
- `ontology_engine/api/routes/schema.py` - deprecation headers
- `ontology_engine/api/routes/entities.py` - deprecation headers
- `ontology_engine/api/routes/visualization.py` - deprecation headers

### Frontend (3 文件)
- `ontology-engine-ui/src/api/spaceApi.ts` - BASE_URL + 路径
- `ontology-engine-ui/src/pages/ConsumptionViewPage.tsx` - 硬编码路径
- `ontology-engine-ui/src/pages/consumption/ConsumptionViewListPage.tsx` - 硬编码路径

---

## 相关文档

- 提案: `docs/02-design/02-api-redesign-proposal.md`
- 状态: `docs/STATUS.md` (待更新)
