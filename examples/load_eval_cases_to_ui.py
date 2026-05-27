#!/usr/bin/env python3
"""Load eval case data into persistent DB for UI visualization.

Usage:
    python examples/load_eval_cases_to_ui.py

This script populates eval case data into the persistent cognitive DB
(~/.ontology_engine/cognitive_db) so the UI at localhost:3000 can
display the semantic space visualization.

Prerequisites:
    - Backend server running: uvicorn ontology_engine.api.server:app --port 8000
    - UI running: cd ontology-engine-ui && npm run dev (port 3000)

After running, visit:
    http://localhost:3000/spaces/case16_mixed_retrieval/memory?tab=overview
    http://localhost:3000/spaces/case17_knowledge_layering/memory?tab=overview
    http://localhost:3000/spaces/case18_iterative_refinement/memory?tab=overview
"""

from __future__ import annotations

import httpx
import asyncio
import sys
from pathlib import Path

BASE_URL = "http://localhost:8000/v1"


async def remember(space_id: str, content: str, memory_type: str = "fragment",
                   tags: list[str] | None = None, confidence: float = 1.0,
                   created_by: str = "eval_loader", belief_status: str = "accepted",
                   metadata: dict | None = None) -> dict:
    """Call remember API. Tags must be dict[str, str|list[str]]."""
    tags_dict = {"tags": tags} if tags else None
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/spaces/{space_id}/memory/remember",
            json={
                "content": content,
                "memory_type": memory_type,
                "tags": tags_dict,
                "confidence": confidence,
                "created_by": created_by,
                "belief_status": belief_status,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def get_stats(space_id: str) -> dict:
    """Get space stats."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/spaces/{space_id}/memory/stats", timeout=10)
        resp.raise_for_status()
        return resp.json()


async def load_case16_mixed_retrieval():
    """Load case16: Mixed Retrieval — Hybrid RRF Fusion data."""
    space_id = "case16_mixed_retrieval"
    print(f"\n{'='*60}")
    print(f"Loading {space_id}...")

    data = [
        # TC-R01: Factual semantic
        ("TechNova is a cloud infrastructure company based in Shenzhen, founded 2019", "entity", ["company", "TechNova", "factual"], 0.9),
        ("CloudGroup is TechNova's main product, a Kubernetes-based platform", "observation", ["product", "CloudGroup"], 0.85),

        # TC-R02: Multi-hop graph
        ("王芳 is CTO of TechNova, previously worked at Alibaba Cloud", "entity", ["person", "王芳", "TechNova"], 0.9),
        ("TechNova main product is CloudGroup, Kubernetes-based platform", "observation", ["product", "CloudGroup", "TechNova"], 0.85),
        ("CloudGroup supports multi-cluster management and auto-scaling", "observation", ["feature", "CloudGroup"], 0.8),

        # TC-R03: Temporal query
        ("2025 Q1 revenue reached 50M CNY, growth 30% YoY", "observation", ["financial", "2025", "Q1"], 0.9),
        ("2024 Q1 revenue was 38M CNY", "observation", ["financial", "2024", "Q1"], 0.85),

        # TC-R04: BM25 keyword
        ("Metric DSO_DIO: Days Sales Outstanding + Days Inventory Outstanding, formula=DSO+DIO", "observation", ["metric", "DSO_DIO", "exact"], 0.95),
        ("DSO measures average collection period for receivables", "observation", ["metric", "DSO", "related"], 0.8),

        # TC-R05: Mixed query
        ("Rule: 供应商授信额度不超过总敞口15%", "rule", ["rule", "credit_limit"], 0.95),
        ("Entity: 华为技术有限公司, credit_rating AAA, is_whitelist=True", "entity", ["entity", "华为"], 0.9),
        ("Observation: 华为2025年供应链融资规模500亿", "observation", ["observation", "华为", "2025"], 0.85),

        # TC-R06: Confidence filter
        ("High confidence: Production database is PostgreSQL 15", "observation", ["infrastructure", "high_conf"], 0.95),
        ("Low confidence: Office might use MySQL, not sure", "observation", ["infrastructure", "low_conf"], 0.3),

        # TC-R07: Cognitive layer filter
        ("Entity: 供应商A, registered_capital 50M, credit_rating AA", "entity", ["entity", "供应商A"], 0.9),
        ("Rule: 供应商需通过核心企业担保", "rule", ["rule", "担保"], 0.95),

        # TC-R08: Cross-path dedup
        ("CoreEnterprise 华为: credit_rating AAA, whitelist=True, annual_revenue 9000亿", "entity", ["core_enterprise", "华为", "multi_signal"], 0.95),
        ("华为 2025年供应链融资规模500亿, 核心企业担保覆盖300家供应商", "observation", ["observation", "华为", "2025", "multi_signal"], 0.9),
    ]

    for content, mtype, tags, conf in data:
        try:
            await remember(space_id, content, mtype, tags, conf)
        except Exception as e:
            print(f"  WARN: {content[:40]}... failed: {e}")

    stats = await get_stats(space_id)
    total = stats.get("data", stats).get("total", 0)
    print(f"  Loaded {total} nodes into {space_id}")


async def load_case17_knowledge_layering():
    """Load case17: Knowledge Layering — Memory Types, State & Observability data."""
    space_id = "case17_knowledge_layering"
    print(f"\n{'='*60}")
    print(f"Loading {space_id}...")

    data = [
        # TC-L01: All memory types
        ("Entity: 供应商A, credit_rating AA, registered_capital 5000万", "entity", ["supplier", "供应商A", "entity"], 0.9),
        ("Observation: 供应商A Q3营收增长20%, 毛利率42%", "observation", ["supplier", "供应商A", "financial"], 0.85),
        ("Rule: 供应商授信不超过总敞口15%", "rule", ["rule", "credit_limit"], 0.95),
        ("Fragment: 会议提到供应商A可能扩大合作范围", "fragment", ["supplier", "供应商A", "rumor"], 0.5),
        ("Mental model: 供应商A是战略合作伙伴，需长期维护关系，技术互补", "mental_model", ["supplier", "供应商A", "strategy"], 0.95),
        ("Opinion: 供应商A的技术实力在行业内领先，但交付能力有待观察", "opinion", ["supplier", "供应商A", "assessment"], 0.7),
        ("Procedure: 供应商准入流程包括资质审查、信用评级、担保评估", "procedure", ["procedure", "准入流程"], 0.9),
        ("Episode: 2025Q1与供应商A签订框架协议，合作期限3年", "episode", ["episode", "供应商A", "2025"], 0.85),
        ("Commitment: 需在Q2完成供应商A的年度审查", "commitment", ["commitment", "供应商A", "Q2"], 0.9),
        ("Constraint: 供应商A的授信额度上限5000万", "constraint", ["constraint", "供应商A", "limit"], 0.95),
        ("Task state: 供应商A审查进行中，已完成资质审查，待信用评级", "task_state", ["task_state", "供应商A", "in_progress"], 0.8),
        ("Self experience: 上次与供应商A合作交付准时率95%，满意度高", "self_experience", ["self_experience", "供应商A", "history"], 0.85),

        # TC-L02: Analytical layer weights
        ("Mental model: 华为供应链风险低，技术实力强，是核心战略合作伙伴", "mental_model", ["analytic", "华为", "mental_model"], 0.95),
        ("Entity: 华为技术有限公司, credit_rating AAA, revenue 9000亿", "entity", ["analytic", "华为", "entity"], 0.9),
        ("Observation: 华为2025年供应链融资规模500亿", "observation", ["analytic", "华为", "observation"], 0.85),
        ("Fragment: 听说华为在扩展供应链合作伙伴", "fragment", ["analytic", "华为", "fragment"], 0.5),

        # TC-L03: Structured + text
        ("供应商 深圳智造科技有限公司 注册资本5000万人民币 成立于2019年 主营业务为智能硬件研发", "entity", ["supplier", "深圳智造", "structured"], 0.9),

        # TC-L04: Belief status
        ("Rule: 供应商需通过核心企业担保", "rule", ["rule", "belief_test"], 0.9),
        ("Rule: 供应商需通过核心企业担保（待审核版本）", "rule", ["rule", "belief_test", "pending"], 0.6),

        # TC-L05: Supersede chain
        ("Rule v1.0: 供应商授信额度不超过总敞口10%", "rule", ["rule", "credit_limit", "v1"], 0.8),
        ("Rule v2.0: 供应商授信额度不超过总敞口15%（基于Q2数据调整）", "rule", ["rule", "credit_limit", "v2"], 0.9),
        ("Rule v3.0: 供应商授信额度不超过总敞口20%（基于Q3数据调整）", "rule", ["rule", "credit_limit", "v3"], 0.95),

        # TC-L06: Temporal validity
        ("Rule: 2025年供应商准入标准A类 valid_from=2025-01-01 valid_to=2025-12-31", "rule", ["rule", "2025", "valid"], 0.9),
        ("Rule: 2024年供应商准入标准B类（已过期）valid_from=2024-01-01 valid_to=2024-12-31", "rule", ["rule", "2024", "expired"], 0.85),

        # TC-L07: Confidence distribution
        ("Test item high confidence 0.95", "observation", ["confidence_test", "conf_95"], 0.95),
        ("Test item medium confidence 0.7", "observation", ["confidence_test", "conf_70"], 0.7),
        ("Test item low confidence 0.3", "observation", ["confidence_test", "conf_30"], 0.3),

        # TC-L08: Audit trail
        ("Rule: 供应商审查流程v1", "rule", ["audit_test", "v1"], 0.9),
        ("Rule: 供应商审查流程v2（更新）", "rule", ["audit_test", "v2"], 0.95),
    ]

    for content, mtype, tags, conf in data:
        try:
            await remember(space_id, content, mtype, tags, conf)
        except Exception as e:
            print(f"  WARN: {content[:40]}... failed: {e}")

    stats = await get_stats(space_id)
    total = stats.get("data", stats).get("total", 0)
    print(f"  Loaded {total} nodes into {space_id}")


async def load_case18_iterative_refinement():
    """Load case18: Iterative Refinement — Deep Research Support data."""
    space_id = "case18_iterative_refinement"
    print(f"\n{'='*60}")
    print(f"Loading {space_id}...")

    data = [
        # TC-I01: Broad to targeted
        ("Entity: TechNova, cloud infrastructure, Shenzhen, founded 2019, revenue 500M", "entity", ["company", "TechNova", "entity"], 0.9),
        ("Observation: TechNova Q3营收增长30%, 毛利率42%", "observation", ["company", "TechNova", "financial"], 0.85),
        ("Rule: cloud行业供应商准入标准: 注册资本>=1000万, 成立>=3年", "rule", ["rule", "cloud", "准入"], 0.95),
        ("Opinion: TechNova技术实力强, 但交付能力有待观察", "opinion", ["company", "TechNova", "opinion"], 0.7),

        # TC-I02: Gap analysis
        ("Entity: 供应商B, 注册资本2000万, 成立5年", "entity", ["supplier", "供应商B", "entity"], 0.9),
        ("Observation: 供应商B Q2交付准时率88%", "observation", ["supplier", "供应商B", "delivery"], 0.8),

        # TC-I03: Query refinement
        ("Entity: 华为, credit_rating AAA, revenue 9000亿", "entity", ["company", "华为", "entity"], 0.95),
        ("Rule: 核心企业白名单制度, 华为在名单内", "rule", ["rule", "华为", "whitelist"], 0.9),
        ("Observation: 华为2025年供应链融资500亿", "observation", ["observation", "华为", "financing"], 0.85),
        ("Fragment: 听说华为在考虑新的供应商政策", "fragment", ["fragment", "华为", "rumor"], 0.4),

        # TC-I04: Evidence chain
        ("Entity: 担保圈风险企业A, 担保链深度3层, 涉及B→C→D", "entity", ["risk", "担保圈", "企业A"], 0.9),
        ("Observation: 企业B为企业A担保5000万", "observation", ["risk", "担保圈", "企业B"], 0.85),
        ("Observation: 企业C为企业B担保3000万", "observation", ["risk", "担保圈", "企业C"], 0.8),
        ("Rule: 担保圈深度超过3层需特别审查", "rule", ["rule", "担保圈", "审查"], 0.95),

        # TC-I05: State checkpoint
        ("Entity: 供应商C, 注册资本3000万, 主营电子元器件", "entity", ["supplier", "供应商C", "entity"], 0.9),
        ("Observation: 供应商C 2024年交付准时率92%", "observation", ["supplier", "供应商C", "delivery"], 0.85),
        ("Rule: 电子元器件供应商需通过ISO9001认证", "rule", ["rule", "电子元器件", "ISO9001"], 0.95),
        ("Observation: 供应商C已通过ISO9001认证", "observation", ["supplier", "供应商C", "ISO9001"], 0.9),

        # TC-I06: Convergence detection
        ("Entity: 供应商D, 注册资本1000万, 主营物流服务", "entity", ["supplier", "供应商D", "entity"], 0.9),
        ("Observation: 供应商D 2024年准时交付率95%", "observation", ["supplier", "供应商D", "delivery"], 0.85),
        ("Opinion: 供应商D服务态度好, 但价格偏高", "opinion", ["supplier", "供应商D", "opinion"], 0.7),
    ]

    for content, mtype, tags, conf in data:
        try:
            await remember(space_id, content, mtype, tags, conf)
        except Exception as e:
            print(f"  WARN: {content[:40]}... failed: {e}")

    stats = await get_stats(space_id)
    total = stats.get("data", stats).get("total", 0)
    print(f"  Loaded {total} nodes into {space_id}")


async def main():
    print("=" * 60)
    print("Eval Case Data Loader for UI Visualization")
    print("=" * 60)
    print("Target: http://localhost:8000/v1")
    print("UI: http://localhost:3000")

    # Check backend is running
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:8000/health", timeout=5)
            resp.raise_for_status()
            print("Backend: OK")
    except Exception as e:
        print(f"ERROR: Backend not reachable at localhost:8000: {e}")
        print("Start it with: uvicorn ontology_engine.api.server:app --port 8000")
        sys.exit(1)

    await load_case16_mixed_retrieval()
    await load_case17_knowledge_layering()
    await load_case18_iterative_refinement()

    print("\n" + "=" * 60)
    print("Done! View in UI:")
    print("  http://localhost:3000/spaces/case16_mixed_retrieval/memory?tab=overview")
    print("  http://localhost:3000/spaces/case17_knowledge_layering/memory?tab=overview")
    print("  http://localhost:3000/spaces/case18_iterative_refinement/memory?tab=overview")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
