from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from application.exceptions import ApplicationException
from application.session.exceptions import SessionException
from application.user.exceptions import UserNotFoundException
from infrastructure.http.auth.cookies import CookieManager
from infrastructure.persistence.couchdb.exceptions import (
    CouchDbConflictException,
    CouchDbNotFoundException,
)


def setup_exception_handlers(app: FastAPI) -> None:
    """Регистрация глобальных обработчиков исключений."""

    @app.exception_handler(ApplicationException)
    async def application_exception_handler(
        _: Request,
        exc: ApplicationException,
    ) -> JSONResponse:
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc)},
        )
        if isinstance(exc, (SessionException, UserNotFoundException)):
            CookieManager.clear_auth_cookies(response)
        return response

    @app.exception_handler(CouchDbConflictException)
    async def couchdb_conflict_handler(
        _: Request,
        exc: CouchDbConflictException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc)},
        )

    @app.exception_handler(CouchDbNotFoundException)
    async def couchdb_not_found_handler(
        _: Request,
        exc: CouchDbNotFoundException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )
