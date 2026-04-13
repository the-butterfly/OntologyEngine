# ontology_engine/engine/validation/__init__.py
"""Validation utilities for the rule engine."""

from ontology_engine.engine.validation.value_domain_validator import (
    ValidationResult,
    ValueDomainValidator,
)

__all__ = ["ValidationResult", "ValueDomainValidator"]
