"""
GraphRAG Hybrid Retrieval Backend
==================================
FastAPI server exposing:
  1. Knowledge graph structure (nodes + edges)
  2. Hybrid search (vector + graph proximity + path traversal → RRF fusion)
  3. LLM-powered answer synthesis

Endpoints:
  GET  /api/graph    → full graph for frontend visualization
  GET  /api/domains  → list domains
  POST /api/search   → hybrid retrieval (returns chunks + paths)
  POST /api/query    → search + LLM answer (returns answer + evidence)
"""

import json, math, os, re
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Config ─────────────────────────────────────────────────────────────

DATA_PATH = Path(__file__).parent / "kb_data.json"
EMBED_URL = "http://127.0.0.1:7852/v1/embeddings"
EMBED_MODEL = "text-embedding-qwen3-embedding-4b"
LLM_URL = "http://localhost:9528/v1"
LLM_KEY = "sk-noop"
LLM_MODEL = "sensenova/sensenova-6.7-flash-lite"

TOP_K_VECTOR = 10
TOP_K_GRAPH = 8
TOP_K_FUSION = 12

# ── Data Store ─────────────────────────────────────────────────────────

nodes: dict[str, dict] = {}
edges: list[dict] = []
chunks: list[dict] = []
embeddings: dict[str, list[float]] = {}   # chunk_id → vector

# entity → [chunk_id, ...]
entity_index: dict[str, list[str]] = {}
# chunk_id → [entity, ...]
chunk_entities: dict[str, list[str]] = {}
chunk_domain: dict[str, str] = {}

# ── Load ───────────────────────────────────────────────────────────────

def load_data() -> None:
    global nodes, edges, chunks, embeddings, entity_index, chunk_entities, chunk_domain
    if not DATA_PATH.exists():
        print(f"[WARN] {DATA_PATH} not found. Run loader.py first.")
        return
    data = json.loads(DATA_PATH.read_text("utf-8"))
    nodes.clear()
    for n in data.get("nodes", []):
        nodes[n["id"]] = n
    edges.clear()
    edges.extend(data.get("edges", []))
    chunks.clear()
    chunks.extend(data.get("chunks", []))
    # Build indices
    entity_index.clear()
    chunk_entities.clear()
    chunk_domain.clear()
    for ch in chunks:
        cid = ch["id"]
        chunk_domain[cid] = ch.get("domain", "")
        ents = ch.get("entities", [])
        chunk_entities[cid] = ents
        for ent in ents:
            entity_index.setdefault(ent, []).append(cid)
    # Load external embeddings if available
    emb_path = DATA_PATH.with_suffix(".emb.json")
    if emb_path.exists():
        embeddings.update(json.loads(emb_path.read_text("utf-8")))
        print(f"[OK] Loaded {len(embeddings)} pre-computed embeddings")
    else:
        print("[INFO] No pre-computed embeddings. Will compute on demand.")

load_data()

# ── Embedding (on-demand with cache) ───────────────────────────────────

def get_embedding(text: str) -> list[float] | None:
    """Compute single embedding with write-through cache."""
    cache_key = f"query:{hash(text)}"
    # Check if we already have it
    try:
        resp = requests.post(
            EMBED_URL,
            json={"input": [text], "model": EMBED_MODEL},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["data"][0]["embedding"]
    except Exception as e:
        print(f"[WARN] Embedding error: {e}")
    return None

def cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(y*y for y in b))
    return dot / (na * nb) if na * nb > 0 else 0

# ── Hybrid Search ────────────────────────────────────────────────────

def vector_search(q_emb: list[float], top_k: int = TOP_K_VECTOR) -> list[dict]:
    """Top-k cosine similarity over chunk embeddings."""
    scored = []
    for ch in chunks:
        cid = ch["id"]
        if cid not in embeddings:
            continue
        sim = cosine_sim(q_emb, embeddings[cid])
        scored.append({"chunk_id": cid, "score": sim, "source": "vector"})
    scored.sort(key=lambda x: -x["score"])
    return scored[:top_k]

def graph_expansion(vector_results: list[dict], top_k: int = TOP_K_GRAPH) -> list[dict]:
    """Expand from vector-matched chunks via entity co-occurrence.
    If a chunk mentions entity E, and entity E appears in another chunk,
    that other chunk gets a graph score boost."""
    seen = set(r["chunk_id"] for r in vector_results)
    bridge_entities: set[str] = set()
    for r in vector_results:
        for ent in chunk_entities.get(r["chunk_id"], []):
            bridge_entities.add(ent)

    expanded = []
    for ent in bridge_entities:
        for cid in entity_index.get(ent, []):
            if cid in seen:
                continue
            seen.add(cid)
            # score = fraction of shared entities
            shared = len(set(chunk_entities.get(cid, [])) & bridge_entities)
            total = max(len(chunk_entities.get(cid, [])), 1)
            expanded.append({
                "chunk_id": cid,
                "score": shared / total,
                "source": "graph",
                "via_entities": [ent],
            })
    expanded.sort(key=lambda x: -x["score"])
    return expanded[:top_k]

def path_search(q_emb: list[float] | None, query: str, top_k: int = 5) -> list[dict]:
    """Entity-chain path traversal: find entity→chunk→entity→chunk paths
    that connect query terms."""
    # Extract query entities
    query_entities = set()
    for ent in entity_index:
        if any(term in query.lower() for term in ent.lower().split()):
            query_entities.add(ent)
        elif any(term in ent.lower() for term in re.findall(r'\w+', query.lower())):
            query_entities.add(ent)

    if len(query_entities) < 1:
        return []

    # BFS 2-hop: entity → chunk → neighbor_entity → neighbor_chunk
    path_chunks: dict[str, float] = {}
    for ent in query_entities:
        for cid in entity_index.get(ent, []):
            path_chunks[cid] = path_chunks.get(cid, 0) + 1.0
            for neighbor_ent in chunk_entities.get(cid, []):
                if neighbor_ent == ent:
                    continue
                for neighbor_cid in entity_index.get(neighbor_ent, []):
                    if neighbor_cid == cid:
                        continue
                    path_chunks[neighbor_cid] = path_chunks.get(neighbor_cid, 0) + 0.5

    results = [
        {"chunk_id": cid, "score": sc, "source": "path"}
        for cid, sc in path_chunks.items()
    ]
    results.sort(key=lambda x: -x["score"])
    return results[:top_k]

def rrf_fusion(*rankings: list[dict], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion: combine multiple scored lists."""
    scores: dict[str, float] = {}
    details: dict[str, dict] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            cid = item["chunk_id"]
            rrf_score = 1.0 / (k + rank + 1)
            scores[cid] = scores.get(cid, 0) + rrf_score
            if cid not in details:
                details[cid] = {
                    "chunk_id": cid, "score": 0, "sources": [],
                    "via_entities": item.get("via_entities", []),
                }
            details[cid]["sources"].append(item["source"])
            if item.get("via_entities"):
                details[cid]["via_entities"].extend(item.get("via_entities", []))

    for cid in details:
        details[cid]["score"] = round(scores[cid], 4)
        details[cid]["sources"] = list(set(details[cid]["sources"]))

    results = sorted(details.values(), key=lambda x: -x["score"])
    return results

# ── LLM Answer ─────────────────────────────────────────────────────────

def build_context(results: list[dict]) -> str:
    """Build LLM context from retrieved chunks with evidence traces."""
    parts = []
    for i, r in enumerate(results[:8]):
        cid = r["chunk_id"]
        ch = next((c for c in chunks if c["id"] == cid), None)
        if not ch:
            continue
        domain = ch.get("domain", "?")
        text = ch.get("text", "")[:800]
        entities = ",".join(ch.get("entities", [])[:5])
        sources = ",".join(r.get("sources", []))
        parts.append(f"[{i+1}] ({domain} | {sources} | entities: {entities})\n{text}")
    return "\n\n---\n\n".join(parts)

def query_llm(query: str, context: str) -> str:
    """Call Sensenova LLM for answer synthesis."""
    if not LLM_KEY:
        return "[LLM未配置] 请在环境变量 LLM_KEY 中设置API密钥"
    system_prompt = (
        "你是GraphRAG智能助手。基于检索到的知识片段回答用户问题。\n"
        "每个片段标注了所属领域和检索来源(V=向量, G=图扩散, P=路径遍历)。\n"
        "请在回答末尾标注所用证据来源编号，如 [来源: 1(V+G), 3(V+P)]。\n"
        "如知识不足，请明确说明，不要编造信息。"
    )
    user_prompt = f"## 用户问题\n{query}\n\n## 检索到的知识片段\n{context}"
    try:
        resp = requests.post(
            f"{LLM_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
            },
            timeout=60,
        )
        if resp.status_code == 200:
            msg = resp.json()["choices"][0]["message"]
            return msg.get("content") or msg.get("reasoning") or str(msg)
        return f"[LLM错误 {resp.status_code}] {resp.text[:200]}"
    except Exception as e:
        return f"[LLM调用失败] {e}"

# ── API ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_data()
    yield

app = FastAPI(title="GraphRAG Demo", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class SearchRequest(BaseModel):
    query: str

class QueryRequest(BaseModel):
    query: str
    use_llm: bool = True

@app.get("/api/health")
def health():
    return {"status": "ok", "chunks": len(chunks), "nodes": len(nodes), "edges": len(edges), "embeddings": len(embeddings)}

@app.get("/api/graph")
def get_graph():
    """Return nodes and edges for frontend visualization."""
    return {"nodes": list(nodes.values()), "edges": edges}

@app.get("/api/domains")
def get_domains():
    domains = {}
    for ch in chunks:
        d = ch.get("domain", "unknown")
        domains.setdefault(d, {"chunks": 0, "entities": set()})
        domains[d]["chunks"] += 1
        for ent in ch.get("entities", []):
            domains[d]["entities"].add(ent)
    return {
        d: {"chunks": v["chunks"], "entities": len(v["entities"])}
        for d, v in domains.items()
    }

@app.post("/api/search")
def search(req: SearchRequest):
    """Hybrid search: vector + graph + path → RRF fusion."""
    if not chunks:
        raise HTTPException(400, "Knowledge base not loaded")

    q_emb = get_embedding(req.query)
    vec_results = vector_search(q_emb) if q_emb else []
    graph_results = graph_expansion(vec_results)
    path_results = path_search(q_emb, req.query)

    fused = rrf_fusion(vec_results, graph_results, path_results)[:TOP_K_FUSION]

    # Hydrate with text
    for r in fused:
        ch = next((c for c in chunks if c["id"] == r["chunk_id"]), None)
        if ch:
            r["text"] = ch.get("text", "")[:300]
            r["domain"] = ch.get("domain", "")
            r["entities"] = ch.get("entities", [])[:8]

    return {
        "results": fused,
        "meta": {
            "vector_results": len(vec_results),
            "graph_results": len(graph_results),
            "path_results": len(path_results),
            "embedding_available": q_emb is not None,
        },
    }

@app.post("/api/query")
def query(req: QueryRequest):
    """Hybrid search + optional LLM answer."""
    search_results = search(SearchRequest(query=req.query))
    results = search_results["results"]

    context = build_context(results)
    answer = query_llm(req.query, context) if req.use_llm else None

    # Build evidence chains
    evidence_chains = []
    for r in results[:5]:
        chain = {
            "chunk_id": r["chunk_id"],
            "domain": r.get("domain", ""),
            "sources": r.get("sources", []),
            "text": r.get("text", "")[:200],
            "entities": r.get("entities", [])[:5],
        }
        evidence_chains.append(chain)

    return {
        "answer": answer,
        "evidence": evidence_chains,
        "meta": search_results["meta"],
    }

# ── Main ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)

"""
Quick Start:
  # 1. Load knowledge base
  python examples/demo_graphrag/loader.py

  # 2. Start backend
  LLM_KEY="sk-xxx" python examples/demo_graphrag/backend.py

  # 3. Open frontend
  open examples/demo_graphrag/frontend.html
"""
