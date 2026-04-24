"""HTTP client for CLI to communicate with OntologyEngine API."""

from __future__ import annotations

import json
from typing import Any

import httpx

_DEFAULT_BASE_URL = "http://localhost:8000/v1"


class APIClient:
    """Thin HTTP client wrapping the OntologyEngine REST API.

    Supports two modes:
    - API mode (default): calls a running FastAPI server
    - Direct mode: calls services directly (for CI/CD, no server needed)
    """

    def __init__(self, base_url: str = _DEFAULT_BASE_URL, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path.lstrip('/')}"

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(self._url(path), params=params)
            return self._handle_response(resp)

    async def post(self, path: str, json_body: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(self._url(path), json=json_body, params=params)
            return self._handle_response(resp)

    async def put(self, path: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.put(self._url(path), json=json_body)
            return self._handle_response(resp)

    async def delete(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.delete(self._url(path), params=params)
            return self._handle_response(resp)

    @staticmethod
    def _handle_response(resp: httpx.Response) -> dict[str, Any]:
        body = resp.json()
        if resp.status_code >= 400:
            error = body.get("error", {})
            raise CLIError(
                code=error.get("code", "HTTP_ERROR"),
                message=error.get("message", resp.text),
                suggestion=error.get("suggestion"),
                status_code=resp.status_code,
            )
        return body


class CLIError(Exception):
    """Structured error from API calls."""

    def __init__(
        self,
        code: str,
        message: str,
        suggestion: str | None = None,
        status_code: int = 500,
    ):
        self.code = code
        self.message = message
        self.suggestion = suggestion
        self.status_code = status_code
        super().__init__(f"[{code}] {message}" + (f" — {suggestion}" if suggestion else ""))


def format_output(data: Any, fmt: str = "json") -> str:
    """Format data for CLI output.

    Args:
        data: Data to format
        fmt: Output format — "json", "table", or "yaml"

    Returns:
        Formatted string
    """
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    if fmt == "yaml":
        try:
            import yaml
            return yaml.dump(data, allow_unicode=True, default_flow_style=False)
        except ImportError:
            return json.dumps(data, ensure_ascii=False, indent=2)
    return str(data)
