from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from domain.product import Product


class ProductCouchDbMapper:
    """Маппер товара для CouchDB со встроенными категориями и вложениями."""

    @staticmethod
    def to_doc(
        product: Product,
        rev: str = "",
        categories: list[dict[str, Any]] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Преобразовать доменный Product во встроенный CouchDB-документ."""
        doc: dict[str, Any] = {
            "_id": str(product.id),
            "type": "product",
            "name": product.name,
            "description": product.description,
            "price": float(product.price),
            "price_str": str(product.price),
            "quantity": product.quantity,
            "categories": categories if categories is not None else [],
            "category_ids": [str(cid) for cid in product.category_ids],
            "attachments": attachments if attachments is not None else [],
            "attachment_ids": [str(aid) for aid in product.attachment_ids],
        }
        if rev:
            doc["_rev"] = rev
        return doc

    @staticmethod
    def from_doc(doc: dict[str, Any]) -> Product:
        """Восстановить доменный Product из документа CouchDB."""
        raw_id = doc.get("id") or doc.get("_id")
        prod_id = UUID(str(raw_id)) if raw_id else uuid4()

        category_ids: list[UUID] = []
        if doc.get("category_ids"):
            category_ids = [UUID(str(cid)) for cid in doc["category_ids"]]
        elif doc.get("categories"):
            category_ids = [
                UUID(str(c["id"]))
                for c in doc["categories"]
                if isinstance(c, dict) and "id" in c
            ]

        attachment_ids: list[UUID] = []
        if doc.get("attachment_ids"):
            attachment_ids = [UUID(str(aid)) for aid in doc["attachment_ids"]]
        elif doc.get("attachments"):
            attachment_ids = [
                UUID(str(a["id"]))
                for a in doc["attachments"]
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
