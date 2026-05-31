import asyncio
import logging
import time
from typing import Dict, Generic, List, Any, Callable, TypeVar, Awaitable, Optional, Tuple, Union

T = TypeVar('T')  # Type variable for task results


logger = logging.getLogger("deribridge.rate_limiter")


class RateLimiter:
    """Simple rate limiter for API requests."""

    def __init__(self, rate_limit: int):
        """
        Initialize rate limiter.

        Args:
            rate_limit: Maximum number of requests per second
        """
        self.rate_limit = rate_limit
        self.tokens = rate_limit
        self.updated_at = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Acquire a token, waiting if necessary."""
        while True:
            async with self.lock:
                now = time.monotonic()
                elapsed = now - self.updated_at

                self.tokens = min(self.rate_limit, self.tokens + elapsed * self.rate_limit)
                self.updated_at = now

                if self.tokens >= 1:
                    self.tokens -= 1
                    return

                wait_time = (1 - self.tokens) / self.rate_limit

            # Sleep outside the lock so other coroutines can proceed
            await asyncio.sleep(wait_time)


class TaskGroup(Generic[T]):
    """Group of related tasks with metadata and named task access."""

    def __init__(
            self,
            name: str,
            tasks: List[Union[
                Tuple[Callable[..., Awaitable[T]], Dict[str, Any]],  # Original format
                Tuple[Callable[..., Awaitable[T]], Dict[str, Any], str]  # New format with task name
            ]]
    ):
        """
        Initialize a task group.

        Args:
            name: Name of the task group
            tasks: List of (coroutine_function, kwargs) tuples or
                  (coroutine_function, kwargs, task_name) tuples
        """
        self.name = name
        self.tasks = tasks
        # Results and errors are indexed by the task's ORIGINAL input position,
        # so they stay aligned with `tasks` regardless of completion order.
        self.results: List[Optional[T]] = [None] * len(tasks)
        self.errors: List[Optional[Exception]] = [None] * len(tasks)
        self.named_results: Dict[str, Optional[T]] = {}
        self.named_errors: Dict[str, Exception] = {}

        # Extract task names for easy lookup
        self.task_names: Dict[int, str] = {}
        for i, task in enumerate(tasks):
            if len(task) > 2:  # It has a name
                self.task_names[i] = task[2]

    def get_result(self, task_id: Union[int, str]) -> Optional[T]:
        """
        Get the result of a task by index or name.

        The index refers to the task's original position in the input list,
        not its completion order.

        Args:
            task_id: Index (int) or name (str) of the task

        Returns:
            The task result, or None if not found
        """
        if isinstance(task_id, int):
            # Get by original input index
            if 0 <= task_id < len(self.results):
                return self.results[task_id]
        else:
            # Get by name
            return self.named_results.get(task_id)
        return None

    def get_error(self, task_id: Union[int, str]) -> Optional[Exception]:
        """
        Get the error of a task by index or name.

        The index refers to the task's original position in the input list,
        not its completion order.

        Args:
            task_id: Index (int) or name (str) of the task

        Returns:
            The task error, or None if not found
        """
        if isinstance(task_id, int):
            # Get by original input index
            if 0 <= task_id < len(self.errors):
                return self.errors[task_id]
            return None
        else:
            # Get by name
            return self.named_errors.get(task_id)

    def get_task_name(self, index: int) -> Optional[str]:
        """Get the name of a task by index."""
        return self.task_names.get(index)

    def get_task_names(self) -> List[str]:
        """Get all task names in this group."""
        return list(self.named_results.keys())


async def run_rate_limited_tasks(
        task_groups: Dict[str, List[Union[
            Tuple[Callable[..., Awaitable[T]], Dict[str, Any]],  # Original format
            Tuple[Callable[..., Awaitable[T]], Dict[str, Any], str]  # New format with task name
        ]]],
        rate_limit: int = 5,
        error_handler: Optional[Callable[[str, Exception], None]] = None
) -> Dict[str, TaskGroup[T]]:
    """
    Run multiple groups of tasks concurrently with rate limiting.

    Args:
        task_groups: Dictionary mapping group names to lists of
                    (coroutine_function, kwargs) tuples or
                    (coroutine_function, kwargs, task_name) tuples
        rate_limit: Maximum requests per second
        error_handler: Optional function to handle errors

    Returns:
        Dictionary mapping group names to TaskGroup objects containing results
    """
    # Create rate limiter
    limiter = RateLimiter(rate_limit)

    # Create task groups
    groups: Dict[str, TaskGroup[T]] = {
        name: TaskGroup(name, tasks)
        for name, tasks in task_groups.items()
    }

    async def wrapped_task(group_name: str, task_fn: Callable, task_kwargs: Dict[str, Any], index: int):
        """Wrap a task with rate limiting and error handling."""
        # Get task name if available
        task_name = groups[group_name].get_task_name(index)

        try:
            # Acquire rate limit token
            await limiter.acquire()

            # Execute the task
            start_time = time.monotonic()
            result = await task_fn(**task_kwargs)
            elapsed = time.monotonic() - start_time

            # Store the result at the task's ORIGINAL input index so positional
            # lookups stay correct regardless of completion order.
            groups[group_name].results[index] = result

            # If there's a task name, also store in the named dictionary
            if task_name:
                groups[group_name].named_results[task_name] = result

            # For logging
            task_id = task_name if task_name else f"{index}"
            logger.debug(f"✓ {group_name} task {task_id} completed in {elapsed:.3f}s")

            return result

        except Exception as e:
            # Store null result and the error at the task's ORIGINAL input index
            # so positional lookups stay aligned with the input list.
            groups[group_name].results[index] = None
            groups[group_name].errors[index] = e

            # If there's a task name, also store in the named dictionary
            if task_name:
                groups[group_name].named_errors[task_name] = e

            # Handle the error
            if error_handler:
                error_handler(group_name, e)
            else:
                task_id = task_name if task_name else f"{index}"
                logger.error(f"✗ Error in {group_name} task {task_id}: {str(e)}")

            return None

    # Create all tasks
    all_tasks = []

    for group_name, task_list in task_groups.items():
        for i, task_tuple in enumerate(task_list):
            # Handle the task tuple
            task_fn = task_tuple[0]
            task_kwargs = task_tuple[1]

            task = wrapped_task(group_name, task_fn, task_kwargs, i)
            all_tasks.append(task)

    # Run all tasks concurrently
    await asyncio.gather(*all_tasks)

    return groups
