# ontology_engine/engine/errors.py
"""Shared error types for the engine layer."""

from __future__ import annotations


class OntologyError(Exception):
    """Base exception for all OntologyEngine errors."""
    pass


# Metric errors
class MetricError(OntologyError):
    """Base exception for metric computation errors."""
    pass


class MetricNotFoundError(MetricError):
    """Raised when a metric definition is not found."""
    pass


class MetricNotComputableError(MetricError):
    """Raised when a metric cannot be computed (missing inputs)."""
    pass


class MetricDAGError(MetricError):
    """Raised when there's an error in the metric dependency DAG."""
    pass


class MetricTimeoutError(MetricError):
    """Raised when metric computation exceeds timeout."""
    pass


# Categorization errors
class CategorizationError(OntologyError):
    """Base exception for categorization errors."""
    pass


class CategoryNotFoundError(CategorizationError):
    """Raised when a category cannot be determined."""
    pass


# Rule errors
class RuleError(OntologyError):
    """Base exception for rule execution errors."""
    pass


class RuleNotFoundError(RuleError):
    """Raised when a rule definition is not found."""
    pass


class RuleExecutionError(RuleError):
    """Raised when rule execution fails."""
    pass


# Expression errors
class ExpressionError(OntologyError):
    """Base exception for expression evaluation errors."""
    pass


class ExpressionSecurityError(ExpressionError):
    """Raised when expression violates security constraints."""
    pass


# Service errors
class ServiceError(OntologyError):
    """Base exception for service layer errors."""
    pass


class ServiceInitializationError(ServiceError):
    """Raised when service initialization fails."""
    pass


class ServiceNotAvailableError(ServiceError):
    """Raised when a service is not available."""
    pass
