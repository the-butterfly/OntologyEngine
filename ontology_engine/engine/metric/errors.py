# ontology_engine/engine/metric/errors.py
"""Metric-specific errors."""

from ontology_engine.engine.errors import (
    MetricError as BaseMetricError,
    MetricNotFoundError as BaseMetricNotFoundError,
    MetricNotComputableError as BaseMetricNotComputableError,
    MetricDAGError as BaseMetricDAGError,
    MetricTimeoutError as BaseMetricTimeoutError,
)

# Re-export for convenience
MetricError = BaseMetricError
MetricNotFoundError = BaseMetricNotFoundError
MetricNotComputableError = BaseMetricNotComputableError
MetricDAGError = BaseMetricDAGError
MetricTimeoutError = BaseMetricTimeoutError
