# API Error Codes

> **status**: accepted
> **phase**: phase1-enhancement
> **source_of_truth**: 本文档
> **last_verified**: 2026-04-23

---

## 错误响应格式

所有 API 错误响应使用以下格式，并返回正确的 HTTP 状态码：

```json
{
    "success": false,
    "data": null,
    "error": {
        "code": "SPACE_NOT_FOUND",
        "message": "Space 'space_xxx' not found",
        "suggestion": "Use GET /v1/spaces to list available spaces",
        "details": {"space_id": "space_xxx"}
    },
    "meta": {
        "request_id": "...",
        "timestamp": "..."
    }
}
```

字段说明：
- `code`: 结构化错误码，Agent 可据此程序化处理
- `message`: 英文可读错误消息
- `suggestion`: 修复建议，引导 Agent 下一步操作
- `details`: 可选的结构化上下文信息

---

## 错误码注册表

### 4xx 客户端错误

| 错误码 | HTTP | 含义 | suggestion |
|--------|:----:|------|-----------|
| `NOT_FOUND` | 404 | 通用资源不存在 | Use the corresponding list endpoint to find available resources |
| `SPACE_NOT_FOUND` | 404 | 语义空间不存在 | Use GET /v1/spaces to list available spaces |
| `ENTITY_NOT_FOUND` | 404 | 实体不存在 | Use GET /v1/spaces/{id}/instances/entities to list entities |
| `VIEW_NOT_FOUND` | 404 | 消费视图不存在 | Use GET /v1/views to list available views |
| `DATASET_NOT_FOUND` | 404 | 数据集不存在 | Use GET /v1/datasets to list available datasets |
| `CONCEPT_NOT_FOUND` | 404 | 概念类型未定义 | Check schema L1 fact_objects for defined concept types |
| `CONFLICT` | 409 | 通用资源冲突 | Resource already exists, use a different identifier |
| `SPACE_CONFLICT` | 409 | 空间名称冲突 | Use a different name or delete the existing space |
| `DUPLICATE_NAME` | 409 | 名称重复 | Use a unique name for the resource |
| `VALIDATION_ERROR` | 422 | 请求验证失败 | Check request body format against the API schema |
| `SCHEMA_NOT_LOADED` | 422 | Schema 未加载 | Load schema first via POST /v1/spaces/{id}/schema/load-yaml |
| `MISSING_PARAMETER` | 422 | 缺少必需参数 | Check required parameters in the API documentation |
| `INVALID_REQUEST` | 422 | 请求格式无效 | Check request format against the API documentation |
| `FACT_OBJECT_REQUIRED` | 422 | 缺少 fact_object | Provide _fact_object or _concept in the request |
| `FILE_NOT_FOUND` | 422 | 文件不存在 | Check the file path and ensure the file exists |
| `SCHEMA_LOAD_ERROR` | 422 | Schema 加载失败 | Check YAML syntax and schema structure |
| `SCHEMA_CONVERT_ERROR` | 422 | Schema 转换失败 | Check schema format and field types |
| `INSTANCE_LOAD_ERROR` | 422 | 实例加载失败 | Check instance data format and entity types |
| `SPACE_LOAD_ERROR` | 422 | 空间加载失败 | Check space data integrity |

### 5xx 服务端错误

| 错误码 | HTTP | 含义 | suggestion |
|--------|:----:|------|-----------|
| `QUERY_ERROR` | 400 | 查询执行失败 | Check query parameters and try again |
| `ANALYSIS_ERROR` | 500 | 分析执行失败 | Check entity data and rule definitions |
| `INTERNAL_ERROR` | 500 | 内部错误 | Retry the operation or contact support |
| `STORAGE_ERROR` | 500 | 存储层错误 | Check storage configuration and retry |
| `SNAPSHOT_ERROR` | 500 | 快照创建失败 | Check space state and retry |
| `ROLLBACK_ERROR` | 500 | 回退执行失败 | Check version history and space state |
| `INGESTION_ERROR` | 500 | 数据导入失败 | Check data format and retry |

---

## 使用方式

### API 路由中使用

```python
from ontology_engine.api.dto.responses import error_response

# 自动映射 HTTP 状态码
return error_response(
    code="SPACE_NOT_FOUND",
    message=f"Space '{space_id}' not found",
    suggestion="Use GET /v1/spaces to list available spaces",
)

# 手动指定 HTTP 状态码
return error_response(
    code="CUSTOM_ERROR",
    message="Custom error message",
    status_code=400,
)
```

### MCP 工具中使用

```python
from ontology_engine.mcp import mcp_response

return mcp_response(
    success=False,
    error={
        "code": "SPACE_NOT_FOUND",
        "message": f"Space '{space_id}' not found",
        "suggestion": "Use oe_list_spaces to find available spaces",
    },
)
```

---

## 新增错误码规范

新增错误码时必须：
1. 在本文档中注册，包含：错误码、HTTP 状态码、含义、suggestion
2. 在 `responses.py` 的 `_ERROR_CODE_TO_HTTP_STATUS` 映射中添加
3. 错误码命名使用 `UPPER_SNAKE_CASE`
4. 错误码应具有描述性，避免过于通用（使用 `SPACE_NOT_FOUND` 而非 `NOT_FOUND`）
