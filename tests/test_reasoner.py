import pytest
import time
from sentinel.level2.reasoner import RateLimiter


class TestRateLimiter:
    def test_allows_under_limit(self):
        rl = RateLimiter(max_calls_per_hour=3)
        assert rl.allow()
        assert rl.allow()
        assert rl.allow()

    def test_blocks_at_limit(self):
        rl = RateLimiter(max_calls_per_hour=2)
        assert rl.allow()
        assert rl.allow()
        assert not rl.allow()

    def test_remaining_count(self):
        rl = RateLimiter(max_calls_per_hour=5)
        assert rl.remaining == 5
        rl.allow()
        rl.allow()
        assert rl.remaining == 3

    def test_expired_calls_dont_count(self):
        rl = RateLimiter(max_calls_per_hour=1)
        # Simulate a call from 2 hours ago
        rl._timestamps = [time.time() - 7200]
        assert rl.allow()  # old call expired, so this should pass
