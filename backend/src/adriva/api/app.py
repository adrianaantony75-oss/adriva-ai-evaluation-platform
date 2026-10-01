import logging
import time
from typing import Any
from uuid import UUID, uuid4

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field

from adriva.config import Settings
from adriva.db.connection import connect
from adriva.db.migrate import ready
from adriva.domain.benchmarks import (
    create_project,
    export_benchmark,
    import_benchmark,
    publish_release,
)
from adriva.domain.contracts import BenchmarkImport, StrictModel
from adriva.domain.runs import cancel_run, create_run, register_model
from adriva.errors import DomainError
from adriva.evaluation.service import score_run
from adriva.gateway.contracts import AdapterError, ModelConfig
from adriva.logging import configure_logging

logger = logging.getLogger("adriva.api")


class ProjectInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")


class RunInput(StrictModel):
    release_id: UUID
    model_id: UUID
    repetitions: int = Field(default=1, ge=1, le=10)


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or Settings()
    configure_logging()
    app = FastAPI(
        title="ADRIVA",
        version="0.1.0",
        description="Loopback-only evaluation foundation. No production authentication.",
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Any:
        request_id = str(uuid4())
        request.state.request_id = request_id
        started = time.monotonic()
        host = request.url.hostname
        allowed_hosts = {"127.0.0.1", "localhost", "::1"}
        if configuration.environment == "test":
            allowed_hosts.add("testserver")
        if host not in allowed_hosts:
            return JSONResponse({"error": {"code": "INVALID_HOST"}}, status_code=400)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
                return JSONResponse({"error": {"code": "CROSS_ORIGIN_REJECTED"}}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"error": {"code": "CROSS_SITE_REJECTED"}}, status_code=403)
        if request.method in {"POST", "PUT", "PATCH"}:
            # Buffer only bounded JSON requests. Reject misleading Content-Length as well as actual size.
            limit = 5_000_000
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    return JSONResponse(
                        {"error": {"code": "PAYLOAD_TOO_LARGE", "request_id": request_id}},
                        status_code=413,
                    )
                chunks.append(chunk)
            request._body = b"".join(chunks)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path not in {"/docs", "/redoc"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
            )
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            },
        )
        return response

    def safe_error(request: Request, code: str, message: str, status: int) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            {"error": {"code": code, "message": message, "request_id": request_id}},
            status_code=status,
        )

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return safe_error(request, exc.code, exc.message, exc.status)

    @app.exception_handler(AdapterError)
    async def adapter_error(request: Request, exc: AdapterError) -> JSONResponse:
        return safe_error(request, exc.code, "Invalid adapter configuration", 422)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return safe_error(
            request, "VALIDATION_ERROR", "Request does not match the typed contract", 422
        )

    @app.exception_handler(psycopg.IntegrityError)
    async def integrity_error(request: Request, exc: psycopg.IntegrityError) -> JSONResponse:
        return safe_error(
            request,
            "CONSTRAINT_VIOLATION",
            "Evidence or database constraint rejected the operation",
            409,
        )

    @app.exception_handler(psycopg.OperationalError)
    async def database_error(request: Request, exc: psycopg.OperationalError) -> JSONResponse:
        return safe_error(request, "DATABASE_UNAVAILABLE", "Database operation unavailable", 503)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "request_failed",
            extra={
                "request_id": getattr(request.state, "request_id", "unknown"),
                "error_code": "INTERNAL_ERROR",
            },
        )
        return safe_error(request, "INTERNAL_ERROR", "Unexpected internal error", 500)

    @app.get("/api/v1/health/live")
    def live() -> dict[str, str]:
        return {"status": "live", "mode": "local-development"}

    @app.get("/api/v1/health/ready")
    def readiness() -> JSONResponse:
        try:
            available = ready(configuration)
        except psycopg.Error:
            available = False
        return JSONResponse(
            {"status": "ready" if available else "unavailable"},
            status_code=200 if available else 503,
        )

    @app.post("/api/v1/projects", status_code=201)
    def project_create(payload: ProjectInput) -> dict[str, UUID]:
        with connect(configuration) as db:
            return {"id": create_project(db, payload.name, payload.slug)}

    @app.get("/api/v1/projects")
    def project_list() -> list[dict[str, Any]]:
        with connect(configuration) as db:
            return db.execute(
                "SELECT id,name,slug FROM project ORDER BY created_at,id LIMIT 100"
            ).fetchall()

    @app.post("/api/v1/projects/{project_id}/benchmarks/import", status_code=201)
    def registry_import(project_id: UUID, payload: BenchmarkImport) -> dict[str, UUID]:
        if len(payload.cases) > configuration.max_import_cases:
            raise DomainError("IMPORT_LIMIT", "Import exceeds configured case limit")
        with connect(configuration) as db:
            return {"release_id": import_benchmark(db, project_id, payload)}

    @app.post("/api/v1/projects/{project_id}/releases/{release_id}/publish")
    def release_publish(project_id: UUID, release_id: UUID) -> dict[str, str]:
        with connect(configuration) as db:
            return {"manifest_digest": publish_release(db, project_id, release_id)}

    @app.get("/api/v1/projects/{project_id}/releases")
    def release_list(project_id: UUID, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        if not 0 <= offset <= 100000 or not 1 <= limit <= 100:
            raise DomainError("PAGINATION", "Invalid pagination limits")
        with connect(configuration) as db:
            return db.execute(
                "SELECT id,version,state,manifest_digest FROM benchmark_release WHERE project_id=%s ORDER BY id LIMIT %s OFFSET %s",
                (project_id, limit, offset),
            ).fetchall()

    @app.get("/api/v1/projects/{project_id}/releases/{release_id}/export")
    def release_export(project_id: UUID, release_id: UUID) -> dict[str, Any]:
        with connect(configuration) as db:
            return export_benchmark(db, project_id, release_id).model_dump(mode="json")

    @app.get("/api/v1/projects/{project_id}/coverage")
    def coverage(project_id: UUID, include_fixtures: bool = False) -> list[dict[str, Any]]:
        with connect(configuration) as db:
            return db.execute(
                "SELECT * FROM v_benchmark_coverage WHERE project_id=%s AND (%s OR usage_class<>'FIXTURE') ORDER BY release_id,split LIMIT 1000",
                (project_id, include_fixtures),
            ).fetchall()

    @app.post("/api/v1/projects/{project_id}/models", status_code=201)
    def model_register(project_id: UUID, payload: ModelConfig) -> dict[str, UUID]:
        with connect(configuration) as db:
            return {"model_id": register_model(db, project_id, payload)}

    @app.post("/api/v1/projects/{project_id}/runs", status_code=202)
    def run_create(project_id: UUID, payload: RunInput) -> dict[str, UUID]:
        with connect(configuration) as db:
            return {
                "run_id": create_run(
                    db, project_id, payload.release_id, payload.model_id, payload.repetitions
                )
            }

    @app.get("/api/v1/projects/{project_id}/runs/{run_id}")
    def run_status(project_id: UUID, run_id: UUID) -> dict[str, Any]:
        with connect(configuration) as db:
            result = db.execute(
                "SELECT * FROM v_run_completion WHERE project_id=%s AND run_id=%s",
                (project_id, run_id),
            ).fetchone()
            if not result:
                raise DomainError("NOT_FOUND", "Run not found", 404)
            return result

    @app.post("/api/v1/projects/{project_id}/runs/{run_id}/cancel")
    def run_cancel(project_id: UUID, run_id: UUID) -> dict[str, str]:
        with connect(configuration) as db:
            cancel_run(db, project_id, run_id)
        return {"state": "CANCELLED"}

    @app.post("/api/v1/projects/{project_id}/runs/{run_id}/score", status_code=201)
    def run_score(project_id: UUID, run_id: UUID) -> dict[str, UUID]:
        with connect(configuration) as db:
            return {"scoring_run_id": score_run(db, project_id, run_id)}

    @app.get("/api/v1/projects/{project_id}/responses/{response_id}")
    def response_get(project_id: UUID, response_id: UUID) -> dict[str, Any]:
        with connect(configuration) as db:
            row = db.execute(
                "SELECT id,normalized_text,finish_reason,digest FROM response WHERE id=%s AND project_id=%s",
                (response_id, project_id),
            ).fetchone()
            if not row:
                raise DomainError("NOT_FOUND", "Response not found", 404)
            return row

    from importlib.resources import files

    from fastapi.staticfiles import StaticFiles

    from adriva.api.product import product_router
    from adriva.api.reviews import reviews_router

    app.include_router(product_router(configuration))
    app.include_router(reviews_router(configuration))
    app.mount(
        "/", StaticFiles(directory=str(files("adriva").joinpath("web")), html=True), name="product"
    )
    return app


app = create_app()
