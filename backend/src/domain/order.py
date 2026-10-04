from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ProductSnapshot:
    id: UUID
    name: str
    description: str
    price: Decimal

    @classmethod
    def from_product(cls, product: Any) -> "ProductSnapshot":
        return cls(
            id=product.id,
            name=product.name,
            description=product.description,
            price=product.price,
        )


class OrderStatus(StrEnum):
    CREATED = "CREATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class Order:
    user_id: UUID
    product_id: UUID
    quantity: int
    unit_price: Decimal
    product_snapshot: ProductSnapshot
    id: UUID = field(default_factory=uuid4)
    status: OrderStatus = OrderStatus.CREATED
    total_amount: Decimal = field(default=Decimal("0.00"))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")
        if self.unit_price < Decimal("0.00"):
            raise ValueError("Unit price cannot be negative")
        if self.total_amount == Decimal("0.00"):
            self.total_amount = self.unit_price * Decimal(self.quantity)
