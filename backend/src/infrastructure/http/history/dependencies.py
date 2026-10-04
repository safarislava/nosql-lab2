from functools import cache
from typing import Annotated

from fastapi import Depends

from application.history.repository import IHistoryRepository
from application.history.service import HistoryService
from infrastructure.event_bus.dependencies import get_event_bus
from infrastructure.persistence.composite.history_repository import (
    CompositeHistoryRepository,
)
from infrastructure.persistence.postgres.history_repository import (
    PostgresHistoryRepository,
)
from infrastructure.persistence.riak.history_cache_repository import (
    RiakHistoryCacheRepository,
)


@cache
def get_postgres_history_repository() -> PostgresHistoryRepository:
    return PostgresHistoryRepository()


@cache
def get_riak_history_cache_repository() -> RiakHistoryCacheRepository:
    return RiakHistoryCacheRepository()


@cache
def get_history_repository() -> IHistoryRepository:
    return CompositeHistoryRepository(
        postgres_repo=get_postgres_history_repository(),
        riak_repo=get_riak_history_cache_repository(),
    )


HistoryRepositoryDep = Annotated[IHistoryRepository, Depends(get_history_repository)]


@cache
def get_history_service() -> HistoryService:
    return HistoryService(
        history_repository=get_history_repository(),
        event_bus=get_event_bus(),
    )


HistoryServiceDep = Annotated[HistoryService, Depends(get_history_service)]

