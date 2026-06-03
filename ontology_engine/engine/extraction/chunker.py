from __future__ import annotations

import re
from dataclasses import dataclass, field

TARGET_TOKENS = 900
OVERLAP_RATIO = 0.15
SEARCH_WINDOW_TOKENS = 200
CHARS_PER_TOKEN = 4

AST_SCORES: dict[str, int] = {
    "class_declaration": 100,
    "class_definition": 100,
    "interface_declaration": 100,
    "struct_item": 100,
    "function_declaration": 90,
    "function_definition": 90,
    "method_definition": 90,
    "arrow_function": 90,
    "type_alias_declaration": 80,
    "type_definition": 80,
    "enum_declaration": 80,
    "enum_definition": 80,
}

MARKDOWN_SCORES: list[tuple[re.Pattern, int]] = [
    (re.compile(r"^#{1}\s"), 100),
    (re.compile(r"^#{2}\s"), 90),
    (re.compile(r"^#{3}\s"), 80),
    (re.compile(r"^```"), 80),
    (re.compile(r"^#{4}\s"), 70),
    (re.compile(r"^---\s*$"), 60),
    (re.compile(r"^\*\*\*\s*$"), 60),
]

TREE_SITTER_AVAILABLE = False
try:
    import tree_sitter_python  # type: ignore[import-untyped]
    import tree_sitter_javascript  # type: ignore[import-untyped]
    import tree_sitter_typescript  # type: ignore[import-untyped]
    import tree_sitter_go  # type: ignore[import-untyped]
    import tree_sitter_rust  # type: ignore[import-untyped]

    from tree_sitter import Language, Parser  # type: ignore[import-untyped]

    TREE_SITTER_AVAILABLE = True
except ImportError:
    pass


@dataclass
class BreakPoint:
    offset: int
    line: int
    score: float
    source: str = "regex"


@dataclass
class Chunk:
    index: int
    content: str
    offset_start: int
    offset_end: int
    line_start: int
    line_end: int
    token_count: int
    break_source: str = ""


@dataclass
class ChunkResult:
    chunks: list[Chunk] = field(default_factory=list)
    total_tokens: int = 0
    break_points: list[BreakPoint] = field(default_factory=list)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _is_in_code_fence(lines: list[str], line_idx: int) -> bool:
    fence_count = 0
    for i in range(line_idx + 1):
        stripped = lines[i].strip()
        if stripped.startswith("```"):
            fence_count += 1
    return fence_count % 2 == 1


def find_regex_breakpoints(text: str) -> list[BreakPoint]:
    lines = text.split("\n")
    breakpoints: list[BreakPoint] = []
    offset = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if not _is_in_code_fence(lines, i):
                breakpoints.append(BreakPoint(offset=offset, line=i, score=20, source="regex:blank"))
        elif stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("+ "):
            if not _is_in_code_fence(lines, i):
                breakpoints.append(BreakPoint(offset=offset, line=i, score=5, source="regex:list"))
        else:
            for pattern, score in MARKDOWN_SCORES:
                if pattern.match(stripped):
                    if score >= 80 or not _is_in_code_fence(lines, i):
                        breakpoints.append(BreakPoint(offset=offset, line=i, score=score, source="regex:md"))
                    break
        offset += len(line) + 1
    return breakpoints


def find_ast_breakpoints(text: str, language: str) -> list[BreakPoint]:
    if not TREE_SITTER_AVAILABLE:
        return []
    lang_map: dict[str, object] = {}
    try:
        lang_map["python"] = tree_sitter_python.language()
        lang_map["javascript"] = tree_sitter_javascript.language()
        lang_map["typescript"] = tree_sitter_typescript.language_typescript()
        lang_map["tsx"] = tree_sitter_typescript.language_tsx()
        lang_map["go"] = tree_sitter_go.language()
        lang_map["rust"] = tree_sitter_rust.language()
    except Exception:
        return []
    lang_obj = lang_map.get(language)
    if lang_obj is None:
        return []
    try:
        parser = Parser(Language(lang_obj))
    except Exception:
        return []
    tree = parser.parse(text.encode("utf-8"))
    breakpoints: list[BreakPoint] = []
    lines = text.split("\n")

    def _walk(node: object) -> None:
        node_type = getattr(node, "type", "")
        start_point = getattr(node, "start_point", None)
        if node_type in AST_SCORES and start_point is not None:
            row = getattr(start_point, "row", 0)
            offset = sum(len(lines[r]) + 1 for r in range(row))
            breakpoints.append(
                BreakPoint(offset=offset, line=row, score=AST_SCORES[node_type], source=f"ast:{node_type}")
            )
        children = getattr(node, "children", [])
        for child in children:
            _walk(child)

    _walk(tree.root_node)
    return breakpoints


def merge_breakpoints(regex_bps: list[BreakPoint], ast_bps: list[BreakPoint]) -> list[BreakPoint]:
    by_line: dict[int, BreakPoint] = {}
    for bp in regex_bps:
        by_line[bp.line] = bp
    for bp in ast_bps:
        if bp.line in by_line:
            existing = by_line[bp.line]
            if bp.score > existing.score:
                by_line[bp.line] = bp
        else:
            by_line[bp.line] = bp
    return sorted(by_line.values(), key=lambda b: b.offset)


def apply_distance_decay(bps: list[BreakPoint], window: int) -> list[BreakPoint]:
    if not bps:
        return []
    window_chars = window * CHARS_PER_TOKEN
    result: list[BreakPoint] = []
    for bp in bps:
        dist = bp.offset
        if dist <= window_chars:
            decay = 1.0 - (dist / window_chars) ** 2 * 0.7
        else:
            decay = 0.3
        result.append(BreakPoint(offset=bp.offset, line=bp.line, score=bp.score * decay, source=bp.source))
    return result


def _find_best_split(
    text: str, start: int, target_end: int, breakpoints: list[BreakPoint], search_start: int, search_end: int
) -> int:
    best_pos = target_end
    best_score = -1.0
    for bp in breakpoints:
        if bp.offset < search_start or bp.offset > search_end:
            continue
        if bp.score > best_score:
            best_score = bp.score
            best_pos = bp.offset
    if best_score <= 0:
        for i in range(min(search_end, len(text)) - 1, max(search_start, start), -1):
            if text[i] in ("\n", "。", "！", "？", ".", "!", "?"):
                return i + 1
    return best_pos


def chunk_text(
    text: str,
    target_tokens: int = TARGET_TOKENS,
    overlap_ratio: float = OVERLAP_RATIO,
    search_window_tokens: int = SEARCH_WINDOW_TOKENS,
    language: str = "",
) -> ChunkResult:
    if not text.strip():
        return ChunkResult()
    regex_bps = find_regex_breakpoints(text)
    ast_bps = find_ast_breakpoints(text, language) if language else []
    merged = merge_breakpoints(regex_bps, ast_bps)
    decayed = apply_distance_decay(merged, search_window_tokens)
    target_chars = target_tokens * CHARS_PER_TOKEN
    overlap_chars = int(target_chars * overlap_ratio)
    search_chars = search_window_tokens * CHARS_PER_TOKEN
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    while start < len(text):
        ideal_end = start + target_chars
        if ideal_end >= len(text):
            chunk_content = text[start:]
            tokens = _estimate_tokens(chunk_content)
            line_start = sum(1 for _ in range(start)) if start == 0 else text[:start].count("\n")
            line_end = text.count("\n")
            chunks.append(
                Chunk(
                    index=idx,
                    content=chunk_content,
                    offset_start=start,
                    offset_end=len(text),
                    line_start=line_start,
                    line_end=line_end,
                    token_count=tokens,
                )
            )
            break
        search_start = max(start, ideal_end - search_chars)
        search_end = min(len(text), ideal_end + search_chars)
        split_pos = _find_best_split(text, start, ideal_end, decayed, search_start, search_end)
        chunk_content = text[start:split_pos]
        tokens = _estimate_tokens(chunk_content)
        line_start = text[:start].count("\n") if start > 0 else 0
        line_end = text[:split_pos].count("\n")
        bp_source = ""
        for bp in decayed:
            if bp.offset == split_pos:
                bp_source = bp.source
                break
        chunks.append(
            Chunk(
                index=idx,
                content=chunk_content,
                offset_start=start,
                offset_end=split_pos,
                line_start=line_start,
                line_end=line_end,
                token_count=tokens,
                break_source=bp_source,
            )
        )
        idx += 1
        overlap_start = max(start, split_pos - overlap_chars)
        for nl_pos in range(overlap_start, split_pos):
            if text[nl_pos] == "\n":
                overlap_start = nl_pos + 1
                break
        start = overlap_start
    total_tokens = sum(c.token_count for c in chunks)
    return ChunkResult(chunks=chunks, total_tokens=total_tokens, break_points=decayed)
