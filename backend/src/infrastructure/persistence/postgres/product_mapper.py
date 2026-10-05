from decimal import Decimal
from typing import Any
from uuid import UUID

from domain.order import ProductSnapshot


class ProductSnapshotMapper:
    """Маппер для сериализации ProductSnapshot в dict/JSON."""

    @staticmethod
    def to_dict(snapshot: ProductSnapshot) -> dict[str, Any]:
        return {
            "id": str(snapshot.id),
            "name": snapshot.name,
            "description": snapshot.description,
            "price": f"{snapshot.price:.2f}",
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ProductSnapshot:
        return ProductSnapshot(
            id=UUID(str(data["id"])),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            price=Decimal(str(data.get("price", "0.00"))),
        )
