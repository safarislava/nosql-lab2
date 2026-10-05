from __future__ import annotations

import builtins
from uuid import UUID

from application.category.repository import ICategoryRepository
from domain.category import Category
from infrastructure.environment.settings import settings
from infrastructure.persistence.couchdb.category_embedded_repository import (
    CouchDbEmbeddedCategoryRepository,
)
from infrastructure.persistence.couchdb.category_migrator import (
    CategoryMigrator,
)
from infrastructure.persistence.couchdb.category_referenced_repository import (
    CouchDbReferencedCategoryRepository,
)
from infrastructure.persistence.couchdb.client import CouchDbClient


class CompositeCategoryRepository(ICategoryRepository):
    """Композитный репозиторий категорий."""

    def __init__(
        self,
        v1_repo: CouchDbEmbeddedCategoryRepository,
        v2_repo: CouchDbReferencedCategoryRepository,
        migrator: CategoryMigrator,
        client: CouchDbClient,
    ) -> None:
        self._v1_repo = v1_repo
        self._v2_repo = v2_repo
        self._migrator = migrator
        self._client = client
        self._products_db = settings.couchdb.products_db

    @property
    def _active_repo(self) -> ICategoryRepository:
        return self._v2_repo if settings.app_version >= 2 else self._v1_repo

    def _ensure_migrated(self, product_id: UUID) -> None:
        doc = self._client.get_doc(self._products_db, str(product_id))
        if doc is not None and doc.get("type") == "product":
            self._migrator.lazy_migrate_doc(doc)

    def get_by_id(self, product_id: UUID, category_id: UUID) -> Category | None:
        self._ensure_migrated(product_id)
        return self._active_repo.get_by_id(product_id, category_id)

    def list(self, product_id: UUID) -> builtins.list[Category]:
        self._ensure_migrated(product_id)
        return self._active_repo.list(product_id)

    def add(self, product_id: UUID, category: Category) -> Category:
        self._ensure_migrated(product_id)
        return self._active_repo.add(product_id, category)

    def update(self, product_id: UUID, category: Category) -> Category | None:
        self._ensure_migrated(product_id)
        return self._active_repo.update(product_id, category)

    def delete(self, product_id: UUID, category_id: UUID) -> bool:
        self._ensure_migrated(product_id)
        return self._active_repo.delete(product_id, category_id)
