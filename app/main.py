import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import db
from app.api import router
from app.config import Settings
from app.log import configure_logging, log_event
from app.worker import Worker


class BodySizeLimit:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        declared = headers.get(b"content-length", b"0")
        if declared.isdigit() and int(declared) > self.max_bytes:
            response = JSONResponse({"detail": "Request body too large"}, status_code=413)
            await response(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                raise HTTPException(status_code=413, detail="Request body too large")
            return message

        await self.app(scope, limited_receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.api_pool = await db.create_api_pool(settings)
        app.state.worker_pool = await db.create_worker_pool(settings)
        await db.apply_schema(app.state.worker_pool)
        worker = Worker(app.state.worker_pool, settings)
        worker.start()
        yield
        await worker.stop()
        await app.state.worker_pool.close()
        await app.state.api_pool.close()

    app = FastAPI(title="Transaction Webhook Service", lifespan=lifespan)
    app.add_middleware(BodySizeLimit, max_bytes=settings.max_body_bytes)
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )
    app.include_router(router)

    async def database_unavailable(request: Request, exc: Exception) -> JSONResponse:
        log_event(logging.ERROR, "database.unavailable", path=request.url.path, error=repr(exc))
        return JSONResponse({"detail": "Service temporarily unavailable"}, status_code=503)

    for error in (asyncpg.PostgresError, asyncpg.InterfaceError, OSError):
        app.add_exception_handler(error, database_unavailable)

    return app
