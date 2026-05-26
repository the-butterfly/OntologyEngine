import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from ontology_engine.api.middleware import DeprecationMiddleware, DEPRECATION_MAP, SUNSET_HTTP_DATE


@pytest.fixture
def app():
    app = Starlette()

    @app.route("/{path:path}")
    async def catch_all(request):
        return PlainTextResponse("ok")

    app.add_middleware(DeprecationMiddleware, mode="header")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestDeprecationHeaders:
    def test_deprecated_route_returns_deprecation_header(self, client):
        response = client.get("/v1/management")
        assert response.headers["deprecation"] == "true"

    def test_deprecated_route_returns_sunset_header(self, client):
        response = client.get("/v1/management")
        assert response.headers["sunset"] == SUNSET_HTTP_DATE
        assert response.headers["sunset"] == "Tue, 30 Jun 2026 00:00:00 GMT"

    def test_deprecated_route_returns_x_deprecation_warning(self, client):
        response = client.get("/v1/management")
        assert "Deprecated endpoint" in response.headers["x-deprecation-warning"]
        assert "/v1/spaces" in response.headers["x-deprecation-warning"]

    def test_deprecated_route_returns_link_header(self, client):
        response = client.get("/v1/management")
        assert 'rel="successor-version"' in response.headers["link"]

    def test_non_deprecated_route_no_deprecation_headers(self, client):
        response = client.get("/v1/spaces")
        assert "deprecation" not in response.headers
        assert "sunset" not in response.headers
        assert "x-deprecation-warning" not in response.headers

    def test_non_deprecated_route_no_sunset_header(self, client):
        response = client.get("/v1/query/search")
        assert "sunset" not in response.headers


class TestAllDeprecatedPaths:
    @pytest.mark.parametrize("old_prefix", list(DEPRECATION_MAP.keys()))
    def test_each_deprecated_path_has_headers(self, client, old_prefix):
        response = client.get(old_prefix)
        assert response.headers["deprecation"] == "true"
        assert response.headers["sunset"] == SUNSET_HTTP_DATE

    @pytest.mark.parametrize("old_prefix", list(DEPRECATION_MAP.keys()))
    def test_each_deprecated_path_has_link_header(self, client, old_prefix):
        response = client.get(old_prefix)
        assert "link" in response.headers
        assert 'rel="successor-version"' in response.headers["link"]


class TestSubPaths:
    def test_deprecated_subpath_gets_headers(self, client):
        response = client.get("/v1/entities/some-entity-id")
        assert response.headers["deprecation"] == "true"
        assert response.headers["sunset"] == SUNSET_HTTP_DATE
        assert "/v1/spaces/default/instances/entities/some-entity-id" in response.headers["x-deprecation-warning"]

    def test_deprecated_subpath_link_points_to_new_subpath(self, client):
        response = client.get("/v1/schema/validate")
        assert "/v1/spaces/default/schema/validate" in response.headers["link"]


class TestRedirectMode:
    @pytest.fixture
    def redirect_client(self):
        app = Starlette()

        @app.route("/{path:path}")
        async def catch_all(request):
            return PlainTextResponse("ok")

        app.add_middleware(DeprecationMiddleware, mode="redirect")
        return TestClient(app, follow_redirects=False)

    def test_redirect_mode_returns_301(self, redirect_client):
        response = redirect_client.get("/v1/management")
        assert response.status_code == 301
        assert response.headers["location"] == "/v1/spaces"

    def test_redirect_mode_no_deprecation_headers(self, redirect_client):
        response = redirect_client.get("/v1/management")
        assert "deprecation" not in response.headers
        assert "sunset" not in response.headers
