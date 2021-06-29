import asyncio
import threading


class TaskHandler:
    """Helper to manage asyncio tasks in one spot."""

    def __init__(self):
        self.tasks = []
        self._lock = threading.Lock()

    def create(self, coro):
        """Schedule the execution of a coroutine object in a spawn task."""
        task = asyncio.create_task(coro)
        with self._lock:
            self.tasks.append(task)
        task.add_done_callback(self._remove_completed_task)
        return task

    def _remove_completed_task(self, task):
        try:
            with self._lock:
                self.tasks.remove(task)
        except ValueError:
            # May have been cancelled or removed otherwise
            ...

    @staticmethod
    async def cancel(task):
        task.cancel()
        await task

    async def cancel_all(self, wait=False):
        with self._lock:
            tasks = list(self.tasks)
            self.tasks.clear()

        for task in list(tasks):
            task.cancel()

        if wait and len(tasks):
            await asyncio.wait(tasks)
