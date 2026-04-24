"""Unit tests for API error response — status codes, suggestion, structured errors."""

import pytest

from ontology_engine.api.dto.responses import (
    error_response,
    success_response,
    _ERROR_CODE_TO_HTTP_STATUS,
    _serialize_data,
)


class TestErrorResponse:
    """Test error_response returns correct HTTP status codes and structured errors."""

    def test_not_found_returns_404(self):
        resp = error_response(code="NOT_FOUND", message="Resource not found")
        assert resp.status_code == 404

    def test_space_not_found_returns_404(self):
        resp = error_response(code="SPACE_NOT_FOUND", message="Space not found")
        assert resp.status_code == 404

    def test_entity_not_found_returns_404(self):
        resp = error_response(code="ENTITY_NOT_FOUND", message="Entity not found")
        assert resp.status_code == 404

    def test_conflict_returns_409(self):
        resp = error_response(code="CONFLICT", message="Resource conflict")
        assert resp.status_code == 409

    def test_space_conflict_returns_409(self):
        resp = error_response(code="SPACE_CONFLICT", message="Space name conflict")
        assert resp.status_code == 409

    def test_validation_error_returns_422(self):
        resp = error_response(code="VALIDATION_ERROR", message="Invalid request")
        assert resp.status_code == 422

    def test_schema_not_loaded_returns_422(self):
        resp = error_response(code="SCHEMA_NOT_LOADED", message="Schema not loaded")
        assert resp.status_code == 422

    def test_internal_error_returns_500(self):
        resp = error_response(code="INTERNAL_ERROR", message="Internal error")
        assert resp.status_code == 500

    def test_unknown_code_defaults_to_500(self):
        resp = error_response(code="UNKNOWN_CODE", message="Unknown error")
        assert resp.status_code == 500

    def test_custom_status_code_override(self):
        resp = error_response(code="CUSTOM", message="Custom", status_code=418)
        assert resp.status_code == 418

    def test_error_body_contains_code(self):
        resp = error_response(code="SPACE_NOT_FOUND", message="Space not found")
        body = resp.body
        import json
        parsed = json.loads(body)
        assert parsed["error"]["code"] == "SPACE_NOT_FOUND"

    def test_error_body_contains_message(self):
        resp = error_response(code="NOT_FOUND", message="Space xyz not found")
        import json
        parsed = json.loads(resp.body)
        assert parsed["error"]["message"] == "Space xyz not found"

    def test_error_body_contains_suggestion(self):
        resp = error_response(
            code="SPACE_NOT_FOUND",
            message="Space not found",
            suggestion="Use GET /v1/spaces to list available spaces",
        )
        import json
        parsed = json.loads(resp.body)
        assert parsed["error"]["suggestion"] == "Use GET /v1/spaces to list available spaces"

    def test_error_body_without_suggestion(self):
        resp = error_response(code="NOT_FOUND", message="Not found")
        import json
        parsed = json.loads(resp.body)
        assert "suggestion" not in parsed["error"]

    def test_error_body_contains_details(self):
        resp = error_response(
            code="VALIDATION_ERROR",
            message="Invalid field",
            details={"field": "name", "constraint": "required"},
        )
        import json
        parsed = json.loads(resp.body)
        assert parsed["error"]["details"]["field"] == "name"

    def test_error_body_success_is_false(self):
        resp = error_response(code="NOT_FOUND", message="Not found")
        import json
        parsed = json.loads(resp.body)
        assert parsed["success"] is False

    def test_error_body_data_is_none(self):
        resp = error_response(code="NOT_FOUND", message="Not found")
        import json
        parsed = json.loads(resp.body)
        assert parsed["data"] is None

    def test_error_body_contains_meta(self):
        resp = error_response(code="NOT_FOUND", message="Not found")
        import json
        parsed = json.loads(resp.body)
        assert "meta" in parsed
        assert "request_id" in parsed["meta"]
        assert "timestamp" in parsed["meta"]


class TestSuccessResponse:
    """Test success_response format."""

    def test_success_response_format(self):
        result = success_response(data={"id": "123"})
        assert result["success"] is True
        assert result["data"] == {"id": "123"}
        assert result["error"] is None
        assert "meta" in result

    def test_success_response_none_data(self):
        result = success_response()
        assert result["success"] is True
        assert result["data"] is None

    def test_success_response_serializes_to_dict(self):
        class DTO:
            def to_dict(self):
                return {"serialized": True}

        result = success_response(data=DTO())
        assert result["data"] == {"serialized": True}


class TestErrorCodeMapping:
    """Test _ERROR_CODE_TO_HTTP_STATUS mapping completeness."""

    def test_all_4xx_codes_mapped(self):
        four_xx_codes = ["NOT_FOUND", "SPACE_NOT_FOUND", "ENTITY_NOT_FOUND",
                         "VIEW_NOT_FOUND", "DATASET_NOT_FOUND", "CONCEPT_NOT_FOUND",
                         "CONFLICT", "SPACE_CONFLICT", "DUPLICATE_NAME",
                         "PRECONDITION_FAILED",
                         "VALIDATION_ERROR", "SCHEMA_NOT_LOADED", "MISSING_PARAMETER",
                         "INVALID_REQUEST", "FACT_OBJECT_REQUIRED", "FILE_NOT_FOUND"]
        for code in four_xx_codes:
            assert code in _ERROR_CODE_TO_HTTP_STATUS, f"Missing mapping for {code}"
            assert 400 <= _ERROR_CODE_TO_HTTP_STATUS[code] < 500

    def test_all_5xx_codes_mapped(self):
        five_xx_codes = ["INTERNAL_ERROR", "STORAGE_ERROR", "ANALYSIS_ERROR",
                         "SNAPSHOT_ERROR", "ROLLBACK_ERROR", "INGESTION_ERROR"]
        for code in five_xx_codes:
            assert code in _ERROR_CODE_TO_HTTP_STATUS, f"Missing mapping for {code}"
            assert _ERROR_CODE_TO_HTTP_STATUS[code] >= 500


class TestSerializeData:
    """Test _serialize_data helper."""

    def test_none(self):
        assert _serialize_data(None) is None

    def test_primitive(self):
        assert _serialize_data("hello") == "hello"
        assert _serialize_data(42) == 42
        assert _serialize_data(3.14) == 3.14
        assert _serialize_data(True) is True

    def test_list(self):
        assert _serialize_data([1, 2, 3]) == [1, 2, 3]

    def test_dict(self):
        assert _serialize_data({"a": 1}) == {"a": 1}

    def test_to_dict_object(self):
        class Obj:
            def to_dict(self):
                return {"x": 1}
        assert _serialize_data(Obj()) == {"x": 1}

    def test_nested_to_dict(self):
        class Inner:
            def to_dict(self):
                return {"inner": True}
        assert _serialize_data({"items": [Inner()]}) == {"items": [{"inner": True}]}

    def test_precondition_failed_returns_412(self):
        resp = error_response(code="PRECONDITION_FAILED", message="ETag mismatch")
        assert resp.status_code == 412

    def test_unknown_type_passthrough(self):
        class Custom:
            pass
        result = _serialize_data(Custom())
        assert isinstance(result, Custom)

    def test_datetime_serialization(self):
        from datetime import datetime
        dt = datetime(2026, 1, 15, 10, 30, 0)
        result = _serialize_data(dt)
        assert result == "2026-01-15T10:30:00"

    def test_enum_serialization(self):
        from enum import Enum
        class Color(Enum):
            RED = "red"
            BLUE = "blue"
        result = _serialize_data(Color.RED)
        assert result == "red"

    def test_nested_datetime_serialization(self):
        from datetime import datetime
        dt = datetime(2026, 1, 15, 10, 30, 0)
        result = _serialize_data({"created_at": dt, "items": [dt]})
        assert result["created_at"] == "2026-01-15T10:30:00"
        assert result["items"][0] == "2026-01-15T10:30:00"
