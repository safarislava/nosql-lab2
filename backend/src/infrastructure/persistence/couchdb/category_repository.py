from __future__ import annotations

import builtins
import logging
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


class CouchDbCategoryRepository(ICategoryRepository):
    """Гранулярный CRUD-репозиторий категорий в CouchDB.
    
    Категории хранятся непосредственно как встроенный массив `categories`
    внутри документа товара в базе `products`.
    """

    def __init__(
        self,
        client: CouchDbClient,
    ) -> None:
        self._client = client
        self._db = settings.couchdb.products_db
        self._ensure_db_initialized()

    def _ensure_db_initialized(self) -> None:
        """Гарантировать существование базы данных товаров."""
        try:
            self._client.ensure_database(self._db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось инициализировать базу '%s': %s", self._db, exc)

    def get_by_id(
        self, product_id: UUID, category_id: UUID
    ) -> Category | None:
        """Получить встроенную категорию товара по ID."""
        doc = self._client.get_doc(self._db, str(product_id))
        if not doc or doc.get("type") != "product":
            return None

        cat_id_str = str(category_id)
        for c in doc.get("categories", []):
            if isinstance(c, dict) and c.get("id") == cat_id_str:
                return CategoryCouchDbMapper.from_dict(c)

        return None

    def list(
        self, product_id: UUID
    ) -> builtins.list[Category]:
        """Получить список всех встроенных категорий конкретного товара."""
        doc = self._client.get_doc(self._db, str(product_id))
        if not doc or doc.get("type") != "product":
            return []

        return [
            CategoryCouchDbMapper.from_dict(c)
            for c in doc.get("categories", [])
            if isinstance(c, dict)
        ]

    def add(
        self, product_id: UUID, category: Category
    ) -> Category:
        """Добавить категорию во встроенный массив товара."""
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
            raise ProductNotFoundException(product_id)
        return category

    def update(
        self, product_id: UUID, category: Category
    ) -> Category | None:
        """Обновить существующую встроенную категорию товара."""
        cat_dict = CategoryCouchDbMapper.to_dict(category)
        cat_id_str = str(category.id)

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            cats = doc.get("categories", [])
            for i, c in enumerate(cats):
                if isinstance(c, dict) and c.get("id") == cat_id_str:
                    cats[i] = cat_dict
                    return True
            return False

        if not self._client.mutate_doc(self._db, str(product_id), mutator):
            return None
        return category

    def delete(
        self, product_id: UUID, category_id: UUID
    ) -> bool:
        """Удалить встроенную категорию из товара по ID."""
        cat_id_str = str(category_id)

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            cats = doc.get("categories", [])
            new_cats = [
                c for c in cats
                if not (isinstance(c, dict) and c.get("id") == cat_id_str)
            ]
            if len(new_cats) == len(cats):
                return False
            doc["categories"] = new_cats
            return True

        return self._client.mutate_doc(self._db, str(product_id), mutator)
