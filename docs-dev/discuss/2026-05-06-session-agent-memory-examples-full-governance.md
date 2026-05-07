# Session: Agent Memory Examples 全面治理

> 日期: 2026-05-06
> 主题: case5-16 案例全面治理 — 封装修复 + 脚本补全 + CLIRunner 扩展

## 关键决策

### D1: 补齐 5 个缺失的 MemoryAPI 方法（四层完整实现）

**问题**: `correct_memory`, `delete_memory`, `list_my_memories`, `record_commitment`, `check_commitments` 在设计文档中已定义，但四层实现全缺失。

**决策**: 自底向上完整实现：
- MemoryAPI: 5 个方法
- API 路由: 5 个新端点
- CLI 命令: 5 个新命令
- MCP 工具: 5 个新工具

### D2: MemoryAPI 新增 compile/dream 方法

**问题**: case7 T5/T6 和 case16 T5 直接访问内部模块（compilation, _dream），违反封装原则。

**决策**: 在 MemoryAPI 中新增 3 个公共方法：
- `compile_entity_page(entity_id, space_id)` — 编译实体页面
- `compile_topic_page(topic, entity_ids, space_id)` — 编译主题页面
- `run_dream_cycle(space_id)` — 运行 DreamCycle 维护

### D3: CLIRunner 扩展 4 个新方法

**决策**: 在 CLIRunner 中新增：
- `compile_entity(entity_id)` — 包装 compile_entity_page
- `compile_topic(topic, entity_ids)` — 包装 compile_topic_page
- `dream()` — 包装 run_dream_cycle
- `extract_constraints(query)` — 静态工具方法，调用 extract_temporal_constraint

### D4: 增强 reflect_agent 规则矛盾检测

**决策**:
1. 新增实体名称分组（正则匹配中文企业名后缀）
2. 改进否定模式匹配（限制贪婪捕获到 1-8 字符 + 分隔符）
3. 新增风险等级和数值冲突检测
4. 放宽 insight 生成条件

### D5: 全面消除封装违规

| 案例 | 违规类型 | 修复方式 |
|------|---------|---------|
| case7 T5/T6 | 直接导入 compilation + 访问 `cli.api._repo` | 改用 `cli.compile_entity/compile_topic` |
| case8 全部 | 13 个内部模块导入 + 大量 `api._repo/_consolidation/_forgetting/_dream` 访问 | 完全重写为 CLIRunner 模式 |
| case9 run_direct.py | 同 case8 级别 | 新建 run_eval.py 使用 CLIRunner |
| case10 | 13 个内部模块导入 + MemoryCLISimulator | 完全重写为 CLIRunner 模式 |
| case16 T1/T5 | 直接导入 rrf_fusion + 访问 `cli.api._dream` | 改用 `cli.extract_constraints/cli.dream` |

### D6: case11-14 脚本补全

**问题**: case11-14 仅有 results/ 目录，无源代码脚本。

**决策**: 为每个案例创建 run_eval.py，使用 CLIRunner 标准接口：
- case11: 生命周期 + MCP 接口验证（8 轨迹）
- case12: Gap 19-25 验证（8 轨迹）
- case13: 全量 Agent 记忆评估（8 轨迹）
- case14: 真实 LLM 评估（8 轨迹）

### D7: CLIRunner 方法名修正

**问题**: `types()` 调用 `get_memory_types()` 但 MemoryAPI 实际方法名为 `get_types()`。

**决策**: 修正 CLIRunner.types() 调用为 `self._api.get_types()`。

## 变更文件清单

| 文件 | 变更类型 |
|------|---------|
| `ontology_engine/engine/cognitive/memory_api.py` | 新增 8 方法（5+3） |
| `ontology_engine/engine/cognitive/reflect_agent.py` | 增强矛盾检测 |
| `ontology_engine/engine/cognitive/repository.py` | 新增 delete_cognitive_edge |
| `ontology_engine/api/routes/memory.py` | 新增 5 端点 |
| `ontology_engine/cli/memory.py` | 新增 5 命令 |
| `ontology_engine/mcp/tools/memory.py` | 新增 5 工具函数 |
| `ontology_engine/mcp/server.py` | 注册 5 新工具 |
| `examples/_lib/cli_runner.py` | 新增 4 方法 + 修复 2 处 |
| `examples/case7_*/run_eval.py` | 修复 T5/T6 封装 |
| `examples/case8_*/run_eval.py` | 完全重写（784→250行） |
| `examples/case9_*/run_eval.py` | 新建 CLIRunner 版本 |
| `examples/case10_*/run_eval.py` | 完全重写 |
| `examples/case11_*/run_eval.py` | 新建 |
| `examples/case12_*/run_eval.py` | 新建 |
| `examples/case13_*/run_eval.py` | 新建 |
| `examples/case14_*/run_eval.py` | 新建 |
| `examples/case15_*/run_eval.py` | 重写 T1/T2/T4/T5/T7 |
| `examples/case16_*/run_eval.py` | 修复 T1/T5 封装 |
| `docs/STATUS.md` | 更新状态 |
| `docs/02-design/agent-memory/memory-api.md` | 去重 + 更新工具数 |

## 验证结果

| 案例 | 通过/总数 | 封装状态 | 轨迹数 |
|------|----------|---------|--------|
| case5 | 8/8 ✅ | 无违规 | 8 |
| case6 | 7/7 ✅ | 无违规 | 7 |
| case7 | 8/8 ✅ | 已修复 | 8 |
| case8 | 10/10 ✅ | 已重写 | 10 |
| case9 | 6/6 ✅ | 已重写 | 6 |
| case10 | 6/6 ✅ | 已重写 | 6 |
| case11 | 8/8 ✅ | 新建 | 8 |
| case12 | 8/8 ✅ | 新建 | 8 |
| case13 | 8/8 ✅ | 新建 | 8 |
| case14 | 8/8 ✅ | 新建 | 8 |
| case15 | 8/8 ✅ | 已修复 | 8 |
| case16 | 8/8 ✅ | 已修复 | 8 |

**总计: 92/92 轨迹全部通过，0 封装违规**
