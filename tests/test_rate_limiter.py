"""Tests for the rate limiter and task-group result mapping.

Covers a Tier 1 correctness bug: results were stored in COMPLETION order
(via ``list.append``) while callers read them positionally with
``get_result(index)``, expecting INPUT order. When a later-submitted task
finished before an earlier one, ``get_result(N)`` returned the wrong task's
result. Results (and errors) are now indexed by original input position.
"""
import asyncio

from deribridge.api_client.rate_limiter import (
    RateLimiter,
    TaskGroup,
    run_rate_limited_tasks,
)


async def _slow_echo(value, delay):
    """Return ``value`` after sleeping ``delay`` seconds."""
    await asyncio.sleep(delay)
    return value


async def _boom(delay):
    """Sleep, then raise so we can test error positioning."""
    await asyncio.sleep(delay)
    raise ValueError("boom")


async def test_results_follow_input_order_when_completion_is_reversed():
    # Task 0 sleeps longest, task 2 finishes first -> completion order is
    # the reverse of input order. With the old append-based code, get_result(0)
    # would return task 2's value.
    task_groups = {
        "group": [
            (_slow_echo, {"value": "first", "delay": 0.06}),
            (_slow_echo, {"value": "second", "delay": 0.03}),
            (_slow_echo, {"value": "third", "delay": 0.0}),
        ]
    }

    groups = await run_rate_limited_tasks(task_groups, rate_limit=100)
    group = groups["group"]

    assert group.get_result(0) == "first"
    assert group.get_result(1) == "second"
    assert group.get_result(2) == "third"
    assert group.results == ["first", "second", "third"]


async def test_named_results_match_their_task_regardless_of_completion():
    task_groups = {
        "group": [
            (_slow_echo, {"value": "A", "delay": 0.06}, "alpha"),
            (_slow_echo, {"value": "B", "delay": 0.0}, "beta"),
        ]
    }

    groups = await run_rate_limited_tasks(task_groups, rate_limit=100)
    group = groups["group"]

    # Positional and named lookups must agree even though "beta" finished first.
    assert group.get_result(0) == "A"
    assert group.get_result(1) == "B"
    assert group.get_result("alpha") == "A"
    assert group.get_result("beta") == "B"


async def test_error_is_stored_at_input_index_not_completion_index():
    # The failing task (index 1) finishes first; the successful tasks finish
    # later. The error must land at index 1, and successful results at 0 and 2.
    errors_seen = []

    def handler(group_name, exc):
        errors_seen.append((group_name, exc))

    task_groups = {
        "group": [
            (_slow_echo, {"value": "ok0", "delay": 0.05}),
            (_boom, {"delay": 0.0}),
            (_slow_echo, {"value": "ok2", "delay": 0.05}),
        ]
    }

    groups = await run_rate_limited_tasks(
        task_groups, rate_limit=100, error_handler=handler
    )
    group = groups["group"]

    assert group.get_result(0) == "ok0"
    assert group.get_result(1) is None
    assert group.get_result(2) == "ok2"

    assert group.get_error(0) is None
    assert isinstance(group.get_error(1), ValueError)
    assert group.get_error(2) is None

    assert len(errors_seen) == 1
    assert errors_seen[0][0] == "group"


async def test_get_result_out_of_range_returns_none():
    group: TaskGroup[str] = TaskGroup("g", [(_slow_echo, {"value": "x", "delay": 0.0})])
    assert group.get_result(5) is None
    assert group.get_result(-1) is None
    assert group.get_result("missing") is None
    assert group.get_error(5) is None


async def test_rate_limiter_throttles_when_over_limit():
    # With a rate limit of 5/s, issuing 6 acquisitions must take at least the
    # refill time for the 6th token (~1/5 s).
    limiter = RateLimiter(rate_limit=5)
    start = asyncio.get_event_loop().time()
    for _ in range(6):
        await limiter.acquire()
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed >= 0.18
