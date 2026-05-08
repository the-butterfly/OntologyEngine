"""Tests for BM25 Chinese tokenization dual support.

TDD-5: Verify jieba, fts5_icu, and character tokenizers work correctly.
"""

from __future__ import annotations

import pytest

from ontology_engine.engine.cognitive.bm25_tokenizer import (
    ChineseTokenizer,
    tokenize_chinese,
)


class TestChineseTokenizerBasics:
    """Basic tokenizer functionality."""

    def test_character_tokenizer_default(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.CHARACTER)
        assert tokenizer.backend == ChineseTokenizer.CHARACTER

    def test_character_tokenize_simple(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.CHARACTER)
        tokens = tokenizer.tokenize("你好世界")
        assert "你" in tokens
        assert "好" in tokens
        assert "世" in tokens
        assert "界" in tokens

    def test_character_tokenize_mixed(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.CHARACTER)
        tokens = tokenizer.tokenize("Python编程")
        assert "P" in tokens
        assert "y" in tokens
        assert "python" in tokens  # whole word also extracted
        assert "编" in tokens
        assert "程" in tokens

    def test_character_tokenize_with_spaces(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.CHARACTER)
        tokens = tokenizer.tokenize("A B C")
        assert "A" in tokens
        assert "B" in tokens
        assert "C" in tokens

    def test_tokenizer_auto_selects_backend(self):
        tokenizer = ChineseTokenizer()
        assert tokenizer.backend in (
            ChineseTokenizer.JIEBA,
            ChineseTokenizer.CHARACTER,
        )

    def test_is_chinese_text(self):
        assert ChineseTokenizer.is_chinese_text("华信科技")
        assert ChineseTokenizer.is_chinese_text("Hello 华信")
        assert not ChineseTokenizer.is_chinese_text("Hello World")
        assert not ChineseTokenizer.is_chinese_text("12345")

    def test_has_chinese_mixed(self):
        assert ChineseTokenizer.has_chinese("Oracle数据库")
        assert not ChineseTokenizer.has_chinese("Oracle Database")


class TestFTS5ICUTokenizer:
    """FTS5 ICU-style overlapping bigram tokenization."""

    def test_fts5_icu_chinese_bigrams(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.FTS5_ICU)
        tokens = tokenizer.tokenize("华信科技")
        assert "华信" in tokens
        assert "信科" in tokens
        assert "科技" in tokens

    def test_fts5_icu_single_char(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.FTS5_ICU)
        tokens = tokenizer.tokenize("大")
        assert "大" in tokens

    def test_fts5_icu_mixed_text(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.FTS5_ICU)
        tokens = tokenizer.tokenize("使用Oracle数据库")
        assert "oracle" in tokens
        assert "使用" in tokens or "数据" in tokens or "据库" in tokens

    def test_fts5_icu_empty(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.FTS5_ICU)
        tokens = tokenizer.tokenize("")
        assert len(tokens) == 0


class TestJiebaTokenizer:
    """Jieba dictionary-based tokenization (if available)."""

    @pytest.fixture
    def jieba_tokenizer(self):
        if not ChineseTokenizer.is_jieba_available():
            pytest.skip("jieba not installed")
        return ChineseTokenizer(backend=ChineseTokenizer.JIEBA)

    def test_jieba_tokenize_chinese(self, jieba_tokenizer):
        tokens = jieba_tokenizer.tokenize("华信科技使用Oracle数据库")
        assert len(tokens) >= 2
        assert "Oracle" in tokens or "oracle" in tokens

    def test_jieba_tokenize_pure_chinese(self, jieba_tokenizer):
        tokens = jieba_tokenizer.tokenize("今天天气很好")
        assert len(tokens) >= 2

    def test_jieba_falls_back_when_unavailable(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.JIEBA)
        assert tokenizer.backend in (
            ChineseTokenizer.JIEBA,
            ChineseTokenizer.CHARACTER,
        )


class TestTokenizeQuery:
    """Query tokenization with deduplication."""

    def test_tokenize_query_removes_duplicates(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.CHARACTER)
        tokens = tokenizer.tokenize_query("你好你好")
        assert tokens.count("你") == 1
        assert tokens.count("好") == 1

    def test_tokenize_query_mixed_lowercase(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.FTS5_ICU)
        tokens = tokenizer.tokenize_query("Oracle oracle DB")
        assert tokens.count("oracle") == 1

    def test_tokenize_query_vs_tokenize(self):
        tokenizer = ChineseTokenizer(backend=ChineseTokenizer.CHARACTER)
        all_tokens = tokenizer.tokenize("aa bb aa")
        query_tokens = tokenizer.tokenize_query("aa bb aa")
        assert len(query_tokens) <= len(all_tokens)


class TestConvenienceFunction:
    """Test tokenize_chinese convenience function."""

    def test_tokenize_chinese_default(self):
        tokens = tokenize_chinese("测试文本")
        assert len(tokens) >= 2

    def test_tokenize_chinese_with_backend(self):
        tokens = tokenize_chinese("测试文本", backend=ChineseTokenizer.FTS5_ICU)
        assert len(tokens) >= 2

    def test_tokenize_chinese_character_backend(self):
        tokens = tokenize_chinese("测试", backend=ChineseTokenizer.CHARACTER)
        assert "测" in tokens
        assert "试" in tokens
