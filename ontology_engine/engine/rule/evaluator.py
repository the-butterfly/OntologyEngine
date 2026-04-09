"""Simple expression evaluator for rule conditions."""
from __future__ import annotations
import re
from datetime import date, datetime
from typing import Any


class ExpressionSyntaxError(Exception):
    """Invalid expression syntax"""
    pass


class ExpressionEvaluator:
    """Simple expression evaluator for rule conditions."""

    # Known function names that should not be replaced as field references
    _KNOWN_FUNCTIONS = frozenset(["today", "days_between"])
    # Boolean literals
    _BOOLEAN_LITERALS = frozenset(["true", "false"])

    def evaluate(self, condition: str | list | dict | None | object, context: dict[str, Any]) -> Any:
        """Evaluate a condition against context.

        Args:
            condition: Can be:
                - Expression string like "status == 'ACTIVE'"
                - List of conditions for allOf/anyOf
                - Dict with allOf/anyOf keys
                - None (always True)
            context: Dict with entity data and computed metrics

        Returns:
            Boolean or other value depending on condition
        """
        if condition is None:
            return True

        # Handle objects with expression attribute (like RuleWhen Pydantic models)
        if hasattr(condition, "expression"):
            # Extract expression from the object
            expr = getattr(condition, "expression")
            if expr is not None:
                return self._evaluate_expression(expr, context)
            # If expression is None, check for allOf/anyOf
            if hasattr(condition, "allOf") and condition.allOf:
                return self.evaluate_allOf(condition.allOf, context)
            if hasattr(condition, "anyOf") and condition.anyOf:
                return self.evaluate_anyOf(condition.anyOf, context)
            return True

        # Handle allOf/anyOf structure (dict form)
        if isinstance(condition, dict):
            if "allOf" in condition:
                return self.evaluate_allOf(condition["allOf"], context)
            if "anyOf" in condition:
                return self.evaluate_anyOf(condition["anyOf"], context)
            if "expression" in condition:
                return self._evaluate_expression(condition["expression"], context)

        # Handle list of conditions
        if isinstance(condition, list):
            # If list contains dicts with expressions, treat as allOf
            if all(isinstance(c, dict) for c in condition):
                return self.evaluate_allOf(condition, context)
            # Otherwise evaluate each and return all results
            return [self._evaluate_expression(str(c), context) for c in condition]

        # Handle string expression
        if isinstance(condition, str):
            return self._evaluate_expression(condition, context)

        return True

    def evaluate_allOf(self, conditions: list, context: dict[str, Any]) -> bool:
        """Evaluate allOf - all conditions must be true."""
        for cond in conditions:
            if isinstance(cond, dict) and "expression" in cond:
                result = self._evaluate_expression(cond["expression"], context)
                if not result:
                    return False
            else:
                result = self.evaluate(cond, context)
                if not result:
                    return False
        return True

    def evaluate_anyOf(self, conditions: list, context: dict[str, Any]) -> bool:
        """Evaluate anyOf - at least one condition must be true."""
        for cond in conditions:
            if isinstance(cond, dict) and "expression" in cond:
                result = self._evaluate_expression(cond["expression"], context)
                if result:
                    return True
            else:
                result = self.evaluate(cond, context)
                if result:
                    return True
        return False

    def _evaluate_expression(self, expression: str, context: dict[str, Any]) -> Any:
        """Evaluate a single expression string."""
        if not expression or not expression.strip():
            return True

        # Replace field references with context values
        expr = self._resolve_fields(expression, context)

        # Handle special functions
        expr = self._resolve_functions(expr)

        # Evaluate comparison operators
        return self._eval_comparison(expr)

    # Reserved words that should not be replaced as field references
    _RESERVED_WORDS = frozenset([
        "true", "false", "and", "or", "not",
        "in", "is", "none", "null",
    ]) | _KNOWN_FUNCTIONS

    def _find_string_ranges(self, expr: str) -> list[tuple[int, int]]:
        """Find all string literal ranges (start, end exclusive) in expression."""
        ranges = []
        i = 0
        while i < len(expr):
            if expr[i] in ('"', "'"):
                quote = expr[i]
                start = i
                i += 1
                while i < len(expr):
                    if expr[i] == '\\' and i + 1 < len(expr):
                        i += 2  # Skip escaped character
                    elif expr[i] == quote:
                        ranges.append((start, i + 1))
                        i += 1
                        break
                    else:
                        i += 1
            else:
                i += 1
        return ranges

    def _is_inside_string(self, pos: int, string_ranges: list[tuple[int, int]]) -> bool:
        """Check if position is inside any string literal range."""
        for start, end in string_ranges:
            if start <= pos < end:
                return True
        return False

    def _split_outside_strings(self, expr: str, sep: str) -> list[str]:
        """Split expression by separator only outside string literals."""
        string_ranges = self._find_string_ranges(expr)
        parts: list[str] = []
        current: list[str] = []
        i = 0
        while i < len(expr):
            # Check if we're at the separator and not in a string
            if expr[i:].upper().startswith(sep.upper()) and not self._is_inside_string(i, string_ranges):
                parts.append(''.join(current))
                current = []
                i += len(sep)
            else:
                current.append(expr[i])
                i += 1
        parts.append(''.join(current))
        return parts

    def _resolve_fields(self, expr: str, context: dict[str, Any]) -> str:
        """Replace field references like 'status' or 'supplier.status' with values."""
        pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\b'
        string_ranges = self._find_string_ranges(expr)

        def replace_field(match):
            field_path = match.group(1)

            # Skip if inside a string literal
            if self._is_inside_string(match.start(), string_ranges):
                return match.group(0)

            # Skip reserved words
            if field_path.lower() in self._RESERVED_WORDS:
                return match.group(0)

            # Resolve nested field
            value = self._get_nested(context, field_path)
            if value is None:
                return "None"
            elif isinstance(value, bool):
                return "true" if value else "false"
            elif isinstance(value, str):
                return f"'{value}'"
            else:
                return str(value)

        return re.sub(pattern, replace_field, expr)

    def _get_nested(self, data: dict, path: str) -> Any:
        """Get nested value from dict using dot notation."""
        keys = path.split(".")
        value: Any = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _resolve_functions(self, expr: str) -> str:
        """Replace function calls with actual values."""
        # Handle today()
        expr = re.sub(r'\btoday\(\)', str(date.today()), expr)

        # Handle days_between(d1, d2)
        def replace_days_between(match):
            args = match.group(1)
            # Simple parsing - expect 'date1, date2'
            parts = [a.strip() for a in args.split(",")]
            if len(parts) == 2:
                d1 = self._parse_date(parts[0])
                d2 = self._parse_date(parts[1])
                if d1 and d2:
                    return str(abs((d2 - d1).days))
            return "0"

        expr = re.sub(r'days_between\(([^)]+)\)', replace_days_between, expr)
        return expr

    def _parse_date(self, s: str) -> date | None:
        """Parse date from string or return None."""
        s = s.strip().strip("'\"")
        for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"]:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    def _eval_comparison(self, expr: str) -> Any:
        """Evaluate comparison expression."""
        expr = expr.strip()

        # Handle OR first (lowest precedence)
        if " OR " in expr.upper():
            parts = self._split_outside_strings(expr, " OR ")
            # Only recurse if split actually produced multiple parts
            if len(parts) > 1:
                for part in parts:
                    result = self._eval_comparison(part.strip())
                    if result:
                        return True
                return False
            # If only 1 part, separator was inside strings - fall through

        # Handle AND (higher precedence than OR)
        if " AND " in expr.upper():
            parts = self._split_outside_strings(expr, " AND ")
            # Only recurse if split actually produced multiple parts
            if len(parts) > 1:
                for part in parts:
                    result = self._eval_comparison(part.strip())
                    if not result:
                        return False
                return True
            # If only 1 part, separator was inside strings - fall through

        # Handle NOT
        if expr.upper().startswith("NOT "):
            operand = expr[4:].strip()
            return not self._eval_comparison(operand)

        # Handle IS NULL / IS NOT NULL (before other operators to avoid misparsing)
        # Must check longer pattern first to avoid splitting "IS NOT NULL" on "IS"
        if " IS NOT NULL" in expr.upper():
            # field IS NOT NULL -> check if field value is not None
            parts = expr.rsplit(" IS NOT NULL", 1)
            if len(parts) == 2:
                field_name = parts[0].strip()
                # After _resolve_fields, None values become "None" string
                return field_name != "None"

        if " IS NULL" in expr.upper():
            # field IS NULL -> check if field value is None
            parts = expr.rsplit(" IS NULL", 1)
            if len(parts) == 2:
                field_name = parts[0].strip()
                return field_name == "None"

        # Replace Python comparison operators with safe equivalents
        # Handle: ==, !=, >=, <=, >, <

        # First, handle simple equality with strings
        # Pattern: 'ACTIVE' == status -> evaluate both sides
        if "==" in expr:
            parts = expr.split("==", 1)
            if len(parts) == 2:
                left, right = parts[0].strip(), parts[1].strip()
                return self._compare_eq(left, right)

        if "!=" in expr:
            parts = expr.split("!=", 1)
            if len(parts) == 2:
                left, right = parts[0].strip(), parts[1].strip()
                return not self._compare_eq(left, right)

        if ">=" in expr:
            parts = expr.split(">=", 1)
            if len(parts) == 2:
                try:
                    return float(parts[0].strip()) >= float(parts[1].strip())
                except ValueError:
                    return False

        if "<=" in expr:
            parts = expr.split("<=", 1)
            if len(parts) == 2:
                try:
                    return float(parts[0].strip()) <= float(parts[1].strip())
                except ValueError:
                    return False

        if ">" in expr:
            parts = expr.split(">", 1)
            if len(parts) == 2:
                try:
                    return float(parts[0].strip()) > float(parts[1].strip())
                except ValueError:
                    return False

        if "<" in expr:
            parts = expr.split("<", 1)
            if len(parts) == 2:
                try:
                    return float(parts[0].strip()) < float(parts[1].strip())
                except ValueError:
                    return False

        # If no operators, evaluate as boolean
        # Handle "true" and "false" strings
        if expr.lower() == "true":
            return True
        if expr.lower() == "false":
            return False

        return bool(expr)

    def _compare_eq(self, left: str, right: str) -> bool:
        """Compare two values for equality."""
        # Remove quotes from strings (caller already strips whitespace)
        left = left.strip("'\"")
        right = right.strip("'\"")

        # If either side is "None" (missing field), comparison is False
        # A missing field does not equal any value (including another missing field)
        if left == "None" or right == "None":
            return False

        # Try numeric comparison
        try:
            return float(left) == float(right)
        except ValueError:
            return left == right
