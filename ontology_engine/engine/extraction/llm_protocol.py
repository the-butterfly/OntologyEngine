"""LLM client protocol and configuration loader.

Defines the interface that any LLM provider adapter must implement,
and a helper to build a client instance from config.yaml.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


# ─────────────────────────── Protocol ────────────────────────────────────────

@runtime_checkable
class LLMClientProtocol(Protocol):
    """Minimal interface that every LLM provider adapter must satisfy.

    Callers should depend on this protocol, not on concrete implementations.
    """

    def chat_complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """Send a prompt and return the completion text synchronously.

        Args:
            prompt: User-facing prompt text.
            system_prompt: Optional system instruction.
            temperature: Sampling temperature (0 = deterministic).
            max_tokens: Upper bound for generated tokens.

        Returns:
            The raw completion string from the provider.

        Raises:
            LLMProviderError: If the provider returns an error response.
        """
        ...


class LLMProviderError(Exception):
    """Raised when an LLM provider returns an error response."""


# ─────────────────────────── Config loader ───────────────────────────────────

def load_llm_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load LLM provider configuration from config.yaml.

    Search order:
      1. ``config_path`` argument (if provided).
      2. Environment variable ``OE_CONFIG_PATH``.
      3. ``<workspace_root>/config.yaml``.
      4. ``~/.ontology_engine/config.yaml``.

    The expected YAML structure is::

        llm:
          provider: openai          # openai | anthropic | ollama | custom
          api_key: sk-...           # or set OE_LLM_API_KEY env var
          model: gpt-4o-mini        # model name / tag
          base_url: ~               # optional — override endpoint
          temperature: 0.2
          max_tokens: 2048

    Returns:
        Dict with keys ``provider``, ``api_key``, ``model``, ``base_url``,
        ``temperature``, ``max_tokens``.  Missing keys fall back to
        environment-variable defaults.
    """
    import yaml  # soft dependency: only needed when reading config

    candidates: list[Path] = []
    if config_path is not None:
        candidates.append(Path(config_path))

    env_path = os.environ.get("OE_CONFIG_PATH")
    if env_path:
        candidates.append(Path(env_path))

    # workspace root — walk up from this file until we find config.yaml
    here = Path(__file__).parent
    for _ in range(10):
        candidate = here / "config.yaml"
        if candidate.exists():
            candidates.append(candidate)
            break
        here = here.parent

    candidates.append(Path.home() / ".ontology_engine" / "config.yaml")

    raw: dict[str, Any] = {}
    for path in candidates:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
                if isinstance(data, dict) and "llm" in data:
                    raw = data["llm"]
                    break
            except Exception:
                continue

    return {
        "provider": raw.get("provider") or os.environ.get("OE_LLM_PROVIDER", "openai"),
        "api_key": raw.get("api_key") or os.environ.get("OE_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"),
        "model": raw.get("model") or os.environ.get("OE_LLM_MODEL", "gpt-4o-mini"),
        "base_url": raw.get("base_url") or os.environ.get("OE_LLM_BASE_URL"),
        "temperature": float(raw.get("temperature", 0.2)),
        "max_tokens": int(raw.get("max_tokens", 2048)),
    }


def build_llm_client_from_config(
    config_path: str | Path | None = None,
) -> LLMClientProtocol | None:
    """Attempt to instantiate an LLM client from config.yaml / env vars.

    Returns ``None`` if no provider config is found or dependencies are
    missing, allowing callers to degrade gracefully.
    """
    cfg = load_llm_config(config_path)
    provider = cfg.get("provider", "openai")
    api_key = cfg.get("api_key")

    if provider == "openai":
        try:
            from ontology_engine.engine.extraction.llm_providers.openai_client import OpenAILLMClient  # type: ignore[import]
            return OpenAILLMClient(
                api_key=api_key or "",
                model=cfg.get("model", "gpt-4o-mini"),
                base_url=cfg.get("base_url"),
                temperature=cfg.get("temperature", 0.2),
                max_tokens=cfg.get("max_tokens", 2048),
            )
        except (ImportError, Exception):
            return None

    if provider == "anthropic":
        try:
            from ontology_engine.engine.extraction.llm_providers.anthropic_client import AnthropicLLMClient  # type: ignore[import]
            return AnthropicLLMClient(
                api_key=api_key or "",
                model=cfg.get("model", "claude-3-haiku-20240307"),
                temperature=cfg.get("temperature", 0.2),
                max_tokens=cfg.get("max_tokens", 2048),
            )
        except (ImportError, Exception):
            return None

    return None
