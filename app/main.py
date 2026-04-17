from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routers.auth import router as auth_router
from app.api.routers.rounds import router as rounds_router
from app.api.routers.stages import router as stages_router
from app.api.routers.users import router as users_router
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.db.session import SessionLocal
from app.seed_data import seed_initial_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_seed_on_startup:
        with SessionLocal() as db:
            seed_initial_data(db)
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.message, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0]["msg"] if exc.errors() else "잘못된 요청입니다."
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": first_error, "data": None},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": str(exc), "data": None},
    )


@app.get("/health")
def healthcheck():
    return {"status": "success", "message": "ok", "data": None}


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(stages_router)
app.include_router(rounds_router)
