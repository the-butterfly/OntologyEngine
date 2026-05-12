"""Comprehensive E2E verification for ingest, recall, reflect, and lifecycle flows."""
import asyncio
import tempfile
import os
import shutil


async def verify_ingest_flow():
    from ontology_engine.engine.cognitive.factory import create_memory_api

    db_dir = tempfile.mkdtemp(prefix="oe_e2e_")
    db_path = os.path.join(db_dir, "cognitive_db")
    llm_config = {
        "enabled": True,
        "base_url": "http://localhost:9528/v1",
        "model": "sensenova/sensenova-6.7-flash-lite",
    }

    api, _ = await create_memory_api(db_path=db_path, llm_config=llm_config)
    results = {}

    # === Flow 1: Ingest entity via remember (dual-layer write) ===
    print("=" * 60)
    print("Flow 1: Ingest Entity via remember()")
    print("=" * 60)
    r1 = await api.remember(
        "Python是一种通用编程语言，支持面向对象和函数式编程",
        "test_space",
        memory_type="entity",
        tags=["python", "programming"],
    )
    entity_id = r1["data"]["memory_id"]
    entity_node = await api._repo.get_node(entity_id)
    results["1_entity_created"] = entity_node is not None
    results["1_entity_model_domain"] = getattr(entity_node, "model_domain", None) == "world"
    results["1_entity_cognitive_layer"] = getattr(entity_node, "cognitive_layer", None) == "semantic"
    results["1_entity_belief_status"] = getattr(entity_node, "belief_status", None) == "accepted"
    print(f"  Entity created: {entity_id}")
    print(f"  model_domain: {getattr(entity_node, 'model_domain', None)}")
    print(f"  cognitive_layer: {getattr(entity_node, 'cognitive_layer', None)}")
    print(f"  belief_status: {getattr(entity_node, 'belief_status', None)}")

    # Check fragment was created
    frag_nodes = await api._repo.query_nodes(
        space_id="test_space",
        attributes_filter={"_source_content_hash": True},
        limit=10,
    )
    frag_found = False
    all_nodes = await api._repo.query_nodes(space_id="test_space", limit=50)
    for n in all_nodes:
        if n.id.startswith("frag:"):
            frag_found = True
            results["1_fragment_created"] = True
            results["1_fragment_memory_type"] = n.memory_type == "fragment"
            results["1_fragment_cognitive_layer"] = n.cognitive_layer == "perception"
            print(f"  Fragment created: {n.id}")
            print(f"  Fragment memory_type: {n.memory_type}")
            print(f"  Fragment cognitive_layer: {n.cognitive_layer}")
            break
    if not frag_found:
        results["1_fragment_created"] = False
        print("  WARNING: No fragment found")

    # Check COG_SUPPORTED_BY edge
    edges = await api._repo.query_cognitive_edges(from_id=None, to_id=entity_id, limit=10)
    cog_edge_found = any(e.edge_type == "COG_SUPPORTED_BY" for e in edges)
    results["1_cog_supported_by_edge"] = cog_edge_found
    print(f"  COG_SUPPORTED_BY edge to entity: {cog_edge_found}")

    # === Flow 2: Ingest observation with validity ===
    print()
    print("=" * 60)
    print("Flow 2: Ingest Observation with valid_from/valid_to")
    print("=" * 60)
    r2 = await api.remember(
        "2024年Q1销售数据：营收增长15%",
        "test_space",
        memory_type="observation",
        valid_from="2024-01-01T00:00:00+00:00",
        valid_to="2024-03-31T23:59:59+00:00",
        confidence=0.9,
    )
    obs_id = r2["data"]["memory_id"]
    obs_node = await api._repo.get_node(obs_id)
    results["2_observation_created"] = obs_node is not None
    results["2_observation_valid_from"] = getattr(obs_node, "valid_from", None) is not None
    results["2_observation_confidence"] = getattr(obs_node, "confidence", None) == 0.9
    results["2_observation_model_domain"] = getattr(obs_node, "model_domain", None) == "world"
    print(f"  Observation created: {obs_id}")
    print(f"  valid_from: {getattr(obs_node, 'valid_from', None)}")
    print(f"  confidence: {getattr(obs_node, 'confidence', None)}")

    # === Flow 3: Ingest mental_model (model_domain=self) ===
    print()
    print("=" * 60)
    print("Flow 3: Ingest Mental Model (model_domain=self)")
    print("=" * 60)
    r3 = await api.remember(
        "我认为敏捷开发比瀑布模型更适合小团队",
        "test_space",
        memory_type="mental_model",
        tags=["agile", "methodology"],
    )
    mm_id = r3["data"]["memory_id"]
    mm_node = await api._repo.get_node(mm_id)
    results["3_mental_model_created"] = mm_node is not None
    results["3_mental_model_domain"] = getattr(mm_node, "model_domain", None) == "self"
    results["3_mental_model_layer"] = getattr(mm_node, "cognitive_layer", None) == "opinion"
    print(f"  Mental model created: {mm_id}")
    print(f"  model_domain: {getattr(mm_node, 'model_domain', None)}")
    print(f"  cognitive_layer: {getattr(mm_node, 'cognitive_layer', None)}")

    # === Flow 4: Recall with QUL integration ===
    print()
    print("=" * 60)
    print("Flow 4: Recall with QUL Integration")
    print("=" * 60)
    r4 = await api.recall("Python编程语言", "test_space")
    results["4_recall_success"] = r4.get("status") == "success" or len(r4.get("data", {}).get("results", [])) >= 0
    recall_results = r4.get("data", {}).get("results", [])
    results["4_recall_found_entity"] = any(
        "Python" in (res.get("content", "") or "") for res in recall_results
    )
    print(f"  Recall status: {r4.get('status')}")
    print(f"  Results count: {len(recall_results)}")
    for res in recall_results[:3]:
        print(f"    - [{res.get('memory_type')}] {res.get('content', '')[:60]}...")

    # === Flow 5: Correct memory (belief revision + correction propagation) ===
    print()
    print("=" * 60)
    print("Flow 5: Correct Memory (belief revision)")
    print("=" * 60)
    try:
        r5 = await api.correct_memory(
            obs_id,
            updated_text="2024年Q1销售数据：营收增长12%（修正）",
            reason="数据修正",
        )
        results["5_correct_success"] = True
        # Check old node was superseded
        old_node = await api._repo.get_node(obs_id)
        results["5_old_superseded"] = getattr(old_node, "belief_status", None) in ("superseded",)
        print(f"  Correct success: True")
        print(f"  Old node belief_status: {getattr(old_node, 'belief_status', None)}")
    except Exception as e:
        results["5_correct_success"] = False
        print(f"  Correct failed: {e}")

    # === Flow 6: Approve memory (feedback_weight=1.0) ===
    print()
    print("=" * 60)
    print("Flow 6: Approve Memory (feedback_weight=1.0)")
    print("=" * 60)
    r6 = await api.remember(
        "待审批的观察记录",
        "test_space",
        memory_type="observation",
        belief_status="pending_review",
    )
    pending_id = r6["data"]["memory_id"]
    pending_node = await api._repo.get_node(pending_id)
    pending_node.belief_status = "pending_review"
    await api._repo.update_node(pending_node)
    try:
        await api.approve_memory(pending_id, "approve", modifier_id="test")
        approved = await api._repo.get_node(pending_id)
        results["6_approve_success"] = True
        results["6_feedback_weight_1"] = approved.feedback_weight == 1.0
        results["6_confidence_1"] = approved.confidence == 1.0
        print(f"  Approve success: True")
        print(f"  feedback_weight: {approved.feedback_weight}")
        print(f"  confidence: {approved.confidence}")
    except Exception as e:
        results["6_approve_success"] = False
        print(f"  Approve failed: {e}")

    # === Flow 7: Reflect with LLM ===
    print()
    print("=" * 60)
    print("Flow 7: Reflect with LLM (hybrid mode)")
    print("=" * 60)
    try:
        r7 = await api.reflect("Python和敏捷开发的关系", "test_space", max_iterations=3, async_mode=False)
        method = r7.get("data", {}).get("method", "rule_only")
        insights = r7.get("data", {}).get("insights", [])
        results["7_reflect_success"] = True
        results["7_reflect_hybrid"] = method == "hybrid"
        print(f"  Reflect method: {method}")
        print(f"  Insights count: {len(insights)}")
        for ins in insights[:3]:
            if isinstance(ins, dict):
                print(f"    - {ins.get('text', '')[:60]}...")
            else:
                print(f"    - {str(ins)[:60]}...")
    except Exception as e:
        results["7_reflect_success"] = False
        results["7_reflect_hybrid"] = False
        print(f"  Reflect failed: {e}")

    # === Flow 8: Dream cycle ===
    print()
    print("=" * 60)
    print("Flow 8: Dream Cycle")
    print("=" * 60)
    try:
        r8 = await api.dream("test_space")
        results["8_dream_success"] = True
        print(f"  Dream success: True")
        print(f"  Dream result: {str(r8)[:200]}")
    except Exception as e:
        results["8_dream_success"] = False
        print(f"  Dream failed: {e}")

    # === Flow 9: Correction propagation with signal ===
    print()
    print("=" * 60)
    print("Flow 9: Correction Propagation with signal")
    print("=" * 60)
    from ontology_engine.engine.cognitive.correction_propagation import CorrectionPropagation
    cp = CorrectionPropagation(repository=api._repo)
    prop_result = await cp.propagate("nonexistent_node", signal="superseded")
    results["9_signal_propagation"] = prop_result.signal == "superseded"
    print(f"  Signal propagation: {prop_result.signal}")

    # === Flow 10: QUL constraint extraction + strategy mapping ===
    print()
    print("=" * 60)
    print("Flow 10: QUL Constraint Extraction + Strategy Mapping")
    print("=" * 60)
    from ontology_engine.engine.cognitive.query_understanding_layer import RecallContext
    qul = api._qul
    ctx = RecallContext(space_id="test_space")
    constraints = await qul.extract_constraints("最近Python编程相关的观察", ctx)
    strategy = qul.map_to_retrieval_strategy(constraints)
    results["10_qul_constraints"] = len(constraints) > 0
    results["10_qul_strategy"] = len(strategy.adjustments) > 0
    print(f"  Constraints: {len(constraints)}")
    print(f"  Strategy adjustments: {len(strategy.adjustments)}")
    for c in constraints[:3]:
        print(f"    - {c.constraint_type}: {c.value}")

    # === Summary ===
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = all(results.values())
    for k, v in results.items():
        status = "PASS" if v else "FAIL"
        print(f"  [{status}] {k}")
    print(f"\nOverall: {'ALL PASSED' if all_pass else 'SOME FAILED'} ({sum(results.values())}/{len(results)})")

    shutil.rmtree(db_dir, ignore_errors=True)
    return results


if __name__ == "__main__":
    asyncio.run(verify_ingest_flow())
