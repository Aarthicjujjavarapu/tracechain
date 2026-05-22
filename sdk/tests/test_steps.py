import pytest
from tracechain.steps import step
from tracechain.tracing import set_run_id, reset_run_id, get_run_id, get_step_id
from .conftest import MockClient


# ── fixture: run context ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def run_context():
    """Give each test a live run_id so step decorators record normally."""
    token = set_run_id("run-test")
    yield
    reset_run_id(token)


# ── basic execution ───────────────────────────────────────────────────────────

def test_step_calls_fn_and_returns_result():
    mc = MockClient()

    @step(name="my_step", client=mc)
    def add(a, b):
        return a + b

    assert add(3, 4) == 7


def test_step_creates_step_record():
    mc = MockClient()

    @step(name="my_step", client=mc)
    def do_work():
        return "done"

    do_work()
    assert mc.called("create_step")
    args = mc.call_args("create_step")
    assert args["step_name"] == "my_step"
    assert args["step_type"] == "step"


def test_step_completes_on_success():
    mc = MockClient()

    @step(name="my_step", client=mc)
    def do_work():
        return {"result": 42}

    do_work()
    assert mc.called("complete_step")
    args = mc.call_args("complete_step")
    assert args["output_payload"] == {"result": 42}
    assert args["retry_count"] == 0
    assert args["duration_ms"] >= 0


def test_step_records_duration():
    import time
    mc = MockClient()

    @step(name="timed_step", client=mc)
    def slow():
        time.sleep(0.05)
        return "ok"

    slow()
    args = mc.call_args("complete_step")
    assert args["duration_ms"] >= 40  # at least ~40ms


# ── failure handling ──────────────────────────────────────────────────────────

def test_step_with_no_retries_fails_immediately():
    mc = MockClient()
    call_count = 0

    @step(name="my_step", client=mc)
    def fail():
        nonlocal call_count
        call_count += 1
        raise ValueError("oops")

    with pytest.raises(ValueError, match="oops"):
        fail()

    assert call_count == 1
    assert mc.called("fail_step")
    assert not mc.called("complete_step")


def test_step_reraises_original_exception_type():
    mc = MockClient()

    @step(name="my_step", client=mc)
    def fail():
        raise TypeError("wrong type")

    with pytest.raises(TypeError):
        fail()


def test_fail_step_records_error_message():
    mc = MockClient()

    @step(name="my_step", client=mc)
    def fail():
        raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError):
        fail()

    args = mc.call_args("fail_step")
    assert "database unavailable" in args["error_message"]


# ── retry logic ───────────────────────────────────────────────────────────────

def test_step_retries_on_failure():
    mc = MockClient()
    call_count = 0

    @step(name="flaky", retries=2, retry_delay=0, client=mc)
    def flaky():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("retry me")

    with pytest.raises(ConnectionError):
        flaky()

    assert call_count == 3  # 1 initial + 2 retries


def test_step_succeeds_after_retry():
    mc = MockClient()
    call_count = 0

    @step(name="flaky", retries=2, retry_delay=0, client=mc)
    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise IOError("not ready yet")
        return "finally ok"

    result = flaky()
    assert result == "finally ok"
    assert call_count == 3
    assert mc.called("complete_step")
    assert not mc.called("fail_step")


def test_step_exhausting_retries_records_retry_count():
    mc = MockClient()

    @step(name="flaky", retries=3, retry_delay=0, client=mc)
    def always_fails():
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError):
        always_fails()

    args = mc.call_args("fail_step")
    assert args["retry_count"] == 3


# ── context propagation ───────────────────────────────────────────────────────

def test_step_id_available_inside_fn():
    mc = MockClient(step_id="step-ctx-id")
    captured = {}

    @step(name="my_step", client=mc)
    def capture():
        captured["step_id"] = get_step_id()

    capture()
    assert captured["step_id"] == "step-ctx-id"


# ── outside workflow context ──────────────────────────────────────────────────

def test_step_outside_workflow_still_calls_fn(run_context):
    """Even with no run_id, the underlying function executes normally."""
    # Temporarily clear the run_id set by the autouse fixture
    token = set_run_id(None)  # type: ignore[arg-type]
    mc = MockClient()

    @step(name="bare_step", client=mc)
    def compute():
        return 99

    result = compute()
    assert result == 99
    # no run = no step record created
    assert not mc.called("create_step")

    reset_run_id(token)
