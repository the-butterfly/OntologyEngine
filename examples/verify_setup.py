#!/usr/bin/env python3
"""Quick verification of instance data integrity after setup."""
from __future__ import annotations

import asyncio
import httpx


async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        resp = await client.get("/v1/spaces")
        spaces = resp.json().get("data", [])

        for s in spaces:
            if s.get("space_type") != "management":
                continue
            space_id = s["id"]
            domain = s.get("domain", "?")
            name = s.get("name", "?")

            resp = await client.get(f"/v1/spaces/{space_id}/instances/entities")
            entities = resp.json().get("data", [])

            resp = await client.get(f"/v1/spaces/{space_id}/instances/relations")
            relations = resp.json().get("data", [])

            concept_counts = {}
            missing_concept = 0
            for e in entities:
                concept = e.get("_concept", "MISSING")
                if concept == "MISSING":
                    missing_concept += 1
                concept_counts[concept] = concept_counts.get(concept, 0) + 1

            rel_type_counts = {}
            for r in relations:
                rt = r.get("relation_name") or r.get("relation_type", "MISSING")
                rel_type_counts[rt] = rel_type_counts.get(rt, 0) + 1

            non_belongs = [rt for rt in rel_type_counts if rt != "belongs_to"]

            print(f"\n{'=' * 50}")
            print(f"  {name} ({domain})")
            print(f"  Space ID: {space_id}")
            print(f"{'=' * 50}")
            print(f"  Entities: {len(entities)} | Relations: {len(relations)}")
            if missing_concept > 0:
                print(f"  ⚠️  {missing_concept} entities with MISSING _concept!")
            else:
                print(f"  ✅ All entities have _concept field")
            print(f"  Concepts: {dict(sorted(concept_counts.items()))}")
            print(f"  Relation types: {dict(sorted(rel_type_counts.items()))}")
            if non_belongs:
                print(f"  ✅ {len(non_belongs)} non-belongs_to relation types: {non_belongs}")
            else:
                print(f"  ⚠️  Only belongs_to relations!")


if __name__ == "__main__":
    asyncio.run(main())
