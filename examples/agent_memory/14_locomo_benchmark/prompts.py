"""LOCOMO benchmark prompts.

Adapted from memory-benchmarks/benchmarks/locomo/prompts.py.
Keeps the same judge / answerer prompts so results are comparable.
"""

from __future__ import annotations

# -----------------------------------------------------------------------------
# Category mapping
# -----------------------------------------------------------------------------

CATEGORY_NAMES = {
    1: "short-term",
    2: "medium-term",
    3: "long-term",
    4: "cross-dialogue",
}

CATEGORIES_TO_EVALUATE = [1, 2, 3, 4]

# -----------------------------------------------------------------------------
# Answer generation
# -----------------------------------------------------------------------------

ANSWER_GENERATION_SYSTEM_PROMPT = """You are a helpful question answering assistant.
Answer the given question using the provided memories.
Your answer must be concise and directly address the question.
If the memories do not contain enough information to answer the question, respond with "I don't know".
End your response with ANSWER: <your answer>"""


def get_answer_generation_prompt(
    question: str,
    memories: list[dict],
    reference_date: str | None = None,
    user_profile: dict | None = None,
) -> str:
    """Build the answer-generation prompt."""
    lines = []
    if reference_date:
        lines.append(f"Reference date: {reference_date}")
    if user_profile:
        lines.append(f"User profile: {user_profile}")
    if memories:
        lines.append("Memories:")
        for i, m in enumerate(memories, 1):
            text = m.get("memory", "")
            lines.append(f"{i}. {text}")
    else:
        lines.append("Memories: (none)")
    lines.append(f"\nQuestion: {question}")
    lines.append("\nAnswer the question using the memories above.")
    lines.append("End your response with ANSWER: <your answer>")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Judge
# -----------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = """You are an expert judge evaluating answer correctness.
Compare the generated answer to the ground truth answer and determine if it is correct.
Respond with a JSON object containing:
- "label": either "CORRECT" or "WRONG"
- "reasoning": brief explanation of your judgment"""


def preprocess_answer(category: int, answer: str) -> str:
    """Normalize ground-truth answer for comparison."""
    if category == 3 and answer.lower().startswith("yes"):
        return "yes"
    if category == 3 and answer.lower().startswith("no"):
        return "no"
    return answer.strip()


def get_judge_prompt(category: int, question: str, ground_truth: str, generated: str) -> str:
    """Build the judge prompt (no evidence)."""
    return f"""Question: {question}
Ground Truth Answer: {ground_truth}
Generated Answer: {generated}

Determine if the generated answer is correct compared to the ground truth.
For category {CATEGORY_NAMES.get(category, 'unknown')} questions:
- The answer need not match word-for-word
- It must capture the same key facts and meaning
- Dates and names must match exactly unless equivalent

Respond with JSON: {{"label": "CORRECT" or "WRONG", "reasoning": "..."}}"""


def get_judge_prompt_with_evidence(
    category: int, question: str, ground_truth: str, generated: str, evidence: str
) -> str:
    """Build the judge prompt with ground-truth evidence."""
    return f"""Question: {question}
Ground Truth Answer: {ground_truth}
Generated Answer: {generated}

Reference Evidence:
{evidence}

Determine if the generated answer is correct.
The evidence above shows what was actually said in the conversation.
Compare the generated answer to both the ground truth and the evidence.

Respond with JSON: {{"label": "CORRECT" or "WRONG", "reasoning": "..."}}"""
