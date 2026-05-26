# 文档治理全面分析报告

> **日期**: 2026-05-14
> **范围**: 全项目文档体系（docs/、docs-dev/、docs-baseline/、docs-rust/、docs-ui/、discuss/、CLAUDE.md）
> **方法**: 从 CLAUDE.md 出发，逐层遍历文档结构、内容质量、规则执行情况，对比代码实现
> **状态**: draft

---

## 一、文档体系总体评价

### 优势
1. **三层分离清晰**：docs/（活跃）+ docs-baseline/（归档）+ docs-dev/（过程），结构合理
2. **标注体系完备**：[单一事实源]、[关键设计点]、[待扩展]、[待核对代码]、[已过期入口] 五类标注
3. **审查流程完整**：审视重写覆盖 8 个模块（Schema/Storage/RuleEngine/QueryEngine/Extraction/Services/API/Formula）
4. **治理自动化**：`doc-governance-check.sh` 实现了结构、标注、元数据、discuss 四项自动化检查
5. **文档角色分层**：入口层/状态层/路线层/Backlog 层/认知层/设计层/RFC 层/规范层/Bugfix 层/调研层 10 层清晰定义
6. **SoT 约定完整**：各主题唯一入口已明确映射

### 总体健康分评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 结构完整度 | ⚠️ 75/100 | 结构合理但有空目录和未集成目录 |
| 标注合规率 | ⚠️ 70/100 | 部分标注使用不规范 |
| 元数据新鲜度 | ⚠️ 50/100 | last_verified 大面积过期 |
| 规则执行度 | ❌ 40/100 | 多条 CLAUDE.md 规则未被遵守 |
| 代码一致性 | ⚠️ 65/100 | 模块边界有三处违规，API server 有跨层调用 |
| **总分** | **⚠️ 60/100** | **需改进** |

---

## 二、关键 GAP 清单

### 🔴 GAP-1：CLAUDE.md 规则执行严重缺失

| 规则 | CLAUDE.md 规定 | 实际状态 | 严重度 |
|------|---------------|----------|--------|
| **x-doc-owner 元数据** | 规则 #11：每份设计文档必须有 owner | **0 份文档实现** | 🔴 严重 |
| **complexity 标注** | 规则 #11：标注复杂度 S/M/L | **0 份文档实现** | 🔴 严重 |
| **last_agent_verified** | 规则 #11：标注最近自动化验证时间 | **0 份文档实现** | 🔴 严重 |
| **设计文档元数据** | 规则 #9：status/phase/source_of_truth/last_verified/verified_against | 部分实现，缺少 `verified_against` | 🟡 中等 |
| **状态更新** | STATUS.md 更新要求 #5：审视完成后 under-review→accepted/draft | 所有 8 个模块仍为 `draft`，审视完成已近一个月 | 🟡 中等 |

**结论**：CLAUDE.md 规则 #9/#11 已写入但从未被遵守和审计。这是一条**纸面规则**——定义完美但零执行。

---

### 🔴 GAP-2：discuss/ 目录治理失控

| 问题 | 详情 |
|------|------|
| **3 个 discuss 目录** | `docs-dev/discuss/`（33 文件）、`discuss/`（39 文件）、`docs-ui/discuss/`（文件数未统计） |
| **根 discuss/ 未纳入体系** | `discuss/` 在项目根目录，完全不透明——**CLAUDE.md/STATUS.md/README.md 均未提及** |
| **归档阈值已触发** | `docs-dev/discuss/` 33 文件 > 30 阈值（首条 2026-04-19），但**未触发归档流程** |
| **文件无生命周期管理** | 仅有 2 个 ADR（ADR-008, ADR-009），大量关键决策停留在 discuss 级别未升级为 ADR |

**建议**：
- 将 `discuss/` 整合到 `docs-dev/discuss/` 或明确声明其角色
- 对 `docs-dev/discuss/` 执行归档：将超过 30 天的文件移至 `docs-baseline/archive/discuss/`
- L1/L2 级决策（如 ADR-008 中的决策）应正式化为 ADR 

---

### 🔴 GAP-3：未集成文档目录

| 目录 | 文件数 | 状态 | 问题 |
|------|--------|------|------|
| `docs-rust/` | ~20+ 文件 | 完全未集成 | Rust 架构设计，**CLAUDE.md 和 STATUS.md 均未提及** |
| `docs-ui/` | ~20+ 文件 | 半集成 | 有 README 但不在 STATUS.md 的主文档矩阵中 |
| `docs/plans/` | 9 个计划文件 | 完全未纳入结构 | 不在 CLAUDE.md 的三层结构中 |
| `docs/03-rfc/` | 空目录 | 残留 | CLAUDE.md 说 RFC 放在 `docs-dev/03-rfc/`，但 `docs/03-rfc/` 仍为空残留目录 |

**建议**：
- `docs-rust/` → 要么合并入 docs/，要么移入 docs-baseline/ 并标注废弃
- `docs-ui/` → 在 STATUS.md 中增加文档矩阵条目
- `docs/plans/` → 在 CLAUDE.md 增加说明或移入 docs-dev/
- `docs/03-rfc/` → 删除空目录或改为符号链接到 docs-dev/03-rfc/

---

### 🟡 GAP-4：文档新鲜度大面积过期

| 文档 | last_verified | 距今天数（2026-05-14） | 状态 |
|------|---------------|----------------------|------|
| `docs-dev/04-migration-and-gap/README.md` | 2026-04-16 | **28 天** | ⚠️ 老旧，需重新核验代码 |
| `docs/02-design/storage/kuzudb-schema.md` | 2026-04-19 | **25 天** | 老旧 |
| `docs/02-design/services/README.md` | 2026-04-19 | **25 天** | 老旧 |
| `docs/02-design/query-engine/README.md` | 2026-04-19 | **25 天** | 老旧 |
| `docs/02-design/api/README.md` | 2026-04-19 | **25 天** | 老旧且 [待核对代码] |
| `docs/01-overview/05-concepts.md` | 2026-05-14 | **0 天** | ✅ 新鲜 |
| `docs/STATUS.md` | 2026-05-14 | **0 天** | ✅ 新鲜 |
| `docs/ROADMAP.md` | 2026-05-14 | **0 天** | ✅ 新鲜 |

> 设计文档（02-design/）整体自 2026-04-19 后未更新，距今 25 天。考虑到这期间实施了 Agent 记忆系统、RFC-020~025、前端审查等多个重大变更，**设计文档已落后于代码演进**。

---

### 🟡 GAP-5：文档标注使用不合规

| 问题 | 发现 | 影响 |
|------|------|------|
| **"已实现"误当目标设计** | `rule-engine/04-rule-engine-design.md` 等 8 处使用"已实现"描述目标设计 | 违反规则 #8（示例代码不得写成"已实现"口吻） |
| **[待核对代码] 错用** | `API/README.md` 和 `agent-memory/memory-api.md` 使用 [待核对代码]，但实际是设计文档 | 违反规则 #5 |
| **SoT 声明冲突** | `01-overview/05-concepts.md` 和 `02-design/formula/function-library.md` 都声明 [单一事实源] | 概念级 SoT 和实现级 SoT 边界模糊 |

---

### 🟡 GAP-6：代码与文档模块边界偏差

| 检查项 | CLAUDE.md 声明 | 代码实际 | 问题 |
|--------|--------------|----------|------|
| **API→storage 直接依赖** | 禁止跨层调用 | `api/server.py:27` 直接 `from ontology_engine.storage.config import create_meta_store` | 🔴 违规 |
| **API→engine 直接依赖** | 禁止跨层调用 | `api/server.py:106` 直接 `from ontology_engine.engine.cognitive.factory import MemoryAPISingleton` | 🔴 违规 |
| **API→core 直接依赖** | 禁止跨层调用 | `api/server.py:28-29` 直接 `from ontology_engine.core.schema import SchemaLoader` | 🟡 可接受（core 层性质特殊） |
| **Engine→storage** 直接调用 | 仅通过 base.py 接口 | `engine/cognitive/activity_log.py` 直接 `import sqlite3` | 🟡 应在存储层封装 |
| **Engine 内 sqlite3 调用** | 禁止 | `activity_log.py:149` 和 `pipeline_state.py:466` 直接 `sqlite3.connect` | 🟡 引擎不应直接操作 SQLite |

**建议**：
- 更新 CLAUDE.md 的约束检查命令以反映实际违规
- 将 `activity_log.py` 中的 SQLite 操作封装到 `storage/local/`
- 将 `api/server.py` 中的跨层导入重构到 `services/` 层

---

### 🟡 GAP-7：doc-governance-check.sh 检查能力不足

| 当前缺失检查 | 影响 |
|-------------|------|
| 未检查 `x-doc-owner` / `complexity` 元数据 | 规则 #11 零执行 |
| 未检查根目录 `discuss/` | 不透明目录未暴露 |
| 未检查 `docs/plans/` 游离文档 | 计划文档不在治理范围内 |
| 未检查 `docs-rust/` 和 `docs-ui/` | 未集成目录无合规压力 |
| 未检查 overview 文档的大小（如 01-vision.md 905 行） | 文档过长影响可维护性 |
| 未检查 design 文档复杂度过大的文件（如 agent-memory/memory-api.md 986 行, optimization-sota.md 1246 行） | 文件过大应拆分 |
| 未检查 STATUS.md 中 `discuss/` 文件数声明是否准确 | STATUS.md 说 33，需同步 |
| 未检查 [单一事实源] 声明数量 | 多个 SoT 声明引发混淆 |

---

### 🟢 GAP-8：文档体积膨胀

| 超大文档 | 行数 | 问题 |
|----------|------|------|
| `01-overview/01-vision.md` | 905 行 / 45KB | 含 6 大旅程、8 个核心问题、五层架构、7 大参考系统——信息密度过高 |
| `01-overview/10-kb-process.md` | 938 行 | 新文档，含三阶段 + 梦境循环等，过于详细 |
| `02-design/agent-memory/memory-api.md` | 986 行 | 含完整 API 定义 + 配置表 + 对比表，可拆分 |
| `02-design/agent-memory/optimization-sota.md` | 1246 行 | 超大调研文档，含 SOTA 对比 + 第三方分析 |
| `02-design/storage/kuzudb-schema.md` | 1042 行 | 含完整 DDL + 字段表，可拆分 |

**建议**：
- 对 500+ 行文档设置拆分或重构提醒
- `01-vision.md` 应将 6 大旅程、参考系统对比等独立成子文档
- `memory-api.md` 应将 embedding 配置、认知边定义等拆分为独立参考文档

---

### 🟢 GAP-9：质量门禁检查命令不准确

**问题**：CLAUDE.md 中 "质量门禁" 和 "快速检查" 的 grep 命令存在以下问题：

1. `grep -r "from neo4j\|from redis\|import psycopg" ontology_engine/ --include="*.py" \| grep -v "adapters/"` 
   - 这些模式在当前代码库中没有匹配（✅），但没有检查 `import sqlite3` 在 engine/ 中的直接使用（❌）

2. `grep -r "sqlite3\|faiss\|redis" ontology_engine/{api,services,engine}/ --include="*.py"`
   - 这个命令**确实会命中** `engine/cognitive/activity_log.py` 和 `engine/rule/pipeline_state.py`

3. `mypy ontology_engine/ --strict`
   - 这个命令可能无法通过（Agent memory 代码类型标注可能不完整）

4. `pytest tests/unit/ -v --cov`
   - 单元测试仅 66 个，覆盖率未知

**建议**：
- 在 CLAUDE.md 质量门禁部分增加对 engine/ 中 sqlite3 直接调用的检查
- 运行一次完整的质量门禁并修复失败的检查项
- 确保 `mypy --strict` 在当前代码库上通过

---

### 🟢 GAP-10：测试覆盖率与测试规范

| 检查项 | 实际 | 规范要求 | 偏差 |
|--------|------|----------|------|
| 单元测试总数 | 66 个 | 无明确目标 | 相对于 12 个模块太少 |
| 测试目录结构 | `tests/unit/` 存在 | docs-dev/development/testing.md 定义 | ✅ 符合规范 |
| 覆盖率门禁 | 未运行 | ≥80% | ❌ 无法验证 |
| E2E 测试 | 根目录 3 个脚本 | testing.md 定义 | 半符合 |
| 集成测试 | `tests/integration/` 是否存在？ | testing.md 定义 | 待确认 |

---

## 三、关键决策记录（备份）

### 决策 D-2026-05-14-01：根 discuss/ 目录归属

**问题**：项目根目录的 `discuss/`（39 文件）与 `docs-dev/discuss/`（33 文件）并存，角色不清晰。

**建议**：
- 根 `discuss/` 为旧版本遗留（首条 2026-04-08），内容已被 `docs-dev/discuss/` 覆盖
- 建议统一为 `docs-dev/discuss/`，将根 `discuss/` 内容合并或归档

---

### 决策 D-2026-05-14-02：docs-rust/ 文档集

**问题**：`docs-rust/` 是一套独立的 Rust 架构设计文档（版本 0.1.0, 2026-04-07），与 Python 实现的 Py 文档体系完全平行。

**建议**：
- 明确 Rust 架构在当前项目中的地位——是备选实现、未来方向还是历史尝试
- 若不再维护 → 移入 `docs-baseline/` 并标注 history
- 若继续维护 → 在 STATUS.md 和 CLAUDE.md 中声明

---

### 决策 D-2026-05-14-03：docs-ui/ 文档集成

**问题**：`docs-ui/` 有 README 有结构但未在 STATUS.md 主矩阵中。

**建议**：
- STATUS.md 增加 `docs-ui/` 条目（draft 状态）
- 明确前端文档入口与后端文档体系的连接方式

---

### 决策 D-2026-05-14-04：元数据强制执行

**问题**：x-doc-owner 和 complexity 零执行。

**建议**：
- 在 `doc-governance-check.sh` 中增加强制检查规则
- 要求所有 02-design/ 文档在下次更新时补全元数据
- 设定缓冲期（例如 2026-06-01 后不达标标记为 WARN）

---

## 四、汇总修复路线

```
Phase 0（紧急 - 本周）:
  P0-1: 治理脚本增强：增加 x-doc-owner/complexity 检查，增加根 discuss/ 检查
  P0-2: docs/03-rfc/ 空目录清理
  P0-3: API server.py 中的跨层调用（storage.config, engine.cognitive）重构
  P0-4: docs-dev/discuss/ 归档（超 30 文件，首条 4/19）

Phase 1（重要 - 两周内）:
  P1-1: 根 discuss/ 合并到 docs-dev/discuss/ 或归档
  P1-2: docs-rust/ 状态明确（归档或声明）
  P1-3: docs-ui/ 在 STATUS.md 中注册
  P1-4: docs/plans/ 在文档体系中声明
  P1-5: 修复 API README.md 的 [待核对代码] 标注
  P1-6: 运行质量门禁（mypy + pytest + cov）

Phase 2（改善 - 一个月内）:
  P2-1: 02-design/ 所有文档补充 x-doc-owner/complexity 元数据
  P2-2: 02-design/ 文档 last_verified 更新
  P2-3: 拆分成大文档（memory-api.md, optimization-sota.md, kuzudb-schema.md）
  P2-4: 修复 design 文档中的 "已实现" 误当目标设计
  P2-5: engine/ 中 sqlite3 直接调用封装到 storage/local/

Phase 3（长期）:
  P3-1: documents-to-ADR 升级：关键 discuss 决策转为正式 ADR
  P3-2: 文档健康分纳入质量门禁
  P3-3: 实现文档 AI 校验（自动检测标注合规、SoT 冲突）
  P3-4: 建立文档自动新鲜度追踪系统
```

---

## 五、附录：CLAUDE.md 规则执行状态全表

| 规则 | 类别 | 执行状态 | 合规率 |
|------|------|----------|--------|
| #1 本地存储优先 | 约束 | ✅ 基本合规 | 90% |
| #2 API 边界封闭 | 约束 | ⚠️ 3 处违规（api/server.py） | 80% |
| #3 测试先行 | 约束 | ⚠️ 66 个单测，覆盖率未知 | 60% |
| #4 文档同步 | 约束 | ❌ 不可自动化验证 | — |
| #5 边界外扩需审批 | 约束 | ⚠️ 部分（需人工核对） | — |
| #6 RFC 先行 | 约束 | ✅ 20 个 RFC | 90% |
| 硬规则 #1-13 | 文档治理 | ⚠️ 规则 #9/#11 零执行 | 70% |
| 质量门禁 | 质量 | ❌ 未确认是否实际运行 | — |
| 快速检查 | 质量 | ⚠️ grep 命令不全 | 60% |
| HOOK | 流程 | ⚠️ discuss 记录存在，但 governance-check 未确保每次运行 | — |

> 本文件已备份到 `docs-dev/discuss/`。
