"""L1 ASTSandboxExecutor for complex expressions with control flow."""

from __future__ import annotations

import ast
import threading
from collections.abc import Mapping
from typing import Any

import asteval

from ontology_engine.engine.expression.errors import (
    FormulaSecurityError,
    FormulaSyntaxError,
    FormulaTimeoutError,
)

_ALLOWED_AST_NODES = frozenset(
    {
        ast.Module,
        ast.Expression,
        ast.Assign,
        ast.AugAssign,
        ast.Expr,
        ast.Return,
        ast.If,
        ast.For,
        ast.While,
        ast.Break,
        ast.Continue,
        ast.BoolOp,
        ast.BinOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Constant,
        ast.Name,
        ast.Attribute,
        ast.Subscript,
        ast.Call,
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Set,
        ast.Index,
        ast.Slice,
        ast.Load,
        ast.Store,
        ast.Del,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Not,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.And,
        ast.Or,
        ast.In,
        ast.NotIn,
        ast.Is,
        ast.IsNot,
    }
)


class ASTSandboxExecutor:
    """L1 executor: asteval + AST whitelist + resource limits."""

    CONTROL_FLOW_KEYWORDS = frozenset({"if", "for", "while", "def", "class", "try", "with"})

    def __init__(
        self,
        max_loop_iterations: int = 1000,
        timeout_seconds: int = 5,
        max_ast_depth: int = 20,
        max_assignments: int = 50,
    ) -> None:
        self._max_loop_iterations = max_loop_iterations
        self._timeout_seconds = timeout_seconds
        self._max_ast_depth = max_ast_depth
        self._max_assignments = max_assignments

    def evaluate(
        self,
        expression: str,
        context: Mapping[str, Any],
        safe_functions: Mapping[str, Any],
    ) -> Any:
        tree = self._parse(expression)
        self._validate_ast(tree)
        self._check_depth(tree)
        self._check_assignments(tree)
        return self._execute_with_limits(tree, expression, context, safe_functions)

    def _parse(self, expression: str) -> ast.AST:
        try:
            return ast.parse(expression)
        except SyntaxError as exc:
            raise FormulaSyntaxError(
                f"Invalid expression syntax: {exc}"
            ) from exc

    def _validate_ast(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if type(node) not in _ALLOWED_AST_NODES:
                raise FormulaSecurityError(
                    f"Disallowed AST node: {type(node).__name__}"
                )

    def _check_depth(self, tree: ast.AST) -> None:
        def _depth(node: ast.AST, current: int) -> int:
            children = list(ast.iter_child_nodes(node))
            if not children:
                return current
            return max(_depth(child, current + 1) for child in children)

        if _depth(tree, 0) > self._max_ast_depth:
            raise FormulaSecurityError(
                f"AST depth exceeds limit ({self._max_ast_depth})"
            )

    def _check_assignments(self, tree: ast.AST) -> None:
        count = sum(1 for node in ast.walk(tree) if isinstance(node, ast.Assign))
        if count > self._max_assignments:
            raise FormulaSecurityError(
                f"Too many assignments ({count} > {self._max_assignments})"
            )

    def _execute_with_limits(
        self,
        tree: ast.AST,
        expression: str,
        context: Mapping[str, Any],
        safe_functions: Mapping[str, Any],
    ) -> Any:
        interpreter = asteval.Interpreter()
        interpreter.symtable.update(safe_functions)
        interpreter.symtable.update(context)

        result_container: list[Any] = [None]
        error_container: list[Exception | None] = [None]

        def _run() -> None:
            try:
                result_container[0] = interpreter.eval(expression)
                if interpreter.error:
                    err_msg = "; ".join(str(e) for e in interpreter.error)
                    error_container[0] = FormulaSyntaxError(
                        f"Expression evaluation error: {err_msg}"
                    )
            except Exception as exc:
                error_container[0] = exc

        timer: threading.Timer | None = None
        try:
            timer = threading.Timer(
                self._timeout_seconds,
                lambda: self._timeout_handler(interpreter),
            )
            timer.daemon = True
            timer.start()
            _run()
        finally:
            if timer is not None:
                timer.cancel()

        if error_container[0] is not None:
            raise error_container[0]

        return result_container[0]

    def _timeout_handler(self, interpreter: asteval.Interpreter) -> None:
        raise FormulaTimeoutError(
            f"Expression execution timed out after {self._timeout_seconds}s"
        )
