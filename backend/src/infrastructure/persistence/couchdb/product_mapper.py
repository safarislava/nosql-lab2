from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from domain.product import Product


class ProductCouchDbMapper:
    """Маппер товара для CouchDB со встроенными категориями и вложениями (без лишних category_ids/attachment_ids)."""

    @staticmethod
    def to_doc(
        product: Product,
        categories: list[dict[str, Any]] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Преобразовать доменный Product во встроенный CouchDB-документ."""
        return {
            "_id": str(product.id),
            "type": "product",
            "name": product.name,
            "description": product.description,
            "price": float(product.price),
            "price_str": str(product.price),
            "quantity": product.quantity,
            "categories": categories if categories is not None else [],
            "attachments": attachments if attachments is not None else [],
        }

    @staticmethod
    def from_doc(doc: dict[str, Any]) -> Product:
        """Восстановить доменный Product из встроенного документа CouchDB."""
        raw_id = doc.get("id") or doc.get("_id")
        prod_id = UUID(str(raw_id)) if raw_id else uuid4()

        category_ids: list[UUID] = [
            UUID(str(c["id"]))
            for c in doc.get("categories", [])
            if isinstance(c, dict) and "id" in c
        ]

        attachment_ids: list[UUID] = [
            UUID(str(a["id"]))
            for a in doc.get("attachments", [])
            if isinstance(a, dict) and "id" in a
        ]

        price_val = doc.get("price_str") or doc.get("price", "0.00")

        return Product(
            id=prod_id,
            name=str(doc.get("name", "")),
            description=str(doc.get("description", "")),
            price=Decimal(str(price_val)),
            quantity=int(doc.get("quantity", 0)),
            category_ids=category_ids,
            attachment_ids=attachment_ids,
        )


product_to_doc = ProductCouchDbMapper.to_doc
doc_to_product = ProductCouchDbMapper.from_doc
