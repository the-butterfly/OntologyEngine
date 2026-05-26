from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

DEPRECATION_MAP: dict[str, tuple[str, str]] = {
    "/v1/management": ("/v1/spaces", "301"),
    "/v1/consumption": ("/v1/views", "301"),
    "/v1/visualize": ("/v1/views", "301"),
    "/v1/analysis": ("/v1/views", "301"),
    "/v1/entities": ("/v1/spaces/default/instances/entities", "301"),
    "/v1/relations": ("/v1/spaces/default/instances/relations", "301"),
    "/v1/datasets": ("/v1/spaces/default/instances/datasets", "301"),
    "/v1/incremental": ("/v1/spaces/default/instances/incremental", "301"),
    "/v1/ingestion": ("/v1/spaces/default/instances/ingestion", "301"),
    "/v1/categories": ("/v1/spaces/default/rules/categories", "301"),
    "/v1/schema": ("/v1/spaces/default/schema", "301"),
}

SUNSET_HTTP_DATE = "Tue, 30 Jun 2026 00:00:00 GMT"


class DeprecationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, mode: str = "header"):
        super().__init__(app)
        self._mode = mode

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        deprecated_prefix = None
        new_path = None

        for old_prefix, (replacement, _) in DEPRECATION_MAP.items():
            if path.startswith(old_prefix):
                deprecated_prefix = old_prefix
                new_path = replacement + path[len(old_prefix):]
                break

        if deprecated_prefix and new_path:
            if self._mode == "redirect":
                return RedirectResponse(url=new_path, status_code=301)

            response = await call_next(request)
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = SUNSET_HTTP_DATE
            response.headers["X-Deprecation-Warning"] = (
                f"Deprecated endpoint. Use {new_path} instead."
            )
            response.headers["Link"] = f'<{new_path}>; rel="successor-version"'
            return response

        return await call_next(request)
