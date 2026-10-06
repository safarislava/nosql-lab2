from uuid import UUID

from application.event_bus import IEventBus
from application.product.service import ProductService
from domain.history import OperationEvent, OperationType
from domain.order import Order, OrderStatus, ProductSnapshot

from .counter_repository import IOrderCounterRepository
from .dto import (
    CreateOrderDto,
    OrderFilterDto,
    OrderListResponseDto,
    OrderResponseDto,
)
from .exceptions import (
    InvalidOrderQuantityException,
    InvalidOrderStatusException,
    OrderNotFoundException,
)
from .repository import IOrderRepository


class OrderService:
    def __init__(
        self,
        order_repository: IOrderRepository,
        product_service: ProductService,
        event_bus: IEventBus,
        counter_repository: IOrderCounterRepository,
    ) -> None:
        self._order_repository = order_repository
        self._product_service = product_service
        self._event_bus = event_bus
        self._counter_repository = counter_repository

    def create(self, user_id: UUID, dto: CreateOrderDto) -> OrderResponseDto:
        if dto.quantity <= 0:
            raise InvalidOrderQuantityException()

        product = self._product_service.reserve_stock(dto.product_id, dto.quantity)
        snapshot = ProductSnapshot.from_product(product)

        order = Order(
            user_id=user_id,
            product_id=dto.product_id,
            quantity=dto.quantity,
            unit_price=product.price,
            product_snapshot=snapshot,
        )

        saved = self._order_repository.save(order)
        self._counter_repository.increment(user_id)
        self._product_service.increment_orders_count(dto.product_id, 1)

        self._event_bus.publish(
            OperationEvent(
                user_id=user_id,
                action=OperationType.CREATE_ORDER,
                target_id=saved.id,
                details={
                    "product_id": str(saved.product_id),
                    "product_name": product.name,
                    "quantity": saved.quantity,
                    "total_amount": f"{saved.total_amount:.2f}",
                },
            )
        )

        return OrderResponseDto.from_domain(saved)

    def get_by_id(
        self,
        order_id: UUID,
        user_id: UUID | None = None,
    ) -> OrderResponseDto:
        order = self._order_repository.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundException(order_id)

        if user_id is not None and order.user_id != user_id:
            raise OrderNotFoundException(order_id)

        return OrderResponseDto.from_domain(order)

    def list(
        self,
        filter_dto: OrderFilterDto | None = None,
    ) -> OrderListResponseDto:
        if filter_dto is None:
            filter_dto = OrderFilterDto()

        items = self._order_repository.list(filter_dto=filter_dto)
        return OrderListResponseDto(
            items=[OrderResponseDto.from_domain(o) for o in items],
            offset=filter_dto.offset,
            limit=filter_dto.limit,
        )

    def list_user_orders(
        self,
        user_id: UUID,
        status: OrderStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> OrderListResponseDto:
        filter_dto = OrderFilterDto(
            user_id=user_id,
            status=status,
            offset=offset,
            limit=limit,
        )
        return self.list(filter_dto)

    def cancel(
        self,
        order_id: UUID,
        user_id: UUID | None = None,
    ) -> OrderResponseDto:
        order = self._order_repository.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundException(order_id)

        if user_id is not None and order.user_id != user_id:
            raise OrderNotFoundException(order_id)

        if order.status != OrderStatus.CREATED:
            raise InvalidOrderStatusException(
                f"Невозможно отменить заказ со статусом {order.status}. "
                f"Отмена доступна только для заказов в статусе CREATED (до одобрения)."
            )

        updated_order = self._order_repository.update_status_and_get(
            order_id, OrderStatus.CANCELLED, expected_status=OrderStatus.CREATED
        )
        if updated_order is None:
            order = self._order_repository.get_by_id(order_id)
            curr_status = order.status if order else "UNKNOWN"
            raise InvalidOrderStatusException(
                f"Невозможно отменить заказ со статусом {curr_status}. "
                f"Отмена доступна только для заказов в статусе CREATED (до одобрения)."
            )

        self._product_service.restore_stock(
            updated_order.product_id, updated_order.quantity
        )
        self._product_service.decrement_orders_count(
            updated_order.product_id, 1
        )

        self._event_bus.publish(
            OperationEvent(
                user_id=updated_order.user_id,
                action=OperationType.CANCEL_ORDER,
                target_id=updated_order.id,
                details={
                    "product_id": str(updated_order.product_id),
                    "quantity": updated_order.quantity,
                },
            )
        )

        return OrderResponseDto.from_domain(updated_order)

    def approve(self, order_id: UUID) -> OrderResponseDto:
        updated_order = self._order_repository.update_status_and_get(
            order_id, OrderStatus.APPROVED, expected_status=OrderStatus.CREATED
        )
        if updated_order is None:
            order = self._order_repository.get_by_id(order_id)
            if order is None:
                raise OrderNotFoundException(order_id)
            raise InvalidOrderStatusException(
                f"Cannot approve order with status {order.status}"
            )

        self._event_bus.publish(
            OperationEvent(
                user_id=updated_order.user_id,
                action=OperationType.APPROVE_ORDER,
                target_id=updated_order.id,
            )
        )

        return OrderResponseDto.from_domain(updated_order)

    def reject(self, order_id: UUID) -> OrderResponseDto:
        updated_order = self._order_repository.update_status_and_get(
            order_id, OrderStatus.REJECTED, expected_status=OrderStatus.CREATED
        )
        if updated_order is None:
            order = self._order_repository.get_by_id(order_id)
            if order is None:
                raise OrderNotFoundException(order_id)
            raise InvalidOrderStatusException(
                f"Cannot reject order with status {order.status}"
            )

        self._product_service.restore_stock(
            updated_order.product_id, updated_order.quantity
        )
        self._product_service.decrement_orders_count(
            updated_order.product_id, 1
        )

        self._event_bus.publish(
            OperationEvent(
                user_id=updated_order.user_id,
                action=OperationType.REJECT_ORDER,
                target_id=updated_order.id,
            )
        )

        return OrderResponseDto.from_domain(updated_order)

    def get_user_orders_count(self, user_id: UUID) -> int:
        return self._counter_repository.get_by_user_id(user_id)

    def get_total_orders_count(self) -> int:
        return self._counter_repository.get_total_count()
