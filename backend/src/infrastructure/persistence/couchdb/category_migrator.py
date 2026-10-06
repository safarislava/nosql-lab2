from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from infrastructure.environment.settings import settings
from infrastructure.persistence.couchdb.category_mapper import (
    CategoryCouchDbMapper,
)
from infrastructure.persistence.couchdb.client import (
    CouchDbClient,
    get_couchdb_client,
)

logger = logging.getLogger(__name__)


@dataclass
class MigrationStats:
    is_running: bool = False
    total_scanned: int = 0
    migrated_products: int = 0
    migrated_categories: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_global_migration_stats = MigrationStats()


def _needs_migration(doc: dict[str, Any]) -> bool:
    """Определить, требуется ли документу миграция под текущую версию приложения."""
    if settings.app_version >= 2:
        return doc.get("categories") is not None or doc.get("schema_version", 1) < 2
    return doc.get("category_ids") is not None or doc.get("schema_version", 1) >= 2


class CategoryMigrator:
    """Двусторонний мигратор категорий (v1 <-> v2)."""

    def __init__(self, client: CouchDbClient | None = None) -> None:
        self._client = client or get_couchdb_client()
        self._products_db = settings.couchdb.products_db
        self._categories_db = settings.couchdb.categories_db
        self._ensure_dbs_initialized()

    def _ensure_dbs_initialized(self) -> None:
        try:
            self._client.ensure_database(self._products_db)
            self._client.ensure_database(self._categories_db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ошибка инициализации баз: %s", exc)

    @classmethod
    def get_status(cls) -> MigrationStats:
        return _global_migration_stats

    @staticmethod
    def _needs_v2_migration(doc: dict[str, Any]) -> bool:
        """Нужна ли миграция v1 -> v2 (вынос категорий в отдельную базу)."""
        return doc.get("categories") is not None or doc.get("schema_version", 1) < 2

    @staticmethod
    def _needs_v1_migration(doc: dict[str, Any]) -> bool:
        """Нужна ли миграция v2 -> v1 (встраивание категорий обратно в товар)."""
        return doc.get("category_ids") is not None or doc.get("schema_version", 1) >= 2

    def _needs_migration(self, doc: dict[str, Any]) -> bool:
        """Определить, требуется ли документу миграция под текущую версию приложения."""
        if settings.app_version >= 2:
            return self._needs_v2_migration(doc)
        return self._needs_v1_migration(doc)

    def lazy_migrate_doc(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Проверить схему документа и выполнить ленивую миграцию при несовпадении."""
        doc_id = doc.get("_id") or doc.get("id")
        if not doc_id or not self._needs_migration(doc):
            return doc
        migrate = (
            self.migrate_product_to_v2
            if settings.app_version >= 2
            else self.migrate_product_to_v1
        )
        if migrate(doc):
            return self._client.get_doc(self._products_db, str(doc_id)) or doc
        return doc

    def _save_categories_to_categories_db(
        self, categories_data: list[dict[str, Any]]
    ) -> list[str]:
        """Сохранить категории в базу categories и вернуть список их идентификаторов."""
        saved_category_ids: list[str] = []
        for category_dict in categories_data:
            if not isinstance(category_dict, dict) or "id" not in category_dict:
                continue
            category = CategoryCouchDbMapper.from_dict(category_dict)
            self._client.mutate_doc(
                self._categories_db,
                str(category.id),
                CategoryCouchDbMapper.mutator(category),
                create_if_missing=True,
            )
            saved_category_ids.append(str(category.id))
        return saved_category_ids

    @staticmethod
    def _convert_product_doc_to_v2(
        product_doc: dict[str, Any], new_category_ids: list[str]
    ) -> bool:
        """Мутировать документ товара: переключить со встроенных категорий на ссылки."""
        if product_doc.get("type") != "product":
            return False

        existing_category_ids: list[str] = product_doc.setdefault("category_ids", [])
        for category_id in new_category_ids:
            if category_id not in existing_category_ids:
                existing_category_ids.append(category_id)

        product_doc.pop("categories", None)
        product_doc["schema_version"] = 2
        return True

    def migrate_product_to_v2(self, product_document: dict[str, Any]) -> bool:
        """Миграция товара v1 -> v2 (вынос категорий в базу categories)."""
        product_id = str(product_document.get("_id") or product_document.get("id"))
        embedded_categories = product_document.get("categories") or []

        saved_category_ids = self._save_categories_to_categories_db(embedded_categories)

        def mutator(target_product_doc: dict[str, Any]) -> bool:
            return self._convert_product_doc_to_v2(
                target_product_doc, saved_category_ids
            )

        return self._client.mutate_doc(self._products_db, product_id, mutator)

    migrate_product_doc = migrate_product_to_v2

    def _fetch_category_dict_for_embedding(self, category_id: str) -> dict[str, Any]:
        """Загрузить категорию из базы categories в виде словаря для встраивания."""
        category_doc = self._client.get_doc(self._categories_db, category_id)
        if category_doc and category_doc.get("type") == "category":
            category = CategoryCouchDbMapper.from_dict(category_doc)
            return CategoryCouchDbMapper.to_dict(category)
        return {
            "id": category_id,
            "name": "",
            "slug": "",
            "description": "",
        }

    def _load_embedded_categories_by_ids(
        self, category_ids: list[Any]
    ) -> list[dict[str, Any]]:
        """Загрузить все связанные категории по их ID для встраивания в товар."""
        return [
            self._fetch_category_dict_for_embedding(str(category_id))
            for category_id in category_ids
            if category_id
        ]

    @staticmethod
    def _convert_product_doc_to_v1(
        product_doc: dict[str, Any], embedded_categories: list[dict[str, Any]]
    ) -> bool:
        """Мутировать документ товара: переключить со ссылок на встроенный массив категорий."""
        if product_doc.get("type") != "product":
            return False

        product_doc["categories"] = embedded_categories
        product_doc.pop("category_ids", None)
        product_doc["schema_version"] = 1
        return True

    def migrate_product_to_v1(self, product_document: dict[str, Any]) -> bool:
        """Миграция товара v2 -> v1 (встраивание категорий обратно в товар)."""
        product_id = str(product_document.get("_id") or product_document.get("id"))
        category_ids = product_document.get("category_ids") or []

        embedded_categories = self._load_embedded_categories_by_ids(category_ids)

        def mutator(target_product_doc: dict[str, Any]) -> bool:
            return self._convert_product_doc_to_v1(
                target_product_doc, embedded_categories
            )

        return self._client.mutate_doc(self._products_db, product_id, mutator)

    def _process_migration_batch(
        self,
        documents_batch: list[dict[str, Any]],
        migrate_document_fn: Callable[[dict[str, Any]], bool],
        count_categories_fn: Callable[[dict[str, Any]], int],
    ) -> int:
        """Обработать одну пачку документов и вернуть число успешно смигрированных."""
        migrated_count = 0
        for document in documents_batch:
            _global_migration_stats.total_scanned += 1
            product_id = str(document.get("_id") or document.get("id"))
            try:
                categories_count = count_categories_fn(document)
                if migrate_document_fn(document):
                    _global_migration_stats.migrated_products += 1
                    _global_migration_stats.migrated_categories += categories_count
                    migrated_count += 1
                else:
                    _global_migration_stats.errors.append(
                        f"Не удалось смигрировать товар {product_id}"
                    )
            except Exception as error:  # noqa: BLE001
                error_message = f"Ошибка миграции товара {product_id}: {error}"
                logger.error(error_message)
                _global_migration_stats.errors.append(error_message)

        return migrated_count

    def _run_batch_migration(
        self,
        selector: dict[str, Any],
        migrate_document_fn: Callable[[dict[str, Any]], bool],
        count_categories_fn: Callable[[dict[str, Any]], int],
        batch_size: int,
    ) -> MigrationStats:
        """Выполнить пакетную миграцию документов с пагинацией."""
        global _global_migration_stats

        if _global_migration_stats.is_running:
            return _global_migration_stats

        _global_migration_stats = MigrationStats(
            is_running=True,
            started_at=datetime.now(UTC).isoformat(),
        )

        try:
            skip = 0
            while True:
                batch_query = {
                    "selector": selector,
                    "limit": batch_size,
                    "skip": skip,
                }
                documents_batch = self._client.find(self._products_db, batch_query)
                if not documents_batch:
                    break

                migrated_in_batch = self._process_migration_batch(
                    documents_batch=documents_batch,
                    migrate_document_fn=migrate_document_fn,
                    count_categories_fn=count_categories_fn,
                )

                skip += len(documents_batch) - migrated_in_batch

                if len(documents_batch) < batch_size:
                    break
        finally:
            _global_migration_stats.is_running = False
            _global_migration_stats.completed_at = datetime.now(UTC).isoformat()

        return _global_migration_stats

    def migrate_all_to_v2(self, batch_size: int = 50) -> MigrationStats:
        """Фоновая миграция всех товаров v1 -> v2."""
        selector = {
            "type": "product",
            "categories.0": {"$exists": True},
        }

        def count_categories(document: dict[str, Any]) -> int:
            categories = document.get("categories", [])
            return len(categories) if isinstance(categories, list) else 0

        return self._run_batch_migration(
            selector=selector,
            migrate_document_fn=self.migrate_product_to_v2,
            count_categories_fn=count_categories,
            batch_size=batch_size,
        )

    migrate_all = migrate_all_to_v2

    def migrate_all_to_v1(self, batch_size: int = 50) -> MigrationStats:
        """Фоновая миграция всех товаров v2 -> v1 (откат)."""
        selector = {
            "type": "product",
            "$or": [
                {"schema_version": {"$gte": 2}},
                {"category_ids.0": {"$exists": True}},
            ],
        }

        def count_categories(document: dict[str, Any]) -> int:
            category_ids = document.get("category_ids", [])
            return len(category_ids) if isinstance(category_ids, list) else 0

        return self._run_batch_migration(
            selector=selector,
            migrate_document_fn=self.migrate_product_to_v1,
            count_categories_fn=count_categories,
            batch_size=batch_size,
        )
