# RFC-020~025 实施审查报告

> **审查日期**: 2026-05-12
> **审查范围**: docs/02-design/agent-memory/ + docs-dev/03-rfc/RFC-020 ~ RFC-025
> **审查方法**: 6 个并行 sub-agent 逐项对照代码实现 + 单元测试验证 + eval 结果分析

## 总体结论

| RFC | 状态 | 完成度 | 最大缺口 |
|-----|------|--------|----------|
| RFC-020 | partially-implemented | ~75% | CONTRADICTION_CANDIDATE 处理不完整 |
| RFC-021 | partially-implemented | ~80% | LLM 提取为 stub，QUL 后置处理不完整 |
| RFC-022 | partially-implemented | ~69% | LLM tool-calling 循环未实现 |
| RFC-023 | mostly-implemented | ~85% | QUL 后置处理 5 项未实现 |
| RFC-024 | mostly-implemented | ~80% | OCC 底层实现缺失，模块边界 V2/V3 未修复 |
| RFC-025 | partially-implemented | ~65% | Phase 6 (LLM 反思) 完成度最低 |

**GAP 修复进度**: 52 个 GAP 中 28 已修复 (54%)、16 部分修复 (31%)、8 未修复 (15%)

## 审查新发现的运行时 Bug

| # | Bug | 严重度 | 位置 | 说明 |
|---|-----|--------|------|------|
| NB-1 | `KuzuGraphStore.update_cognitive_node_with_occ` 方法不存在 | **P0** | kuzu_store.py | repository.update_node_with_occ 调用时会抛出 AttributeError |
| NB-2 | `MemoryAPI.update_disposition` 依赖 `_disposition_store` 但 __init__ 未初始化 | **P1** | memory_api.py:1038 | 方法体永远不会执行保存逻辑 |
| NB-3 | `models.validate_node_fields` 未被 `repository._validate_node` 调用 | **P2** | repository.py:508 | 新字段校验规则形同虚设 |
| NB-4 | `MemoryAPI` 缺少 `run_dream_cycle` 属性 | **P1** | memory_api.py | 04_locomo T9 评估直接失败 |

## 各 RFC 详细审查

### RFC-020: 记忆生成路径优化 (~75%)

| 设计决策 | 完成度 | 关键差距 |
|----------|--------|----------|
| D1: IngestionService 双层写入 | 75% | CognitiveIngestionService 已实现；DeduplicationGate 缺 source_content_hash 快速路径；ExtractionPipeline 定义在 ingestion_service.py 而非独立文件 |
| D2: CONTRADICTION_CANDIDATE 处理 | 40% | 仅设置 belief_status=pending_review，缺少高优先级 Consolidation 触发和 _log_contradiction_candidate() |
| D3: COG_SUPPORTED_BY 边创建 | 70% | ingest 和 execute_create 已创建边，但 execute_update 缺少 COG_SUPPORTED_BY 边 |
| D4: OCC version 字段 | 100% | update_node() 支持 expected_version |
| D5: L1 精确匹配 | 100% | _resolve_l1_exact() 完整实现 |
| D7: consolidation_reasoning | 90% | 格式与 RFC 指定不一致 |
| D8: 补充缺失定义 | 60% | _log_contradiction_candidate() 未实现 |

### RFC-021: QUL 完整实现 (~80%)

| 设计决策 | 完成度 | 关键差距 |
|----------|--------|----------|
| D1: QUL 统一入口 + 类型定义 | 95% | 所有数据类和映射已实现 |
| D2: 约束提取器关键词表 | 70% | 8 种提取器全部存在；RuleExtractor 非 ABC；extract 签名缺 context；EntityTargetExtractor 缺 repository 缓存；ConfidenceDemandExtractor 缺 5 个关键词 |
| D4: recall 集成 | 95% | 完整集成链路 |
| D5: QUL 与 detect_query_type 统一 | 60% | QueryRouter.route() 未委托 QUL，两套判定逻辑并存 |
| D6: _extract_with_llm | 10% | stub 实现 |

### RFC-022: LLM 反思 + 策略性遗忘 (~69%)

| 设计决策 | 完成度 | 关键差距 |
|----------|--------|----------|
| D1: LLM 反思混合模式 | ~39% | 当前为单次 JSON prompt 模式，缺 tool-calling 循环、6 工具集、_ToolExecutor、_TokenTracker |
| D2: 策略性遗忘 | 100% | 完整实现含级联限制 |
| D3: 遗忘因子修正 | 100% | confirmation 使用 exp(-0.05×days)，衰减率使用 feedback_weight |
| D4: CorrectionPropagation 差异化 | 100% | 6 种 memory_type 差异化标记完整 |
| D5: DreamCycle Phase 5 修正 | ~25% | 仅规则层词重叠+COGNITIVE_RELATES_TO 边 |

### RFC-023: 检索路径优化 (~85%)

| 设计决策 | 完成度 | 关键差距 |
|----------|--------|----------|
| D1: FTS5 双表 BM25 索引 | 80% | FTS5Manager 功能等价但类结构不同；缺 on_fragment_updated |
| D2: Analytical 查询路由修复 | 95% | 缺 COG_SUPPORTED_BY 证据回溯 boost |
| D3: 降级链路径切换 | 100% | 完全对齐 RFC |
| D4: 后置排序 + 短路优化 | 100% | 完全对齐 RFC |
| D5: DispositionProfile 7 维度 | 100% | 完全对齐 RFC |
| D6: valid_from/valid_to 统一过滤 | 95% | 签名差异但功能等价 |
| D7: BASE_TYPE_WEIGHTS 对齐 | 100% | 12 个键值对完全一致 |
| D8: QUL 约束驱动重排序集成 | 50% | 缺 5 项后置处理 |

### RFC-024: CognitiveNode 模型补齐 + Bug 修复 (~80%)

| 设计决策 | 完成度 | 关键差距 |
|----------|--------|----------|
| D1: 运行时 Bug 修复 | 100% | B1-B4 全部修复 |
| D2: CognitiveNode 字段补齐 | 95% | validate_node_fields 未被调用 |
| D2.1: Schema 迁移 | 70% | 无 ALTER TABLE 迁移脚本 |
| D2.2: OCC 并发控制 | 50% | KuzuGraphStore 缺底层实现；OCCQueue 缺失 |
| D3: 模块边界修复 | 60% | V2 未修复（sqlite3）；V3 部分实现 |
| D4: 静默吞异常修复 | 40% | disposition_store.py 两处 except pass 未修复 |

## 验收组通过率

| 验收组 | 通过率 | 关键问题 |
|--------|--------|----------|
| 01_ingestion | 100% (8/8) | T1 recall_hits=0（低分通过） |
| 02_contradiction | 100% (7/7) | T1 score=0.33（低分通过） |
| 04_locomo | 70% (7/10) | T8/T10 节点丢失；T9 MemoryAPI 缺 run_dream_cycle |
| 05_lifecycle | 100% (8/8) | T1 recall=False（低分通过） |
| 06_full_agent | 87.5% (7/8) | T1 User Model hits=0 |

**单元测试**: 262/262 passed (tests/unit/engine/cognitive/)

## LLM 端点验证

- 端点 `localhost:9528` 可达
- 模型 `sensenova/sensenova-6.7-flash-lite` 已注册
- api_key 不能为空字符串（需非空值如 `sk-dummy`），但使用 dummy key 时返回 OUT_OF_RANGE 错误
- **结论**: LLM 端点当前不可用于实际调用，所有 LLM 相关功能（反思、提取、QUL LLM 层）均以降级模式运行

## 下一步优先级建议

1. **P0**: 修复 NB-1 (KuzuGraphStore.update_cognitive_node_with_occ 缺失)
2. **P0**: 修复 NB-4 (MemoryAPI 缺 run_dream_cycle)
3. **P1**: 修复 NB-2 (update_disposition _disposition_store 未初始化)
4. **P1**: 实现 RFC-023 D8 缺失的 5 项 QUL 后置处理
5. **P1**: 实现 RFC-020 D2 CONTRADICTION_CANDIDATE 完整处理链
6. **P2**: 重构 RFC-022 D1 LLM 反思为 tool-calling 循环模式
7. **P2**: 修复 RFC-024 D3 V2 (activity_log sqlite3 迁移) 和 D4 (静默吞异常)
