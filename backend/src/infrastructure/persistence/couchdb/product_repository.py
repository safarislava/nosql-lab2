from __future__ import annotations

import builtins
import logging
import re
from typing import Any
from uuid import UUID

from application.category.repository import ICategoryRepository
from application.product.dto import ProductFilterDto, ProductSortBy
from application.product.exceptions import (
    ProductAlreadyExistsException,
    ProductNotFoundException,
)
from application.product.repository import IProductRepository
from domain.attachment import AttachmentMetadata
from domain.category import Category
from domain.product import Product
from infrastructure.environment.settings import settings
from infrastructure.persistence.composite.category_repository import (
    CompositeCategoryRepository,
)
from infrastructure.persistence.couchdb.attachment_mapper import (
    AttachmentCouchDbMapper,
)
from infrastructure.persistence.couchdb.category_embedded_repository import (
    CouchDbEmbeddedCategoryRepository,
)
from infrastructure.persistence.couchdb.category_mapper import (
    CategoryCouchDbMapper,
)
from infrastructure.persistence.couchdb.category_migrator import (
    CategoryMigrator,
)
from infrastructure.persistence.couchdb.category_referenced_repository import (
    CouchDbReferencedCategoryRepository,
)
from infrastructure.persistence.couchdb.client import CouchDbClient
from infrastructure.persistence.couchdb.product_mapper import (
    doc_to_product,
    product_to_doc,
)

logger = logging.getLogger(__name__)


class CouchDbProductRepository(IProductRepository):
    """Репозиторий товаров CouchDB."""

    def __init__(
        self,
        client: CouchDbClient,
        category_repo: ICategoryRepository | None = None,
    ) -> None:
        self._client = client
        self._db = settings.couchdb.products_db
        self._migrator = CategoryMigrator(client=self._client)
        self._category_repo = category_repo or CompositeCategoryRepository(
            v1_repo=CouchDbEmbeddedCategoryRepository(client=self._client),
            v2_repo=CouchDbReferencedCategoryRepository(client=self._client),
            migrator=self._migrator,
            client=self._client,
        )
        self._ensure_db_initialized()

    def _ensure_db_initialized(self) -> None:
        try:
            self._client.ensure_database(self._db)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Не удалось проверить или создать базу '%s': %s", self._db, exc
            )

    def _maybe_lazy_migrate(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Ленивая миграция (v1->v2 или v2->v1)."""
        return self._migrator.lazy_migrate_doc(doc)

    def get_by_id(self, product_id: UUID) -> Product | None:
        doc = self._client.get_doc(self._db, str(product_id))
        if doc is None or doc.get("type") != "product":
            return None
        doc = self._maybe_lazy_migrate(doc)
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
        return [doc_to_product(self._maybe_lazy_migrate(d)) for d in docs]

    def exists_by_id(self, product_id: UUID) -> bool:
        return self.get_by_id(product_id) is not None

    def list(
        self,
        filter_dto: ProductFilterDto | None = None,
    ) -> list[Product]:
        selector: dict[str, Any] = {"type": "product"}
        limit = 50
        skip = 0
        sort: list[dict[str, str]] | None = None

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
                selector["name"] = {"$regex": f"(?i){q}"}
            if filter_dto.category_ids:
                cat_ids = [str(cid) for cid in filter_dto.category_ids]
                selector["$or"] = [
                    {"category_ids": {"$in": cat_ids}},
                    {"categories": {"$elemMatch": {"id": {"$in": cat_ids}}}},
                ]

            if filter_dto.sort_by == ProductSortBy.POPULARITY:
                selector.setdefault("orders_count", {})["$gte"] = 0
                sort = [{"orders_count": "desc"}]
            elif filter_dto.sort_by == ProductSortBy.PRICE_ASC:
                selector.setdefault("price", {})["$gte"] = 0
                sort = [{"price": "asc"}]
            elif filter_dto.sort_by == ProductSortBy.PRICE_DESC:
                selector.setdefault("price", {})["$gte"] = 0
                sort = [{"price": "desc"}]
            elif filter_dto.sort_by == ProductSortBy.NAME_ASC:
                selector.setdefault("name", {})["$gt"] = None
                sort = [{"name": "asc"}]
            elif filter_dto.sort_by == ProductSortBy.NAME_DESC:
                selector.setdefault("name", {})["$gt"] = None
                sort = [{"name": "desc"}]
            elif filter_dto.sort_by == ProductSortBy.NEWEST:
                selector.setdefault("created_at", {})["$gt"] = None
                sort = [{"created_at": "desc"}]

        mango_query: dict[str, Any] = {
            "selector": selector,
            "limit": limit,
            "skip": skip,
        }
        if sort is not None:
            mango_query["sort"] = sort

        docs = self._client.find(self._db, mango_query)
        return [doc_to_product(self._maybe_lazy_migrate(d)) for d in docs]

    def _resolve_v2_category_ids(
        self,
        categories: builtins.list[Category] | None,
        category_ids: builtins.list[UUID] | None,
    ) -> builtins.list[UUID]:
        """Определить список ID категорий товара для схемы v2."""
        if categories is not None:
            return self._category_repo.save_missing_categories(categories)
        if category_ids:
            return self._category_repo.filter_existing_category_ids(category_ids)
        return []

    def create(
        self,
        product: Product,
        categories: builtins.list[Category] | None = None,
        attachments: builtins.list[AttachmentMetadata] | None = None,
    ) -> Product:
        """Создать товар."""
        doc_id = str(product.id)
        existing = self._client.get_doc(self._db, doc_id)
        if existing is not None:
            raise ProductAlreadyExistsException(product.id)

        embedded_atts = (
            [AttachmentCouchDbMapper.to_dict(a) for a in attachments]
            if attachments is not None
            else []
        )

        if settings.app_version >= 2:
            product.category_ids = self._resolve_v2_category_ids(
                categories, product.category_ids
            )

            doc = product_to_doc(
                product,
                categories=None,
                attachments=embedded_atts,
                schema_version=settings.app_version,
            )
            self._client.save_doc(self._db, doc)
        else:
            embedded_cats = (
                [CategoryCouchDbMapper.to_dict(c) for c in categories]
                if categories is not None
                else []
            )
            doc = product_to_doc(
                product,
                categories=embedded_cats,
                attachments=embedded_atts,
                schema_version=1,
            )
            doc["schema_version"] = 1
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
        """Обновить товар."""
        doc_id = str(product.id)
        existing_doc = self._client.get_doc(self._db, doc_id)
        if existing_doc is None or existing_doc.get("type") != "product":
            return None
        self._maybe_lazy_migrate(existing_doc)

        embedded_atts = (
            [AttachmentCouchDbMapper.to_dict(a) for a in attachments]
            if attachments is not None
            else None
        )

        embedded_cats: builtins.list[dict[str, Any]] | None = None
        if settings.app_version >= 2:
            product.category_ids = self._resolve_v2_category_ids(
                categories, product.category_ids
            )
        else:
            if categories is not None:
                embedded_cats = [CategoryCouchDbMapper.to_dict(c) for c in categories]
                product.category_ids = [c.id for c in categories]

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            doc["name"] = product.name
            doc["description"] = product.description
            doc["price"] = float(product.price)
            doc["price_str"] = str(product.price)
            doc["quantity"] = product.quantity

            if settings.app_version >= 2:
                if product.category_ids is not None:
                    doc["category_ids"] = [str(cid) for cid in product.category_ids]
                doc.pop("categories", None)
                doc["schema_version"] = settings.app_version
            else:
                if embedded_cats is not None:
                    doc["categories"] = embedded_cats
                doc.pop("category_ids", None)
                doc["schema_version"] = 1

            if embedded_atts is not None:
                doc["attachments"] = embedded_atts
            return True

        if not self._client.mutate_doc(self._db, doc_id, mutator):
            return None

        if embedded_atts is not None:
            product.attachment_ids = [
                UUID(str(a["id"]))
                for a in embedded_atts
                if isinstance(a, dict) and "id" in a
            ]

        return product

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

    def increment_orders_count(self, product_id: UUID, delta: int = 1) -> bool:
        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            current_count = int(doc.get("orders_count", 0))
            doc["orders_count"] = max(0, current_count + delta)
            return True

        return self._client.mutate_doc(self._db, str(product_id), mutator)

    def decrement_orders_count(self, product_id: UUID, delta: int = 1) -> bool:
        return self.increment_orders_count(product_id, -delta)

    def delete(self, product_id: UUID) -> bool:
        doc_id = str(product_id)
        doc = self._client.get_doc(self._db, doc_id)
        if doc is None or doc.get("type") != "product":
            return False
        rev = doc.get("_rev", "")
        return self._client.delete_doc(self._db, doc_id, rev)

    def get_categories(self, product_id: UUID) -> builtins.list[Category]:
        """Получить категории товара."""
        return self._category_repo.list(product_id)

    def get_attachments(self, product_id: UUID) -> builtins.list[AttachmentMetadata]:
        """Получить вложения товара."""
        doc = self._client.get_doc(self._db, str(product_id))
        if doc is None or doc.get("type") != "product":
            return []
        return [
            AttachmentCouchDbMapper.from_dict(a)
            for a in doc.get("attachments", [])
            if isinstance(a, dict)
        ]

    def add_category(self, product_id: UUID, category: Category) -> Product | None:
        """Добавить категорию к товару."""
        try:
            self._category_repo.add(product_id, category)
            return self.get_by_id(product_id)
        except ProductNotFoundException:
            return None

    def remove_category(self, product_id: UUID, category_id: UUID) -> Product | None:
        """Отвязать категорию от товара."""
        if self._category_repo.delete(product_id, category_id):
            return self.get_by_id(product_id)
        return None

    def add_attachment(
        self, product_id: UUID, attachment: AttachmentMetadata
    ) -> Product | None:
        """Добавить вложение к товару."""
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
        """Удалить вложение товара."""
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
