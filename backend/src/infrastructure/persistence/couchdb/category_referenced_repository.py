from __future__ import annotations

import builtins
import logging
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from application.category.repository import ICategoryRepository
from application.product.exceptions import ProductNotFoundException
from domain.category import Category
from infrastructure.environment.settings import settings
from infrastructure.persistence.couchdb.category_mapper import (
    CategoryCouchDbMapper,
)
from infrastructure.persistence.couchdb.client import CouchDbClient

logger = logging.getLogger(__name__)


class CouchDbReferencedCategoryRepository(ICategoryRepository):
    """Репозиторий категорий (ссылки category_ids + база categories)."""

    def __init__(
        self,
        client: CouchDbClient,
    ) -> None:
        self._client = client
        self._products_db = settings.couchdb.products_db
        self._categories_db = settings.couchdb.categories_db
        self._ensure_dbs_initialized()

    def _ensure_dbs_initialized(self) -> None:
        """Гарантировать существование баз данных товаров и категорий."""
        try:
            self._client.ensure_database(self._products_db)
            self._client.ensure_database(self._categories_db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось инициализировать базы CouchDB: %s", exc)

    def get_by_id(self, product_id: UUID, category_id: UUID) -> Category | None:
        """Получить категорию товара по ID."""
        doc = self._client.get_doc(self._products_db, str(product_id))
        if not doc or doc.get("type") != "product":
            return None

        cat_id_str = str(category_id)
        if cat_id_str not in doc.get("category_ids", []):
            return None

        cat_doc = self._client.get_doc(self._categories_db, cat_id_str)
        if cat_doc and cat_doc.get("type") == "category":
            return CategoryCouchDbMapper.from_dict(cat_doc)

        return None

    def list(self, product_id: UUID) -> builtins.list[Category]:
        """Получить список всех категорий товара."""
        doc = self._client.get_doc(self._products_db, str(product_id))
        if not doc or doc.get("type") != "product":
            return []

        cids = [str(cid) for cid in doc.get("category_ids", []) if cid]
        if not cids:
            return []

        query = CategoryCouchDbMapper.find_by_ids_query(cids)
        docs = self._client.find(self._categories_db, query)
        return [CategoryCouchDbMapper.from_dict(d) for d in docs]

    def add(self, product_id: UUID, category: Category) -> Category:
        """Добавить категорию и привязать к товару."""
        cat_id_str = str(category.id)
        self._client.mutate_doc(
            self._categories_db,
            cat_id_str,
            CategoryCouchDbMapper.mutator(category),
            create_if_missing=True,
        )

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            cids = doc.setdefault("category_ids", [])
            if cat_id_str not in cids:
                cids.append(cat_id_str)
            return True

        if not self._client.mutate_doc(self._products_db, str(product_id), mutator):
            raise ProductNotFoundException(product_id)

        return category

    def update(self, product_id: UUID, category: Category) -> Category | None:
        """Обновить существующую категорию товара."""
        doc = self._client.get_doc(self._products_db, str(product_id))
        if not doc or doc.get("type") != "product":
            return None

        cat_id_str = str(category.id)
        if cat_id_str not in doc.get("category_ids", []):
            return None

        if not self._client.mutate_doc(
            self._categories_db, cat_id_str, CategoryCouchDbMapper.mutator(category)
        ):
            return None

        return category

    def delete(self, product_id: UUID, category_id: UUID) -> bool:
        """Отвязать категорию от товара по ID."""
        cat_id_str = str(category_id)

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            cids = doc.get("category_ids", [])
            if cat_id_str not in cids:
                return False

            cids.remove(cat_id_str)
            doc["category_ids"] = cids
            return True

        return self._client.mutate_doc(self._products_db, str(product_id), mutator)

    def _find_existing_ids(self, ids: Sequence[UUID | str]) -> set[str]:
        """Получить множество существующих строковых _id категорий."""
        if not ids:
            return set()
        query = CategoryCouchDbMapper.find_by_ids_query(ids)
        return {
            str(doc["_id"])
            for doc in self._client.find(self._categories_db, query)
            if "_id" in doc
        }

    def save_missing_categories(
        self,
        categories: builtins.list[Category],
    ) -> builtins.list[UUID]:
        """Обработать категории для v2:
        - существующие в categories_db категории НЕ должны мутировать;
        - если категории нет в базе, она создается в categories_db с данными из запроса;
        - идентификаторы категорий возвращаются для прикрепления к товару.
        """
        cats_by_id = {str(c.id): c for c in categories if getattr(c, "id", None)}
        if not cats_by_id:
            return []

        existing_ids = self._find_existing_ids(list(cats_by_id.keys()))

        for cat_id, cat in cats_by_id.items():
            if cat_id not in existing_ids:
                self._client.save_doc(
                    self._categories_db,
                    CategoryCouchDbMapper.to_dict(cat),
                )

        return [c.id for c in cats_by_id.values()]

    def filter_existing_category_ids(
        self,
        category_ids: builtins.list[UUID],
    ) -> builtins.list[UUID]:
        """Оставить только существующие в categories_db ID категорий (батч-запрос)."""
        existing_ids = self._find_existing_ids(category_ids)
        return [cid for cid in category_ids if str(cid) in existing_ids]
