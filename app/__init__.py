from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

from . import db, mongo
from .auth import check_csrf
from .lifecycle import RuleError
from .main_config import ROOT, database_url, mongo_name, mongo_url, production, secret_key
from .routes import account, admin, attachments, cases, complaints, criminals

DIST = ROOT / "frontend" / "dist"


def create_app(database=None, secret=None, mongo_client=None):
    path = database or database_url()
    if db.dialect_of(path) == "sqlite":
        Path(path.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    db.init_db(path)
    mongo.configure(mongo_url(), mongo_name(), client=mongo_client)

    app = FastAPI(title="Crime Records Management System", dependencies=[Depends(check_csrf)])

    app.state.database_url = path

    @app.middleware("http")
    async def connection(request: Request, call_next):
        token = db.use(db.connect(path))
        try:
            return await call_next(request)
        finally:
            db.release(token)

    app.add_middleware(
        SessionMiddleware, secret_key=secret or secret_key(), same_site="lax", max_age=7 * 24 * 3600,
        https_only=production(),  # behind HTTPS the cookie is never sent in the clear
    )

    for module in (account, complaints, attachments, cases, criminals, admin):
        app.include_router(module.router)

    @app.exception_handler(RuleError)
    async def rule_error(request: Request, exc: RuleError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(RequestValidationError)
    async def bad_input(request: Request, exc: RequestValidationError):
        return JSONResponse({"detail": "That request could not be read."}, status_code=400)

    # the built React app; any non-API path falls back to index.html so client routes work
    if DIST.exists():
        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str):
            if path.startswith("api/"):
                raise HTTPException(404, "Not found.")
            target = (DIST / path).resolve()
            if path and target.is_file() and DIST in target.parents:
                return FileResponse(target)
            return FileResponse(DIST / "index.html")

    return app
