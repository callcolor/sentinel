import pytest
from sentinel.proxy.jsonrpc import (
    extract_tool_call,
    extract_tool_result,
    get_request_id,
    is_tool_call_request,
    parse_jsonrpc,
)


class TestParseJsonrpc:
    def test_valid_json(self):
        msg = parse_jsonrpc('{"jsonrpc": "2.0", "id": 1, "method": "test"}')
        assert msg == {"jsonrpc": "2.0", "id": 1, "method": "test"}

    def test_bytes_input(self):
        msg = parse_jsonrpc(b'{"id": 1}')
        assert msg == {"id": 1}

    def test_invalid_json(self):
        assert parse_jsonrpc("not json") is None

    def test_empty_string(self):
        assert parse_jsonrpc("") is None

    def test_whitespace(self):
        assert parse_jsonrpc("   ") is None

    def test_non_dict_json(self):
        assert parse_jsonrpc("[1, 2, 3]") is None


class TestIsToolCallRequest:
    def test_tool_call(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {}}
        assert is_tool_call_request(msg)

    def test_not_tool_call(self):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        assert not is_tool_call_request(msg)

    def test_notification_without_id(self):
        msg = {"jsonrpc": "2.0", "method": "tools/call"}
        assert not is_tool_call_request(msg)


class TestExtractToolCall:
    def test_basic(self):
        msg = {
            "method": "tools/call",
            "params": {"name": "search", "arguments": {"query": "hello"}},
        }
        name, args = extract_tool_call(msg)
        assert name == "search"
        assert args == {"query": "hello"}

    def test_no_arguments(self):
        msg = {"method": "tools/call", "params": {"name": "ping"}}
        name, args = extract_tool_call(msg)
        assert name == "ping"
        assert args is None

    def test_empty_params(self):
        msg = {"method": "tools/call", "params": {}}
        name, args = extract_tool_call(msg)
        assert name == ""
        assert args is None


class TestExtractToolResult:
    def test_success(self):
        msg = {
            "id": 1,
            "result": {"content": [{"type": "text", "text": "hello"}]},
        }
        result, is_error, error_msg = extract_tool_result(msg)
        assert not is_error
        assert error_msg is None
        assert result["content"][0]["text"] == "hello"

    def test_jsonrpc_error(self):
        msg = {
            "id": 1,
            "error": {"code": -32601, "message": "Method not found"},
        }
        result, is_error, error_msg = extract_tool_result(msg)
        assert is_error
        assert error_msg == "Method not found"
        assert result is None

    def test_mcp_tool_error(self):
        msg = {
            "id": 1,
            "result": {
                "isError": True,
                "content": [{"type": "text", "text": "file not found"}],
            },
        }
        result, is_error, error_msg = extract_tool_result(msg)
        assert is_error
        assert error_msg == "file not found"


class TestGetRequestId:
    def test_int_id(self):
        assert get_request_id({"id": 42}) == 42

    def test_string_id(self):
        assert get_request_id({"id": "abc"}) == "abc"

    def test_no_id(self):
        assert get_request_id({"method": "test"}) is None
