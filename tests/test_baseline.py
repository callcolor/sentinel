import pytest
import pytest_asyncio
from sentinel.level1.baseline import Baseline
from sentinel.level1.fingerprint import fingerprint_tool_call


@pytest_asyncio.fixture
async def baseline(tmp_path):
    b = Baseline(db_path=tmp_path / "test.db", threshold=5)
    await b.initialize()
    yield b
    await b.close()


async def _fill_baseline(baseline: Baseline, n: int = 5):
    """Add n observations of 'greet' to establish baseline."""
    for i in range(n):
        fp = fingerprint_tool_call("greet", {"name": f"user_{i}"})
        await baseline.update(fp)


class TestBaseline:
    @pytest.mark.asyncio
    async def test_not_established_initially(self, baseline):
        assert not baseline.is_established

    @pytest.mark.asyncio
    async def test_established_after_threshold(self, baseline):
        await _fill_baseline(baseline, 5)
        assert baseline.is_established

    @pytest.mark.asyncio
    async def test_nothing_anomalous_before_established(self, baseline):
        fp = fingerprint_tool_call("unknown_tool", {"x": 1})
        result = await baseline.is_anomalous(fp, sensitivity=0.0)
        assert not result.is_anomalous

    @pytest.mark.asyncio
    async def test_known_tool_normal(self, baseline):
        await _fill_baseline(baseline)
        fp = fingerprint_tool_call("greet", {"name": "Alice"})
        result = await baseline.is_anomalous(fp, sensitivity=0.5)
        assert not result.is_anomalous
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_unknown_tool_anomalous(self, baseline):
        await _fill_baseline(baseline)
        fp = fingerprint_tool_call("delete_everything", {"confirm": True})
        result = await baseline.is_anomalous(fp, sensitivity=0.5)
        assert result.is_anomalous
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_new_param_shape_anomalous(self, baseline):
        await _fill_baseline(baseline)
        fp = fingerprint_tool_call("greet", {"name": "Alice", "lang": "fr"})
        result = await baseline.is_anomalous(fp, sensitivity=0.5)
        assert result.is_anomalous
        assert result.score == 0.7

    @pytest.mark.asyncio
    async def test_new_param_shape_not_anomalous_at_high_sensitivity(self, baseline):
        await _fill_baseline(baseline)
        fp = fingerprint_tool_call("greet", {"name": "Alice", "lang": "fr"})
        result = await baseline.is_anomalous(fp, sensitivity=0.8)
        assert not result.is_anomalous

    @pytest.mark.asyncio
    async def test_error_on_reliable_tool(self, baseline):
        await _fill_baseline(baseline)
        fp = fingerprint_tool_call(
            "greet", {"name": "Alice"}, is_error=True, error_message="timeout"
        )
        result = await baseline.is_anomalous(fp, sensitivity=0.3)
        assert result.is_anomalous
        assert result.score == 0.5

    @pytest.mark.asyncio
    async def test_sensitivity_zero_flags_everything(self, baseline):
        await _fill_baseline(baseline)
        # Even a known tool with known shape — error gives score 0.5
        fp = fingerprint_tool_call(
            "greet", {"name": "Alice"}, is_error=True, error_message="err"
        )
        result = await baseline.is_anomalous(fp, sensitivity=0.0)
        assert result.is_anomalous

    @pytest.mark.asyncio
    async def test_get_summary(self, baseline):
        await _fill_baseline(baseline)
        summary = await baseline.get_summary()
        assert summary["total_observations"] == 5
        assert "greet" in summary["known_tools"]
        assert summary["known_tools"]["greet"]["calls"] == 5
