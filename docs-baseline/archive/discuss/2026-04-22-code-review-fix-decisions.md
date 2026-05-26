# 代码审查修复：关键决策记录

> 日期: 2026-04-22
> 触发: 代码审查发现 5 个设计偏差 + 15 个代码质量问题 + 4 个跨模块一致性问题
> 状态: 实施中

## 审查范围

最近 6 次提交（`f95a75b` ~ `a6951b3`），涉及 90+ 文件、+15,818/-8,354 行变更。

核心模块：Expression Engine / Extraction Pipeline / Query Engine / Storage

## 关键决策

### D-1: L1 超时机制 — multiprocessing 隔离

**问题**: `threading.Timer` 无法中断同步 asteval 执行，超时机制完全无效（C-1）

**选项评估**:
| 方案 | 可靠性 | 开销 | 平台兼容 | 与 asyncio 兼容 |
|------|--------|------|----------|----------------|
| multiprocessing 隔离 | ✅ 最高 | 高（fork 进程） | 全平台 | ✅ |
| sys.settrace 计数 | 中 | 低 | 全平台 | ✅ |
| signal.alarm | 高 | 低 | ❌ 仅 Unix | ❌ 与 asyncio 冲突 |

**决策**: 采用 multiprocessing 隔离。子进程执行 asteval，超时后 terminate。

**理由**: 安全关键路径（表达式执行）必须保证超时可中断，即使开销较大也可接受（L1 本身预期 1-50ms 延迟，fork 开销 ~10ms）。

### D-2: L0 fallback 策略 — 保留有限 fallback

**问题**: L0 执行失败无条件 fallback 到 L1，违反分级安全模型（S-1）

**选项评估**:
| 方案 | 安全性 | 兼容性 | 设计一致性 |
|------|--------|--------|-----------|
| 移除 fallback | ✅ 最高 | ❌ 破坏现有行为 | ✅ 完全对齐 |
| 有限 fallback | 中 | ✅ 兼容 | 部分对齐 |
| 暂不修改 | 最低 | ✅ | ❌ |

**决策**: 保留有限 fallback — 仅在 `FunctionNotDefined` / `NameNotDefined` 时 fallback

**理由**: simpleeval 不支持列表字面量等合法语法，完全移除 fallback 会导致合法表达式执行失败。有限 fallback 在安全（语法/类型错误不 fallback）和兼容（功能缺失 fallback）间取得平衡。

### D-3: UUID5 去重 — DedupStrategy 增加模糊匹配

**问题**: AST 和 LLM 提取器对同一实体生成不同 entity_id（C-New-5）

**选项评估**:
| 方案 | 去重准确率 | 实现复杂度 | 向后兼容 |
|------|-----------|-----------|---------|
| 统一为 AST 格式 | ✅ 最高 | 中（LLM 需关联 source_fragment_id） | ❌ ID 变更 |
| 统一为 name+fact_object | 高 | 低 | ❌ ID 变更 |
| DedupStrategy 模糊匹配 | 高 | 中 | ✅ |

**决策**: DedupStrategy 增加基于 `name` + `fact_object` 的二次匹配

**理由**: 不改变现有 ID 生成策略（向后兼容），在去重层增加模糊匹配作为安全网。未来可考虑统一 ID 生成。

### D-4: Cypher 参数化范围 — 仅修 P0 路径

**问题**: KuzuDB Cypher 查询使用 f-string 拼接，存在注入风险（C-5）

**决策**: 仅将 `get_neighbors` 和 `_get_fragment_neighbors` 中的用户可控参数（node_id, fragment_id, node_concept）改为参数化查询

**理由**: 这两个方法是 Query Engine 的直接入口，暴露面最大。其他方法（retrieval.py）的参数来自内部构造，风险较低，后续迭代处理。

**限制**: Cypher 标签名和关系类型名无法参数化（KuzuDB 限制），对 `edge_type` 添加白名单校验。

## 新发现 Bug

### B-3: `detect_cycles` 参数化失效

**位置**: kuzu_store.py:722

`entity_id: '$cid'` 中 `$cid` 被单引号包裹，变成字面量字符串 `"$cid"` 而非参数占位符。导致 `detect_cycles()` 始终搜索不存在的节点，功能完全失效。

**修复**: 移除单引号 → `entity_id: $cid`

### B-4: `LayerSRetriever._fetch_entity` 签名错误

**位置**: layer_s.py:149

调用 `get_entity(entity_id)` 但签名需要两个参数 `get_entity(fact_object, entity_id)`。应使用 `get_entity_by_id(entity_id)`。

**影响**: Layer-S 实体详情获取功能完全不可用（运行时 TypeError）。

## 修复批次

| Batch | 修复项 | 优先级 |
|-------|--------|--------|
| 1 | Fix-1~4 (L1超时/虚假证据链/签名修复/detect_cycles) | P0 |
| 2 | Fix-5 (L1预处理) | P0 |
| 3 | Fix-6~9 (有限fallback/Entity属性/模糊去重/Cypher参数化) | P1 |
| 4 | Fix-10~16 (缓存/日志/副作用/去重查询/时区/日期精度/文档同步) | P2 |
