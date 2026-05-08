"""Chinese text tokenizer for BM25 with dual backend support.

Supports:
- jieba: Dictionary-based Chinese word segmentation
- fts5_icu: Emulates SQLite FTS5 ICU tokenizer behavior (overlapping bigrams)
- character: Character n-gram fallback (always available)

Design decision (2026-05-06):
- Both backends supported as options, default to jieba if available.
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar

logger = logging.getLogger(__name__)

_CJK_RANGE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]", re.UNICODE)
_LATIN_RANGE = re.compile(r"[a-zA-Z0-9]+", re.UNICODE)


class ChineseTokenizer:
    """Chinese text tokenizer with multiple backend options."""

    JIEBA: ClassVar[str] = "jieba"
    FTS5_ICU: ClassVar[str] = "fts5_icu"
    CHARACTER: ClassVar[str] = "character"

    def __init__(self, backend: str | None = None):
        if backend is None:
            backend = self.JIEBA if self.is_jieba_available() else self.CHARACTER
        self._backend = backend
        self._jieba_instance = None
        if backend == self.JIEBA:
            self._init_jieba()

    @property
    def backend(self) -> str:
        return self._backend

    def _init_jieba(self):
        try:
            import jieba
            self._jieba_instance = jieba
        except ImportError:
            logger.warning("jieba not installed, falling back to character tokenizer")
            self._backend = self.CHARACTER

    @staticmethod
    def is_jieba_available() -> bool:
        try:
            import jieba  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def is_chinese_text(text: str) -> bool:
        return bool(_CJK_RANGE.search(text))

    @staticmethod
    def has_chinese(content: str) -> bool:
        return bool(_CJK_RANGE.search(content))

    def tokenize(self, text: str) -> list[str]:
        if self._backend == self.JIEBA and self._jieba_instance is not None:
            return self._tokenize_jieba(text)
        elif self._backend == self.FTS5_ICU:
            return self._tokenize_fts5_icu(text)
        else:
            return self._tokenize_character(text)

    def _tokenize_jieba(self, text: str) -> list[str]:
        if self._jieba_instance is None:
            return self._tokenize_character(text)
        tokens: list[str] = []
        latin_parts = _LATIN_RANGE.split(text)
        latin_matches = _LATIN_RANGE.findall(text)
        idx = 0
        for part in latin_parts:
            if self.has_chinese(part):
                segs = list(self._jieba_instance.cut(part))
                tokens.extend(s for s in segs if s.strip())
            idx += 1
        for match in latin_matches:
            tokens.append(match)
        return tokens

    @staticmethod
    def _tokenize_fts5_icu(text: str) -> list[str]:
        tokens: list[str] = []
        latin_parts = _LATIN_RANGE.split(text)
        latin_matches = _LATIN_RANGE.findall(text)
        for part in latin_parts:
            if _CJK_RANGE.search(part):
                cjk_only = "".join(_CJK_RANGE.findall(part))
                for i in range(len(cjk_only) - 1):
                    tokens.append(cjk_only[i:i + 2])
                if len(cjk_only) == 1:
                    tokens.append(cjk_only)
        for match in latin_matches:
            tokens.append(match.lower())
        return tokens

    @staticmethod
    def _tokenize_character(text: str) -> list[str]:
        tokens: list[str] = []
        for ch in text:
            if ch.strip() and not ch.isspace():
                tokens.append(ch)
        latin_matches = _LATIN_RANGE.findall(text)
        for m in latin_matches:
            if len(m) > 1:
                tokens.append(m.lower())
        return tokens

    def tokenize_query(self, query: str) -> list[str]:
        """Tokenize a search query, returning unique tokens."""
        tokens = self.tokenize(query)
        seen: set[str] = set()
        unique: list[str] = []
        for t in tokens:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique.append(t)
        return unique


def tokenize_chinese(text: str, backend: str = "jieba") -> list[str]:
    """Convenience function for Chinese tokenization."""
    tokenizer = ChineseTokenizer(backend=backend)
    return tokenizer.tokenize(text)
