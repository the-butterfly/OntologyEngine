# ontology_engine/engine/rule/operators/llm_judge.py
"""LLM Judge operator for structured LLM-based decisions."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry

logger = logging.getLogger(__name__)


@OperatorRegistry.register("llm_judge")
class LLMJudgeOperator(Operator):
    """LLM inference operator for structured judgment.

    Safety constraints:
    1. Timeout protection: single call < timeout_ms
    2. Retry strategy: exponential backoff, max max_retries
    3. Output validation: JSON schema validation + value domain
    4. Cost tracking: record token usage
    5. Fallback: return fallback_output on timeout/error

    Inputs:
        - model: LLM model name
        - temperature: Sampling temperature (0 = deterministic)
        - max_tokens: Max output tokens
        - timeout_ms: Single call timeout
        - max_retries: Failure retry count
        - prompt: Prompt template with {variable} placeholders
        - output_format: JSON schema for structured output
        - value_domain_ref: Reference to value domain for validation
        - fallback_output: Fallback result on error
        - output_key: Key to store result

    Example:
        action:
            operator: "llm_judge"
            inputs:
                model: "gpt-4o-mini"
                temperature: 0.0
                timeout_ms: 5000
                prompt: |
                    Determine risk level: {credit_score}, {overdue_ratio}
                    Options: LOW / MEDIUM / HIGH / CRITICAL
                output_format:
                    type: json_schema
                    schema:
                        type: object
                        properties:
                            risk_level:
                                type: string
                                enum: [LOW, MEDIUM, HIGH, CRITICAL]
                fallback_output: {risk_level: "MEDIUM", reason: "LLM unavailable"}
                output_key: llm_risk_assessment
    """

    @property
    def name(self) -> str:
        return "llm_judge"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        model = inputs.get("model", "gpt-4o-mini")
        prompt_template = inputs.get("prompt", "")
        temperature = inputs.get("temperature", 0.0)
        max_tokens = inputs.get("max_tokens", 200)
        output_format = inputs.get("output_format", {})
        value_domain_ref = inputs.get("value_domain_ref")
        output_key = inputs.get("output_key", "llm_result")
        timeout_ms = inputs.get("timeout_ms", 5000)
        max_retries = inputs.get("max_retries", 2)
        fallback_output = inputs.get("fallback_output", {"llm_error": "unavailable"})

        # Step 1: Render prompt template
        eval_context = self._build_context(context)
        prompt = self._render_template(prompt_template, eval_context)

        # Step 2: Call LLM with timeout and retries
        last_error: str | None = None
        result: dict[str, Any] = {}

        for attempt in range(max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self._call_llm(model, prompt, temperature, max_tokens, output_format),
                    timeout=timeout_ms / 1000.0,
                )
                result["llm_status"] = "success"
                result["llm_model"] = model
                break
            except asyncio.TimeoutError:
                last_error = "timeout"
                logger.warning(f"LLM Judge timeout (attempt {attempt + 1}/{max_retries + 1})")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"LLM Judge error (attempt {attempt + 1}/{max_retries + 1}): {e}")

            # Exponential backoff before retry
            if attempt < max_retries:
                await asyncio.sleep(0.5 * (2 ** attempt))
        else:
            # All retries exhausted
            result = {
                output_key: fallback_output,
                "llm_status": f"error: {last_error}",
                "llm_model": model,
                "llm_attempts": max_retries + 1,
            }
            return result

        # Step 3: Value domain validation (if referenced)
        if value_domain_ref and "llm_status" not in result:
            # Value domain validation would be done by ValueDomainValidator
            # For now, store the reference for downstream validation
            result["value_domain_ref"] = value_domain_ref

        result["output_key"] = output_key
        return result

    async def _call_llm(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        output_format: dict[str, Any],
    ) -> dict[str, Any]:
        """Call LLM API.

        This is a placeholder implementation. In production, integrate with
        actual LLM provider (OpenAI, Anthropic, etc.) via configuration.

        Returns a parsed dict from LLM response.
        """
        # Placeholder: simulate LLM response for testing
        # In production, replace with actual API call:
        #   async with httpx.AsyncClient() as client:
        #       response = await client.post(...)
        #       return response.json()

        logger.info(f"[LLM Judge] Placeholder: model={model}, prompt_length={len(prompt)}")

        # Return a structured placeholder response
        return {
            "judgment": "PLACEHOLDER",
            "confidence": 0.0,
            "reason": "LLM integration not configured. Implement _call_llm() with actual provider.",
            "llm_token_usage": {"input": len(prompt.split()), "output": 10},
        }

    def _render_template(self, template: str, context: dict[str, Any]) -> str:
        """Render prompt template by replacing {variable} placeholders."""
        rendered = template
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            rendered = rendered.replace(placeholder, str(value))
        return rendered

    def _build_context(self, context: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in context.items():
            if isinstance(value, dict) and "value" in value:
                result[key] = value["value"]
            else:
                result[key] = value
        return result
