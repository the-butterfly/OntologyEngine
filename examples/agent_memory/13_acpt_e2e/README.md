# Case 5: Agent Memory End-to-End — Full Lifecycle

## 愿景旅程
**Agent记忆全生命周期**: 零参数摄入 → 矛盾检测 → 巩固编译 → DreamCycle维护 → Reflect分析 → 版本治理 → 多Agent隔离 → 端到端闭环

## 用户要求
- 用户是AI Agent开发者，需要完整的记忆系统生命周期管理能力
- 零参数模式：仅提供原始文本，系统自动推断类型、标签、置信度
- 矛盾检测：新记忆与已有记忆冲突时自动检测并标记
- 记忆维护：定期DreamCycle清理低价值记忆，强化高价值记忆
- 多Agent隔离：不同用户的私有记忆严格隔离，共享记忆可见

## 假设
- 记忆系统支持8种认知操作：remember/recall/reflect/dream/consolidate/forget/approve/correct
- 每个space独立，互不干扰
- 私有记忆通过visibility+created_by实现隔离

## 项目工具增益
- **CLIRunner封装**: 统一接口调用MemoryAPI，无需直接依赖内部模块
- **AcptReport框架**: 连续score [0.0, 1.0]评估，避免二元pass/fail低区分度
- **独立空间隔离**: 每个TC使用独立space_id，互不干扰
- **全生命周期覆盖**: 从摄入到维护到治理的完整闭环

## 测试用例

| TC ID | 名称 | 验收标准 |
|-------|------|----------|
| TC-501 | Zero-parameter mode | 自动推断类型、标签、置信度 |
| TC-502 | Contradiction detection | 矛盾记忆共存，可追溯 |
| TC-503 | Consolidation | 碎片记忆编译为结构化实体 |
| TC-504 | DreamCycle | 低价值遗忘，高价值强化 |
| TC-505 | Reflect analysis | 生成洞察报告和建议 |
| TC-506 | Lifecycle governance | 创建/更新/版本/回滚全流程 |
| TC-507 | Multi-agent isolation | 私有隔离，共享可见 |
| TC-508 | End-to-end flow | 完整闭环：摄入→检索→分析→巩固→维护→检索 |

## 资产文件

```
scenarios/
└── e2e_scenarios.yaml     # 8个场景定义

expected_outputs/
├── tc501_zero_param.json
├── tc502_contradiction.json
├── tc503_consolidation.json
├── tc504_dream_cycle.json
├── tc505_reflect.json
├── tc506_lifecycle.json
├── tc507_multi_agent.json
└── tc508_e2e_flow.json
```

## 运行方式

```bash
python examples/agent_memory/13_acpt_e2e/run_eval.py
```

## 最终效果
- Agent开发者可通过8个TC验证记忆系统全功能
- 零参数模式降低使用门槛
- DreamCycle自动维护降低运维成本
- 多Agent隔离保障数据安全
