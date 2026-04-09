# ontology_engine/engine/rule/operators/base.py
"""Base operator class and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Operator(ABC):
    """Base class for all rule operators.

    Operators are the atomic execution units in the rule engine.
    Each operator performs a specific action like setting a flag,
    rejecting an entity, computing a formula, etc.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the operator name for registration."""
        pass

    @abstractmethod
    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the operator.

        Args:
            inputs: Input values from the rule action
            config: Configuration for the operator
            context: Execution context with entity data and computed metrics

        Returns:
            Output dict with results
        """
        pass


class OperatorRegistry:
    """Registry for all available operators.

    Operators are registered by name and can be retrieved by name.
    This allows dynamic operator selection in rule execution.
    """

    _operators: dict[str, type[Operator]] = {}

    @classmethod
    def register(cls, name: str) -> type[Operator]:
        """Decorator to register an operator.

        Usage:
            @OperatorRegistry.register("set_flag")
            class SetFlagOperator(Operator):
                ...

        Args:
            name: The name to register the operator under

        Returns:
            The operator class decorator
        """
        def deco(operator_cls: type[Operator]) -> type[Operator]:
            cls._operators[name] = operator_cls
            return operator_cls
        return deco

    @classmethod
    def get(cls, name: str) -> Operator:
        """Get an operator instance by name.

        Args:
            name: The operator name

        Returns:
            An instance of the requested operator

        Raises:
            KeyError: If operator is not registered
        """
        if name not in cls._operators:
            raise KeyError(f"Operator '{name}' not found in registry. Available: {list(cls._operators.keys())}")
        return cls._operators[name]()

    @classmethod
    def available(cls) -> list[str]:
        """Get list of available operator names."""
        return list(cls._operators.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered operators (mainly for testing)."""
        cls._operators.clear()
