# RFC-001: KGML (Knowledge Graph Markup Language)

**Status**: ✅ Adopted
**Date**: 2026-04-08
**Author**: OntologyEngine Team

## 背景

需要一种声明式格式定义：
- 领域本体（概念、关系、属性）
- 业务规则（约束、推理、计算）
- 分析指标（原子/派生/复合）

传统方案的问题：
- RDF/OWL: 学术化，学习曲线陡峭
- JSON Schema: 无规则表达能力
- 硬编码 Python: 不可热更新

## 提案

基于 YAML 的领域特定语言 KGML。

### 核心结构

```yaml
metadata:      # 标识与版本
types:         # 复合类型定义
enums:         # 枚举值
concepts:      # 实体/关系本体
metrics:       # 指标定义
rules:         # 规则集
```

### 设计原则

1. **声明式** —— 描述"要什么"，非"怎么做"
2. **可验证** —— Pydantic 模型校验
3. **可扩展** —— 保留字段支持新特性
4. **人可读** —— YAML 优于 JSON/XML

## 替代方案对比

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| RDF/OWL | 标准完备 | 复杂，工具链重 | ❌ 否决 |
| Protobuf | 性能好 | 无规则表达 | ❌ 否决 |
| JSON Schema | 生态好 | 表达能力弱 | ❌ 否决 |
| Python DSL | 灵活 | 需发版更新 | ❌ 否决 |
| **YAML DSL** | 平衡 | 需自建解析 | ✅ 采用 |

## 实现

```python
# core/schema/loader.py
class KGMLLoader:
    def load(self, path: Path) -> Schema:
        raw = yaml.safe_load(path)
        return Schema(**raw)  # Pydantic 验证
```

## 影响

- 所有业务配置使用 YAML
- Schema 变更无需发版
- 需要配套 Schema 校验工具
