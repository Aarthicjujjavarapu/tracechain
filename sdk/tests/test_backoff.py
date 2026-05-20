"""
Tests for exponential backoff in @step retries.
time.sleep and asyncio.sleep are mocked — no real waits occur.
"""
import asyncio
from unittest.mock import patch, MagicMock
import pytest

from tracechain.steps import step, _backoff_delay
from tracechain.tracing import set_run_id, reset_run_id
from .conftest import MockClient


# ── _backoff_delay unit tests ─────────────────────────────────────────────────

def test_first_retry_delay_equals_base():
    assert _backoff_delay(attempt=1, base=1.0, max_delay=30.0, jitter=False) == 1.0


def test_second_retry_delay_doubles():
    assert _backoff_delay(attempt=2, base=1.0, max_delay=30.0, jitter=False) == 2.0


def test_third_retry_delay_quadruples():
    assert _backoff_delay(attempt=3, base=1.0, max_delay=30.0, jitter=False) == 4.0


def test_delay_capped_at_max():
    # base=10, attempt=10 → 10 * 2^9 = 5120 → capped at max_delay=30
    assert _backoff_delay(attempt=10, base=10.0, max_delay=30.0, jitter=False) == 30.0


def test_jitter_adds_positive_offset():
    # With jitter, delay must be >= base value (no-jitter)
    no_jitter = _backoff_delay(1, base=1.0, max_delay=30.0, jitter=False)
    with_jitter = _backoff_delay(1, base=1.0, max_delay=30.0, jitter=True)
    assert with_jitter >= no_jitter


def test_jitter_bounded_above():
    # jitter adds at most `base` seconds, so delay <= base * 2^(attempt-1) + base
    for _ in range(50):
        d = _backoff_delay(1, base=2.0, max_delay=100.0, jitter=True)
        assert d <= 2.0 + 2.0  # base * 2^0 + base


def test_zero_base_returns_zero_without_jitter():
    assert _backoff_delay(1, base=0.0, max_delay=30.0, jitter=False) == 0.0


# ── sync @step backoff ────────────────────────────────────────────────────────

@pytest.fixture
def run_ctx():
    token = set_run_id("backoff-run")
    yield
    reset_run_id(token)


def test_sync_step_sleeps_between_retries(run_ctx):
    mc = MockClient()
    call_count = 0

    @step(name="flaky", retries=2, retry_delay=1.0, retry_jitter=False, client=mc)
    def flaky():
        nonlocal call_count
        call_count += 1
        raise IOError("down")

    with patch("time.sleep") as mock_sleep:
        with pytest.raises(IOError):
            flaky()

    assert call_count == 3
    assert mock_sleep.call_count == 2


def test_sync_backoff_values_are_exponential(run_ctx):
    mc = MockClient()

    @step(name="flaky", retries=3, retry_delay=1.0, retry_jitter=False, client=mc)
    def flaky():
        raise ValueError("fail")

    with patch("time.sleep") as mock_sleep:
        with pytest.raises(ValueError):
            flaky()

    delays = [call.args[0] for call in mock_sleep.call_args_list]
    assert delays == [1.0, 2.0, 4.0]  # base * 2^0, base * 2^1, base * 2^2


def test_sync_backoff_respects_max_delay(run_ctx):
    mc = MockClient()

    @step(name="flaky", retries=4, retry_delay=10.0, retry_max_delay=15.0,
          retry_jitter=False, client=mc)
    def flaky():
        raise RuntimeError("fail")

    with patch("time.sleep") as mock_sleep:
        with pytest.raises(RuntimeError):
            flaky()

    delays = [call.args[0] for call in mock_sleep.call_args_list]
    # 10, 20 → capped 15, 40 → capped 15, 80 → capped 15
    assert delays == [10.0, 15.0, 15.0, 15.0]


def test_sync_no_sleep_when_retries_zero(run_ctx):
    mc = MockClient()

    @step(name="flaky", retries=0, client=mc)
    def flaky():
        raise RuntimeError("fail")

    with patch("time.sleep") as mock_sleep:
        with pytest.raises(RuntimeError):
            flaky()

    mock_sleep.assert_not_called()


def test_sync_no_sleep_on_success(run_ctx):
    mc = MockClient()

    @step(name="ok", retries=3, client=mc)
    def ok():
        return "done"

    with patch("time.sleep") as mock_sleep:
        ok()

    mock_sleep.assert_not_called()


def test_sync_no_sleep_on_last_failed_attempt(run_ctx):
    """Sleep happens only *between* retries, not after the final failure."""
    mc = MockClient()

    @step(name="flaky", retries=2, retry_delay=1.0, retry_jitter=False, client=mc)
    def flaky():
        raise RuntimeError("fail")

    with patch("time.sleep") as mock_sleep:
        with pytest.raises(RuntimeError):
            flaky()

    # retries=2 → 3 total attempts → 2 sleeps (between attempts 1→2 and 2→3)
    assert mock_sleep.call_count == 2


def test_sync_jitter_sleep_within_expected_range(run_ctx):
    mc = MockClient()

    @step(name="flaky", retries=1, retry_delay=2.0, retry_max_delay=30.0,
          retry_jitter=True, client=mc)
    def flaky():
        raise RuntimeError("fail")

    with patch("time.sleep") as mock_sleep:
        with pytest.raises(RuntimeError):
            flaky()

    delay = mock_sleep.call_args.args[0]
    # base=2.0, attempt=1 → 2.0 * 2^0 = 2.0, plus jitter in [0, 2.0)
    assert 2.0 <= delay < 4.0


# ── async @step backoff ───────────────────────────────────────────────────────

def test_async_step_sleeps_between_retries(run_ctx):
    mc = MockClient()
    call_count = 0

    @step(name="flaky", retries=2, retry_delay=1.0, retry_jitter=False, client=mc)
    async def flaky():
        nonlocal call_count
        call_count += 1
        raise IOError("down")

    async def run():
        with patch("asyncio.sleep", new_callable=MagicMock) as mock_sleep:
            mock_sleep.return_value = asyncio.coroutine(lambda: None)()
            with pytest.raises(IOError):
                await flaky()
            return mock_sleep

    # Use a different approach that works cleanly
    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    async def run2():
        with patch("asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(IOError):
                await flaky()

    asyncio.run(run2())
    assert call_count == 3
    assert len(sleep_calls) == 2


def test_async_backoff_values_are_exponential(run_ctx):
    mc = MockClient()
    sleep_calls = []

    @step(name="flaky", retries=3, retry_delay=1.0, retry_jitter=False, client=mc)
    async def flaky():
        raise ValueError("fail")

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    async def run():
        with patch("asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(ValueError):
                await flaky()

    asyncio.run(run())
    assert sleep_calls == [1.0, 2.0, 4.0]


def test_async_no_sleep_when_retries_zero(run_ctx):
    mc = MockClient()
    sleep_calls = []

    @step(name="flaky", retries=0, client=mc)
    async def flaky():
        raise RuntimeError("fail")

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    async def run():
        with patch("asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(RuntimeError):
                await flaky()

    asyncio.run(run())
    assert sleep_calls == []


def test_async_succeeds_after_retry_with_backoff(run_ctx):
    mc = MockClient()
    call_count = 0
    sleep_calls = []

    @step(name="flaky", retries=2, retry_delay=0.5, retry_jitter=False, client=mc)
    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise IOError("not ready")
        return "ok"

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    async def run():
        with patch("asyncio.sleep", side_effect=fake_sleep):
            return await flaky()

    result = asyncio.run(run())
    assert result == "ok"
    assert call_count == 2
    assert sleep_calls == [0.5]  # only one sleep before the successful retry
