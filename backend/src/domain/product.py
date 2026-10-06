from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass
class Product:
    name: str
    description: str
    price: Decimal
    quantity: int
    id: UUID = field(default_factory=uuid4)
    attachment_ids: list[UUID] = field(default_factory=list)
    category_ids: list[UUID] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    orders_count: int = 0

    def is_in_stock(self) -> bool:
        return self.quantity > 0

    def has_enough_stock(self, required_quantity: int) -> bool:
        return self.quantity >= required_quantity
