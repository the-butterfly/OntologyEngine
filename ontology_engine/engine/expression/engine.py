"""Shared safe expression engine built on top of simpleeval."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

import simpleeval


class ExpressionSyntaxError(Exception):
    """Raised when an expression cannot be parsed or evaluated safely."""


class ExpressionEngine:
    """Evaluate formulas and rule conditions with consistent semantics."""

    _KNOWN_FUNCTIONS = frozenset(
        {
            "today",
            "days_between",
            "is_null",
            "max",
            "min",
            "round",
            "abs",
            "int",
            "float",
            "bool",
        }
    )
    _RESERVED_WORDS = frozenset(
        {"True", "False", "None", "and", "or", "not", "in", "is"}
    ) | _KNOWN_FUNCTIONS
    _FIELD_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\b")

    def evaluate(
        self,
        expression: str | None,
        context: Mapping[str, Any] | None = None,
    ) -> Any:
        """Evaluate one expression against a context."""
        if expression is None or not expression.strip():
            return True

        prepared = self._prepare_expression(expression, context or {})

        evaluator = simpleeval.SimpleEval()
        evaluator.functions.update(
            {
                "today": lambda: date.today().isoformat(),
                "days_between": self._days_between,
                "is_null": lambda value: value is None,
                "max": max,
                "min": min,
                "round": round,
                "abs": abs,
                "int": int,
                "float": float,
                "bool": bool,
            }
        )

        try:
            return evaluator.eval(prepared)
        except Exception as exc:  # noqa: BLE001
            raise ExpressionSyntaxError(f"Invalid expression '{expression}': {exc}") from exc

    def _prepare_expression(
        self,
        expression: str,
        context: Mapping[str, Any],
    ) -> str:
        normalized = self._normalize_keywords(expression)
        return self._resolve_fields(normalized, context)

    def _normalize_keywords(self, expression: str) -> str:
        replacements: list[tuple[re.Pattern[str], str]] = [
            (
                re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_\.]*)\s+IS\s+NOT\s+NULL\b", re.IGNORECASE),
                r"not is_null(\1)",
            ),
            (
                re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_\.]*)\s+IS\s+NULL\b", re.IGNORECASE),
                r"is_null(\1)",
            ),
            (re.compile(r"\bAND\b", re.IGNORECASE), "and"),
            (re.compile(r"\bOR\b", re.IGNORECASE), "or"),
            (re.compile(r"\bNOT\b", re.IGNORECASE), "not"),
            (re.compile(r"\btrue\b", re.IGNORECASE), "True"),
            (re.compile(r"\bfalse\b", re.IGNORECASE), "False"),
            (re.compile(r"\bnull\b", re.IGNORECASE), "None"),
            (re.compile(r"\bnone\b", re.IGNORECASE), "None"),
        ]

        return self._replace_outside_strings(expression, replacements)

    def _replace_outside_strings(
        self,
        expression: str,
        replacements: list[tuple[re.Pattern[str], str]],
    ) -> str:
        string_ranges = self._find_string_ranges(expression)
        if not string_ranges:
            return self._apply_replacements(expression, replacements)

        parts: list[str] = []
        cursor = 0
        for start, end in string_ranges:
            if cursor < start:
                parts.append(self._apply_replacements(expression[cursor:start], replacements))
            parts.append(expression[start:end])
            cursor = end
        if cursor < len(expression):
            parts.append(self._apply_replacements(expression[cursor:], replacements))
        return "".join(parts)

    @staticmethod
    def _apply_replacements(
        segment: str,
        replacements: list[tuple[re.Pattern[str], str]],
    ) -> str:
        for pattern, replacement in replacements:
            segment = pattern.sub(replacement, segment)
        return segment

    def _find_string_ranges(self, expr: str) -> list[tuple[int, int]]:
        ranges: list[tuple[int, int]] = []
        index = 0
        while index < len(expr):
            if expr[index] in ('"', "'"):
                quote = expr[index]
                start = index
                index += 1
                while index < len(expr):
                    if expr[index] == "\\" and index + 1 < len(expr):
                        index += 2
                        continue
                    if expr[index] == quote:
                        ranges.append((start, index + 1))
                        index += 1
                        break
                    index += 1
            else:
                index += 1
        return ranges

    def _resolve_fields(
        self,
        expression: str,
        context: Mapping[str, Any],
    ) -> str:
        string_ranges = self._find_string_ranges(expression)

        def replace_field(match: re.Match[str]) -> str:
            field_path = match.group(1)
            if self._is_inside_string(match.start(), string_ranges):
                return match.group(0)
            if field_path in self._RESERVED_WORDS:
                return match.group(0)
            if expression[match.end(): match.end() + 1] == "(":
                return match.group(0)
            value = self._get_nested(context, field_path)
            return self._to_literal(value)

        return self._FIELD_PATTERN.sub(replace_field, expression)

    @staticmethod
    def _is_inside_string(pos: int, ranges: list[tuple[int, int]]) -> bool:
        return any(start <= pos < end for start, end in ranges)

    def _get_nested(self, data: Mapping[str, Any], path: str) -> Any:
        value: Any = data
        for key in path.split("."):
            if isinstance(value, Mapping):
                value = value.get(key)
            else:
                return None
        return value

    @staticmethod
    def _to_literal(value: Any) -> str:
        if value is None:
            return "None"
        if isinstance(value, datetime):
            return repr(value.isoformat())
        if isinstance(value, date):
            return repr(value.isoformat())
        return repr(value)

    @staticmethod
    def _days_between(start: Any, end: Any) -> int:
        start_date = ExpressionEngine._parse_date(start)
        end_date = ExpressionEngine._parse_date(end)
        if start_date is None or end_date is None:
            return 0
        return abs((end_date - start_date).days)

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if value is None:
            return None
        raw = str(value).strip().strip("\"'")
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None
