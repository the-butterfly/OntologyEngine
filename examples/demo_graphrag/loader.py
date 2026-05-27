"""
Knowledge Base Loader for GraphRAG Demo
=========================================
Loads the rag-skill knowledge base (PDF/MD/TXT/XLSX), chunks documents,
extracts entities, builds rich graph relationships, and creates vector embeddings.

Graph Structure:
  domain ──belongs_to── document ──contains── chunk ──mentioned_in── entity
    │                                                            │
    └──────────────────────related_to─────────────────────────────┘  (entity↔entity co-occurrence)
    └──entity_belongs_to── entity  (entity↔domain direct link)
  chunk ──references── chunk  (cross-document entity bridge)

Uses OntologyEngine's layered architecture principles:
  storage/ (text + graph + vector) → engine/ (index search) → api/ (expose)
"""

import json, re, os, hashlib
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict

# ── Optional format handlers ──────────────────────────────────────────
_HAS_FITZ = False
_HAS_OPENPYXL = False
try:
    import fitz
    _HAS_FITZ = True
except ImportError:
    pass
try:
    import openpyxl
    _HAS_OPENPYXL = True
except ImportError:
    pass

# ── Config ─────────────────────────────────────────────────────────────
KB_PATH = Path(os.environ.get("KB_PATH", "/Volumes/Extension/Projects/AgentKB-Memory/rag-skill/knowledge"))
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

EMBED_URL = "http://127.0.0.1:7852/v1/embeddings"
EMBED_MODEL = "text-embedding-qwen3-embedding-4b"

# ── Data Model ─────────────────────────────────────────────────────────

@dataclass
class GraphNode:
    id: str
    label: str
    type: str           # domain | document | chunk | entity
    metadata: dict = field(default_factory=dict)

@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str       # belongs_to | contains | mentioned_in | related_to
                        # | references | entity_belongs_to | cross_domain
    weight: float = 1.0

@dataclass
class Chunk:
    id: str
    doc_id: str
    domain: str
    text: str
    entities: list[str] = field(default_factory=list)
    embedding: list[float] | None = None

@dataclass
class KnowledgeBase:
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)
    documents: dict[str, dict] = field(default_factory=dict)
    # Track entity co-occurrence for dedup edges
    _entity_pairs: set = field(default_factory=set)


# ── Multi-format file readers ──────────────────────────────────────────

def read_file_content(fpath: Path) -> str | None:
    """Read text from .txt/.md/.pdf/.xlsx. Returns None on failure."""
    suffix = fpath.suffix.lower()

    # Plain text formats
    if suffix in ('.txt', '.md', '.csv'):
        return fpath.read_text(encoding='utf-8', errors='replace')

    # PDF via PyMuPDF
    if suffix == '.pdf':
        if not _HAS_FITZ:
            print(f"  [SKIP] {fpath.name} — install PyMuPDF (pip install pymupdf)")
            return None
        try:
            doc = fitz.open(fpath)
            pages = []
            for page in doc:
                pages.append(page.get_text())
            doc.close()
            text = "\n\n".join(pages).strip()
            if len(text) < 20:  # scanned/image-only PDF
                print(f"  [WARN] {fpath.name}: extracted only {len(text)} chars (scanned?)")
            return text if text else None
        except Exception as e:
            print(f"  [ERROR] {fpath.name}: PDF read failed — {e}")
            return None

    # XLSX via openpyxl (convert rows to structured text)
    if suffix == '.xlsx':
        if not _HAS_OPENPYXL:
            print(f"  [SKIP] {fpath.name} — install openpyxl (pip install openpyxl)")
            return None
        try:
            wb = openpyxl.load_workbook(fpath, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return None
            # First row = header
            header = [str(c) if c is not None else "" for c in rows[0]]
            lines = [f"# {fpath.stem} — {' | '.join(header)}"]
            for row in rows[1:]:
                vals = [str(c) if c is not None else "" for c in row]
                lines.append(" | ".join(vals))
            text = "\n".join(lines)
            wb.close()
            return text
        except Exception as e:
            print(f"  [ERROR] {fpath.name}: XLSX read failed — {e}")
            return None

    print(f"  [SKIP] {fpath.name}: unsupported format '{suffix}'")
    return None


# ── Chunking ───────────────────────────────────────────────────────────

def chunk_text(text: str, doc_id: str, domain: str,
               chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[Chunk]:
    """Split text into overlapping chunks at paragraph boundaries."""
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    buffer = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(buffer) + len(para) < chunk_size:
            buffer += ("\n\n" + para) if buffer else para
        else:
            if buffer:
                chunk_id = hashlib.md5(buffer.encode()).hexdigest()[:12]
                chunks.append(Chunk(id=chunk_id, doc_id=doc_id, domain=domain, text=buffer.strip()))
            # start new buffer with overlap from previous
            words = buffer.split()
            overlap_text = " ".join(words[-overlap:]) if len(words) > overlap else ""
            buffer = (overlap_text + "\n\n" + para) if overlap_text else para
    if buffer:
        chunk_id = hashlib.md5(buffer.encode()).hexdigest()[:12]
        chunks.append(Chunk(id=chunk_id, doc_id=doc_id, domain=domain, text=buffer.strip()))
    return chunks


# ── Entity Extraction ──────────────────────────────────────────────────

# Domain-specific entity patterns — expanded for better coverage
ENTITY_PATTERNS: dict[str, list[str]] = {
    "Safety Knowledge": [
        r'\b(XSS|CSRF|CORS|SQL\s*注入|跨站脚本|跨站请求伪造|同源策略|'
        r'SOP|CSP|沙箱|Sandbox|HttpOnly|P3P|Cookie\s*劫持|Session\s*劫持|'
        r'点击劫持|Clickjacking|XFS|SSRF|文件上传|路径遍历|Path\s*Traversal|'
        r'XXE|反序列化|Deserialization|WebSocket\s*劫持|缓存投毒)\b',
        r'\b(反射型|存储型|DOM\s*Based)\s*XSS\b',
        r'\b(Same-?Origin|Cross-?Origin)\s*(Policy|Request|Site)\b',
        r'\b(OWASP|安全头部|Content-Security-Policy|X-Frame-Options|'
        r'X-Content-Type-Options|Strict-Transport-Security)\b',
    ],
    "Financial Report Data": [
        r'\b(营业收入|营业成本|利润总额|净利润|毛利率|净利率|营业利润|'
        r'总资产|净资产|流动资产|非流动资产|流动负债|非流动负债|'
        r'每股收益|基本每股收益|稀释每股收益|加权平均净资产收益率|'
        r'经营活动现金流|投资活动现金流|筹资活动现金流|'
        r'非经常性损益|政府补助|资产负债率|销售费用|管理费用|研发费用|'
        r'财务费用|投资收益|公允价值变动|信用减值|资产减值)\b',
        r'\b(航天动力|三一重工|上汽集团|宁德时代|贵州茅台|招商银行)\b',
        r'证券(代)?码[：:]\s*(\d{6})',
        r'\b(同比|环比|期末|期初|报告期)\b',
        r'\b(万元|亿元|万手|亿股)\b',
    ],
    "E-commerce Data": [
        r'\b(员工|客户|库存|订单|销售|商品|用户|运营|运营主管|销售经理|'
        r'转化率|复购|客单价|GMV|SKU|仓库|入库|出库|盘点|'
        r'补货|缺货|滞销|促销|满减|折扣)\b',
        r'\b(employees|customers|inventory|sales_orders|sku|reorder_level)\b',
        r'\b(华北|华东|华南|华中|西南|西北|东北)\b',
    ],
    "AI Knowledge": [
        r'\b(大模型|LLM|AGI|RAG|Agent|AI\s*Agent|MCP|生成式|人工智能|'
        r'深度学习|机器学习|Transformer|注意力机制|扩散模型|Diffusion|'
        r'知识图谱|向量数据库|图数据库|Neo4j|Milvus|Pinecone|'
        r'微调|SFT|RLHF|DPO|LoRA|QLoRA|Prompt|Chain-of-Thought|'
        r'多模态|多模态大模型|VLM|文生图|文生视频|Sora|'
        r'强化学习|半监督|自监督|迁移学习|联邦学习|边缘计算|'
        r'数字孪生|Digital\s*Twin|NLP|自然语言处理|计算机视觉|CV|'
        r'AIGC|Copilot|智能体|具身智能|世界模型|'
        r'GPU|TPU|NPU|算力|推理|训练|部署|蒸馏|量化|'
        r'MoE|混合专家|GPT|Claude|Gemini|Llama|Qwen|DeepSeek)\b',
        r'\b(AI\s*治理|AI\s*安全|AI\s*伦理|可解释性|XAI|'
        r'幻觉|Hallucination|对齐|Alignment|价值观对齐)\b',
    ],
}


def extract_entities(text: str, domain: str) -> list[str]:
    """Extract domain-relevant entities from text using regex patterns."""
    found = set()
    patterns = ENTITY_PATTERNS.get(domain, [])
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            entity = m.group(0).strip()
            # Normalize whitespace in multi-word entities
            entity = re.sub(r'\s+', ' ', entity)
            if 1 < len(entity) <= 50:
                found.add(entity)
    return sorted(found)


# ── Build Graph ────────────────────────────────────────────────────────

def build_knowledge_base(kb_path: str | Path = KB_PATH) -> KnowledgeBase:
    """Load all knowledge domains, chunk, extract entities, build rich graph."""
    kb = KnowledgeBase()
    base = Path(kb_path)
    if not base.exists():
        print(f"[WARN] Knowledge base path not found: {base}")
        return kb

    # ── Phase 1: Domain nodes ──────────────────────────────────────────
    domain_names = sorted(
        d.name for d in base.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    )
    for dname in domain_names:
        nid = f"domain:{dname}"
        kb.nodes[nid] = GraphNode(
            id=nid, label=dname, type="domain",
            metadata={"description": f"{dname} knowledge domain",
                      "name": dname}
        )

    # ── Phase 2: Walk files per domain ─────────────────────────────────
    for domain_dir in base.iterdir():
        if not domain_dir.is_dir() or domain_dir.name.startswith('.'):
            continue
        domain = domain_dir.name
        domain_id = f"domain:{domain}"

        # Collect files, deduplicating: if both .txt and .pdf exist for same doc,
        # prefer .txt (manually cleaned) over .pdf (raw extraction)
        files_to_process: list[Path] = []
        seen_stems: set[str] = set()
        for fpath in sorted(domain_dir.iterdir()):
            if fpath.name.startswith('.') or fpath.name == "data_structure.md":
                continue
            stem = re.sub(r'[_ ]', '', fpath.stem.lower())  # normalize for dedup
            if stem in seen_stems:
                # A higher-priority format (txt > pdf > xlsx > md) already claimed this stem
                continue
            # Check if a better format exists for this stem
            for other in domain_dir.iterdir():
                if other.name.startswith('.') or other == fpath:
                    continue
                other_stem = re.sub(r'[_ ]', '', other.stem.lower())
                if other_stem == stem:
                    fmt_rank = {'.txt': 0, '.csv': 0, '.md': 1, '.pdf': 2, '.xlsx': 3}
                    this_rank = fmt_rank.get(fpath.suffix.lower(), 99)
                    other_rank = fmt_rank.get(other.suffix.lower(), 99)
                    if other_rank < this_rank:
                        break  # better format exists; skip this file
            else:
                files_to_process.append(fpath)
                seen_stems.add(stem)

        for fpath in files_to_process:
            # Read content with format auto-detection
            text = read_file_content(fpath)
            if not text:
                continue

            doc_id = f"doc:{domain}:{fpath.stem}"

            # Document node
            kb.nodes[doc_id] = GraphNode(
                id=doc_id, label=fpath.stem, type="document",
                metadata={
                    "file": fpath.name,
                    "domain": domain,
                    "size": len(text),
                    "format": fpath.suffix.lower().lstrip('.'),
                }
            )
            kb.edges.append(GraphEdge(
                source=doc_id, target=domain_id, relation="belongs_to"
            ))
            kb.documents[doc_id] = {
                "path": str(fpath), "domain": domain,
                "title": fpath.stem, "format": fpath.suffix.lower().lstrip('.'),
            }

            # Chunking + entity extraction
            chunks = chunk_text(text, doc_id, domain)
            for chunk in chunks:
                chunk.entities = extract_entities(chunk.text, domain)
                cid = chunk.id
                kb.nodes[cid] = GraphNode(
                    id=cid, label=f"chunk:{fpath.stem}:{cid[:8]}",
                    type="chunk",
                    metadata={"domain": domain, "doc": fpath.stem}
                )
                kb.edges.append(GraphEdge(
                    source=cid, target=doc_id, relation="contains"
                ))
                kb.chunks.append(chunk)

                # Entity nodes + mentioned_in edges
                for ent in chunk.entities:
                    eid = f"entity:{ent}"
                    if eid not in kb.nodes:
                        kb.nodes[eid] = GraphNode(
                            id=eid, label=ent, type="entity",
                            metadata={"domain": domain}
                        )
                    kb.edges.append(GraphEdge(
                        source=eid, target=cid, relation="mentioned_in"
                    ))

        print(f"  [OK] {domain}: {sum(1 for c in kb.chunks if c.domain==domain)} chunks")

    # ── Phase 3: Entity ↔ Entity co-occurrence edges ───────────────────
    # If two entities appear in the same chunk, they get a related_to edge
    print("[GRAPH] Building entity co-occurrence edges...")
    entity_chunk_map: dict[str, set[str]] = defaultdict(set)
    for ch in kb.chunks:
        for ent in ch.entities:
            entity_chunk_map[ent].add(ch.id)

    # Build co-occurrence pairs
    cooccur_count: dict[tuple[str, str], int] = defaultdict(int)
    for ch in kb.chunks:
        ents = ch.entities
        for i in range(len(ents)):
            for j in range(i + 1, len(ents)):
                pair = tuple(sorted([ents[i], ents[j]]))
                cooccur_count[pair] += 1

    for (e1, e2), count in cooccur_count.items():
        eid1 = f"entity:{e1}"
        eid2 = f"entity:{e2}"
        if eid1 in kb.nodes and eid2 in kb.nodes:
            # Weight = how many chunks they co-occur in (normalized)
            weight = min(count / 5.0, 1.0)
            kb.edges.append(GraphEdge(
                source=eid1, target=eid2,
                relation="related_to", weight=round(weight, 2)
            ))

    print(f"       {len(cooccur_count)} entity-entity pairs")

    # ── Phase 4: Entity ↔ Domain direct edges ──────────────────────────
    # Each entity gets an entity_belongs_to edge to its domain node
    print("[GRAPH] Building entity→domain edges...")
    entity_domain = {}
    for ch in kb.chunks:
        for ent in ch.entities:
            eid = f"entity:{ent}"
            if eid in kb.nodes:
                entity_domain[eid] = ch.domain

    for eid, dom in entity_domain.items():
        did = f"domain:{dom}"
        if did in kb.nodes:
            # Avoid duplicates (entity may appear in chunks from same domain)
            edge_key = (eid, did, "entity_belongs_to")
            already_exists = any(
                e.source == eid and e.target == did and e.relation == "entity_belongs_to"
                for e in kb.edges
            )
            if not already_exists:
                kb.edges.append(GraphEdge(
                    source=eid, target=did, relation="entity_belongs_to", weight=0.9
                ))

    print(f"       {sum(1 for e in kb.edges if e.relation=='entity_belongs_to')} edges")

    # ── Phase 5: Cross-document reference edges ────────────────────────
    # Chunks that share entities get reference edges (existing logic, improved)
    print("[GRAPH] Building cross-document references...")
    ref_count = 0
    for eid, cids in entity_chunk_map.items():
        cid_list = list(cids)
        if len(cid_list) > 1:
            for i in range(len(cid_list) - 1):
                for j in range(i + 1, min(i + 4, len(cid_list))):
                    kb.edges.append(GraphEdge(
                        source=cid_list[i], target=cid_list[j],
                        relation="references", weight=0.7
                    ))
                    ref_count += 1
    print(f"       {ref_count} reference edges")

    # ── Phase 6: Document-to-document similarity edges ─────────────────
    # Documents in the same domain that share entity types
    print("[GRAPH] Building document similarity edges...")
    doc_entities: dict[str, set[str]] = defaultdict(set)
    for ch in kb.chunks:
        doc_entities[ch.doc_id].update(ch.entities)

    doc_list = list(doc_entities.keys())
    doc_sim_count = 0
    for i in range(len(doc_list)):
        for j in range(i + 1, len(doc_list)):
            d1, d2 = doc_list[i], doc_list[j]
            shared = doc_entities[d1] & doc_entities[d2]
            if len(shared) >= 1:
                weight = min(len(shared) / 3.0, 1.0)
                kb.edges.append(GraphEdge(
                    source=d1, target=d2,
                    relation="related_to", weight=round(weight, 2)
                ))
                doc_sim_count += 1
    print(f"       {doc_sim_count} doc-doc similarity edges")

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n[OK] Loaded {len(kb.nodes)} nodes, {len(kb.edges)} edges, {len(kb.chunks)} chunks")
    print(f"     Domains: {domain_names}")
    total_entities = sum(1 for n in kb.nodes.values() if n.type == "entity")
    print(f"     Entities: {total_entities}")
    edge_types = defaultdict(int)
    for e in kb.edges:
        edge_types[e.relation] += 1
    print(f"     Edge types: {dict(edge_types)}")
    return kb


# ── Embedding ──────────────────────────────────────────────────────────

import requests

def compute_embeddings(kb: KnowledgeBase, batch_size: int = 10) -> None:
    """Compute vector embeddings for all chunks via LMStudio API."""
    texts = [(i, c.text) for i, c in enumerate(kb.chunks)]
    if not texts:
        return

    print(f"\n[EMBED] Computing embeddings for {len(texts)} chunks via {EMBED_URL}")
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        try:
            resp = requests.post(
                EMBED_URL,
                json={"input": [t[1] for t in batch], "model": EMBED_MODEL},
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                for (idx, _), emb_data in zip(batch, data["data"]):
                    kb.chunks[idx].embedding = emb_data["embedding"]
                print(f"  [{start+1}-{start+len(batch)}/{len(texts)}] OK")
            else:
                print(f"  [WARN] Embedding API error {resp.status_code}: {resp.text[:200]}")
        except requests.ConnectionError:
            print(f"  [WARN] Cannot connect to {EMBED_URL} — skipping embeddings")
            break
        except Exception as e:
            print(f"  [WARN] Embedding error: {e}")

    embedded = sum(1 for c in kb.chunks if c.embedding is not None)
    print(f"[EMBED] Done: {embedded}/{len(kb.chunks)} chunks embedded")


# ── Serialize ──────────────────────────────────────────────────────────

def serialize(kb: KnowledgeBase) -> dict[str, Any]:
    """Export knowledge base to JSON-serializable dict.

    Stores full text for LLM context; API layer truncates for display.
    """
    return {
        "nodes": [asdict(n) for n in kb.nodes.values()],
        "edges": [asdict(e) for e in kb.edges],
        "chunks": [
            {
                "id": c.id,
                "doc_id": c.doc_id,
                "domain": c.domain,
                "text": c.text,               # full text for LLM context
                "entities": c.entities,
                "has_embedding": c.embedding is not None,
            }
            for c in kb.chunks
        ],
        "documents": kb.documents,
        "stats": {
            "nodes": len(kb.nodes),
            "edges": len(kb.edges),
            "chunks": len(kb.chunks),
            "documents": len(kb.documents),
            "entities": sum(1 for n in kb.nodes.values() if n.type == "entity"),
        },
    }


# ── Main ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("GraphRAG Knowledge Base Loader")
    print("=" * 60)
    print(f"Knowledge base: {KB_PATH}")
    print(f"PDF support:   {'YES (PyMuPDF)' if _HAS_FITZ else 'NO'}")
    print(f"XLSX support:  {'YES (openpyxl)' if _HAS_OPENPYXL else 'NO'}")
    print()

    kb = build_knowledge_base()
    compute_embeddings(kb)
    dump = serialize(kb)

    out_path = Path(__file__).parent / "kb_data.json"
    out_path.write_text(
        json.dumps(dump, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\n[OK] Data written to {out_path}")
    print(f"     Size: {out_path.stat().st_size / 1024:.1f} KB")
