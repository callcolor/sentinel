import pytest
from sentinel.level1.fingerprint import (
    _parameterize_path,
    fingerprint_http_request,
)


class TestParameterizePath:
    def test_numeric_segment(self):
        assert _parameterize_path("/users/123/posts") == "/users/:id/posts"

    def test_uuid_segment(self):
        assert _parameterize_path("/items/550e8400-e29b-41d4-a716-446655440000") == "/items/:id"

    def test_no_dynamic_segments(self):
        assert _parameterize_path("/api/users") == "/api/users"

    def test_root(self):
        assert _parameterize_path("/") == "/"

    def test_multiple_dynamic(self):
        assert _parameterize_path("/users/42/posts/99") == "/users/:id/posts/:id"

    def test_mixed(self):
        assert _parameterize_path("/api/v2/users/123") == "/api/v2/users/:id"


class TestFingerprintHttpRequest:
    def test_basic_get(self):
        fp = fingerprint_http_request("GET", "/api/users")
        assert fp.tool_name == "GET /api/users"
        assert not fp.is_error

    def test_post_with_body(self):
        fp = fingerprint_http_request("POST", "/api/users", body={"name": "Alice", "age": 30})
        assert fp.tool_name == "POST /api/users"
        assert fp.param_keys == frozenset({"name", "age"})

    def test_path_parameterization(self):
        fp = fingerprint_http_request("GET", "/users/123")
        assert fp.tool_name == "GET /users/:id"

    def test_error_status(self):
        fp = fingerprint_http_request("GET", "/api/users", status_code=404)
        assert fp.is_error
        assert fp.error_message == "HTTP 404"

    def test_success_status(self):
        fp = fingerprint_http_request("GET", "/api/users", status_code=200)
        assert not fp.is_error

    def test_query_params(self):
        fp = fingerprint_http_request("GET", "/search", query_params={"q": "hello", "limit": 10})
        assert fp.param_keys == frozenset({"q", "limit"})

    def test_same_shape_same_hash(self):
        fp1 = fingerprint_http_request("POST", "/api/users", body={"name": "Alice"})
        fp2 = fingerprint_http_request("POST", "/api/users", body={"name": "Bob"})
        assert fp1.shape_hash == fp2.shape_hash

    def test_different_path_params_same_identity(self):
        fp1 = fingerprint_http_request("GET", "/users/123")
        fp2 = fingerprint_http_request("GET", "/users/456")
        assert fp1.tool_name == fp2.tool_name
