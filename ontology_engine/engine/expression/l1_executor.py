"""L1 ASTSandboxExecutor for complex expressions with control flow."""

from __future__ import annotations

import ast
import logging
import multiprocessing
from collections.abc import Mapping
from typing import Any

import asteval

from ontology_engine.engine.expression.errors import (
    FormulaSecurityError,
    FormulaSyntaxError,
    FormulaTimeoutError,
)

logger = logging.getLogger(__name__)

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


def _subprocess_worker(
    expression: str,
    context: dict[str, Any],
    safe_functions: dict[str, Any],
    result_queue: multiprocessing.Queue,
) -> None:
    try:
        interpreter = asteval.Interpreter()
        interpreter.symtable.update(safe_functions)
        interpreter.symtable.update(context)
        value = interpreter.eval(expression)
        if interpreter.error:
            err_msg = "; ".join(str(e) for e in interpreter.error)
            result_queue.put(("error", "syntax", err_msg))
        else:
            result_queue.put(("ok", value))
    except Exception as exc:
        result_queue.put(("error", type(exc).__name__, str(exc)))


class ASTSandboxExecutor:
    """L1 executor: asteval + AST whitelist + resource limits + subprocess isolation."""

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
        instrumented = self._inject_loop_guard(tree)
        return self._execute_with_timeout(instrumented, context, safe_functions)

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

    def _inject_loop_guard(self, tree: ast.AST) -> ast.AST:
        guard_name = "_loop_guard_count"
        limit = self._max_loop_iterations

        has_loop = any(
            isinstance(node, (ast.For, ast.While))
            for node in ast.walk(tree)
        )
        if not has_loop:
            return tree

        self._transform_loops(tree, guard_name, limit)

        init_assign = ast.Assign(
            targets=[ast.Name(id=guard_name, ctx=ast.Store())],
            value=ast.Constant(value=0),
            lineno=0,
            col_offset=0,
        )
        if isinstance(tree, ast.Module):
            tree.body.insert(0, init_assign)
        ast.fix_missing_locations(tree)
        return tree

    def _transform_loops(self, node: ast.AST, guard_name: str, limit: int) -> None:
        for child in list(ast.iter_child_nodes(node)):
            self._transform_loops(child, guard_name, limit)

        if not isinstance(node, (ast.For, ast.While)):
            return

        guard_increment = ast.AugAssign(
            target=ast.Name(id=guard_name, ctx=ast.Store()),
            op=ast.Add(),
            value=ast.Constant(value=1),
            lineno=0,
            col_offset=0,
        )
        guard_check = ast.If(
            test=ast.Compare(
                left=ast.Name(id=guard_name, ctx=ast.Load()),
                ops=[ast.Gt()],
                comparators=[ast.Constant(value=limit)],
            ),
            body=[ast.Break()],
            orelse=[],
            lineno=0,
            col_offset=0,
        )
        node.body = [guard_increment, guard_check] + node.body

    def _execute_with_timeout(
        self,
        tree: ast.AST,
        context: Mapping[str, Any],
        safe_functions: Mapping[str, Any],
    ) -> Any:
        try:
            return self._execute_in_subprocess(tree, context, safe_functions)
        except Exception as exc:
            logger.debug(
                "Subprocess execution failed, falling back to in-process: %s", exc
            )
            return self._execute_in_process(tree, context, safe_functions)

    def _execute_in_subprocess(
        self,
        tree: ast.AST,
        context: Mapping[str, Any],
        safe_functions: Mapping[str, Any],
    ) -> Any:
        expression = ast.unparse(tree)
        ctx_dict = dict(context)
        fn_dict = {k: v for k, v in safe_functions.items() if callable(v)}

        result_queue: multiprocessing.Queue[tuple[str, str, Any]] = multiprocessing.Queue()

        proc = multiprocessing.Process(
            target=_subprocess_worker,
            args=(expression, ctx_dict, fn_dict, result_queue),
            daemon=True,
        )
        proc.start()
        proc.join(timeout=self._timeout_seconds)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1)
            if proc.is_alive():
                proc.kill()
                proc.join(timeout=1)
            raise FormulaTimeoutError(
                f"Expression execution timed out after {self._timeout_seconds}s"
            )

        if not result_queue.empty():
            status, detail, value = result_queue.get_nowait()
            if status == "error":
                if detail == "syntax":
                    raise FormulaSyntaxError(value)
                raise FormulaSyntaxError(f"{detail}: {value}")
            return value

        return None

    def _execute_in_process(
        self,
        tree: ast.AST,
        context: Mapping[str, Any],
        safe_functions: Mapping[str, Any],
    ) -> Any:
        expression = ast.unparse(tree)
        interpreter = asteval.Interpreter()
        interpreter.symtable.update(safe_functions)
        interpreter.symtable.update(context)
        value = interpreter.eval(expression)
        if interpreter.error:
            err_msg = "; ".join(str(e) for e in interpreter.error)
            raise FormulaSyntaxError(f"Expression evaluation error: {err_msg}")
        return value
