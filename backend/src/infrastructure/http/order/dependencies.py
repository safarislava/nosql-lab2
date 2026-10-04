from functools import cache
from typing import Annotated

from fastapi import Depends

from application.order.counter_repository import IOrderCounterRepository
from application.order.repository import IOrderRepository
from application.order.service import OrderService
from infrastructure.event_bus.dependencies import EventBusDep
from infrastructure.http.product.dependencies import ProductServiceDep
from infrastructure.persistence.postgres.order_repository import (
    PostgresOrderRepository,
)
from infrastructure.persistence.riak.order_counter_repository import (
    RiakOrderCounterRepository,
)


@cache
def get_order_repository() -> IOrderRepository:
    return PostgresOrderRepository()


@cache
def get_counter_repository() -> IOrderCounterRepository:
    return RiakOrderCounterRepository()


OrderRepositoryDep = Annotated[IOrderRepository, Depends(get_order_repository)]
CounterRepositoryDep = Annotated[
    IOrderCounterRepository, Depends(get_counter_repository)
]


def get_order_service(
    order_repository: OrderRepositoryDep,
    counter_repository: CounterRepositoryDep,
    product_service: ProductServiceDep,
    event_bus: EventBusDep,
) -> OrderService:
    return OrderService(
        order_repository=order_repository,
        counter_repository=counter_repository,
        product_service=product_service,
        event_bus=event_bus,
    )


OrderServiceDep = Annotated[OrderService, Depends(get_order_service)]
