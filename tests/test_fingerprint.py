import pytest
from sentinel.level1.fingerprint import fingerprint_tool_call


class TestFingerprint:
    def test_basic_fingerprint(self):
        fp = fingerprint_tool_call("get_weather", {"city": "Portland"})
        assert fp.tool_name == "get_weather"
        assert fp.param_keys == frozenset({"city"})
        assert fp.param_types == {"city": "str"}
        assert not fp.is_error

    def test_deterministic_hash(self):
        fp1 = fingerprint_tool_call("greet", {"name": "Alice", "age": 30})
        fp2 = fingerprint_tool_call("greet", {"name": "Bob", "age": 25})
        # Same keys and types → same shape hash
        assert fp1.shape_hash == fp2.shape_hash

    def test_different_keys_different_hash(self):
        fp1 = fingerprint_tool_call("search", {"query": "hello"})
        fp2 = fingerprint_tool_call("search", {"query": "hello", "limit": 10})
        assert fp1.shape_hash != fp2.shape_hash

    def test_different_types_different_hash(self):
        fp1 = fingerprint_tool_call("search", {"limit": 10})
        fp2 = fingerprint_tool_call("search", {"limit": "10"})
        assert fp1.shape_hash != fp2.shape_hash

    def test_none_arguments(self):
        fp = fingerprint_tool_call("ping", None)
        assert fp.param_keys == frozenset()
        assert fp.param_types == {}

    def test_error_fingerprint(self):
        fp = fingerprint_tool_call(
            "fail", {"x": 1}, is_error=True, error_message="boom"
        )
        assert fp.is_error
        assert fp.error_message == "boom"
