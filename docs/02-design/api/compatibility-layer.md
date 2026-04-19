# 兼容层设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: [02-api-redesign-proposal.md](02-api-redesign-proposal.md) | **last_verified**: 2026-04-19

---

## 目的

定义从旧 API 路由到新 API 路由的兼容层，确保前端和外部调用方在迁移期间不受影响。兼容层通过 301 重定向和 Deprecation 响应头实现渐进式迁移。

## 解决的问题

| # | 问题 | 方案 |
|---|------|------|
| 1 | 旧路由直接删除会导致前端崩溃 | 301 重定向到新路由 |
| 2 | 调用方不知道路由已变更 | Deprecation 响应头通知 |
| 3 | 需要明确的迁移时间线 | 分阶段弃用，最终删除 |

---

## 兼容策略

### 策略 1: 301 重定向

适用于路径变更但语义不变的端点。服务端返回 `301 Moved Permanently`，Location 头指向新路径。

```http
HTTP/1.1 301 Moved Permanently
Location: /v1/spaces
X-Deprecation-Warning: /v1/management/spaces is deprecated, use /v1/spaces
Deprecation: true
Sunset: Sat, 01 Jul 2026 00:00:00 GMT
```

### 策略 2: Deprecation Header

适用于语义有变化但短期内保持兼容的端点。正常响应 + 弃用警告头。

```http
HTTP/1.1 200 OK
X-Deprecation-Warning: /v1/schema is deprecated, use /v1/ontology
Deprecation: true
Sunset: Sat, 01 Jul 2026 00:00:00 GMT
Link: </v1/ontology>; rel="successor-version"
```

### 策略 3: 兼容层映射

适用于请求/响应结构有变化的端点。兼容层做参数转换后转发到新路由。

---

## 完整映射表

### 管理面路由

| 旧路由 | 新路由 | 策略 | 旧文件 | 新文件 |
|--------|--------|------|--------|--------|
| `POST /v1/management/spaces` | `POST /v1/spaces` | 301 | management.py | spaces.py |
| `GET /v1/management/spaces` | `GET /v1/spaces` | 301 | management.py | spaces.py |
| `GET /v1/management/spaces/{id}` | `GET /v1/spaces/{id}` | 301 | management.py | spaces.py |
| `PUT /v1/management/spaces/{id}` | `PUT /v1/spaces/{id}` | 301 | management.py | spaces.py |
| `DELETE /v1/management/spaces/{id}` | `DELETE /v1/spaces/{id}` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/activate` | `POST /v1/spaces/{id}/activate` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/deactivate` | `POST /v1/spaces/{id}/deactivate` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/archive` | `POST /v1/spaces/{id}/archive` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/schema/L1/fact-objects` | `GET /v1/spaces/{id}/schema/L1/fact-objects` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/schema/L1/fact-objects` | `POST /v1/spaces/{id}/schema/L1/fact-objects` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/schema/L2/categorizations` | `GET /v1/spaces/{id}/schema/L2/categorizations` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/schema/L2/categorizations` | `POST /v1/spaces/{id}/schema/L2/categorizations` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/schema/L3/analytical-elements` | `GET /v1/spaces/{id}/schema/L3/analytical-elements` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/schema/L3/analytical-elements` | `POST /v1/spaces/{id}/schema/L3/analytical-elements` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/schema/L4/rules/definitions` | `GET /v1/spaces/{id}/schema/L4/rules` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/schema/L4/rules/definitions` | `POST /v1/spaces/{id}/schema/L4/rules` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/schema/L4/rules/definitions/{rid}` | `GET /v1/spaces/{id}/schema/L4/rules/{rid}` | 301 | management.py | spaces.py |
| `PUT /v1/management/{id}/schema/L4/rules/definitions/{rid}` | `PUT /v1/spaces/{id}/schema/L4/rules/{rid}` | 301 | management.py | spaces.py |
| `DELETE /v1/management/{id}/schema/L4/rules/definitions/{rid}` | `DELETE /v1/spaces/{id}/schema/L4/rules/{rid}` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/schema/L4/rules/logics` | `GET /v1/spaces/{id}/schema/L4/rules/{rid}/logics` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/schema/L4/rules/logics` | `POST /v1/spaces/{id}/schema/L4/rules/{rid}/logics` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/schema/L4/rules/logics/{lid}` | `GET /v1/spaces/{id}/schema/L4/rules/{rid}/logics/{lid}` | 301 | management.py | spaces.py |
| `PUT /v1/management/{id}/schema/L4/rules/logics/{lid}` | `PUT /v1/spaces/{id}/schema/L4/rules/{rid}/logics/{lid}` | 301 | management.py | spaces.py |
| `DELETE /v1/management/{id}/schema/L4/rules/logics/{lid}` | `DELETE /v1/spaces/{id}/schema/L4/rules/{rid}/logics/{lid}` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/schema/L4/rules/dependency-graph` | `GET /v1/spaces/{id}/schema/rules/dependency-graph` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/instances/entities` | `GET /v1/spaces/{id}/instances/entities` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/instances/entities` | `POST /v1/spaces/{id}/instances/entities` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/instances/relations` | `GET /v1/spaces/{id}/instances/relations` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/instances/relations` | `POST /v1/spaces/{id}/instances/relations` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/versions` | `GET /v1/spaces/{id}/versions` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/versions` | `POST /v1/spaces/{id}/versions` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/versions/{v}/rollback` | `POST /v1/spaces/{id}/versions/{v}/rollback` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/schema/load-from-yaml` | `POST /v1/spaces/{id}/schema/load-yaml` | 301 | management.py | spaces.py |
| `POST /v1/management/{id}/instances/load-from-yaml` | `POST /v1/spaces/{id}/instances/entities/load-yaml` | 301 | management.py | spaces.py |
| `GET /v1/management/{id}/schema/overview` | `GET /v1/spaces/{id}/schema` | 301 | management.py | spaces.py |

### Schema 路由（弃用）

| 旧路由 | 新路由 | 策略 | 旧文件 |
|--------|--------|------|--------|
| `POST /v1/schema/load` | `POST /v1/ontology/load` | Deprecation + 301 | schema.py |
| `GET /v1/schema` | `GET /v1/ontology` | Deprecation + 301 | schema.py |
| `POST /v1/schema/reload` | `POST /v1/ontology/load` | Deprecation + 301 | schema.py |
| `GET /v1/schema/versions` | `GET /v1/ontology/versions` | Deprecation + 301 | schema.py |
| `POST /v1/schema/rollback/{v}` | `POST /v1/ontology/rollback/{v}` | Deprecation + 301 | schema.py |

### 消费面路由

| 旧路由 | 新路由 | 策略 | 旧文件 |
|--------|--------|------|--------|
| `GET /v1/consumption/views` | `GET /v1/views` | 301 | consumption.py |
| `GET /v1/consumption/views/{id}` | `GET /v1/views/{id}` | 301 | consumption.py |
| `GET /v1/consumption/views/{id}/entities` | `GET /v1/views/{id}/entities` | 301 | consumption.py |
| `GET /v1/consumption/views/{id}/visualize/schema-graph` | `GET /v1/views/{id}/schema-graph` | 301 | consumption.py |
| `GET /v1/consumption/views/{id}/rules/dependency-graph` | `GET /v1/views/{id}/rules/dependency-graph` | 301 | consumption.py |
| `GET /v1/consumption/views/{id}/rules/for-entity/{eid}` | `GET /v1/views/{id}/rules/for-entity/{eid}` | 301 | consumption.py |
| `POST /v1/consumption/views/{id}/execute/analyze` | `POST /v1/views/{id}/execute/analyze` | 301 | consumption.py |
| `POST /v1/consumption/views/{id}/execute/simulate` | `POST /v1/views/{id}/execute/simulate` | 301 | consumption.py |

### 可视化路由（弃用）

| 旧路由 | 新路由 | 策略 | 旧文件 |
|--------|--------|------|--------|
| `GET /v1/visualize/schema/graph` | `GET /v1/views/{id}/schema-graph` | Deprecation + 301 | visualization.py |
| `GET /v1/visualize/entities` | `GET /v1/views/{id}/entities` | Deprecation + 301 | visualization.py |
| `GET /v1/visualize/metrics/{eid}` | `GET /v1/views/{id}/metrics/{eid}` | Deprecation + 301 | visualization.py |
| `GET /v1/visualize/rule-chain/{dim}` | `GET /v1/views/{id}/rule-chain/{dim}` | Deprecation + 301 | visualization.py |
| `POST /v1/visualize/simulate` | `POST /v1/views/{id}/execute/simulate` | Deprecation + 301 | visualization.py |
| `GET /v1/visualize/execution/{eid}/{dim}` | `GET /v1/views/{id}/execution/{eid}/{dim}` | Deprecation + 301 | visualization.py |

### 实体/关系路由（弃用）

| 旧路由 | 新路由 | 策略 | 旧文件 |
|--------|--------|------|--------|
| `POST /v1/entities` | `POST /v1/spaces/{id}/instances/entities` | Deprecation + 301 | entities.py |
| `POST /v1/entities/batch` | `POST /v1/spaces/{id}/instances/entities/batch` | Deprecation + 301 | entities.py |
| `GET /v1/entities/{eid}` | `GET /v1/spaces/{id}/instances/entities` | Deprecation + 301 | entities.py |
| `POST /v1/entities/query` | `POST /v1/spaces/{id}/instances/entities` | Deprecation + 301 | entities.py |
| `GET /v1/entities/{eid}/neighbors` | `GET /v1/spaces/{id}/instances/entities` | Deprecation + 301 | entities.py |
| `POST /v1/relations` | `POST /v1/spaces/{id}/instances/relations` | Deprecation + 301 | relations.py |

### 规则路由（兼容层映射）

| 旧路由 | 新路由 | 策略 | 说明 |
|--------|--------|------|------|
| `POST /v1/rule-groups` | `POST /v1/spaces/{id}/schema/L4/rules` | 兼容层映射 | 需从 query param 获取 space_id |
| `GET /v1/rule-groups` | `GET /v1/spaces/{id}/schema/L4/rules` | 兼容层映射 | 需从 query param 获取 space_id |
| `GET /v1/rule-groups/{id}` | `GET /v1/spaces/{id}/schema/L4/rules/{rid}` | 兼容层映射 | |
| `PUT /v1/rule-groups/{id}` | `PUT /v1/spaces/{id}/schema/L4/rules/{rid}` | 兼容层映射 | |
| `DELETE /v1/rule-groups/{id}` | `DELETE /v1/spaces/{id}/schema/L4/rules/{rid}` | 兼容层映射 | |
| `POST /v1/rule-groups/{name}/steps` | `POST /v1/spaces/{id}/schema/L4/rules/{rid}/logics` | 兼容层映射 | name → rule_id |
| `GET /v1/rule-groups/{name}/steps` | `GET /v1/spaces/{id}/schema/L4/rules/{rid}/logics` | 兼容层映射 | |
| `PUT /v1/rule-groups/{name}/steps/{sid}` | `PUT /v1/spaces/{id}/schema/L4/rules/{rid}/logics/{lid}` | 兼容层映射 | |
| `DELETE /v1/rule-groups/{name}/steps/{sid}` | `DELETE /v1/spaces/{id}/schema/L4/rules/{rid}/logics/{lid}` | 兼容层映射 | |
| `POST /v1/rule-groups/{name}/steps/reorder` | `PUT /v1/spaces/{id}/schema/L4/rules/{rid}/logics/reorder` | 兼容层映射 | POST → PUT |
| `POST /v1/rule-groups/{name}/simulate` | `POST /v1/actions/{name}/simulate` | 301 | |
| `POST /v1/rule-groups/import` | `POST /v1/spaces/{id}/schema/load-yaml` | 兼容层映射 | |
| `POST /v1/rule-groups/validate-yaml` | `POST /v1/spaces/{id}/schema/load-yaml` (dry_run) | 兼容层映射 | |
| `GET /v1/rule-groups/{name}/export` | `GET /v1/spaces/{id}/schema/L4/rules/{rid}/export` | 兼容层映射 | |
| `GET /v1/rules` | `GET /v1/spaces/{id}/schema/L4/rules` | 兼容层映射 | |
| `POST /v1/rules/execute` | `POST /v1/actions/{name}/execute` | 301 | |

### 分析路由（弃用）

| 旧路由 | 新路由 | 策略 | 旧文件 |
|--------|--------|------|--------|
| `POST /v1/analysis/execute` | `POST /v1/actions/{name}/execute` | Deprecation + 301 | analysis.py |
| `POST /v1/analysis/dry-run` | `POST /v1/actions/{name}/simulate` | Deprecation + 301 | analysis.py |

### 查询路由

| 旧路由 | 新路由 | 策略 |
|--------|--------|------|
| `POST /v1/query/vector` | `POST /v1/query/search` | 301 |
| `GET /v1/query/pattern-match/{concept}` | `POST /v1/query/graph` (mode=pattern) | 移除 |
| `POST /v1/query/pattern-match/{concept}` | `POST /v1/query/graph` (mode=pattern) | 301 |
| `GET /v1/query/traverse/{eid}` | `POST /v1/query/graph` (mode=traverse) | 移除 |
| `POST /v1/query/traverse/{eid}` | `POST /v1/query/graph` (mode=traverse) | 301 |
| `GET /v1/query/path/{from}/{to}` | `POST /v1/query/graph` (mode=path) | 移除 |
| `POST /v1/query/path` | `POST /v1/query/graph` (mode=path) | 301 |

### DAG/算子路由

| 旧路由 | 新路由 | 策略 |
|--------|--------|------|
| `GET /v1/dag/full` | `GET /v1/spaces/{id}/schema/rules/dependency-graph` | 301 |
| `GET /v1/dag/path` | `GET /v1/spaces/{id}/schema/rules/dependency-graph` | 301 |
| `GET /v1/metrics/{name}/dag` | `GET /v1/spaces/{id}/schema/rules/dependency-graph` | 301 |
| `GET /v1/operators` | `GET /v1/operators` | 不变 |
| `GET /v1/operators/{name}/schema` | `GET /v1/operators/{name}/schema` | 不变 |

---

## Deprecation 响应头规范

所有弃用端点必须返回以下响应头：

```http
X-Deprecation-Warning: {旧路径} is deprecated, use {新路径}
Deprecation: true
Sunset: {弃用日期, ISO 8601}
Link: <{新路径}>; rel="successor-version"
```

### Sunset 时间线

| 阶段 | 日期 | 操作 |
|------|------|------|
| Phase 1 | 2026-04-19 ~ 2026-05-19 | 旧端点返回 301 + Deprecation Header |
| Phase 2 | 2026-05-19 ~ 2026-06-19 | 旧端点返回 301 + Deprecation Header + 日志告警 |
| Phase 3 | 2026-07-01 | 旧端点返回 410 Gone，完全移除 |

---

## 迁移时间线

```
Phase 1: 路由整合 (2 周)
├── 实现新路由文件 (spaces.py, views.py, actions.py, ontology.py)
├── 旧路由添加 301 重定向
├── 旧路由添加 Deprecation Header
└── 前端 spaceApi.ts 更新 BASE_URL

Phase 2: 语义统一 (1 周)
├── 实现 Actions API
├── 实现兼容层映射 (rule-groups → spaces/L4/rules)
├── 前端适配新路由
└── 删除 visualization.ts，迁移到 viewsApi

Phase 3: 清理 (1 周)
├── 删除 semantic_spaces.py
├── 删除 visualization.py
├── 删除 analysis.py
├── schema.py → ontology.py
├── entities.py / relations.py 标记弃用
└── 更新 OpenAPI 文档
```

---

## 实现方式

### FastAPI 中间件实现

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse


class DeprecationMiddleware(BaseHTTPMiddleware):
    ROUTE_MAP = {
        "/v1/management/spaces": "/v1/spaces",
        "/v1/consumption/views": "/v1/views",
        "/v1/schema": "/v1/ontology",
    }

    async def dispatch(self, request, call_next):
        path = request.url.path
        for old_prefix, new_prefix in self.ROUTE_MAP.items():
            if path.startswith(old_prefix):
                new_path = path.replace(old_prefix, new_prefix, 1)
                response = RedirectResponse(
                    url=new_path,
                    status_code=301,
                )
                response.headers["X-Deprecation-Warning"] = (
                    f"{path} is deprecated, use {new_path}"
                )
                response.headers["Deprecation"] = "true"
                response.headers["Sunset"] = "Sat, 01 Jul 2026 00:00:00 GMT"
                response.headers["Link"] = f'<{new_path}>; rel="successor-version"'
                return response

        response = await call_next(request)
        return response
```
