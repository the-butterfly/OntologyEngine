"""L0/L1 expression engine with automatic executor selection."""

from __future__ import annotations

import ast
import math
import re
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import simpleeval

from ontology_engine.engine.expression.errors import (
    FormulaError,
    FormulaNameError,
    FormulaSyntaxError,
    FormulaTypeError,
)
from ontology_engine.engine.expression.l1_executor import ASTSandboxExecutor


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


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _days_between(start: Any, end: Any) -> int:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if start_date is None or end_date is None:
        return 0
    return abs((end_date - start_date).days)


def _days_since(start: Any) -> int:
    start_date = _parse_date(start)
    if start_date is None:
        return 0
    return abs((date.today() - start_date).days)


def _date_diff(start: Any, end: Any, unit: str = "day") -> int:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if start_date is None or end_date is None:
        return 0
    if unit == "month":
        months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        if (end_date.day < start_date.day) and months != 0:
            months -= 1
        return abs(months)
    if unit == "year":
        years = end_date.year - start_date.year
        if (end_date.month < start_date.month) or (
            end_date.month == start_date.month and end_date.day < start_date.day
        ):
            if years != 0:
                years -= 1
        return abs(years)
    return abs((end_date - start_date).days)


def _date_add(date_val: Any, amount: int, unit: str = "day") -> str:
    d = _parse_date(date_val)
    if d is None:
        return ""
    if unit == "day":
        result = d + timedelta(days=amount)
    elif unit == "month":
        # Handle cross-year month overflow correctly.
        # d.replace(month=d.month + amount) raises ValueError when the result
        # is outside [1, 12].  We use calendar arithmetic instead.
        total_months = d.year * 12 + (d.month - 1) + amount
        new_year, new_month_0 = divmod(total_months, 12)
        new_month = new_month_0 + 1  # convert back to 1-based month
        # Clamp day to valid range for the target month (e.g. Jan 31 + 1 month → Feb 28/29)
        import calendar as _calendar
        max_day = _calendar.monthrange(new_year, new_month)[1]
        new_day = min(d.day, max_day)
        result = d.replace(year=new_year, month=new_month, day=new_day)
    elif unit == "year":
        # Guard against Feb 29 on non-leap years
        try:
            result = d.replace(year=d.year + amount)
        except ValueError:
            # e.g. 2024-02-29 + 1 year: clamp to Feb 28
            result = d.replace(year=d.year + amount, day=28)
    else:
        result = d + timedelta(days=amount)
    return result.isoformat()


def _year(date_val: Any) -> int:
    d = _parse_date(date_val)
    return d.year if d else 0


def _month(date_val: Any) -> int:
    d = _parse_date(date_val)
    return d.month if d else 0


def _day(date_val: Any) -> int:
    d = _parse_date(date_val)
    return d.day if d else 0


def _is_null(value: Any) -> bool:
    return value is None


def _coalesce(*values: Any) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


def _if_expr(condition: bool, then_value: Any, else_value: Any) -> Any:
    return then_value if condition else else_value


def _clamp(value: Any, min_val: Any, max_val: Any) -> Any:
    if value is None or min_val is None or max_val is None:
        return value
    try:
        return max(min_val, min(max_val, value))
    except (TypeError, ValueError):
        return value


def _len(s: Any) -> int:
    if s is None:
        return 0
    try:
        return len(s)
    except TypeError:
        return 0


def _upper(s: Any) -> str:
    if s is None:
        return ""
    return str(s).upper()


def _lower(s: Any) -> str:
    if s is None:
        return ""
    return str(s).lower()


def _trim(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def _replace(s: Any, old: Any, new: Any) -> str:
    if s is None or old is None:
        return str(s) if s is not None else ""
    return str(s).replace(str(old), str(new))


def _substring(s: Any, start: int, length: int | None = None) -> str:
    text = str(s) if s is not None else ""
    if length is None:
        return text[start:]
    return text[start:start + length]


def _contains(s: Any, substr: Any) -> bool:
    if s is None or substr is None:
        return False
    return str(substr) in str(s)


def _starts_with(s: Any, prefix: Any) -> bool:
    if s is None or prefix is None:
        return False
    return str(s).startswith(str(prefix))


def _ends_with(s: Any, suffix: Any) -> bool:
    if s is None or suffix is None:
        return False
    return str(s).endswith(str(suffix))


def _split(s: Any, delimiter: Any) -> list[str]:
    if s is None:
        return []
    return str(s).split(str(delimiter))


def _join(parts: Any, delimiter: Any) -> str:
    if parts is None:
        return ""
    return str(delimiter).join(str(p) for p in parts)


def _to_string(x: Any) -> str:
    if x is None:
        return ""
    return str(x)


def _to_decimal(x: Any) -> Decimal:
    """Convert a value to decimal.Decimal for high-precision financial calculations.

    Special value handling:
    - None → Decimal("0")
    - inf / -inf → propagated as Decimal("Infinity") / Decimal("-Infinity")
    - NaN float → Decimal("0") (treat as missing/invalid)
    - Conversion failure → Decimal("0")
    """
    if x is None:
        return Decimal(0)
    if isinstance(x, Decimal):
        return x
    if isinstance(x, float):
        if math.isnan(x):
            return Decimal(0)
        if math.isinf(x):
            return Decimal("Infinity") if x > 0 else Decimal("-Infinity")
        # Use string conversion to avoid float representation errors:
        # Decimal(0.1) != Decimal("0.1"), but str(0.1) = "0.1" in Python >= 3.1
        return Decimal(str(x))
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


def _sum(values: Any) -> Any:
    if values is None:
        return 0
    try:
        items = list(values)
        if not items:
            return 0
        if any(isinstance(v, Decimal) for v in items):
            return sum(items, Decimal(0))
        return sum(items)
    except (TypeError, ValueError):
        return 0


def _avg(values: Any) -> float:
    if values is None:
        return 0.0
    try:
        items = list(values)
        if not items:
            return 0.0
        return sum(items) / len(items)
    except (TypeError, ValueError):
        return 0.0


def _count(values: Any) -> int:
    if values is None:
        return 0
    try:
        return sum(1 for v in values if v is not None)
    except (TypeError, ValueError):
        return 0


def _weighted_sum(components: Any, weights: Any) -> float:
    if components is None or weights is None:
        return 0.0
    try:
        c_list = list(components)
        w_list = list(weights)
        if len(c_list) != len(w_list):
            return 0.0
        return sum(c * w for c, w in zip(c_list, w_list))
    except (TypeError, ValueError):
        return 0.0


def _ceil(x: Any) -> int:
    if x is None:
        return 0
    try:
        return math.ceil(float(x))
    except (TypeError, ValueError):
        return 0


def _floor(x: Any) -> int:
    if x is None:
        return 0
    try:
        return math.floor(float(x))
    except (TypeError, ValueError):
        return 0


def _sqrt(x: Any) -> float:
    if x is None:
        return 0.0
    try:
        return math.sqrt(float(x))
    except (TypeError, ValueError):
        return 0.0


def _pow(base: Any, exp: Any) -> float:
    if base is None or exp is None:
        return 0.0
    try:
        return float(base) ** float(exp)
    except (TypeError, ValueError):
        return 0.0


def _log(x: Any, base: float | None = None) -> float:
    if x is None:
        return 0.0
    try:
        val = math.log(float(x)) if base is None else math.log(float(x), base)
        return float(val)
    except (TypeError, ValueError):
        return 0.0


_FUNCTION_NAMES = frozenset({
    "today", "now",
    "days_between", "days_since", "date_diff", "date_add",
    "year", "month", "day",
    "is_null", "coalesce", "if_expr",
    "clamp",
    "max", "min", "round", "abs",
    "int", "float", "bool", "str",
    "len", "upper", "lower", "trim",
    "replace", "substring",
    "contains", "starts_with", "ends_with",
    "split", "join",
    "to_string", "to_decimal",
    "sum", "avg", "count", "weighted_sum",
    "ceil", "floor", "sqrt", "pow", "log",
})

_SAFE_FUNCTIONS_MAP: dict[str, Any] = {
    "today": _today,
    "now": _now,
    "days_between": _days_between,
    "days_since": _days_since,
    "date_diff": _date_diff,
    "date_add": _date_add,
    "year": _year,
    "month": _month,
    "day": _day,
    "is_null": _is_null,
    "coalesce": _coalesce,
    "if_expr": _if_expr,
    "clamp": _clamp,
    "max": max,
    "min": min,
    "round": round,
    "abs": abs,
    "int": int,
    "float": float,
    "bool": bool,
    "str": _to_string,
    "len": _len,
    "upper": _upper,
    "lower": _lower,
    "trim": _trim,
    "replace": _replace,
    "substring": _substring,
    "contains": _contains,
    "starts_with": _starts_with,
    "ends_with": _ends_with,
    "split": _split,
    "join": _join,
    "to_string": _to_string,
    "to_decimal": _to_decimal,
    "sum": _sum,
    "avg": _avg,
    "count": _count,
    "weighted_sum": _weighted_sum,
    "ceil": _ceil,
    "floor": _floor,
    "sqrt": _sqrt,
    "pow": _pow,
    "log": _log,
}


ExpressionSyntaxError = FormulaSyntaxError


class ExpressionEngine:
    """Evaluate formulas with L0 (SimpleEval) / L1 (ASTSandbox) auto-selection."""

    CONTROL_FLOW_KEYWORDS = frozenset({"if", "for", "while", "def", "class", "try", "with"})

    SAFE_FUNCTIONS: dict[str, Any] = _SAFE_FUNCTIONS_MAP

    _RESERVED_WORDS = frozenset(
        {"True", "False", "None", "and", "or", "not", "in", "is"}
        | _FUNCTION_NAMES
    )
    _FIELD_PATTERN = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\b")

    def __init__(self) -> None:
        self._l1_executor = ASTSandboxExecutor()

    def evaluate(
        self,
        expression: str | None,
        context: Mapping[str, Any] | None = None,
    ) -> Any:
        if expression is None or not expression.strip():
            return True

        eval_context = context or {}

        normalized = self._normalize_keywords(expression)

        executor = self._select_executor(expression)

        try:
            if executor == "l0":
                prepared = self._resolve_fields(normalized, eval_context)
                return self._evaluate_l0(prepared, eval_context)
            else:
                return self._evaluate_l1(normalized, eval_context)
        except FormulaError:
            raise
        except SyntaxError as exc:
            raise FormulaSyntaxError(
                f"Invalid expression '{expression}': {exc}"
            ) from exc
        except TypeError as exc:
            raise FormulaTypeError(
                f"Type error in expression '{expression}': {exc}"
            ) from exc
        except NameError as exc:
            raise FormulaNameError(
                f"Undefined name in expression '{expression}': {exc}"
            ) from exc
        except Exception as exc:
            raise ExpressionSyntaxError(
                f"Invalid expression '{expression}': {exc}"
            ) from exc

    def _select_executor(self, expression: str) -> str:
        if "\n" in expression or "\r" in expression:
            return "l1"
        tokens = set(self._tokenize(expression))
        if tokens & self.CONTROL_FLOW_KEYWORDS:
            return "l1"
        if "[" in expression:
            return "l1"
        return "l0"

    @staticmethod
    def _tokenize(expression: str) -> set[str]:
        return set(re.findall(r"\b[a-zA-Z_]\w*\b", expression))

    def _evaluate_l0(self, prepared: str, context: Mapping[str, Any]) -> Any:
        evaluator = self._create_simpleeval(context)
        try:
            return evaluator.eval(prepared)
        except (simpleeval.FunctionNotDefined, simpleeval.NameNotDefined):
            return self._l1_executor.evaluate(prepared, context, self.SAFE_FUNCTIONS)
        except simpleeval.InvalidExpression as exc:
            raise FormulaSyntaxError(str(exc)) from exc
        except TypeError as exc:
            raise FormulaTypeError(str(exc)) from exc

    def _evaluate_l1(self, expression: str, context: Mapping[str, Any]) -> Any:
        return self._l1_executor.evaluate(expression, context, self.SAFE_FUNCTIONS)

    def _create_simpleeval(self, context: Mapping[str, Any]) -> simpleeval.SimpleEval:
        evaluator = simpleeval.SimpleEval()
        unsafe_nodes = {
            ast.LShift,
            ast.RShift,
            ast.BitAnd,
            ast.BitOr,
            ast.BitXor,
            ast.Mod,
        }
        for node in unsafe_nodes:
            evaluator.operators.pop(node, None)
        evaluator.functions.update(self.SAFE_FUNCTIONS)
        evaluator.names.update(context)
        return evaluator

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
