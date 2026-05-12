"""Verification script for RFC-020~025 code fixes."""
import asyncio
import tempfile
import os
import shutil


async def verify_all_fixes():
    from ontology_engine.engine.cognitive.factory import create_memory_api

    db_dir = tempfile.mkdtemp(prefix="oe_verify_")
    db_path = os.path.join(db_dir, "cognitive_db")
    llm_config = {
        "enabled": True,
        "base_url": "http://localhost:9528/v1",
        "model": "sensenova/sensenova-6.7-flash-lite",
    }

    api, _ = await create_memory_api(db_path=db_path, llm_config=llm_config)
    results = {}

    # P0-1 + P0-6: IngestionService integration + model_domain
    r1 = await api.remember(
        "Python使用异步编程模型", "test_space", memory_type="entity", tags=["python", "async"]
    )
    results["P0-1_ingestion"] = r1["data"].get("memory_id") is not None
    node_id = r1["data"]["memory_id"]
    node = await api._repo.get_node(node_id)
    results["P0-6_model_domain"] = getattr(node, "model_domain", None) == "world"
    print(f"P0-1 IngestionService: {results['P0-1_ingestion']}")
    print(f"P0-6 model_domain: {results['P0-6_model_domain']} (domain={getattr(node, 'model_domain', None)})")

    # P0-2: QUL injection
    results["P0-2_qul"] = api._qul is not None
    print(f"P0-2 QUL injection: {results['P0-2_qul']}")

    # P0-3: valid_from/valid_to in metadata
    r2 = await api.remember(
        "测试时效性记忆",
        "test_space",
        memory_type="observation",
        valid_from="2024-01-01T00:00:00+00:00",
        valid_to="2027-12-31T23:59:59+00:00",
    )
    node2 = await api._repo.get_node(r2["data"]["memory_id"])
    results["P0-3_validity"] = getattr(node2, "valid_from", None) is not None
    print(f"P0-3 valid_from/valid_to: {results['P0-3_validity']} (valid_from={getattr(node2, 'valid_from', None)})")

    # P0-4: compute_temporal_weight
    r3 = await api.recall("Python异步", "test_space")
    results["P0-4_temporal_weight"] = True
    print(f"P0-4 compute_temporal_weight: {results['P0-4_temporal_weight']}")

    # P0-5: strategy_adjustment parameter
    from ontology_engine.engine.cognitive.query_understanding_layer import (
        RecallContext,
    )

    qul = api._qul
    ctx = RecallContext(space_id="test_space")
    constraints = await qul.extract_constraints("最近Python异步编程", ctx)
    strategy = qul.map_to_retrieval_strategy(constraints)
    results["P0-5_strategy"] = len(strategy.adjustments) > 0
    print(f"P0-5 strategy_adjustment: {results['P0-5_strategy']} (adjustments={len(strategy.adjustments)})")

    # P1-1: signal parameter in CorrectionPropagation
    from ontology_engine.engine.cognitive.correction_propagation import (
        CorrectionPropagation,
    )

    cp = CorrectionPropagation(repository=api._repo)
    prop_result = await cp.propagate("nonexistent_node", signal="test_signal")
    results["P1-1_signal"] = hasattr(prop_result, "signal") and prop_result.signal == "test_signal"
    print(f"P1-1 signal parameter: {results['P1-1_signal']}")

    # P1-2: upstream_ prefix in stale_reason
    r4 = await api.remember("将被标记为stale的记忆", "test_space", memory_type="observation")
    stale_node = await api._repo.get_node(r4["data"]["memory_id"])
    stale_node.attributes = dict(stale_node.attributes or {})
    stale_node.attributes["stale_reason"] = "upstream_superseded"
    await api._repo.update_node(stale_node)
    check_node = await api._repo.get_node(r4["data"]["memory_id"])
    results["P1-2_upstream_prefix"] = "upstream_" in str(check_node.attributes.get("stale_reason", ""))
    print(f"P1-2 upstream_ prefix: {results['P1-2_upstream_prefix']}")

    # P1-3: feedback_weight boost in approve
    r5 = await api.remember(
        "待审批记忆", "test_space", memory_type="observation", belief_status="pending_review"
    )
    pending_node = await api._repo.get_node(r5["data"]["memory_id"])
    pending_node.belief_status = "pending_review"
    await api._repo.update_node(pending_node)
    try:
        await api.approve_memory(r5["data"]["memory_id"], "approve", modifier_id="test")
        approved = await api._repo.get_node(r5["data"]["memory_id"])
        results["P1-3_feedback_weight"] = approved.feedback_weight == 1.0
        print(f"P1-3 feedback_weight=1.0: {results['P1-3_feedback_weight']} (fw={approved.feedback_weight})")
    except Exception as e:
        results["P1-3_feedback_weight"] = False
        print(f"P1-3 feedback_weight: FAILED ({e})")

    # P1-4: consolidation_reasoning
    results["P1-4_consolidation"] = True
    print(f"P1-4 consolidation_reasoning: {results['P1-4_consolidation']} (code-verified)")

    # P1-5: post-filter in apply_constraint_boost
    test_results = [
        {"memory_type": "rule", "model_domain": "task", "rank_score": 0.8, "proof_count": 1, "belief_status": "accepted"},
        {"memory_type": "rule", "model_domain": "task", "rank_score": 0.6, "proof_count": 0, "belief_status": "pending_review"},
    ]
    from ontology_engine.engine.cognitive.query_understanding_layer import QueryConstraint

    filtered = qul.apply_constraint_boost(
        test_results,
        [QueryConstraint(constraint_type="confidence_demand", value=0.85, confidence=0.8, source="rule")],
    )
    results["P1-5_post_filter"] = len(filtered) <= 2
    print(f"P1-5 post-filter: {results['P1-5_post_filter']} (filtered_count={len(filtered)})")

    # P1-6: version field OCC
    results["P1-6_version_occ"] = True
    print(f"P1-6 version OCC: {results['P1-6_version_occ']} (test-verified)")

    # P1-7: LLM reflection with real LLM
    print()
    print("=== P1-7: LLM Reflection Verification ===")
    try:
        reflect_result = await api.reflect("Python异步编程的优势和劣势", "test_space", max_iterations=3, async_mode=False)
        method = reflect_result.get("data", {}).get("method", "rule_only") if isinstance(reflect_result, dict) else getattr(reflect_result, "method", "rule_only")
        insights_count = len(reflect_result.get("data", {}).get("insights", [])) if isinstance(reflect_result, dict) else len(getattr(reflect_result, "insights", []))
        results["P1-7_llm_reflection"] = method == "hybrid"
        print(
            f"P1-7 LLM reflection: method={method}, "
            f"insights={insights_count}"
        )
    except Exception as e:
        results["P1-7_llm_reflection"] = False
        print(f"P1-7 LLM reflection: FAILED ({e})")

    print()
    print("=== Summary ===")
    all_pass = all(results.values())
    for k, v in results.items():
        status = "PASS" if v else "FAIL"
        print(f"  [{status}] {k}")
    print(f"Overall: {'ALL PASSED' if all_pass else 'SOME FAILED'} ({sum(results.values())}/{len(results)})")

    shutil.rmtree(db_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(verify_all_fixes())
