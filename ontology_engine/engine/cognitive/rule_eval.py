"""Safe expression evaluator for belief revision rules.

Replaces ``eval()`` calls in ``_apply_belief_revision_rules()`` with
an AST-based evaluator that only supports a whitelist of operators
and variable names — preventing code injection.

Usage::

    from ontology_engine.engine.cognitive.rule_eval import safe_eval

    context = {"confidence": 0.85, "feedback_weight": -0.3}
    result = safe_eval("confidence > 0.5 and feedback_weight < 0", context)
    # → True
"""

from __future__ import annotations

import ast
from typing import Any

# ---------------------------------------------------------------------------
# Whitelists
# ---------------------------------------------------------------------------

ALLOWED_OPS = frozenset({
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.Pow,
    ast.And,
    ast.Or,
    ast.Not,
    ast.USub,
    ast.UAdd,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
})

ALLOWED_CONST_TYPES = frozenset({bool, int, float, str, type(None)})

ALLOWED_VARIABLES = frozenset({
    "confidence",
    "feedback_weight",
    "evidence_count",
    "is_newer",
    "schema_alignment",
    "source",
    "belief_status",
})


# ---------------------------------------------------------------------------
# AST validator
# ---------------------------------------------------------------------------


def _validate_node(node: ast.AST, context_keys: frozenset[str]) -> None:
    """Recursively validate an AST node against the whitelist.

    Raises ``ValueError`` if any disallowed construct is found.
    """
    if isinstance(node, ast.Expression):
        _validate_node(node.body, context_keys)
        return

    if isinstance(node, ast.BoolOp):
        for op in node.op,:
            if type(op) not in ALLOWED_OPS:  # type: ignore[arg-type]
                raise ValueError(f"Disallowed boolean operator: {type(op).__name__}")
        for child in node.values:
            _validate_node(child, context_keys)
        return

    if isinstance(node, ast.BinOp):
        if type(node.op) not in ALLOWED_OPS:
            raise ValueError(f"Disallowed binary operator: {type(node.op).__name__}")
        _validate_node(node.left, context_keys)
        _validate_node(node.right, context_keys)
        return

    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in ALLOWED_OPS:
            raise ValueError(f"Disallowed unary operator: {type(node.op).__name__}")
        _validate_node(node.operand, context_keys)
        return

    if isinstance(node, ast.Compare):
        for op in node.ops:
            if type(op) not in ALLOWED_OPS:
                raise ValueError(f"Disallowed comparison operator: {type(op).__name__}")
        _validate_node(node.left, context_keys)
        for comparator in node.comparators:
            _validate_node(comparator, context_keys)
        return

    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        for elt in node.elts:
            _validate_node(elt, context_keys)
        return

    if isinstance(node, ast.Name):
        if node.id not in context_keys:
            raise ValueError(
                f"Variable {node.id!r} is not in the allowed set. "
                f"Allowed: {sorted(context_keys)}"
            )
        return

    if isinstance(node, ast.Constant):
        if type(node.value) not in ALLOWED_CONST_TYPES:
            raise ValueError(
                f"Disallowed constant type: {type(node.value).__name__}"
            )
        return

    raise ValueError(
        f"Disallowed AST node: {type(node).__name__}"
    )


def safe_eval(expression: str, context: dict[str, Any]) -> bool:
    """Evaluate a safe boolean expression.

    Args:
        expression: A Python expression string (e.g. ``"confidence > 0.5"``).
        context: Variable name → value mapping. Only keys in
            :data:`ALLOWED_VARIABLES` are permitted.

    Returns:
        The boolean result of evaluating the expression.

    Raises:
        ValueError: If the expression uses disallowed syntax or variables.
        ZeroDivisionError: If division by zero occurs at runtime.
        TypeError: If operand types are incompatible.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Expression syntax error: {exc}") from exc

    allowed_keys = frozenset(context.keys()) & ALLOWED_VARIABLES
    _validate_node(tree, allowed_keys)

    # Build a restricted evaluation environment
    restricted_globals: dict[str, Any] = {
        "True": True,
        "False": False,
        "None": None,
    }

    try:
        result = eval(  # pylint: disable=eval-used
            compile(tree, "<safe_eval>", "eval"),
            restricted_globals,
            context,
        )
    except ZeroDivisionError:
        raise
    except TypeError:
        raise
    except Exception as exc:
        raise ValueError(f"Expression evaluation error: {exc}") from exc

    if not isinstance(result, bool):
        raise ValueError(
            f"Expression did not evaluate to bool, got {type(result).__name__}: {result!r}"
        )
    return result
