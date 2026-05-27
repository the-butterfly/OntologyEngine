"""LOCOMO-10 Benchmark: OE vs Mem0 Fair Comparison.

Usage (OE):
    python -m examples.agent_memory.14_locomo_benchmark.run_eval \
        --backend oe --project-name oe_sensenova \
        --answerer-model sensenova/sensenova-6.7-flash-lite \
        --judge-model sensenova/sensenova-6.7-flash-lite \
        --llm-base-url http://localhost:9528/v1

Usage (Mem0 — requires mem0oss server on localhost:8888):
    python -m examples.agent_memory.14_locomo_benchmark.run_eval \
        --backend mem0 --project-name mem0_sensenova \
        --answerer-model sensenova/sensenova-6.7-flash-lite \
        --judge-model sensenova/sensenova-6.7-flash-lite \
        --llm-base-url http://localhost:9528/v1

After running both backends, compare:
    python -m examples.agent_memory.14_locomo_benchmark.run_eval \
        --compare \
        --oe-results results/locomo_oe/predicted_oe_sensenova/results.json \
        --mem0-results results/locomo_mem0/predicted_mem0_sensenova/results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from tqdm import tqdm

# Add project root and self dir so imports work under `python -m`
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset import (
    download_dataset,
    expected_question_items,
    get_sorted_sessions,
    load_dataset,
    load_evidence_lookup,
    locomo_date_to_epoch,
    session_to_chunks,
)
from prompts import (
    CATEGORY_NAMES,
    JUDGE_SYSTEM_PROMPT,
    get_answer_generation_prompt,
    get_judge_prompt,
    get_judge_prompt_with_evidence,
    preprocess_answer,
)
from metrics import compute_locomo_metrics, cutoff_label, display_results, build_comparison_table
from clients import OEClient, Mem0Client, _format_search_results

# LLM client (lightweight inline to avoid extra deps)
import openai
from aiolimiter import AsyncLimiter


# =============================================================================
# Lightweight LLM client
# =============================================================================

class LLMClient:
    """Async LLM client for answer generation and judging."""

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        rpm: int = 200,
        timeout: float = 120.0,
    ):
        self.model = model
        self.rpm = rpm
        self.timeout = timeout
        self.limiter = AsyncLimiter(rpm, 60)
        client_kwargs: dict[str, Any] = {"timeout": openai.Timeout(timeout, connect=10.0)}
        # Always pass api_key when provided (even empty string) so openai SDK
        # does not fall back to env var lookup which may be unset.
        if api_key is not None:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = openai.AsyncOpenAI(**client_kwargs)

    async def generate(self, system: str, user: str, temperature: float = 0, max_tokens: int = 4096) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        for attempt in range(5):
            try:
                async with self.limiter:
                    resp = await asyncio.wait_for(
                        self._client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        ),
                        timeout=self.timeout,
                    )
                content = resp.choices[0].message.content
                if content:
                    return content.strip()
                if attempt < 4:
                    await asyncio.sleep(2 * (attempt + 1))
            except asyncio.TimeoutError:
                pass
            except Exception as exc:
                if attempt < 4:
                    await asyncio.sleep(2 * (attempt + 1))
        return ""

    async def generate_structured(self, system: str, user: str, temperature: float = 0, max_tokens: int = 4096) -> dict:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        for attempt in range(5):
            try:
                async with self.limiter:
                    resp = await asyncio.wait_for(
                        self._client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            response_format={"type": "json_object"},
                        ),
                        timeout=self.timeout,
                    )
                raw = resp.choices[0].message.content
                if raw:
                    return json.loads(raw.strip())
            except (json.JSONDecodeError, asyncio.TimeoutError):
                pass
            except Exception:
                pass
            if attempt < 4:
                await asyncio.sleep(2 * (attempt + 1))
        return {}


# =============================================================================
# Ingestion
# =============================================================================

CHUNK_SIZE = 1


async def ingest_conversation(
    conv_idx: int,
    entry: dict,
    client: OEClient | Mem0Client,
    run_id: str,
) -> tuple[bool, str, int]:
    """Ingest all sessions of a LOCOMO conversation.

    Returns (success, user_id, total_chunks_processed).
    """
    conversation = entry["conversation"]
    speaker_a = conversation["speaker_a"]
    speaker_b = conversation["speaker_b"]
    user_id = f"locomo_{conv_idx}_{run_id}"

    sorted_sessions = get_sorted_sessions(conversation)
    total_chunks = sum(
        len(session_to_chunks(s, speaker_a, speaker_b, CHUNK_SIZE))
        for _, _, s in sorted_sessions
    )

    total_processed = 0
    total_failed = 0

    for session_key, date_str, turns in sorted_sessions:
        chunks = session_to_chunks(turns, speaker_a, speaker_b, CHUNK_SIZE)
        if not chunks:
            continue
        session_epoch = locomo_date_to_epoch(date_str)

        for chunk_idx, messages in enumerate(chunks):
            if any(not msg.get("content", "").strip() for msg in messages):
                total_processed += 1
                continue

            response = await client.add(
                messages, user_id, timestamp=session_epoch
            )
            if response is not None:
                total_processed += 1
            else:
                total_failed += 1

    return total_failed == 0, user_id, total_processed


# =============================================================================
# Search + Answer + Judge
# =============================================================================

async def process_question(
    qa: dict,
    qa_idx: int,
    conv_idx: int,
    user_id: str,
    client: OEClient | Mem0Client,
    answerer: LLMClient,
    judge_llm: LLMClient,
    cutoffs: list[int],
    top_k: int,
    reference_date_human: str | None,
    evidence_lookup: dict | None,
    predict_only: bool,
) -> dict[str, Any]:
    """Process a single question: search + answer + judge at multiple cutoffs."""
    question_id = f"conv{conv_idx}_q{qa_idx}"
    question = qa["question"]
    category = qa["category"]
    answer = str(qa["answer"])

    # --- Search ---
    start = time.monotonic()
    search_results = await client.search(question, user_id, top_k=top_k)
    search_latency = (time.monotonic() - start) * 1000

    formatted, query_debug = _format_search_results(search_results)

    result: dict[str, Any] = {
        "question_id": question_id,
        "conversation_idx": conv_idx,
        "category": category,
        "category_name": CATEGORY_NAMES.get(category, "unknown"),
        "question": question,
        "ground_truth_answer": answer,
        "evidence": qa.get("evidence", []),
        "user_id": user_id,
        "reference_date": reference_date_human,
        "retrieval": {
            "search_query": question,
            "search_results": formatted,
            "search_latency_ms": round(search_latency, 1),
            "total_results": len(formatted),
        },
    }
    if query_debug:
        result["retrieval"]["query_debug"] = query_debug

    if predict_only:
        return result

    # --- Answer + Judge at each cutoff ---
    cutoff_results: dict[str, dict] = {}
    processed_answer = preprocess_answer(category, answer)

    ev_ctx = ""
    if evidence_lookup:
        for ref in qa.get("evidence", []):
            key = (conv_idx, ref)
            if key in evidence_lookup:
                ev_ctx += evidence_lookup[key] + "\n"
        ev_ctx = ev_ctx.strip()

    for c in cutoffs:
        sliced = formatted[:c]
        label = cutoff_label(c)

        gen_prompt = get_answer_generation_prompt(
            question, sliced, reference_date=reference_date_human
        )
        generated_answer = await answerer.generate(system="", user=gen_prompt)
        if "ANSWER:" in generated_answer:
            generated_answer = generated_answer.rsplit("ANSWER:", 1)[-1].strip()

        if ev_ctx:
            judge_prompt = get_judge_prompt_with_evidence(
                category, question, processed_answer, generated_answer, ev_ctx
            )
        else:
            judge_prompt = get_judge_prompt(category, question, processed_answer, generated_answer)

        raw = await judge_llm.generate_structured(
            system=JUDGE_SYSTEM_PROMPT,
            user=judge_prompt,
        )
        if isinstance(raw, dict):
            label_val = raw.get("label", "").upper()
            correct = label_val == "CORRECT"
        else:
            correct = False

        score = 1.0 if correct else 0.0
        judgment = "CORRECT" if correct else "WRONG"

        cutoff_results[label] = {
            "judgment": judgment,
            "score": score,
            "generated_answer": generated_answer,
            "memories_evaluated": len(sliced),
            "reason": raw.get("reasoning", "") if isinstance(raw, dict) else "",
        }

    result["cutoff_results"] = cutoff_results
    return result


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LOCOMO-10 Benchmark: OE vs Mem0 fair comparison",
    )
    # Mode
    parser.add_argument("--backend", default="oe", choices=["oe", "mem0"],
                        help="Memory backend to evaluate")
    parser.add_argument("--project-name", default="default", help="Name for this eval run")
    parser.add_argument("--compare", action="store_true",
                        help="Compare two existing result files instead of running eval")
    parser.add_argument("--oe-results", default=None, help="Path to OE results JSON")
    parser.add_argument("--mem0-results", default=None, help="Path to Mem0 results JSON")

    # LLM
    parser.add_argument("--answerer-model", default="sensenova/sensenova-6.7-flash-lite",
                        help="Model for answer generation")
    parser.add_argument("--judge-model", default="sensenova/sensenova-6.7-flash-lite",
                        help="Model for judging")
    parser.add_argument("--llm-base-url", default=None,
                        help="Base URL for LLM API (e.g. http://localhost:9528/v1)")
    parser.add_argument("--llm-api-key", default="", help="API key for LLM")
    parser.add_argument("--rpm", type=int, default=200, help="Requests per minute")

    # Dataset
    parser.add_argument("--dataset-path", default=None, help="Path to local locomo10.json")
    parser.add_argument("--conversations", default="0,1,2,3,4,5,6,7,8,9",
                        help="Comma-separated conversation indices")
    parser.add_argument("--categories", default="1,2,3,4",
                        help="Comma-separated category indices")
    parser.add_argument("--max-questions", type=int, default=None,
                        help="Max questions per conversation (for quick testing)")

    # Retrieval
    parser.add_argument("--top-k", type=int, default=200,
                        help="Number of search results to retrieve")
    parser.add_argument("--top-k-cutoffs", default="10,20,50,200",
                        help="Comma-separated cutoffs for evaluation")

    # Output
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: results/locomo_<backend>)")
    parser.add_argument("--predict-only", action="store_true",
                        help="Skip answer+judge, only ingest+search")
    parser.add_argument("--with-evidence", action="store_true",
                        help="Pass evidence to judge")

    # OE-specific
    parser.add_argument("--oe-db-path", default=None, help="OE KuzuDB path")
    parser.add_argument("--oe-llm-model", default=None,
                        help="OE internal LLM model (for consolidation / entity resolution)")
    parser.add_argument("--oe-llm-base-url", default=None, help="OE internal LLM base URL")
    parser.add_argument("--oe-llm-api-key", default="", help="OE internal LLM API key")

    # Mem0-specific
    parser.add_argument("--mem0-host", default=None, help="Mem0 server URL")
    parser.add_argument("--oe-embedding-provider", default="openai_compatible", help="OE embedding provider")
    parser.add_argument("--oe-embedding-base-url", default=None, help="OE embedding base URL (e.g. http://localhost:7852/v1)")
    parser.add_argument("--oe-embedding-model", default=None, help="OE embedding model")
    parser.add_argument("--oe-embedding-dimension", type=int, default=2560, help="OE embedding dimension")
    parser.add_argument("--oe-embedding-api-key", default="dummy", help="OE embedding API key")

    return parser.parse_args()


def parse_cutoffs(s: str) -> list[int]:
    return [int(x.strip()) for x in s.split(",") if x.strip()]


# =============================================================================
# Main eval loop
# =============================================================================

async def run_eval(args: argparse.Namespace) -> None:
    cutoffs = parse_cutoffs(args.top_k_cutoffs)
    categories = [int(c) for c in args.categories.split(",")]
    conv_indices = [int(c) for c in args.conversations.split(",")]

    run_id = uuid.uuid4().hex[:8]
    backend = args.backend
    out_dir_base = args.output_dir or f"results/locomo_{backend}"
    output_dir = os.path.join(out_dir_base, f"predicted_{args.project_name}")
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 70)
    print(f"LOCOMO-10 Benchmark | backend={backend} project={args.project_name} run_id={run_id}")
    print(f"  Answerer: {args.answerer_model}")
    print(f"  Judge:    {args.judge_model}")
    print(f"  LLM base: {args.llm_base_url or 'default'}")
    print(f"  Conversations: {args.conversations}")
    print(f"  Cutoffs: {args.top_k_cutoffs}")
    print("=" * 70)

    # Dataset
    if args.dataset_path:
        dataset_path = Path(args.dataset_path)
    else:
        dataset_path = download_dataset()
    dataset = load_dataset(dataset_path)
    print(f"  Dataset: {dataset_path} ({len(dataset)} conversations)")

    evidence_lookup = None
    if args.with_evidence:
        evidence_lookup = load_evidence_lookup(dataset_path)
        print(f"  Evidence lookup: {len(evidence_lookup)} entries")

    # LLM clients
    answerer = LLMClient(
        model=args.answerer_model,
        base_url=args.llm_base_url,
        api_key=args.llm_api_key,
        rpm=args.rpm,
    )
    judge_llm = LLMClient(
        model=args.judge_model,
        base_url=args.llm_base_url,
        api_key=args.llm_api_key,
        rpm=args.rpm,
    )

    # Memory client
    if backend == "oe":
        oe_llm_config = None
        if args.oe_llm_base_url:
            oe_llm_config = {
                "base_url": args.oe_llm_base_url,
                "api_key": args.oe_llm_api_key or "",
                "model": args.oe_llm_model or "default",
                "enabled": True,
            }
        oe_embedding_config = None
        if args.oe_embedding_base_url:
            oe_embedding_config = {
                "provider": args.oe_embedding_provider,
                "base_url": args.oe_embedding_base_url,
                "api_key": args.oe_embedding_api_key,
                "model": args.oe_embedding_model,
                "dimension": args.oe_embedding_dimension,
            }
        client: OEClient | Mem0Client = OEClient(
            db_path=args.oe_db_path,
            llm_config=oe_llm_config,
            embedding_config=oe_embedding_config,
        )
    else:
        client = Mem0Client(host=args.mem0_host)

    all_evaluations: list[dict] = []
    existing_ids: set[str] = set()
    results_lock = asyncio.Lock()

    # Load existing results for resume
    for p in sorted(Path(output_dir).glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            data = json.loads(p.read_text())
            if data.get("category") in categories:
                all_evaluations.append(data)
                existing_ids.add(data["question_id"])
        except (json.JSONDecodeError, KeyError):
            continue
    if existing_ids:
        print(f"  Resumed from {len(existing_ids)} existing results")

    async with client:
        for conv_idx in conv_indices:
            if conv_idx >= len(dataset):
                print(f"  Warning: conversation {conv_idx} out of range")
                continue

            entry = dataset[conv_idx]
            conversation = entry["conversation"]

            # Ingest
            success, user_id, chunks = await ingest_conversation(
                conv_idx, entry, client, run_id
            )
            print(f"  Conv {conv_idx}: ingested {chunks} chunks (user_id={user_id})")

            # Reference date from last session
            sorted_sessions = get_sorted_sessions(conversation)
            ref_date_human = None
            if sorted_sessions:
                ref_date_human = sorted_sessions[-1][1]

            # Questions
            questions = entry.get("qa", entry.get("qa_pairs", []))
            conv_questions = [
                (qi, qa) for qi, qa in enumerate(questions)
                if qa.get("category") in categories
            ]
            if args.max_questions is not None:
                conv_questions = conv_questions[:args.max_questions]

            for qi, qa in tqdm(conv_questions, desc=f"Q conv {conv_idx}", leave=False):
                qid = f"conv{conv_idx}_q{qi}"
                if qid in existing_ids:
                    continue

                result = await process_question(
                    qa=qa,
                    qa_idx=qi,
                    conv_idx=conv_idx,
                    user_id=user_id,
                    client=client,
                    answerer=answerer,
                    judge_llm=judge_llm,
                    cutoffs=cutoffs,
                    top_k=args.top_k,
                    reference_date_human=ref_date_human,
                    evidence_lookup=evidence_lookup,
                    predict_only=args.predict_only,
                )

                result_path = os.path.join(output_dir, f"{qid}.json")
                Path(result_path).write_text(json.dumps(result, indent=2, ensure_ascii=False))

                async with results_lock:
                    all_evaluations.append(result)
                    existing_ids.add(qid)

    # Metrics
    if not args.predict_only and all_evaluations:
        has_cutoffs = any("cutoff_results" in e for e in all_evaluations)
        if has_cutoffs:
            metrics = compute_locomo_metrics(all_evaluations, cutoffs)
            display_results(metrics, cutoffs)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unified = {
                "metadata": {
                    "benchmark": f"locomo_{backend}",
                    "project_name": args.project_name,
                    "run_id": run_id,
                    "timestamp": timestamp,
                    "answerer_model": args.answerer_model,
                    "judge_model": args.judge_model,
                    "llm_base_url": args.llm_base_url,
                    "backend": backend,
                    "top_k": args.top_k,
                    "top_k_cutoffs": [cutoff_label(c) for c in cutoffs],
                    "total_questions": len(all_evaluations),
                    "categories": categories,
                },
                "metrics_by_cutoff": metrics,
                "evaluations": all_evaluations,
            }
            unified_path = os.path.join(out_dir_base, f"locomo_{backend}_results_{timestamp}.json")
            Path(unified_path).write_text(json.dumps(unified, indent=2, ensure_ascii=False))
            # Also save a simple results.json for --compare
            simple_path = os.path.join(output_dir, "results.json")
            Path(simple_path).write_text(json.dumps(unified, indent=2, ensure_ascii=False))
            print(f"\nResults saved to: {unified_path}")
            print(f"Quick-access: {simple_path}")

    print(f"\nTotal questions processed: {len(all_evaluations)}")


# =============================================================================
# Compare mode
# =============================================================================

def run_compare(args: argparse.Namespace) -> None:
    if not args.oe_results or not args.mem0_results:
        print("--compare requires both --oe-results and --mem0-results")
        sys.exit(1)

    oe_data = json.loads(Path(args.oe_results).read_text())
    mem0_data = json.loads(Path(args.mem0_results).read_text())

    oe_metrics = oe_data.get("metrics_by_cutoff", {})
    mem0_metrics = mem0_data.get("metrics_by_cutoff", {})

    # Infer cutoffs from keys
    cutoffs = []
    for k in oe_metrics:
        if k.startswith("top_"):
            try:
                cutoffs.append(int(k.replace("top_", "")))
            except ValueError:
                pass
    cutoffs.sort()

    md = build_comparison_table(oe_metrics, mem0_metrics, cutoffs)
    print(md)

    out_path = Path(args.oe_results).parent / "comparison.md"
    out_path.write_text(md)
    print(f"\nComparison saved to: {out_path}")


# =============================================================================
# Entry point
# =============================================================================

def main() -> None:
    args = parse_args()
    if args.compare:
        run_compare(args)
    else:
        asyncio.run(run_eval(args))


if __name__ == "__main__":
    main()
