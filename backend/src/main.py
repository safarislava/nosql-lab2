import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI

from infrastructure.environment.settings import settings
from infrastructure.http.auth.controller import router as auth_router
from infrastructure.http.auth.dependencies import get_token_service
from infrastructure.http.cart.controller import router as cart_router
from infrastructure.http.checkout.controller import router as checkout_router
from infrastructure.http.exception_handlers import setup_exception_handlers
from infrastructure.http.favourites.controller import router as favourites_router
from infrastructure.http.health.controller import router as health_router
from infrastructure.http.history.controller import router as history_router
from infrastructure.http.middleware.authentication_middleware import (
    authentication_middleware,
)
from infrastructure.http.openapi import generate_openapi_schema
from infrastructure.http.order.controller import router as order_router
from infrastructure.http.product.controller import router as product_router
from infrastructure.http.recovery.controller import router as recovery_router
from infrastructure.http.teacher.controller import router as teacher_router
from infrastructure.http.user.controller import router as user_router
from infrastructure.persistence.couchdb.category_migrator import (
    CategoryMigrator,
)
from infrastructure.persistence.couchdb.client import close_couchdb_client
from infrastructure.persistence.postgres.connection import close_postgres_pool, init_db
from infrastructure.persistence.riak.client import close_riak_client

logger = logging.getLogger(__name__)


def _run_auto_migration() -> None:
    try:
        migrator = CategoryMigrator()
        if settings.app_version >= 2:
            stats = migrator.migrate_all_to_v2()
            if stats.migrated_products > 0:
                logger.info(
                    "Автомиграция CouchDB (v1 -> v2): обновлено %d товаров, перенесено %d категорий",
                    stats.migrated_products,
                    stats.migrated_categories,
                )
        else:
            stats = migrator.migrate_all_to_v1()
            if stats.migrated_products > 0:
                logger.info(
                    "Автомиграция CouchDB (v2 -> v1): обновлено %d товаров, возвращено %d категорий",
                    stats.migrated_products,
                    stats.migrated_categories,
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ошибка автомиграции CouchDB: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    init_db()
    asyncio.create_task(asyncio.to_thread(_run_auto_migration))
    yield
    close_postgres_pool()
    close_riak_client()
    close_couchdb_client()


class App(FastAPI):
    def openapi(self) -> dict[str, Any]:
        return generate_openapi_schema(self)


app = App(title="Our site", lifespan=lifespan)

setup_exception_handlers(app)

app.add_middleware(authentication_middleware(token_service=get_token_service()))

app.include_router(health_router, prefix="/api")
app.include_router(user_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(product_router, prefix="/api")
app.include_router(favourites_router, prefix="/api")
app.include_router(cart_router, prefix="/api")
app.include_router(checkout_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(teacher_router, prefix="/api")
app.include_router(recovery_router, prefix="/api")
app.include_router(order_router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
