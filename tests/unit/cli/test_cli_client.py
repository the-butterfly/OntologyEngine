"""Unit tests for CLI client and output formatting."""

import pytest
import json

from ontology_engine.cli.client import APIClient, CLIError, format_output


class TestCLIError:
    """Test CLIError structured exception."""

    def test_cli_error_attributes(self):
        err = CLIError(code="SPACE_NOT_FOUND", message="Space not found", suggestion="Use list", status_code=404)
        assert err.code == "SPACE_NOT_FOUND"
        assert err.message == "Space not found"
        assert err.suggestion == "Use list"
        assert err.status_code == 404

    def test_cli_error_str(self):
        err = CLIError(code="NOT_FOUND", message="Not found", suggestion="Try again")
        assert "[NOT_FOUND]" in str(err)
        assert "Not found" in str(err)
        assert "Try again" in str(err)

    def test_cli_error_without_suggestion(self):
        err = CLIError(code="ERROR", message="Fail")
        assert "[ERROR]" in str(err)
        assert "Fail" in str(err)


class TestFormatOutput:
    """Test format_output utility."""

    def test_json_format(self):
        data = {"id": "123", "name": "Test"}
        result = format_output(data, "json")
        parsed = json.loads(result)
        assert parsed["id"] == "123"
        assert parsed["name"] == "Test"

    def test_json_format_unicode(self):
        data = {"name": "供应链金融"}
        result = format_output(data, "json")
        assert "供应链金融" in result

    def test_json_format_indent(self):
        data = {"id": "123"}
        result = format_output(data, "json")
        assert "\n" in result

    def test_yaml_format_fallback(self):
        data = {"id": "123"}
        result = format_output(data, "yaml")
        assert "123" in result

    def test_default_format(self):
        data = {"id": "123"}
        result = format_output(data, "table")
        assert "123" in result


class TestAPIClient:
    """Test APIClient URL construction."""

    def test_url_construction(self):
        client = APIClient(base_url="http://localhost:8000/v1")
        url = client._url("/spaces")
        assert url == "http://localhost:8000/v1/spaces"

    def test_url_construction_trailing_slash(self):
        client = APIClient(base_url="http://localhost:8000/v1/")
        url = client._url("/spaces")
        assert url == "http://localhost:8000/v1/spaces"

    def test_url_construction_no_leading_slash(self):
        client = APIClient(base_url="http://localhost:8000/v1")
        url = client._url("spaces")
        assert url == "http://localhost:8000/v1/spaces"

    def test_default_base_url(self):
        client = APIClient()
        assert client._base_url == "http://localhost:8000/v1"
