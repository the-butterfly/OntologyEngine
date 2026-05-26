# Session Context 层

> **status**: draft | **phase**: phase2 | **source_of_truth**: D-5 设计决策 | **last_verified**: 2026-05-15

---

## 目的

在 Layer-R/S 之上增加 Session Context 层，解决当前 recall 无会话辨识的问题——区分"刚讨论过的"和"三周前的"。

## 设计

### Session 结构

```python
@dataclass
class SessionContext:
    session_id: str
    space_id: str
    start_time: datetime
    recent_nodes: list[str]        # 本次会话涉及的 CognitiveNode IDs
    recent_turns: list[TurnRecord] # 最近 N 轮交互
    disposition: DispositionProfile # 当前会话的倾向配置
```

### Session Recall 优先级

```
1. 当前会话中创建的节点                           → 最高优先级 (boost × 2.0)
2. 当前会话中引用/确认的节点                      → 高优先级 (boost × 1.5)
3. 空间内其他节点（按 TEMPR 正常流程）             → 标准优先级
4. 跨空间节点                                     → 低优先级
```

### 生命周期

| 阶段 | 条件 | 行为 |
|------|------|------|
| 创建 | 新会话开始 | 清空 session_id，加载 disposition |
| 活跃 | 交互进行中 | 追加 turn，标记近期节点 |
| 过期 | 无交互 > 30 min | 降级为 History Session（保留不活跃） |
| 归档 | 会话结束 | 写入 SQLite ActivityLog |

> 详细实现参考 `docs/02-design/agent-memory/memory-api.md` §oe_recall。
