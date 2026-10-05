from __future__ import annotations

import builtins
import logging
import re
from typing import Any
from uuid import UUID

from application.product.dto import ProductFilterDto
from application.product.exceptions import ProductAlreadyExistsException
from application.product.repository import IProductRepository
from domain.attachment import AttachmentMetadata
from domain.category import Category
from domain.product import Product
from infrastructure.environment.settings import settings
from infrastructure.persistence.couchdb.attachment_mapper import (
    AttachmentCouchDbMapper,
)
from infrastructure.persistence.couchdb.category_mapper import (
    CategoryCouchDbMapper,
)
from infrastructure.persistence.couchdb.client import CouchDbClient
from infrastructure.persistence.couchdb.product_mapper import (
    doc_to_product,
    product_to_doc,
)

logger = logging.getLogger(__name__)


class CouchDbProductRepository(IProductRepository):
    """Репозиторий товаров на базе CouchDB со встроенными категориями и вложениями."""

    def __init__(
        self,
        client: CouchDbClient,
    ) -> None:
        self._client = client
        self._db = settings.couchdb.products_db
        self._ensure_db_initialized()

    def _ensure_db_initialized(self) -> None:
        """Гарантировать существование базы данных."""
        try:
            self._client.ensure_database(self._db)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Не удалось проверить или создать базу '%s': %s", self._db, exc
            )

    def get_by_id(self, product_id: UUID) -> Product | None:
        doc = self._client.get_doc(self._db, str(product_id))
        if doc is None or doc.get("type") != "product":
            return None
        return doc_to_product(doc)

    def get_by_ids(self, product_ids: list[UUID]) -> list[Product]:
        if not product_ids:
            return []
        selector: dict[str, Any] = {
            "type": "product",
            "_id": {"$in": [str(pid) for pid in product_ids]},
        }
        docs = self._client.find(
            self._db, {"selector": selector, "limit": len(product_ids)}
        )
        return [doc_to_product(d) for d in docs]

    def exists_by_id(self, product_id: UUID) -> bool:
        return self.get_by_id(product_id) is not None

    def list(
        self,
        filter_dto: ProductFilterDto | None = None,
    ) -> list[Product]:
        selector: dict[str, Any] = {"type": "product"}
        limit = 50
        skip = 0

        if filter_dto is not None:
            limit = filter_dto.limit
            skip = filter_dto.offset

            if filter_dto.min_price is not None:
                selector.setdefault("price", {})["$gte"] = float(filter_dto.min_price)
            if filter_dto.max_price is not None:
                selector.setdefault("price", {})["$lte"] = float(filter_dto.max_price)
            if filter_dto.in_stock_only:
                selector["quantity"] = {"$gt": 0}
            if filter_dto.query and filter_dto.query.strip():
                q = re.escape(filter_dto.query.strip())
                selector["$or"] = [
                    {"name": {"$regex": f"(?i){q}"}},
                    {"description": {"$regex": f"(?i){q}"}},
                ]

        mango_query: dict[str, Any] = {
            "selector": selector,
            "limit": limit,
            "skip": skip,
        }

        docs = self._client.find(self._db, mango_query)
        return [doc_to_product(d) for d in docs]

    def create(
        self,
        product: Product,
        categories: builtins.list[Category] | None = None,
        attachments: builtins.list[AttachmentMetadata] | None = None,
    ) -> Product:
        """Создать новый товар в CouchDB (C в CRUD)."""
        doc_id = str(product.id)
        existing = self._client.get_doc(self._db, doc_id)
        if existing is not None:
            raise ProductAlreadyExistsException(product.id)

        embedded_cats = (
            [CategoryCouchDbMapper.to_dict(c) for c in categories]
            if categories is not None
            else []
        )
        embedded_atts = (
            [AttachmentCouchDbMapper.to_dict(a) for a in attachments]
            if attachments is not None
            else []
        )

        doc = product_to_doc(
            product,
            categories=embedded_cats,
            attachments=embedded_atts,
        )
        self._client.save_doc(self._db, doc)

        product.category_ids = [
            UUID(str(c["id"]))
            for c in embedded_cats
            if isinstance(c, dict) and "id" in c
        ]
        product.attachment_ids = [
            UUID(str(a["id"]))
            for a in embedded_atts
            if isinstance(a, dict) and "id" in a
        ]
        return product

    def update(
        self,
        product: Product,
        categories: builtins.list[Category] | None = None,
        attachments: builtins.list[AttachmentMetadata] | None = None,
    ) -> Product | None:
        """Обновить существующий товар в CouchDB (U в CRUD)."""
        doc_id = str(product.id)
        embedded_cats = (
            [CategoryCouchDbMapper.to_dict(c) for c in categories]
            if categories is not None
            else None
        )
        embedded_atts = (
            [AttachmentCouchDbMapper.to_dict(a) for a in attachments]
            if attachments is not None
            else None
        )

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            doc["name"] = product.name
            doc["description"] = product.description
            doc["price"] = float(product.price)
            doc["price_str"] = str(product.price)
            doc["quantity"] = product.quantity
            if embedded_cats is not None:
                doc["categories"] = embedded_cats
            if embedded_atts is not None:
                doc["attachments"] = embedded_atts
            return True

        if not self._client.mutate_doc(self._db, doc_id, mutator):
            return None

        if embedded_cats is not None:
            product.category_ids = [
                UUID(str(c["id"]))
                for c in embedded_cats
                if isinstance(c, dict) and "id" in c
            ]
        if embedded_atts is not None:
            product.attachment_ids = [
                UUID(str(a["id"]))
                for a in embedded_atts
                if isinstance(a, dict) and "id" in a
            ]

        return product

    def save(
        self,
        product: Product,
        categories: builtins.list[Category] | None = None,
        attachments: builtins.list[AttachmentMetadata] | None = None,
    ) -> Product:
        """Сохранить товар (upsert: обновить или создать)."""
        updated = self.update(product, categories=categories, attachments=attachments)
        if updated is not None:
            return updated
        return self.create(product, categories=categories, attachments=attachments)

    def update_stock(self, product_id: UUID, delta: int) -> bool:
        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            current_qty = int(doc.get("quantity", 0))
            new_qty = current_qty + delta
            if new_qty < 0:
                return False
            doc["quantity"] = new_qty
            return True

        return self._client.mutate_doc(self._db, str(product_id), mutator)

    def update_stock_and_get(self, product_id: UUID, delta: int) -> Product | None:
        if not self.update_stock(product_id, delta):
            return None
        return self.get_by_id(product_id)

    def delete(self, product_id: UUID) -> bool:
        doc_id = str(product_id)
        doc = self._client.get_doc(self._db, doc_id)
        if doc is None or doc.get("type") != "product":
            return False
        rev = doc.get("_rev", "")
        return self._client.delete_doc(self._db, doc_id, rev)

    def get_categories(self, product_id: UUID) -> builtins.list[Category]:
        """Получить встроенные категории товара."""
        doc = self._client.get_doc(self._db, str(product_id))
        if doc is None or doc.get("type") != "product":
            return []
        return [
            CategoryCouchDbMapper.from_dict(c)
            for c in doc.get("categories", [])
            if isinstance(c, dict)
        ]

    def get_attachments(self, product_id: UUID) -> builtins.list[AttachmentMetadata]:
        """Получить встроенные вложения товара."""
        doc = self._client.get_doc(self._db, str(product_id))
        if doc is None or doc.get("type") != "product":
            return []
        return [
            AttachmentCouchDbMapper.from_dict(a)
            for a in doc.get("attachments", [])
            if isinstance(a, dict)
        ]

    def add_category(self, product_id: UUID, category: Category) -> Product | None:
        """Добавить категорию во встроенный список товара."""
        cat_dict = CategoryCouchDbMapper.to_dict(category)
        cat_id_str = str(category.id)

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            cats = doc.setdefault("categories", [])
            for i, c in enumerate(cats):
                if isinstance(c, dict) and c.get("id") == cat_id_str:
                    cats[i] = cat_dict
                    return True
            cats.append(cat_dict)
            return True

        if not self._client.mutate_doc(self._db, str(product_id), mutator):
            return None
        return self.get_by_id(product_id)

    def remove_category(self, product_id: UUID, category_id: UUID) -> Product | None:
        """Удалить категорию из встроенного списка товара."""
        cat_id_str = str(category_id)

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            cats = doc.get("categories", [])
            new_cats = [
                c
                for c in cats
                if not (isinstance(c, dict) and c.get("id") == cat_id_str)
            ]
            if len(new_cats) == len(cats):
                return False
            doc["categories"] = new_cats
            return True

        if not self._client.mutate_doc(self._db, str(product_id), mutator):
            return None
        return self.get_by_id(product_id)

    def add_attachment(
        self, product_id: UUID, attachment: AttachmentMetadata
    ) -> Product | None:
        """Добавить вложение во встроенный список товара."""
        att_dict = AttachmentCouchDbMapper.to_dict(attachment)
        att_id_str = str(attachment.id)

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            atts = doc.setdefault("attachments", [])
            for i, a in enumerate(atts):
                if isinstance(a, dict) and a.get("id") == att_id_str:
                    atts[i] = att_dict
                    return True
            atts.append(att_dict)
            return True

        if not self._client.mutate_doc(self._db, str(product_id), mutator):
            return None
        return self.get_by_id(product_id)

    def remove_attachment(
        self, product_id: UUID, attachment_id: UUID
    ) -> Product | None:
        """Удалить вложение из встроенного списка товара."""
        att_id_str = str(attachment_id)

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            atts = doc.get("attachments", [])
            new_atts = [
                a
                for a in atts
                if not (isinstance(a, dict) and a.get("id") == att_id_str)
            ]
            if len(new_atts) == len(atts):
                return False
            doc["attachments"] = new_atts
            return True

        if not self._client.mutate_doc(self._db, str(product_id), mutator):
            return None
        return self.get_by_id(product_id)
