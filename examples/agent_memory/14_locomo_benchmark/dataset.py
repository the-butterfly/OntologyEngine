"""LOCOMO-10 dataset loader and parser.

Auto-downloads from GitHub if missing.  Reuses the parsing logic from
memory-benchmarks (benchmarks/locomo/run.py) but is self-contained so
the example can run without importing the sibling project.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATASET_URL = "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json"
DEFAULT_DATASET_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DATASET_FILE = "locomo10.json"


def _download(url: str, dest: Path, desc: str = "Downloading") -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"{desc}: {url} -> {dest}")
    urllib.request.urlretrieve(url, dest)


def download_dataset(dataset_dir: Path | None = None) -> Path:
    """Download locomo10.json from GitHub if not present."""
    ddir = dataset_dir or DEFAULT_DATASET_DIR
    path = ddir / DEFAULT_DATASET_FILE
    if path.exists():
        return path
    _download(DATASET_URL, path, "Downloading LOCOMO-10")
    data = json.loads(path.read_text())
    if not isinstance(data, list) or len(data) != 10:
        path.unlink()
        raise RuntimeError(f"Invalid dataset: expected 10 conversations, got {len(data)}")
    print(f"Downloaded: {path} ({len(data)} conversations)")
    return path


def load_dataset(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_locomo_date(date_str: str) -> datetime | None:
    """Parse LOCOMO date: '1:56 pm on 8 May, 2023'."""
    for fmt in ("%I:%M %p on %d %B, %Y", "%I:%M %p on %d %b, %Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


def locomo_date_to_epoch(date_str: str) -> int | None:
    parsed = parse_locomo_date(date_str)
    if parsed:
        return int(parsed.replace(tzinfo=timezone.utc).timestamp())
    return None


def get_sorted_sessions(conversation: dict) -> list[tuple[str, str, list[dict]]]:
    """Extract and sort sessions chronologically.

    Returns list of (session_key, date_str, turns).
    """
    session_keys = [k for k in conversation if re.match(r"^session_\d+$", k)]
    paired = []
    for key in session_keys:
        date_key = f"{key}_date_time"
        date_str = conversation.get(date_key, "")
        turns = conversation[key]
        paired.append((key, date_str, turns))

    def sort_key(item: tuple) -> tuple:
        parsed = parse_locomo_date(item[1])
        if parsed:
            return (0, parsed)
        num = int(re.search(r"\d+", item[0]).group())
        return (1, datetime(2000, 1, num))

    paired.sort(key=sort_key)
    return paired


def session_to_chunks(turns: list[dict], speaker_a: str, speaker_b: str, chunk_size: int = 1) -> list[list[dict]]:
    """Convert turns to message chunks for ingestion."""
    messages = []
    for turn in turns:
        speaker = turn.get("speaker", "")
        text = turn.get("text", "")
        blip = turn.get("blip_caption", "")
        query = turn.get("query", "")
        if query and blip:
            photo_tag = f"[Sharing image - query: {query}. The image shows: {blip}]"
        elif query:
            photo_tag = f"[Sharing image - query for: {query}]"
        elif blip:
            photo_tag = f"[Sharing image that shows: {blip}]"
        else:
            photo_tag = ""
        if photo_tag:
            text = f"{text} {photo_tag}" if text else photo_tag
        if not text:
            continue
        role = "user" if speaker == speaker_a else "assistant"
        messages.append({"role": role, "content": f"{speaker}: {text}"})

    chunks = []
    for i in range(0, len(messages), chunk_size):
        chunk = messages[i : i + chunk_size]
        if chunk:
            chunks.append(chunk)
    return chunks


def load_evidence_lookup(dataset_path: Path) -> dict[tuple[int, str], str]:
    """Build lookup: (conv_idx, dia_id) -> formatted turn text."""
    with open(dataset_path) as f:
        data = json.load(f)
    lookup: dict[tuple[int, str], str] = {}
    for conv_idx, conv in enumerate(data):
        conversation = conv["conversation"]
        session_dates = {}
        for key in conversation:
            if key.endswith("_date_time") and key.startswith("session_"):
                session_num = key.replace("session_", "").replace("_date_time", "")
                session_dates[session_num] = conversation[key]
        for key in conversation:
            if key.startswith("session_") and not key.endswith("date_time"):
                if not isinstance(conversation[key], list):
                    continue
                for turn in conversation[key]:
                    dia_id = turn.get("dia_id", "")
                    if dia_id:
                        speaker = turn.get("speaker", "")
                        text = turn.get("text", "")
                        dia_match = re.match(r"D(\d+):", dia_id)
                        date_suffix = ""
                        if dia_match:
                            snum = dia_match.group(1)
                            sdate = session_dates.get(snum, "")
                            if sdate:
                                date_suffix = f", said on {sdate}"
                        lookup[(conv_idx, dia_id)] = f'[{dia_id}{date_suffix}] {speaker}: "{text}"'
    return lookup


def expected_question_items(
    dataset: list[dict],
    conv_indices: list[int],
    categories: list[int],
    max_questions: int | None,
) -> list[tuple[str, int, int, dict]]:
    """(question_id, conv_idx, qa_idx, qa_dict) for every question in scope."""
    items: list[tuple[str, int, int, dict]] = []
    for conv_idx in conv_indices:
        if conv_idx >= len(dataset):
            continue
        entry = dataset[conv_idx]
        questions = entry.get("qa", entry.get("qa_pairs", []))
        conv_questions = [
            (qi, qa) for qi, qa in enumerate(questions)
            if qa.get("category") in categories
        ]
        if max_questions is not None:
            conv_questions = conv_questions[:max_questions]
        for qi, qa in conv_questions:
            items.append((f"conv{conv_idx}_q{qi}", conv_idx, qi, qa))
    return items
