# Session 2026-05-04: Agent Memory GAP Analysis & E2E Verification

## 参与者
- 用户 + AI Agent

## 关键决策

### D-1: LLM注入策略 → 配置式注入
- **决策**: 在factory.py中增加LLM配置项，从config.yaml或环境变量(`OE_LLM_BASE_URL`, `OE_LLM_API_KEY`, `OE_LLM_MODEL`)读取API endpoint，自动注入到ConsolidationEngine和ReflectAgent
- **理由**: 配置式注入最简洁，与现有EmbeddingConfig模式一致，无需运行时切换复杂度
- **实现**: `_load_llm_config()` + `_create_llm_call_fn()` → 统一OpenAI-compatible chat completions协议
- **降级**: 未配置时走规则降级路径，不影响基本功能

### D-2: DeduplicationGate → 独立模块
- **决策**: 实现独立的DeduplicationGate类，在MemoryAPI.remember中调用
- **理由**: 写入前治理是独立关注点，不应内嵌到remember流程中
- **状态**: 待实施（下一轮）

### D-3: Phase 2c类型 → 仅注册
- **决策**: 先在VALID_MEMORY_TYPES中注册4种新类型(commitment/constraint/self_experience/task_state)及对应的_extract_attributes规则和BASE_TYPE_WEIGHTS
- **理由**: 注册成本低，边类型和完整attributes JSON后续补充
- **实现**: 已完成

### D-4: 矛盾检测增强 → 规则增强 + 后续LLM计划
- **决策**: 在规则矛盾检测基础上增加互斥值检测(同subject不同value)，后续增加LLM判断能力
- **理由**: 规则增强零依赖，立即可用；LLM注入后可进一步提升质量
- **实现**: `_has_mutually_exclusive_values()` 检测12种中文值冲突模式

### D-5: 中文BM25分词 → ASCII+CJK单字+bigram
- **决策**: 从`\w+`改为ASCII词+CJK单字+CJK bigram三级token策略
- **理由**: `\w+`将整句中文当作单个token，导致BM25完全失效；新策略在中文场景下检索从0%提升到100%
- **实现**: `_simple_tokenize()` 重写

## 代码变更清单

| 文件 | 变更 |
|------|------|
| `engine/cognitive/cognitive_vector_index.py` | 中文分词修复 |
| `engine/cognitive/reflect_agent.py` | 互斥值矛盾检测 |
| `engine/cognitive/models.py` | 4种新memory_type注册 |
| `engine/cognitive/memory_api.py` | _infer_cognitive_layer/_extract_attributes扩展 |
| `engine/cognitive/rrf_types.py` | BASE_TYPE_WEIGHTS扩展 |
| `engine/cognitive/factory.py` | LLM配置式注入 |
| `api/routes/memory.py` | REST API参数补全 |
| `mcp/tools/memory.py` | MCP工具参数补全 |
| `cli/memory.py` | CLI参数补全 |
| `docs/02-design/agent-memory/memory-api.md` | BM25分词策略文档 |

## 端到端验证结果

| 案例 | 通过率 |
|------|--------|
| case8 (LOCOMO评估) | 12/12 (100%) |
| case9 (E2E验证) | 8/8 (100%) |
| 单元测试 | 196/196 (100%) |

## 待实施

1. ~~**DeduplicationGate独立模块**~~ — ✅ 已实现
2. ~~**ArbitrationEngine**~~ — ✅ 已实现
3. ~~**实体合并 merge_entities**~~ — ✅ 已实现
4. ~~**L3消歧 LLM辅助**~~ — ✅ 已实现
5. **权限治理端点** — my/correct/delete/commitments
6. **QueryUnderstandingLayer** — 深层查询约束提取

## 第二轮: BUG修复 + 4个功能实现

### BUG修复清单

| # | BUG | 修复 |
|---|-----|------|
| 1 | factory.py: 外部传入llm_config缺少enabled键 | 自动补充`enabled=bool(base_url)` |
| 2 | factory.py: 环境变量设base_url后yaml不加载 | 始终尝试yaml fallback |
| 3 | cognitive_vector_index.py: CJK bigram跨非CJK字符产生伪组合 | 使用finditer获取位置，只组合原文相邻CJK |
| 4 | reflect_agent.py: 跨字段矛盾误报(使用Python vs 位于北京) | 内层循环只比较同field模式 |
| 5 | models.py: DispositionProfile.audit()超出安全边界 | 扩展evidence_demand上界到1.0, recency_bias到0.9 |
| 6 | memory_api.py: _compute_is_newer()逻辑错误 | 改为async实例方法，实际获取对方节点时间戳比较 |
| 7 | reflect_agent.py: 矛盾去重键不正确 | 使用(type, sorted(node_ids))元组作为去重键 |

### 新增模块

| 模块 | 文件 | 功能 |
|------|------|------|
| DeduplicationGate | deduplication_gate.py | 写入前治理: 向量去重(>0.92)+矛盾前置(0.80-0.92)+边际价值评估 |
| ArbitrationEngine | arbitration_engine.py | 证据加权裁决: proof_count×source_trust×recency×confidence |
| merge_entities | entity_resolver.py | 实体合并: 属性合并+边重定向+标记superseded+MERGED_INTO边 |
| L3消歧 | entity_resolver.py | LLM辅助: L2评分0.3-0.6时调用LLM判断是否同一实体 |

### 验证结果

| 案例 | 通过率 |
|------|--------|
| case8 (LOCOMO评估) | 12/12 (100%) |
| case9 (E2E验证) | 8/8 (100%) |
| 单元测试 | 196/196 (100%) |
