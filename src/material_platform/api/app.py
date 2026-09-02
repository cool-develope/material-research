from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from material_platform.api.routes import router
from material_platform.application.runtime import Runtime
from material_platform.config import Settings


def create_app(
    *,
    runtime: Runtime | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    bound = runtime
    configured = settings
    resolved = configured or (bound.settings if bound is not None else Settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.runtime = bound or Runtime(configured or Settings())
        yield

    app = FastAPI(title="Material Platform", lifespan=lifespan)
    origins = [
        item.strip() for item in resolved.cors_origins.split(",") if item.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app
