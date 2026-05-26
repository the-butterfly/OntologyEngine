# 参考设计深度解析

> **作用**: 存放外部参考系统（7 大参考系统 + 业界方案）的设计展开内容
> **最后更新**: 2026-05-15
> **使用规则**: 本项目主要设计文档（docs/02-design/）只保留设计结论和决策理由；参考系统的完整实现细节、伪代码、算法参数等展开内容统一放置在此目录

---

## 设计原则

1. **结论在正式文档，细节在参考目录**：docs/02-design/ 和 docs/01-overview/ 中的设计文档只保留设计结论、决策理由和关键原则；来自外部参考系统的实现级细节（伪代码、算法参数、具体接口）统一存放在本目录
2. **保持可追溯性**：每个参考文件标注来源系统、版本、原文链接，确保原始参考可追溯
3. **非权威参考**：本目录内容不代表 OntologyEngine 设计，仅记录外部参考系统的设计方案供设计时参考
4. **与设计文档的对应关系**：每个参考文件在对应的设计文档中以一句话 + 脚注形式引用

---

## 文件清单

| 文件 | 覆盖参考系统 | 对应设计文档 |
|------|------------|------------|
| [`external-reference-systems.md`](./external-reference-systems.md) | LLM-Wiki-Agent, QMD, Graphify, m_flow, MAMGA, MemPalace, KAG, Understand-Anything, Cognee | `docs/01-overview/01-vision.md` §关键设计点 |
| [`agent-memory-paradigms.md`](./agent-memory-paradigms.md) | Mem0, Zep/Graphiti, Hindsight, BYTEROVER, Memory-R1, Kumiho + BEAM/LoCoMo/LongMemEval 基准 | `docs/02-design/agent-memory/` |

---

## 使用方式

当需要查看某个设计决策的外部参考依据时：
1. 在 `docs/02-design/` 对应设计文档中找到 `(参考 docs/reference/xxx.md)` 脚注
2. 到本目录阅读外部系统的完整实现细节
3. 回到设计文档确认最终设计结论

> 本目录不参与设计文档的治理检查（governance-check 排除此目录）。
