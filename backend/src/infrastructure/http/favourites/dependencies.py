from functools import cache
from typing import Annotated

from fastapi import Depends

from application.favourites.repository import IFavouritesRepository
from application.favourites.service import FavouritesService
from infrastructure.event_bus.dependencies import EventBusDep
from infrastructure.http.product.dependencies import ProductServiceDep
from infrastructure.persistence.riak.favourites_repository import (
    RiakFavouritesRepository,
)


@cache
def get_favourites_repository() -> IFavouritesRepository:
    return RiakFavouritesRepository()


FavouritesRepositoryDep = Annotated[
    IFavouritesRepository, Depends(get_favourites_repository)
]


def get_favourites_service(
    favourites_repository: FavouritesRepositoryDep,
    product_service: ProductServiceDep,
    event_bus: EventBusDep,
) -> FavouritesService:
    return FavouritesService(
        favourites_repository=favourites_repository,
        product_service=product_service,
        event_bus=event_bus,
    )


FavouritesServiceDep = Annotated[FavouritesService, Depends(get_favourites_service)]
