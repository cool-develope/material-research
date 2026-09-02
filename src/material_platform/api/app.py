from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.runtime = bound or Runtime(configured or Settings())
        yield

    app = FastAPI(title="Material Platform", lifespan=lifespan)
    app.include_router(router)
    return app
