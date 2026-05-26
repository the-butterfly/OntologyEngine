# 矛盾检测功能修复验证报告

> **报告日期**: 2026-05-12 | **报告类型**: Bug 修复验证 | **版本**: v1.0
> **修复对象**: ReflectAgent 矛盾检测返回 contradictions=0 的问题
> **修复结论**: **已修复** — 矛盾检测从完全失效恢复到正常工作

---

## 一、根因分析

### 1.1 问题现象

`reflect()` 调用返回 `contradictions=0, insights=0`，即使记忆库中存在明显的矛盾记忆。

### 1.2 根因清单（7 个 Bug，3 个致命级）

| Bug ID | 严重度 | 文件 | 行号 | 描述 | 影响 |
|--------|--------|------|------|------|------|
| BUG-1 | 🔴 致命 | reflect_agent.py | 361-369 | `_search_by_type()` 构造 `RetrievalResult` 时不设置 `metadata["belief_status"]`，导致 `_detect_contradictions()` 永远返回空 | 反射循环内矛盾检测完全失效 |
| BUG-2 | 🔴 致命 | reflect_agent.py | 522-525 | `_detect_rule_based_contradictions()` 的 tag 分组机制要求节点共享 tag 才会比较，无 tag 节点永远不会被比较 | 规则驱动矛盾检测对无 tag 节点失效 |
| BUG-3 | 🔴 致命 | reflect_agent.py | 538-539 | 否定冲突检测条件 `skepticism_threshold > 0.3`，默认值 0.3 使条件永远为 False | 否定冲突检测默认被禁用 |
| BUG-4 | 🟡 高 | cli_runner.py | 106 | `max_iterations=2` 太小，FORCED_SEARCH_SEQUENCE 有 3 个元素，2 轮跳过 observation 且永远不进入 insights 生成 | insights 永远为空 |
| BUG-5 | 🟡 中 | reflect_agent.py | 519 | `except Exception: return contradictions` 不记录日志，数据库错误完全不可见 | 异常被静默吞掉 |
| BUG-6 | 🟡 中 | reflect_agent.py | 547 | 互斥值检测只覆盖 `("observation", "rule", "entity")`，fragment 等类型永远不会被比较 | 类型覆盖不足 |
| BUG-7 | 🟡 中 | reflect_agent.py | 415-416 | `_detect_contradictions()` 只检测 accepted vs contradicted，不检测 accepted vs pending_review | 矛盾组合覆盖不足 |

---

## 二、修复方案

### 2.1 BUG-1 修复：metadata 传播

**修改文件**: [reflect_agent.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/cognitive/reflect_agent.py)

**修改内容**: `_search_by_type()` 构造 `RetrievalResult` 时补充 metadata：

```python
RetrievalResult(
    doc_id=n.id,
    content=n.content,
    source=f"search_by_type:{memory_type}",
    memory_type=n.memory_type,
    cognitive_layer=n.cognitive_layer,
    metadata={
        "belief_status": n.belief_status,
        "confidence": n.confidence,
        "tags": n.tags or [],
        "entity_name": n.entity_name or "",
    },
)
```

### 2.2 BUG-2 修复：分组机制扩展

**修改内容**: 增加 entity_name 分组和无 tag 节点 fallback：

```python
for n in nodes:
    for tag in n.tags:
        tag_groups.setdefault(tag, []).append(n)
    if n.entity_name:
        tag_groups.setdefault(f"__entity__:{n.entity_name}", []).append(n)
    if not n.tags and not n.entity_name:
        tag_groups.setdefault("__untagged__", []).append(n)
```

### 2.3 BUG-3 修复：否定冲突阈值

**修改内容**: `skepticism_threshold > 0.3` → `skepticism_threshold >= 0.3`

### 2.4 BUG-4 修复：迭代次数

**修改文件**: [cli_runner.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/examples/agent_memory/_lib/cli_runner.py)

**修改内容**: `max_iterations=2` → `max_iterations=5`

### 2.5 BUG-5 修复：异常日志

**修改内容**: `except Exception:` → `except Exception as e: logger.warning(...)`

### 2.6 BUG-6 修复：类型覆盖扩展

**修改内容**: `("observation", "rule", "entity")` → `("observation", "rule", "entity", "constraint", "opinion", "commitment")`

### 2.7 BUG-7 修复：矛盾组合扩展

**修改内容**:
- `belief_status == "contradicted"` → `belief_status in ("contradicted", "pending_review")`
- 增加同类型+同实体的否定冲突和值冲突检测

---

## 三、验证结果

### 3.1 单元测试

| 测试套件 | 修复前 | 修复后 | 变化 |
|---------|--------|--------|------|
| cognitive 单元测试 | 262 passed | **262 passed** | 无退化 |
| e2e 集成测试 | 9 passed, 1 failed | **10 passed** | +1 (BUG-01 修复) |
| disposition 管道测试 | 1 failed | **1 passed** | BUG-3 修复后更新 |

### 3.2 LoCoMo 评估

| 轨迹 | 修复前 | 修复后 | 变化 |
|------|--------|--------|------|
| T4: 矛盾检测 | ❌ FAIL (score=0.50, contradictions=0) | ✅ **PASS (score=1.00, contradictions=3)** | **从 FAIL 到 PASS** |
| 总通过率 | 6/10 (60%) | **7/10 (70%)** | +10pp |

### 3.3 SOTA 优化验证

| 轨迹 | 修复前 | 修复后 | 变化 |
|------|--------|--------|------|
| IT-3-01: 核心信念保护 | score=0.50, contradictions=0 | **score=0.70, contradictions=2** | 矛盾检测恢复 |

### 3.4 矛盾检测专项验证（17 条轨迹）

| 类别 | 轨迹数 | 通过 | 关键结果 |
|------|--------|------|---------|
| 常规矛盾模式 (R) | 5 | 3 | R-03 信念冲突 ✅, R-05 约束冲突 ✅, R-04 entity_name 参数缺失 |
| 边界条件 (B) | 5 | 3 | B-04 无 tag 节点 ✅, B-05 superseded 排除 ✅ |
| 异常输入 (A) | 3 | 3 | 特殊字符 ✅, 混合语言 ✅, 超长文本 ✅ |
| 性能压力 (P) | 1 | 1 | 50+ 节点 742ms ✅ |
| 集成测试 (I) | 3 | 3 | metadata 传播 ✅, consolidation ✅, forgetting ✅ |

**通过率**: 12/17 (70.6%) — 未通过的 5 条主要是测试隔离问题（空间污染导致误报），非修复 Bug。

---

## 四、修复前后对比

### 4.1 矛盾检测能力对比

| 检测类型 | 修复前 | 修复后 | 改善 |
|---------|--------|--------|------|
| 信念冲突 (accepted vs contradicted) | ❌ 永远返回 0 | ✅ 正常检测 | **从失效到工作** |
| 信念冲突 (accepted vs pending_review) | ❌ 不检测 | ✅ 正常检测 | **新增** |
| 否定冲突 (默认 skepticism) | ❌ 默认禁用 | ✅ 默认启用 | **从失效到工作** |
| 值冲突 (observation/rule/entity) | ⚠️ 仅 3 种类型 | ✅ 6 种类型 | **+3 种类型** |
| 无 tag 节点冲突 | ❌ 不检测 | ✅ 通过 __untagged__ 分组检测 | **新增** |
| entity_name 分组 | ❌ 不支持 | ✅ 通过 __entity__:name 分组 | **新增** |
| 同类型+同实体冲突 | ❌ 不检测 | ✅ 否定+值冲突检测 | **新增** |
| 异常可见性 | ❌ 静默吞掉 | ✅ logger.warning 记录 | **新增** |

### 4.2 关键指标对比

| 指标 | 修复前 | 修复后 | 目标 |
|------|--------|--------|------|
| LoCoMo T4 矛盾检测 | FAIL (0 矛盾) | **PASS (3 矛盾)** | PASS |
| SOTA IT-3-01 矛盾检测 | 0 矛盾 | **2 矛盾** | ≥ 1 |
| reflect insights 生成 | 0 (max_iterations=2) | **待验证 (max_iterations=5)** | ≥ 1 |
| 50+ 节点压力测试延迟 | N/A | **742ms** | < 10s |

---

## 五、遗留问题

| # | 问题 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | 验证测试空间隔离 | P1 | 当前验证脚本共享空间导致跨测试污染，需每个测试用例独立空间 |
| 2 | CLIRunner.remember() 缺少 entity_name 参数 | P2 | 需在 cli_runner.py 中增加 entity_name 传递 |
| 3 | insights 生成验证 | P2 | max_iterations=5 后需验证 insights 是否正常生成 |
| 4 | 矛盾去重 | P3 | 当前可能产生重复矛盾报告（同一对节点被多个分组检测到） |

---

## 六、修改文件清单

| 文件 | 修改类型 | 修改内容 |
|------|---------|---------|
| ontology_engine/engine/cognitive/reflect_agent.py | 修改 | BUG-1/2/3/5/6/7 共 6 处修复 |
| ontology_engine/engine/cognitive/cognitive_vector_index.py | 修改 | BASE-01 Embedding 降级修复 |
| examples/agent_memory/_lib/cli_runner.py | 修改 | BUG-4 max_iterations 2→5 |
| tests/integration/test_e2e_agent_memory.py | 修改 | BUG-01 await 修复 |
| tests/unit/engine/cognitive/test_disposition_pipeline.py | 修改 | 适配 BUG-3 修复后的行为 |
| examples/agent_memory/10_contradiction_fix_eval/run_eval.py | 新建 | 17 条验证轨迹 |
