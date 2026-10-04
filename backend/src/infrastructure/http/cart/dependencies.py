from functools import cache
from typing import Annotated

from fastapi import Depends

from application.cart.repository import ICartRepository
from application.cart.service import CartService
from infrastructure.event_bus.dependencies import EventBusDep
from infrastructure.http.product.dependencies import ProductServiceDep
from infrastructure.persistence.riak.cart_repository import RiakCartRepository


@cache
def get_cart_repository() -> ICartRepository:
    return RiakCartRepository()


CartRepositoryDep = Annotated[ICartRepository, Depends(get_cart_repository)]


def get_cart_service(
    cart_repository: CartRepositoryDep,
    product_service: ProductServiceDep,
    event_bus: EventBusDep,
) -> CartService:
    return CartService(
        cart_repository=cart_repository,
        product_service=product_service,
        event_bus=event_bus,
    )


CartServiceDep = Annotated[CartService, Depends(get_cart_service)]
