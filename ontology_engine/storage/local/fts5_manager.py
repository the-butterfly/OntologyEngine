from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ontology_engine.engine.cognitive.models import CognitiveNode
    from ontology_engine.storage.base import KnowledgeFragment

logger = logging.getLogger(__name__)


class FTS5Manager:

    def __init__(self, conn_factory: Callable[[], sqlite3.Connection]) -> None:
        self._conn_factory = conn_factory
        self._jieba_available = self._check_jieba()
        self._tables_created = False

    def _get_conn(self) -> sqlite3.Connection:
        return self._conn_factory()

    @staticmethod
    def _check_jieba() -> bool:
        try:
            import jieba  # noqa: F401
            return True
        except ImportError:
            return False

    def _tokenize_for_fts5(self, text: str) -> str:
        if not text:
            return ""
        if self._jieba_available:
            try:
                import jieba
                tokens = jieba.cut_for_search(text)
                return " ".join(tokens)
            except Exception:
                return text
        return text

    def ensure_tables(self) -> None:
        if self._tables_created:
            return
        conn = self._get_conn()
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS cognitive_node_fts
                USING fts5(
                    node_id UNINDEXED,
                    content,
                    space_id,
                    memory_type,
                    entity_name,
                    tags,
                    cognitive_layer,
                    tokenize='porter unicode61'
                )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fragment_fts
                USING fts5(
                    fragment_id UNINDEXED,
                    content,
                    space_id,
                    tags,
                    tokenize='porter unicode61'
                )
        """)
        conn.commit()
        self._tables_created = True

    async def on_node_created(self, node: CognitiveNode) -> None:
        self.ensure_tables()
        tokenized_content = self._tokenize_for_fts5(node.content)
        tag_parts = []
        for k, v in (node.tags or {}).items():
            if isinstance(v, list):
                tag_parts.extend(f"{k}:{item}" for item in v)
            else:
                tag_parts.append(f"{k}:{v}")
        tokenized_tags = " ".join(tag_parts)
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT INTO cognitive_node_fts(
                    node_id, content, space_id, memory_type,
                    entity_name, tags, cognitive_layer
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
            """, (
                node.id, tokenized_content, node.space_id, node.memory_type,
                getattr(node, 'entity_name', None), tokenized_tags,
                node.cognitive_layer,
            ))
            conn.commit()
        except Exception as e:
            logger.error("FTS5 sync failed on create for node %s: %s", node.id, e)

    async def on_node_updated(self, node: CognitiveNode) -> None:
        try:
            conn = self._get_conn()
            conn.execute(
                "DELETE FROM cognitive_node_fts WHERE node_id = ?",
                (node.id,),
            )
            conn.commit()
        except Exception:
            pass
        await self.on_node_created(node)

    async def on_node_deleted(self, node_id: str) -> None:
        try:
            conn = self._get_conn()
            conn.execute(
                "DELETE FROM cognitive_node_fts WHERE node_id = ?",
                (node_id,),
            )
            conn.commit()
        except Exception as e:
            logger.warning("FTS5 cleanup failed for node %s: %s", node_id, e)

    async def on_fragment_created(self, fragment: KnowledgeFragment) -> None:
        self.ensure_tables()
        tokenized_content = self._tokenize_for_fts5(fragment.text)
        tags: list[str] = []
        space_id = "default"
        if fragment.metadata:
            tags = fragment.metadata.get("tags", [])
            space_id = fragment.metadata.get("space_id", "default")
        tokenized_tags = " ".join(tags) if tags else ""
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT INTO knowledge_fragment_fts(
                    fragment_id, content, space_id, tags
                ) VALUES(?, ?, ?, ?)
            """, (fragment.id, tokenized_content, space_id, tokenized_tags))
            conn.commit()
        except Exception as e:
            logger.error(
                "FTS5 sync failed on create for fragment %s: %s",
                fragment.id, e,
            )

    async def on_fragment_deleted(self, fragment_id: str) -> None:
        try:
            conn = self._get_conn()
            conn.execute(
                "DELETE FROM knowledge_fragment_fts WHERE fragment_id = ?",
                (fragment_id,),
            )
            conn.commit()
        except Exception as e:
            logger.warning(
                "FTS5 cleanup failed for fragment %s: %s", fragment_id, e,
            )

    async def rebuild_fts5_if_needed(
        self,
        source_node_count: int,
        nodes: list[CognitiveNode],
        fragments: list[Any] | None = None,
    ) -> int:
        self.ensure_tables()
        conn = self._get_conn()

        fts_count = 0
        try:
            fts_count = conn.execute(
                "SELECT COUNT(*) FROM cognitive_node_fts"
            ).fetchone()[0]
        except Exception:
            fts_count = 0

        if source_node_count == 0:
            return 0

        diff_ratio = abs(source_node_count - fts_count) / source_node_count
        if fts_count == 0 or diff_ratio > 0.05:
            logger.info(
                "FTS5 rebuild triggered: source=%d, fts=%d, diff=%.1f%%",
                source_node_count, fts_count, diff_ratio * 100,
            )
            return await self._full_rebuild(nodes, fragments)
        return 0

    async def _full_rebuild(
        self,
        nodes: list[CognitiveNode],
        fragments: list[Any] | None = None,
    ) -> int:
        conn = self._get_conn()
        conn.execute("DELETE FROM cognitive_node_fts")
        conn.execute("DELETE FROM knowledge_fragment_fts")
        conn.commit()

        for node in nodes:
            await self.on_node_created(node)

        if fragments:
            for frag in fragments:
                await self.on_fragment_created(frag)

        return len(nodes) + (len(fragments) if fragments else 0)

    def search(
        self,
        query: str,
        space_id: str,
        top_k: int,
    ) -> list[tuple[str, str, float]]:
        self.ensure_tables()
        tokenized_query = self._tokenize_for_fts5(query)
        if not tokenized_query.strip():
            return []

        conn = self._get_conn()
        results: list[tuple[str, str, float]] = []

        try:
            node_rows = conn.execute("""
                SELECT node_id, bm25(cognitive_node_fts) as score
                FROM cognitive_node_fts
                WHERE cognitive_node_fts MATCH ? AND space_id = ?
                ORDER BY score
                LIMIT ?
            """, (tokenized_query, space_id, top_k * 3)).fetchall()

            for row in node_rows:
                results.append((row[0], "node", row[1]))
        except Exception as e:
            logger.warning("FTS5 node search failed: %s", e)

        try:
            frag_rows = conn.execute("""
                SELECT fragment_id, bm25(knowledge_fragment_fts) as score
                FROM knowledge_fragment_fts
                WHERE knowledge_fragment_fts MATCH ? AND space_id = ?
                ORDER BY score
                LIMIT ?
            """, (tokenized_query, space_id, top_k)).fetchall()

            for row in frag_rows:
                results.append((row[0], "fragment", row[1]))
        except Exception as e:
            logger.warning("FTS5 fragment search failed: %s", e)

        seen_ids: set[str] = set()
        merged: list[tuple[str, str, float]] = []
        for id_, source, score in results:
            if id_ not in seen_ids:
                merged.append((id_, source, score))
                seen_ids.add(id_)

        merged.sort(key=lambda x: x[2])
        return merged[:top_k]
