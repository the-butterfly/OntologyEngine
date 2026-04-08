#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OntologyEngine Demo - 供应链金融授信评估

使用 ontology_engine 包进行维度分析：
- 加载 KGML Schema
- 加载实例数据
- 执行维度分析（credit_assessment）

运行方法：
    python -m ontology_engine.examples.supply_chain_finance.demo
"""

import asyncio
from ontology_engine import OntologyEngine


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("OntologyEngine Demo - 供应链金融授信评估")
    print("=" * 60)

    # 创建引擎
    print("\n📦 创建引擎...")
    engine = OntologyEngine.from_config(
        "examples/supply_chain_finance/schema.yaml"
    )
    await engine.initialize()
    print("✅ 引擎创建成功")

    # 加载实例
    print("\n📥 加载实例数据...")
    await engine.load_instances(
        "examples/supply_chain_finance/instances.yaml"
    )
    print("✅ 实例加载成功")

    # ============================================================
    # 案例 1: 优质供应商
    # ============================================================
    print("\n" + "=" * 60)
    print("📌 案例 1: 优质供应商（预期：正常授信）")
    print("=" * 60)

    result1 = await engine.analyze(
        entity_id="SUP_2024_001",
        dimension="credit_assessment"
    )

    print(f"\n🏢 企业: {result1.entity_id}")
    print(f"📊 维度: {result1.dimension}")
    print(f"✅ 规则执行: {len(result1.rule_results)} 条")
    print(f"⚠️ 预警: {len(result1.alerts)} 条")
    print(f"📋 决策: {result1.decision}")

    if result1.alerts:
        print("\n预警详情:")
        for alert in result1.alerts:
            print(f"  [{alert.level.upper()}] {alert.message}")

    # ============================================================
    # 案例 2: 高风险供应商
    # ============================================================
    print("\n" + "=" * 60)
    print("📌 案例 2: 高风险供应商（预期：拒绝或严格限制）")
    print("=" * 60)

    result2 = await engine.analyze(
        entity_id="SUP_2024_003",
        dimension="credit_assessment"
    )

    print(f"\n🏢 企业: {result2.entity_id}")
    print(f"📊 维度: {result2.dimension}")
    print(f"✅ 规则执行: {len(result2.rule_results)} 条")
    print(f"⚠️ 预警: {len(result2.alerts)} 条")
    print(f"📋 决策: {result2.decision}")

    if result2.alerts:
        print("\n预警详情:")
        for alert in result2.alerts:
            print(f"  [{alert.level.upper()}] {alert.message}")

    # ============================================================
    # 案例 3: 担保圈供应商
    # ============================================================
    print("\n" + "=" * 60)
    print("📌 案例 3: 担保圈供应商（预期：担保圈预警）")
    print("=" * 60)

    result3 = await engine.analyze(
        entity_id="SUP_2024_A",
        dimension="credit_assessment"
    )

    print(f"\n🏢 企业: {result3.entity_id}")
    print(f"📊 维度: {result3.dimension}")
    print(f"✅ 规则执行: {len(result3.rule_results)} 条")
    print(f"⚠️ 预警: {len(result3.alerts)} 条")
    print(f"📋 决策: {result3.decision}")

    if result3.alerts:
        print("\n预警详情:")
        for alert in result3.alerts:
            print(f"  [{alert.level.upper()}] {alert.message}")

    # ============================================================
    # 总结
    # ============================================================
    print("\n" + "=" * 60)
    print("📊 案例对比总结")
    print("=" * 60)

    print(f"\n{'案例':<15} {'供应商ID':<15} {'决策':<20}")
    print("-" * 60)

    cases = [
        ("案例1", result1),
        ("案例2", result2),
        ("案例3", result3),
    ]

    for case_name, result in cases:
        print(f"{case_name:<15} {result.entity_id:<15} {result.decision or 'N/A':<20}")

    print("\n" + "=" * 60)
    print("✅ Demo 完成")
    print("=" * 60)

    # 清理
    await engine.close()


if __name__ == "__main__":
    asyncio.run(main())
