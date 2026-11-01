import asyncio
import logging
from uuid import UUID

import asyncpg

from app import repository
from app.config import Settings
from app.log import log_event


class Worker:
    def __init__(self, pool: asyncpg.Pool, settings: Settings) -> None:
        self._pool = pool
        self._settings = settings
        self._jobs: set[asyncio.Task[None]] = set()
        self._loop_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._loop_task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        # Cancelled rows are picked up again when their lease expires.
        tasks = [*self._jobs]
        if self._loop_task:
            tasks.append(self._loop_task)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self) -> None:
        while True:
            try:
                await self._claim_available()
            except Exception as exc:
                log_event(logging.ERROR, "worker.error", error=repr(exc))
            await asyncio.sleep(self._settings.poll_interval_seconds)

    async def _claim_available(self) -> None:
        free_slots = self._settings.worker_concurrency - len(self._jobs)
        if free_slots <= 0:
            return
        rows = await repository.claim_transactions(
            self._pool, free_slots, self._settings.lease_seconds
        )
        for row in rows:
            log_event(
                logging.INFO,
                "transaction.claimed",
                transaction_id=row["transaction_id"],
                attempts=row["attempts"],
            )
            job = asyncio.create_task(self._process(row["transaction_id"], row["lease_token"]))
            self._jobs.add(job)
            job.add_done_callback(self._jobs.discard)

    async def _process(self, transaction_id: str, lease_token: UUID) -> None:
        try:
            # No connection is held here, so the delay does not limit the pool.
            await asyncio.sleep(self._settings.processing_delay_seconds)
            duration = await repository.complete_transaction(
                self._pool, transaction_id, lease_token
            )
        except Exception as exc:
            log_event(
                logging.ERROR,
                "worker.error",
                transaction_id=transaction_id,
                error=repr(exc),
            )
            return

        if duration is None:
            log_event(logging.WARNING, "transaction.lease_lost", transaction_id=transaction_id)
        else:
            log_event(
                logging.INFO,
                "transaction.processed",
                transaction_id=transaction_id,
                duration_seconds=round(duration, 3),
            )
