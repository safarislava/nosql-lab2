from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from domain.product import Product


class ProductCouchDbMapper:
    """Маппер товара CouchDB (v1/v2)."""

    @staticmethod
    def to_doc(
        product: Product,
        categories: list[dict[str, Any]] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        *,
        schema_version: int = 1,
    ) -> dict[str, Any]:
        """Преобразовать Product в CouchDB-документ."""
        doc: dict[str, Any] = {
            "_id": str(product.id),
            "type": "product",
            "name": product.name,
            "description": product.description,
            "price": float(product.price),
            "price_str": str(product.price),
            "quantity": product.quantity,
            "attachments": attachments if attachments is not None else [],
        }
        if schema_version >= 2:
            doc["schema_version"] = schema_version
            doc["category_ids"] = [str(cid) for cid in product.category_ids] or [
                str(c["id"])
                for c in (categories or [])
                if isinstance(c, dict) and "id" in c
            ]
        else:
            doc["categories"] = categories or []

        return doc

    @staticmethod
    def from_doc(doc: dict[str, Any]) -> Product:
        """Восстановить Product из документа CouchDB."""
        raw_id = doc.get("id") or doc.get("_id")
        prod_id = UUID(str(raw_id)) if raw_id else uuid4()

        category_ids: list[UUID] = []
        if doc.get("category_ids"):
            category_ids = [UUID(str(cid)) for cid in doc["category_ids"] if cid]
        elif doc.get("categories"):
            category_ids = [
                UUID(str(c["id"]))
                for c in doc["categories"]
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
