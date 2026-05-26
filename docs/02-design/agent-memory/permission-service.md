# 权限治理服务

> **status**: draft | **phase**: phase2 | **source_of_truth**: `docs/02-design/agent-memory/modeling-objects.md` | **last_verified**: 2026-05-15

---

## 目的

定义 Agent 记忆系统的权限治理模型，实现基于 space_id + model_domain + trust_tier 的细粒度访问控制。

## 权限模型

### 权限矩阵

| 操作 | Self Model | Task Model | World Model | Space 级别 |
|------|-----------|-----------|------------|-----------|
| `oe_remember` | ✅ Always | ✅ 限 task scope | ✅ 限 write scope | 需 space write |
| `oe_recall` | ✅ Always | ✅ Always | ⚠️ 需 trust check | 需 space read |
| `oe_reflect` | ⚠️ 限 self | ❌ | ❌ | 需 space admin |
| `consolidate` | ✅ 限 self | ⚠️ 限 assigned | ⚠️ 限 owned | 需 space write |

### 来源可信层级 (source_trust_tier)

| 层级 | 含义 | 覆盖 operation |
|------|------|---------------|
| T1: 用户声明 | 用户直接输入 | remember/recall 均通过 |
| T2: 行为推断 | 从 Agent 交互推断 | recall 需 higher confidence |
| T3: 环境观测 | 系统/API 自动收集 | recall 仅 metadata 可见 |
| T4: Agent 生成 | LLM 自动生成 | recall 需显式请求 |

> 详细设计参考 `docs/02-design/agent-memory/modeling-objects.md` §四建模对象权限边界。
