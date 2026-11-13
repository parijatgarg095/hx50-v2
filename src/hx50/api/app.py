"""FastAPI application factory.  Run with:  hx50 serve   (or uvicorn hx50.api:create_app --factory)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .. import __version__
from ..config import Settings
from ..domain import InsufficientUniverse, InvalidMandate
from ..service import IndexService, RebuildInProgress
from ..storage import IndexNotBuilt
from .routes import router

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# Domain failures carry their own meaning; the HTTP status is decided here, once.
ERROR_STATUS: dict[type[Exception], int] = {
    InvalidMandate: 422,
    InsufficientUniverse: 422,
    RebuildInProgress: 409,
    IndexNotBuilt: 503,
}


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="HX-50 Index API",
        version=__version__,
        description="Equal-weighted US large caps ranked 11-60 by market cap, rebalanced weekly.",
    )
    app.state.service = IndexService(settings or Settings.from_env())
    app.include_router(router)
    _register_error_handlers(app)
    _mount_ui(app)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    for error_type, status in ERROR_STATUS.items():
        app.add_exception_handler(error_type, _responder(status))


def _responder(status: int):
    async def respond(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=status)

    return respond


def _mount_ui(app: FastAPI) -> None:
    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")
