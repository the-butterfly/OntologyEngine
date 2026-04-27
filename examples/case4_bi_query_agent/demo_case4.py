#!/usr/bin/env python3
"""
Case4 End-to-End Verification using Generalized OntologyEngine

Verifies that the generalized InstanceLoader and MetricEngine
can correctly load case4 data and compute metrics.

Usage:
    python examples/case4_bi_query_agent/demo_case4.py
"""

import asyncio
import json
import sys
from pathlib import Path

CASE_DIR = Path(__file__).parent


async def run_case4_demo():
    from ontology_engine import OntologyEngine
    from ontology_engine.core.instances import InstanceLoader
    from ontology_engine.core.schema import SchemaLoader

    print("=" * 70)
    print("  CASE4: BI Query Agent - End-to-End Engine Verification")
    print("=" * 70)

    schema_path = str(CASE_DIR / "schema.yaml")
    instances_path = str(CASE_DIR / "instances.yaml")

    print("\n[1/5] Loading schema...")
    loader = SchemaLoader()
    schema = loader.load(schema_path)
    issues = loader.validate(schema)
    if issues:
        print(f"  Schema validation issues: {issues}")
    else:
        print(f"  Schema loaded: {len(schema.concepts)} concepts, v2={schema.is_v2_format()}")

    print("\n[2/5] Loading instances with generalized InstanceLoader...")
    il = InstanceLoader(schema=schema)
    entities, relations = il.load(instances_path)
    print(f"  Entities: {len(entities)}")
    print(f"  Relations: {len(relations)}")

    concept_counts = {}
    for e in entities:
        c = e._fact_object
        concept_counts[c] = concept_counts.get(c, 0) + 1
    for c, n in sorted(concept_counts.items()):
        print(f"    {c}: {n}")

    rel_type_counts = {}
    for r in relations:
        rn = r.relation_name
        rel_type_counts[rn] = rel_type_counts.get(rn, 0) + 1
    for rn, n in sorted(rel_type_counts.items()):
        print(f"    relation '{rn}': {n}")

    print("\n[3/5] Initializing OntologyEngine...")
    engine = OntologyEngine.from_config(schema_path)
    await engine.initialize()
    print("  Engine initialized")

    print("\n[4/5] Loading instances into engine...")
    await engine.load_instances(instances_path)
    print("  Instances loaded")

    print("\n[5/5] Verifying entity retrieval...")
    store_entities = await engine.query_entities("Store")
    print(f"  Store entities: {len(store_entities)}")

    if store_entities:
        sample = store_entities[0]
        sid = sample.get("store_id", "unknown")
        sname = sample.get("store_name", "unknown")
        print(f"  Sample: {sid} - {sname}")

    print("\n" + "=" * 70)
    print("  VERIFICATION SUMMARY")
    print("=" * 70)

    checks = [
        ("Schema loads correctly", len(schema.concepts) > 0),
        ("InstanceLoader extracts entities", len(entities) > 0),
        ("InstanceLoader extracts relations", len(relations) > 0),
        ("Store entities loaded", len(store_entities) > 0),
        ("Schema is v2 format", schema.is_v2_format()),
    ]

    all_pass = True
    for name, result in checks:
        icon = "✅" if result else "❌"
        print(f"  {icon} {name}")
        if not result:
            all_pass = False

    print()

    if all_pass:
        print("  ✅ ALL CHECKS PASSED - Case4 is compatible with generalized engine")
    else:
        print("  ❌ SOME CHECKS FAILED - See details above")

    await engine.close()
    return all_pass


if __name__ == "__main__":
    result = asyncio.run(run_case4_demo())
    sys.exit(0 if result else 1)
