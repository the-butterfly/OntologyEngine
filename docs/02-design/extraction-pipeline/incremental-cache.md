# 增量缓存与检查点

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` | **last_verified**: 2026-04-19

## 目的

定义提取管线的增量缓存机制——通过 SHA256 内容哈希判断文件是否变更，跳过未变更文件的提取；通过语义缓存分离 AST 和 LLM 提取结果；通过推理检查点支持中断恢复。增量缓存是控制 LLM 调用成本的核心机制。

## 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 每次全量提取都调用 LLM，token 成本过高 | SHA256 哈希比对，未变更文件跳过提取 |
| 2 | YAML frontmatter 变更（如 status/tags）导致缓存误失效 | Markdown body-only 哈希策略 |
| 3 | AST 缓存与 LLM 缓存生命周期不同但混在一起 | 语义缓存分离，AST 和 LLM 结果独立缓存 |
| 4 | LLM 提取中断后需从头开始 | 推理检查点保存中间结果，支持断点续传 |
| 5 | 缓存写入过程中崩溃导致数据损坏 | 原子写入模式（temp file → rename） |

---

## SHA256 缓存键

### 缓存键计算

```
cache_key = SHA256(file_content + \x00 + relative_path)
```

| 组成部分 | 说明 | 参考项目 |
|----------|------|----------|
| file_content | 文件的原始字节内容 | Graphify file_hash |
| \x00 | 分隔符，防止 content 和 path 拼接歧义 | Graphify |
| relative_path | 相对于项目根目录的路径，使缓存可跨机器移植 | Graphify file_hash |

### Markdown 特殊处理

Markdown 文件的缓存键只哈希 body 部分（YAML frontmatter 以下的内容）：

```
def body_content(content: bytes) -> bytes:
    text = content.decode(errors="replace")
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].encode()
    return content

cache_key = SHA256(body_content(raw) + \x00 + relative_path)
```

**理由**：YAML frontmatter 中的 status、tags、reviewed 等元数据变更不应使提取缓存失效——这些变更不影响文档的语义内容。

### 参考项目对齐

| 参考项目 | 模式 | OntologyEngine 对齐 |
|----------|------|-------------------|
| Graphify file_hash | SHA256(content + \x00 + relative_path) | 完全复用 |
| Graphify _body_content | Markdown body-only 哈希 | 完全复用 |
| Cognee DataPoint.source_content_hash | SHA256 内容哈希用于增量缓存 | 在 Instance 层 source_content_hash 字段复用 |

---

## 三层缓存架构

```
┌─────────────────────────────────────────────────────────────┐
│  缓存层                                                      │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ AST 缓存         │  │ 语义缓存         │  │ 推理检查点   │ │
│  │                 │  │ (LLM 提取结果)   │  │             │ │
│  │ cache/{hash}.json│  │ cache/{hash}.json│  │ checkpoint/ │ │
│  │                 │  │                 │  │ {run_id}.json│ │
│  │ 生命周期:       │  │ 生命周期:       │  │ 生命周期:   │ │
│  │ 文件内容不变    │  │ 文件内容不变    │  │ 单次管线运行 │ │
│  │ 即有效          │  │ 即有效          │  │ 完成后清除   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### AST 缓存

| 属性 | 说明 |
|------|------|
| 存储位置 | `{cache_dir}/ast/{hash}.json` |
| 缓存键 | SHA256(file_content + relative_path) |
| 缓存值 | `{"entities": [...], "edges": [...], "extracted_from_edges": [...]}` |
| 失效条件 | 文件内容变更（hash 不匹配） |
| 读取 | `load_ast_cache(path, root) → dict | None` |
| 写入 | `save_ast_cache(path, result, root) → None` |

### 语义缓存（LLM 提取结果）

| 属性 | 说明 |
|------|------|
| 存储位置 | `{cache_dir}/semantic/{hash}.json` |
| 缓存键 | SHA256(file_content + relative_path) |
| 缓存值 | `{"entities": [...], "edges": [...], "categories": [...], "supported_by_edges": [...]}` |
| 失效条件 | 文件内容变更（hash 不匹配） |
| 读取 | `check_semantic_cache(files, root) → (cached, uncached)` |
| 写入 | `save_semantic_cache(nodes, edges, categories, root) → int` |

### 语义缓存检查流程

```
check_semantic_cache(files: list[str], root: Path)
  → (cached_entities, cached_edges, cached_categories, uncached_files)

for each file in files:
  result = load_cached(Path(file), root)
  if result is not None:
    cached_entities.extend(result.get("entities", []))
    cached_edges.extend(result.get("edges", []))
    cached_categories.extend(result.get("categories", []))
  else:
    uncached_files.append(file)

return (cached_entities, cached_edges, cached_categories, uncached_files)
```

### 语义缓存保存流程

```
save_semantic_cache(entities, edges, categories, root)
  → 按 source_file 分组
  → 每组保存为一个缓存文件

by_file = defaultdict(lambda: {"entities": [], "edges": [], "categories": []})
for entity in entities:
  src = entity.get("source_file", "")
  if src:
    by_file[src]["entities"].append(entity)
for edge in edges:
  src = edge.get("source_file", "")
  if src:
    by_file[src]["edges"].append(edge)
for category in categories:
  src = category.get("source_file", "")
  if src:
    by_file[src]["categories"].append(category)

for fpath, result in by_file.items():
  save_cached(Path(fpath), result, root)
```

### 参考项目对齐

| 参考项目 | 模式 | OntologyEngine 对齐 |
|----------|------|-------------------|
| Graphify load_cached / save_cached | SHA256 哈希键 + JSON 缓存文件 | 完全复用存储模式 |
| Graphify check_semantic_cache | 返回 (cached, uncached) 分离 | 扩展为 (cached_entities, cached_edges, cached_categories, uncached_files) |
| Graphify save_semantic_cache | 按 source_file 分组保存 | 扩展为按 source_file 分组，增加 categories |
| Graphify cached_files | 返回有效缓存文件集合 | 复用，用于缓存状态查询 |
| Graphify clear_cache | 删除所有缓存文件 | 复用，用于强制重新提取 |

---

## 推理检查点

### 目的

在 LLM 提取过程中保存中间结果，支持中断后从检查点恢复，避免重复 LLM 调用。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | LLM 提取大批量文件时中断需从头开始 | 检查点记录已完成的文件和提取结果 |
| 2 | 检查点数据与最终结果混在一起 | 检查点独立存储，管线完成后清除 |

### 检查点结构

```json
{
  "run_id": "pipeline_20260419_001",
  "started_at": "2026-04-19T10:00:00Z",
  "total_files": 150,
  "processed_files": 87,
  "current_file": "src/engine/rule_engine.py",
  "results": {
    "entities": [...],
    "edges": [...],
    "categories": [...],
    "supported_by_edges": [...]
  },
  "token_usage": {
    "input_tokens": 125000,
    "output_tokens": 45000
  }
}
```

### 检查点操作

| 操作 | 说明 |
|------|------|
| `create_checkpoint(run_id)` | 创建初始检查点 |
| `update_checkpoint(run_id, file_path, results)` | 处理完一个文件后更新检查点 |
| `load_checkpoint(run_id) → dict | None` | 加载检查点，返回 None 表示无检查点 |
| `clear_checkpoint(run_id)` | 管线完成后清除检查点 |

### 恢复流程

```
load_checkpoint(run_id)
  │
  ├─ 检查点存在?
  │   ├─ 否 → 从头开始
  │   └─ 是 → 从检查点恢复
  │            processed = checkpoint.processed_files
  │            remaining = total_files - processed
  │            只处理 remaining 文件
  │
  └─ 合并结果
      final_results = checkpoint.results + new_results
```

---

## 原子写入

### 目的

确保缓存文件和检查点文件的写入是原子操作，避免写入过程中崩溃导致数据损坏。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 写入过程中崩溃导致缓存文件损坏 | temp file → rename 原子写入模式 |
| 2 | Windows 上 os.replace 可能因文件锁定失败 | 回退到 copy-then-delete |

### 原子写入流程

```
save_cached(path, result, root):
  h = file_hash(path, root)
  entry = cache_dir(root) / f"{h}.json"
  tmp = entry.with_suffix(".tmp")

  try:
    tmp.write_text(json.dumps(result), encoding="utf-8")
    try:
      os.replace(tmp, entry)       # 原子 rename
    except PermissionError:
      shutil.copy2(tmp, entry)      # Windows 回退
      tmp.unlink(missing_ok=True)
  except Exception:
    tmp.unlink(missing_ok=True)     # 清理临时文件
    raise
```

### 参考项目对齐

| 参考项目 | 模式 | OntologyEngine 对齐 |
|----------|------|-------------------|
| Graphify save_cached | tmp → os.replace → PermissionError 回退 | 完全复用原子写入模式 |
| Graphify cache_dir | graphify-out/cache/ | 改为 {project_root}/.ontology/cache/ |

---

## 缓存目录结构

```
{project_root}/.ontology/
├── cache/
│   ├── ast/                    # AST 提取缓存
│   │   ├── {hash1}.json        # 每个文件一个缓存文件
│   │   ├── {hash2}.json
│   │   └── ...
│   ├── semantic/               # LLM 语义提取缓存
│   │   ├── {hash1}.json
│   │   ├── {hash2}.json
│   │   └── ...
│   └── status/                 # 提取状态追踪
│       └── extraction_status.db  # SQLite: 文件 → hash → status 映射
├── checkpoint/                 # 推理检查点
│   ├── pipeline_{run_id}.json
│   └── ...
└── config.yaml                 # 缓存配置
```

### 缓存配置

```yaml
cache:
  enabled: true
  ast_cache_dir: ".ontology/cache/ast"
  semantic_cache_dir: ".ontology/cache/semantic"
  checkpoint_dir: ".ontology/checkpoint"
  max_cache_size_mb: 500
  cache_ttl_days: 30
  markdown_body_only_hash: true
```

---

## 增量处理流程

### 端到端增量流程

```
IngestionService.ingest(dataset_id)
  │
  ├─ 1. 文件发现
  │     scan_files(dataset.source_uri) → file_list
  │
  ├─ 2. 增量判断
  │     for each file:
  │       current_hash = file_hash(file, root)
  │       cached_hash = lookup_status(current_hash)
  │       if cached_hash == current_hash:
  │         skip (文件未变更)
  │       else:
  │         add to changed_files
  │
  ├─ 3. 分片变更文件
  │     for changed_file:
  │       chunk_text(content) → KnowledgeFragment[]
  │       每个碎片计算 content_hash
  │
  ├─ 4. AST 缓存检查
  │     (cached_ast, uncached_ast) = check_ast_cache(changed_files)
  │     for uncached: ast_extract → save_ast_cache
  │
  ├─ 5. 语义缓存检查
  │     (cached_sem, uncached_sem) = check_semantic_cache(changed_files)
  │     for uncached: llm_extract → save_semantic_cache
  │
  ├─ 6. 合并结果
  │     all_results = merge(cached_ast, new_ast, cached_sem, new_sem)
  │
  └─ 7. 更新状态
        update_extraction_status(file → hash → "extracted")
```

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-CACHE-1 | SHA256 而非 MD5 作为缓存键 | SHA256 碰撞概率极低；Graphify 已验证此模式 |
| D-CACHE-2 | Markdown body-only 哈希 | YAML frontmatter 变更（status/tags）不影响语义内容，不应使缓存失效 |
| D-CACHE-3 | AST 缓存与语义缓存分离 | AST 提取快速且确定性，LLM 提取慢且可能失败；分离后 AST 缓存不受 LLM 失败影响 |
| D-CACHE-4 | 缓存键包含 relative_path | 同名文件在不同目录下应有不同缓存；Graphify 已验证此模式 |
| D-CACHE-5 | 原子写入（temp → rename） | 避免写入过程中崩溃导致缓存损坏 |
| D-CACHE-6 | 推理检查点单次运行后清除 | 检查点是临时数据，管线完成后应清除，避免占用存储 |
| D-CACHE-7 | 缓存文件按 hash 命名而非文件路径 | hash 命名避免路径中的特殊字符问题，且天然去重 |
