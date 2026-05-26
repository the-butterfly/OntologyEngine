from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from ontology_engine.engine.cognitive.memory_utils import (
    generate_memory_id,
    infer_cognitive_layer,
    make_response,
)
from ontology_engine.engine.cognitive.models import CognitiveNode

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.repository import CognitiveRepository

logger = logging.getLogger(__name__)


class CommitmentService:

    def __init__(self, repository: "CognitiveRepository"):
        self._repo = repository

    async def record_commitment(
        self,
        content: str,
        space_id: str,
        deadline: str | None = None,
        task_id: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        try:
            node_id = generate_memory_id(content, space_id, "commitment")
            cognitive_layer = infer_cognitive_layer("commitment")

            attributes: dict[str, str] = {}
            if deadline:
                attributes["deadline"] = deadline
            if task_id:
                attributes["task_id"] = task_id

            node = CognitiveNode(
                id=node_id,
                memory_type="commitment",
                cognitive_layer=cognitive_layer,
                content=content,
                domain_id=space_id,
                space_id=space_id,
                visibility="shared",
                created_by=created_by,
                confidence=1.0,
                belief_status="accepted",
                tags={"model": "task"},
                attributes=attributes,
                source_fragment_ids=[],
                proof_count=1,
            )
            await self._repo.create_node(node)
            return make_response(
                data={
                    "memory_id": node_id,
                    "node_id": node_id,
                    "commitment_id": node_id,
                    "decision": "accepted",
                    "space_id": space_id,
                },
                space_id=space_id,
            )
        except Exception as e:
            logger.warning("record_commitment failed: %s", e)
            return make_response(
                data={"memory_id": None, "error": str(e), "space_id": space_id},
                space_id=space_id,
            )

    async def check_commitments(
        self,
        space_id: str,
        status: str | None = None,
        overdue: bool = False,
    ) -> dict[str, Any]:
        try:
            nodes = await self._repo.query_nodes(
                domain_id=space_id,
                memory_type="commitment",
                limit=500,
            )
            now = datetime.now(timezone.utc)
            results = []
            for n in nodes:
                n_status = getattr(n, "belief_status", "accepted")
                if status and n_status != status:
                    continue
                n_deadline = n.attributes.get("deadline") if n.attributes else None
                is_overdue = False
                if n_deadline:
                    try:
                        dl = datetime.fromisoformat(str(n_deadline).replace("Z", "+00:00"))
                        is_overdue = dl < now
                    except (ValueError, TypeError):
                        pass
                if overdue and not is_overdue:
                    continue
                results.append({
                    "id": n.id,
                    "content": n.content,
                    "status": n_status,
                    "deadline": n_deadline,
                    "task_id": n.attributes.get("task_id") if n.attributes else None,
                    "created_by": n.created_by,
                    "is_overdue": is_overdue,
                    "created_at": n.created_at,
                })
            return make_response(
                data={"commitments": results, "total": len(results), "space_id": space_id},
                space_id=space_id,
            )
        except Exception as e:
            logger.warning("check_commitments failed: %s", e)
            return make_response(
                data={"commitments": [], "total": 0, "space_id": space_id},
                space_id=space_id,
            )
