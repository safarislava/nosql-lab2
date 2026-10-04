import logging
from functools import cache
from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from infrastructure.environment.settings import settings

logger = logging.getLogger(__name__)

_INIT_SQL = Path(__file__).resolve().parents[4] / "scripts" / "init_postgres.sql"


@cache
def get_postgres_pool() -> ConnectionPool:
    """Синглтон пула соединений PostgreSQL."""
    return ConnectionPool(
        conninfo=settings.postgres.conninfo,
        min_size=settings.postgres.min_connections,
        max_size=settings.postgres.max_connections,
        open=True,
        kwargs={"row_factory": dict_row},
    )


def close_postgres_pool() -> None:
    """Закрыть пул соединений PostgreSQL."""
    get_postgres_pool().close()


def init_db() -> None:
    if not _INIT_SQL.exists():
        logger.warning("PostgreSQL init script not found at %s", _INIT_SQL)
        return

    with get_postgres_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(_INIT_SQL.read_bytes())
        conn.commit()
    logger.info("PostgreSQL schema initialized from %s", _INIT_SQL.name)
