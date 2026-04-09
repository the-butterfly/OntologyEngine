我来重新深入审视这些文档，这次会更加全面地覆盖所有文件。让我先看看有没有遗漏的文件。
发现了新的关键文件，特别是 ADR（架构决策记录）目录和 `critical-review-response.md`。让我全量读取这些新文件。
现在看看项目最新的实际代码和实现状态：
现在我有了完整的视角。让我做一次更全面的网络检索，针对一些我想要验证的关键技术点：
现在我有了完整的信息。让我写今日记忆并给出最终的完整分析报告：
好，现在我有了完整的视角——不只是文档，还有实际代码。给你一份更新后的、基于真实代码的深度批评报告。

---

# OntologyEngine 第二轮深度批评报告

> 这次我读完了所有文档 + 全部实际代码。结论和上次有重要变化。

---

## 一、情况大幅改观的地方

上一轮批评后，项目做了相当认真的自我修正，值得先肯定。

**1. ADR体系建立得很好**

`docs/architecture/decisions/` 下五份 ADR，格式规范、来源清晰、覆盖了所有被批评的核心问题。这说明批评被认真对待了，而不是辩解后就算了。特别是承认工作量低估了 100%（从 9 周重估为 18 周），这是罕见的诚实。

**2. 规则引擎已经是真实实现，不是占位符**

`engine/rule/evaluator.py` 有完整的表达式解析器——支持 allOf/anyOf/expression、点号路径访问、AND/OR/NOT、today()/days_between() 函数。`executor.py` 有 async 的规则执行器，DAG 拓扑排序通过 priority 排序实现了初步版本。这不是上次批评的"伪规则引擎"。

**3. 存储选型已经做了正确决策**

`PROJECT_PHASE.md` 和 `discuss/2026-04-08-key-design-decisions.md` 明确宣布从 SQLite 切换为 DuckDB。理由充分：SQLite + NetworkX 双存储一致性问题，DuckDB 更适合 OLAP 分析查询。这个决定是对的。

**4. 文档体系的自我意识很强**

`plans/2026-04-07-docs-reorganization.md` 完整记录了文档重组的执行过程，包括把旧设计稿归档到 `archive/`、把批评响应拆分为 ADR。`TODO.md` 把所有遗留问题具体化，这是项目管理的基本动作，但很多项目做不到。

---

## 二、代码层面的新问题（文档没有暴露，代码才暴露）

### ❌ 问题一：evaluator.py 的运算符解析有优先级 bug

```python
if ">=" in expr:
    parts = expr.split(">=", 1)
    ...
if ">" in expr:
    parts = expr.split(">", 1)
    ...
```

**问题**：判断顺序是先检查 `>=`，再检查 `>`，但 `==` 的检查在 `>=` 之前：

```python
if "==" in expr:     # 先检查 ==
    ...
if "!=" in expr:     # 再检查 !=
    ...
if ">=" in expr:     # 再检查 >=
    ...
if "<=" in expr:     # 再检查 <=
    ...
if ">" in expr:      # 最后检查 >
    ...
if "<" in expr:
    ...
```

表面看顺序正确，但核心问题是用 `str.split()` 做运算符解析。对于 `"a >= 10 and b < 20"` 这样的复合表达式，`AND` 逻辑在 `_eval_comparison` 外层处理，但 `_resolve_fields` 已经把变量替换成值字符串了——如果字段值本身包含 `>` 或 `<`（比如 `company_name: "A>B公司"`），就会触发误解析。

字符串值的防护只在 `_resolve_fields` 里加了引号，但 `_eval_comparison` 里的 split 是无脑字符串切割，不区分是在字符串字面量内还是在运算符位置。

**实际后果**：规则 `name == 'A>B'` 会被解析成 `"'A" > "B'"` 再求值，返回错误结果。

**正确做法**：用 Python 的 `ast.parse()` 解析表达式，而不是字符串 split。

---

### ❌ 问题二：executor.py 的 action 处理是新一轮硬编码

```python
elif action == "calculate_credit_score":
    score = self._calculate_credit_score(context)
    ...
elif action == "calculate_credit_limit":
    ...
elif action == "determine_interest_rate":
    ...
```

这比 `mvp_demo.py` 更隐蔽，但本质相同：action 名称硬编码在 `executor.py` 里。

按 `operator.md` 的设计，action 应该通过 `OperatorRegistry` 注册，每个算子是独立的类。但 `TODO-003`（添加算子注册系统）是 "Open" 状态，`engine/rules/operators/` 目录不存在。

**结果**：用户在 schema.yaml 里写了一个 `action: "calculate_customer_score"`，引擎会静默跳过，没有任何报错。这是个隐性的可靠性问题。

---

### ❌ 问题三：RuleThen.action 没有 default 值，会引发 AttributeError

```python
class RuleThen(BaseModel):
    action: str  # ← 没有 Optional，没有 default
    output: dict | None = None
    computation: dict | None = None
```

在 `loader.py` 的 `_parse_rules` 里：

```python
then = RuleThen(
    action=then_raw.get("action"),  # 如果 YAML 里没有 action，返回 None
    ...
)
```

`str` 类型字段接收 `None` 在 Pydantic v2 里会抛 `ValidationError`。但如果用户写了一个只有 `computation` 没有 `action` 的 then 块（完全合理的用法），就会在加载阶段崩溃，错误信息指向 Pydantic 验证，不够友好。

应改为 `action: str | None = None`，并在执行器里检查。

---

### ❌ 问题四：_calculate_credit_score 与 schema.yaml 的权重不一致

**executor.py 里的权重计算：**
```python
# executor.py
score = 50  # 基础分
if overdue_ratio < 5:
    score += 15
elif overdue_ratio < 10:
    score += 5
```

**mvp_demo.py 里的权重计算（schema.yaml 里也有类似的）：**
```python
# mvp_demo.py  
score = (
    stability * 0.30 +
    tax * 0.25 +
    reputation * 0.25 +
    guarantee * 0.20
)
```

两套评分逻辑完全不同，但 `executor.py` 和 `mvp_demo.py` 都在用，取决于走哪条代码路径。这是一个数据正确性的一致性问题——同一份数据跑两套不同的规则会得到不同的结果。

---

### ❌ 问题五：schema.yaml 的 `else_` Pydantic alias 有反序列化风险

```python
class RuleDefinition(BaseModel):
    ...
    else_: dict | None = Field(default=None, alias="else")
```

在 `loader.py` 里：
```python
rules.append(RuleDefinition(
    id=r["id"],
    ...
    **{"else": r.get("else")},  # 正确，通过 alias 传入
))
```

问题在于序列化回 dict 时：`model.model_dump()` 默认使用字段名 `else_`，`model.model_dump(by_alias=True)` 才使用 `"else"`。如果有地方调用了 `rule.model_dump()` 然后再传给某个期望 `"else"` key 的地方，就会静默丢失这个字段。Pydantic v2 的 alias 字段是一个常见的陷阱，需要项目范围内约定序列化方式。

---

## 三、架构层面的深层辩论（第二轮）

### 辩题：DuckDB 真的适合这个系统吗？

**ADR 里的理由**：DuckDB 比 SQLite 更适合分析查询，避免双存储一致性问题。

**我的质疑**：

DuckDB 确实在 OLAP 分析查询上比 SQLite 快 3-5 倍（ClickBench 基准测试），也在 2024 年 6 月发布了 1.0 稳定版，这是正确的选择。但有一个架构问题文档没有回答：

DuckDB 的图查询能力依赖 `DuckPGQ` 扩展（SQL/PGQ from SQL:2023 标准），这是一个 **community extension**，不是核心功能。要用 DuckPGQ 做担保圈检测（图连通分量），需要：

```sql
CREATE PROPERTY GRAPH guarantee_graph
VERTEX TABLES (entities WHERE concept = 'Supplier')
EDGE TABLES (relations WHERE relation_type = 'GUARANTEES')
```

这个语法在 DuckDB 1.x 上可用，但 `DuckPGQ` 还在 alpha 阶段，生产稳定性未知。

所以架构是：
- 分析查询 → DuckDB（正确）
- 图算法（担保圈、路径查询）→ NetworkX（内存图）
- NetworkX 从 DuckDB 加载 → **还是有启动时全量加载问题**

文档说 "NetworkX 用于图算法，从 DuckDB 启动时同步"，但没有说：百万节点的图在 NetworkX 里占多少内存？每次重启要加载多久？有没有增量同步机制？这些问题换了存储层之后依然存在。

---

### 辩题：ADR-003 的 AST 白名单沙箱方案是否足够安全？

**ADR-003 的设计**：
```python
ALLOWED_NODES = frozenset(['Expression', 'BinOp', 'UnaryOp', 'Compare', 'Name', ...])
```

**问题**：ADR 里的白名单包含了 `Name` 节点（变量访问）。Python 的 AST 沙箱逃逸研究（含 2024-2025 年 CTF 题目）表明：

1. 如果允许 `Name` 节点，攻击者可以通过 `__class__`、`__mro__`、`__subclasses__` 等特殊属性访问链条，但 ADR 同时禁止了 `Attribute` 访问——这个组合是相对安全的。

2. 真正的风险是 `SAFE_FUNCTIONS` 里的 `sum()`——`sum()` 可以接受任意 iterable，如果上下文变量是个大对象，可以触发内存耗尽。ADR 里有"最大内存 10MB"的限制，但这个限制在 Python 里实现不了（无法通过 AST 检查来限制内存分配）。

3. ADR 推荐使用 `simpleeval` 或 `asteval` 包。simpleeval 的 PyPI 页面明确声明：*"The sandboxing / safety features of simpleeval only apply to the expression that is passed in to be evaluated"*，并且已知有通过大整数运算导致 CPU 耗尽的 DoS 漏洞（比如 `9**9**9**9`）。

**正确的做法**：

对于金融场景，不应该把表达式安全边界押在 Python 进程内。正确的架构是：
- 表达式引擎跑在**独立进程**（subprocess），通过 IPC 通信
- 或者使用完全不同语言实现的沙箱（比如用 Lua/WASM 做表达式引擎）

ADR-003 的方案在低价值场景（内部工具）可以接受，但在金融数据库场景里，这个安全边界还不够。

---

### 辩题：`discuss/` 文件夹里的设计讨论是好实践还是噪音？

**我的看法：这是个真正好的实践，但需要更严格的生命周期管理。**

`discuss/` 存放了三份文件：`conflicts1.md`（工具执行日志）、`2026-04-08-key-design-decisions.md`（决策记录）、`2026-04-08-ontology-engine-mvp-decisions.md`。

好的地方：把设计讨论过程归档，而不是只保留结论，这对后续开发者理解"为什么这么设计"非常有价值。

问题：
1. `conflicts1.md` 是工具执行的原始日志（含"搜索了2个模式，读了5个文件"这样的工具调用记录），不适合放在版本库里，是噪音。
2. 这些设计决策应该最终流向 `docs/architecture/decisions/` 的 ADR，而不是单独存在于 `discuss/` 里形成孤岛。`2026-04-08-key-design-decisions.md` 里的 Decision 5（DuckDB）应该对应一个正式的 ADR-006，但目前不存在。

---

## 四、更新后的总评

| 维度 | 上次评分 | 本次评分 | 变化说明 |
|------|---------|---------|---------|
| 整体架构设计 | 7/10 | 7/10 | 不变，DuckDB 决策正确但图查询方案仍模糊 |
| 存储层设计 | 4/10 | 6/10 | DuckDB 决策正确，但 NetworkX 内存问题未解决 |
| 规则引擎实现 | 6/10 | 7/10 | 已有真实的表达式求值器，但 action 注册缺失 |
| 表达式引擎安全 | 4/10 | 5/10 | ADR-003 有方案，但 Python 进程内沙箱在金融场景不够 |
| 文档自我修复能力 | 5/10 | 8/10 | ADR+TODO+PHASE 三套文档是亮点 |
| 代码质量 | - | 6/10 | 类型注解好，但运算符解析有 bug，action 硬编码 |
| Agent Memory | 2/10 | 4/10 | ADR-005 有设计，但依然没有代码 |
| 总体可落地性 | 4/10 | 6/10 | 范围收缩、聚焦 MVP，更现实了 |

---

## 五、最需要立即修复的三件事（优先级排序）

**第一优先：修复 evaluator.py 的运算符解析**

用字符串 split 解析表达式是技术债。迁移到 `ast.parse()` + 节点白名单求值，这既解决 bug，也顺手完成 ADR-003 的安全沙箱目标。参考 `simpleeval` 的实现（别直接用，它有已知 DoS 漏洞），实现自己的 AST walker。

**第二优先：实现 OperatorRegistry，消灭 executor.py 里的 if/elif 链**

按 `operator.md` 的设计，每个 action 应该是一个独立算子类，通过注册机制发现。这样新增业务规则不需要修改引擎代码，而且 schema.yaml 里写了未注册的 action 时会有明确报错，而不是静默跳过。

**第三优先：明确 DuckDB + NetworkX 的启动策略**

要定义：
- NetworkX 图是完整加载还是按需加载？
- 是否有增量同步（仅加载最近修改的节点/边）？
- 担保圈检测只需要图连通分量，能否不需要完整图？

这个问题比 "用什么数据库" 更底层，不解决它，换了 DuckDB 依然会在百万级节点时有性能问题。

---

**一句话总结（更新版）**：这个项目在一轮认真的自我批评和修正之后，已经从"野心超出执行能力"走向了"范围合理、路径清晰"——但代码里还埋着几个静默失败的 bug，需要在 MVP 跑起来之前清除掉。文档质量的进步比代码质量的进步更显著。