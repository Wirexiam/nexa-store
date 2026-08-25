"""In-process execution job coordination and cooperative cancellation."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Condition, Event, Lock
from typing import Any, Callable, MutableMapping

from ..config import settings
from .executors.base import discard_transient_mapping

JobTarget = Callable[[Event, MutableMapping[str, Any]], None]


class ExecutionAlreadyRunning(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StopRequest:
    found: bool
    canceled_before_start: bool = False


@dataclass(slots=True)
class _ExecutionJob:
    future: Future[None]
    stop_event: Event
    transient_data: MutableMapping[str, Any]


class ExecutionManager:
    """Run fulfillment jobs without retaining temporary customer data.

    This is deliberately an in-process coordinator. It provides bounded
    concurrency and cooperative cancellation for the local deployment while
    keeping the service layer replaceable by a durable queue later.
    """

    def __init__(self, *, max_workers: int = 4) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="nexa-execution",
        )
        self._lock = Lock()
        self._idle = Condition(self._lock)
        self._jobs: dict[str, _ExecutionJob] = {}
        self._closed = False

    def submit(
        self,
        order_id: str,
        target: JobTarget,
        transient_data: MutableMapping[str, Any],
    ) -> None:
        stop_event = Event()
        with self._lock:
            if self._closed:
                discard_transient_mapping(transient_data)
                raise RuntimeError("Execution manager has stopped")
            current = self._jobs.get(order_id)
            if current is not None and not current.future.done():
                discard_transient_mapping(transient_data)
                raise ExecutionAlreadyRunning("This order already has an active execution")

            future = self._pool.submit(
                self._run_target,
                target,
                stop_event,
                transient_data,
            )
            job = _ExecutionJob(
                future=future,
                stop_event=stop_event,
                transient_data=transient_data,
            )
            self._jobs[order_id] = job
        # add_done_callback() can call synchronously when the future already
        # finished, so install it after releasing the non-reentrant lock.
        future.add_done_callback(
            lambda completed, key=order_id: self._finish(key, completed)
        )

    def request_stop(self, order_id: str) -> StopRequest:
        with self._lock:
            job = self._jobs.get(order_id)
        if job is None or job.future.done():
            return StopRequest(found=False)

        job.stop_event.set()
        # cancel() only succeeds while queued. The done callback clears the
        # payload in that path because _run_target never receives it.
        canceled = job.future.cancel()
        return StopRequest(found=True, canceled_before_start=canceled)

    def is_active(self, order_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(order_id)
            return job is not None and not job.future.done()

    def wait_for_idle(self, order_id: str, timeout: float | None = None) -> bool:
        """Wait until a job is removed; primarily useful for tests/shutdown."""

        with self._idle:
            return self._idle.wait_for(
                lambda: order_id not in self._jobs,
                timeout=timeout,
            )

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            jobs = list(self._jobs.values())
        for job in jobs:
            job.stop_event.set()
            job.future.cancel()
        self._pool.shutdown(wait=wait, cancel_futures=True)

    @staticmethod
    def _run_target(
        target: JobTarget,
        stop_event: Event,
        transient_data: MutableMapping[str, Any],
    ) -> None:
        try:
            target(stop_event, transient_data)
        finally:
            # Executors also clear their mapping. Repeating this operation is
            # harmless and covers failures before executor construction.
            discard_transient_mapping(transient_data)

    def _finish(self, order_id: str, future: Future[None]) -> None:
        with self._idle:
            job = self._jobs.get(order_id)
            if job is not None and job.future is future:
                discard_transient_mapping(job.transient_data)
                self._jobs.pop(order_id, None)
            self._idle.notify_all()


def _configured_worker_count() -> int:
    raw_value = getattr(settings, "execution_max_workers", 4)
    try:
        return max(1, min(32, int(raw_value)))
    except (TypeError, ValueError):
        return 4


execution_manager = ExecutionManager(max_workers=_configured_worker_count())
