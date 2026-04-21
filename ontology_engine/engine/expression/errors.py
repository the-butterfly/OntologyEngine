"""Formula expression error types for L0/L1 execution model."""


class FormulaError(Exception):
    """Base class for all formula evaluation errors."""


class FormulaSyntaxError(FormulaError):
    """Raised when an expression has invalid syntax."""


class FormulaSecurityError(FormulaError):
    """Raised when an expression contains disallowed AST nodes or operations."""


class FormulaTimeoutError(FormulaError):
    """Raised when expression execution exceeds the time limit."""


class FormulaTypeError(FormulaError):
    """Raised when an expression has incompatible types in an operation."""


class FormulaNameError(FormulaError):
    """Raised when an expression references an undefined name or function."""
