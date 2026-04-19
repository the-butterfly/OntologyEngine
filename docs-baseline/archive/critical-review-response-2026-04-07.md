# 设计批评分析与优化方案

> **注意**: 本文档已被拆分为独立的 ADR 文件，完整内容请查阅以下文件。

---

## 批评综述

> 评价："野心超出执行能力的设计"

**承认的问题**：
- 实现细节考虑不足（并发、安全、持久化）
- 技术选型策略模糊（自研 vs 复用）
- 工作量评估过于乐观
- 核心功能（Agent Memory）设计缺失

**需要澄清的误解**：
- "本地优先"与"预留Neo4j接口"并非矛盾，而是分层策略
- 16周是指MVP骨架，不是完整功能

---

## ADR 索引

| ADR | 主题 | 来源 |
|-----|------|------|
| [001-sqlite-graphstore-v2.md](./architecture/decisions/001-sqlite-graphstore-v2.md) | SQLiteGraphStore 并发与一致性改进 | 问题1 (lines 19-328) |
| [002-faiss-vectorstore-persistence.md](./architecture/decisions/002-faiss-vectorstore-persistence.md) | FaissVectorStore 持久化与线程安全 | 问题2 (lines 331-629) |
| [003-expression-engine-security.md](./architecture/decisions/003-expression-engine-security.md) | 表达式引擎安全沙箱 | 问题4 (lines 703-1016) |
| [004-kgml-linkml-integration.md](./architecture/decisions/004-kgml-linkml-integration.md) | KGML 技术选型与 LinkML 集成 | 问题5 (lines 1019-1195) |
| [005-agent-memory-design.md](./architecture/decisions/005-agent-memory-design.md) | Agent Memory 服务设计 | 问题6 (lines 1199-1679) |

---

## 未单独创建 ADR 的内容

| 主题 | 说明 |
|------|------|
| 问题3: Roadmap 与核心约束矛盾澄清 | 已在 [004-kgml-linkml-integration.md](./architecture/decisions/004-kgml-linkml-integration.md) 的 roadmap 部分涵盖 |

---

## 核心改进摘要

| 问题 | 解决方案 | 优先级 |
|------|----------|--------|
| SQLite并发 | 连接池+WAL+SyncManager | P0 |
| Faiss安全 | 读写锁+WAL+自动持久化 | P0 |
| 表达式安全 | AST白名单沙箱 | P0 |
| 工作量低估 | 复用LinkML+ realistic timeline | P1 |
| Agent Memory | 补充完整设计 | P1 |

### 修正后的时间线

```
原16周 ──────────────────────────────────────►
    延长4周用于：
    - 并发安全修复 (+2周)
    - 基于LinkML重构 (+2周)

修正后20周 ───────────────────────────────────►
```

---

## 用户反馈中的额外主题

以下主题来自用户 review feedback，将作为笔记/上下文记录在相应 ADR 中：

- `dimension_attributes` - 维度属性相关
- `规则以数据格式声明` - 规则声明方式
- `LLM 推理` - LLM 推理相关
- `并发写入` - 并发写入问题（已在 ADR-001/002 中覆盖）

---

*最后更新: 2026-04-07*
