from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

DEPRECATION_MAP: dict[str, tuple[str, str]] = {
    "/v1/entities": ("/v1/spaces/default/instances/entities", "301"),
    "/v1/schema": ("/v1/spaces/default/schema", "301"),
    "/v1/visualization": ("/v1/views/default", "301"),
}


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
            response.headers["X-Deprecation-Warning"] = (
                f"Deprecated endpoint. Use {new_path} instead."
            )
            response.headers["Link"] = f'<{new_path}>; rel="successor-version"'
            return response

        return await call_next(request)
