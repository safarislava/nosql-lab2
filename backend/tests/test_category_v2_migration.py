from datetime import UTC
from decimal import Decimal
from typing import Any
from uuid import uuid4

from application.product.dto import ProductFilterDto, ProductSortBy
from domain.category import Category
from domain.product import Product
from infrastructure.environment.settings import settings
from infrastructure.persistence.composite.category_repository import (
    CompositeCategoryRepository,
)
from infrastructure.persistence.couchdb.category_embedded_repository import (
    CouchDbEmbeddedCategoryRepository,
)
from infrastructure.persistence.couchdb.category_migrator import (
    CategoryMigrator,
)
from infrastructure.persistence.couchdb.category_referenced_repository import (
    CouchDbReferencedCategoryRepository,
)
from infrastructure.persistence.couchdb.exceptions import CouchDbConflictException
from infrastructure.persistence.couchdb.product_mapper import (
    ProductCouchDbMapper,
)
from infrastructure.persistence.couchdb.product_repository import (
    CouchDbProductRepository,
)


class MockCouchDbClient:
    """Mock-клиент CouchDB для изолированного тестирования логики репозиториев и мигратора."""

    def __init__(self) -> None:
        self.dbs: dict[str, dict[str, dict[str, Any]]] = {}

    def ensure_database(self, db: str) -> None:
        if db not in self.dbs:
            self.dbs[db] = {}

    def get_doc(self, db: str, doc_id: str) -> dict[str, Any] | None:
        self.ensure_database(db)
        doc = self.dbs[db].get(doc_id)
        return dict(doc) if doc is not None else None

    def save_doc(self, db: str, doc: dict[str, Any]) -> dict[str, Any]:
        self.ensure_database(db)
        doc_id = str(doc.get("_id") or doc.get("id"))
        existing = self.dbs[db].get(doc_id)

        if existing is not None:
            expected_rev = existing.get("_rev", "")
            actual_rev = doc.get("_rev", "")
            if actual_rev != expected_rev:
                raise CouchDbConflictException(doc_id, "Revision conflict in mock")
            gen = int(expected_rev.split("-")[0]) if "-" in expected_rev else 1
            new_rev = f"{gen + 1}-mockrev{uuid4().hex[:8]}"
        else:
            new_rev = f"1-mockrev{uuid4().hex[:8]}"

        doc["_rev"] = new_rev
        doc["_id"] = doc_id
        self.dbs[db][doc_id] = dict(doc)
        return doc

    def delete_doc(self, db: str, doc_id: str, rev: str) -> bool:
        self.ensure_database(db)
        existing = self.dbs[db].get(doc_id)
        if not existing or existing.get("_rev") != rev:
            return False
        del self.dbs[db][doc_id]
        return True

    def mutate_doc(
        self,
        db: str,
        doc_id: str,
        mutator: Any,
        *,
        create_if_missing: bool = False,
        max_retries: int = 5,
    ) -> bool:
        self.ensure_database(db)
        for _ in range(max_retries):
            doc = self.get_doc(db, doc_id)
            if doc is None:
                if not create_if_missing:
                    return False
                doc = {"_id": doc_id}

            if not mutator(doc):
                return False

            try:
                self.save_doc(db, doc)
                return True
            except CouchDbConflictException:
                continue
        return False

    def find(self, db: str, query: dict[str, Any]) -> list[dict[str, Any]]:
        self.ensure_database(db)
        selector = query.get("selector", {})
        results: list[dict[str, Any]] = []

        def match_predicate(doc: dict[str, Any], k: str, v: Any) -> bool:
            if k == "type":
                return doc.get("type") == v
            if k == "_id" and isinstance(v, dict) and "$in" in v:
                return doc.get("_id") in v["$in"]
            if k == "categories.0" and isinstance(v, dict) and "$exists" in v:
                cats = doc.get("categories", [])
                return (len(cats) > 0) == v["$exists"]
            if k == "category_ids.0" and isinstance(v, dict) and "$exists" in v:
                cids = doc.get("category_ids", [])
                return (len(cids) > 0) == v["$exists"]
            if k == "schema_version":
                if isinstance(v, dict) and "$gte" in v:
                    return doc.get("schema_version", 1) >= v["$gte"]
                return doc.get("schema_version") == v
            if k == "$and" and isinstance(v, list):
                return all(
                    all(match_predicate(doc, sk, sv) for sk, sv in sub.items())
                    for sub in v
                )
            if k == "$or" and isinstance(v, list):
                return any(
                    all(match_predicate(doc, sk, sv) for sk, sv in sub.items())
                    for sub in v
                )
            if k == "category_ids" and isinstance(v, dict):
                cids = [str(c) for c in doc.get("category_ids", [])]
                if "$all" in v:
                    return all(str(item) in cids for item in v["$all"])
                if "$in" in v:
                    return any(str(item) in cids for item in v["$in"])
            if k == "categories" and isinstance(v, dict):
                cats = doc.get("categories", [])
                if "$elemMatch" in v:
                    sub_match = v["$elemMatch"]
                    for cat in cats:
                        if isinstance(cat, dict):
                            id_match = sub_match.get("id")
                            if isinstance(id_match, dict) and "$in" in id_match:
                                if str(cat.get("id")) in [
                                    str(x) for x in id_match["$in"]
                                ]:
                                    return True
                            elif id_match is not None and str(cat.get("id")) == str(
                                id_match
                            ):
                                return True
                    return False
            return True

        for doc in self.dbs[db].values():
            if all(match_predicate(doc, k, v) for k, v in selector.items()):
                results.append(dict(doc))

        self.last_query = query
        sort_fields = query.get("sort")
        if sort_fields:
            for s in reversed(sort_fields):
                if isinstance(s, dict):
                    for field, direction in s.items():
                        reverse = direction.lower() == "desc"
                        results.sort(key=lambda d: d.get(field, 0), reverse=reverse)

        limit = query.get("limit", 100)
        skip = query.get("skip", 0)
        return results[skip : skip + limit]


def test_product_couchdb_mapper_v1_and_v2() -> None:
    """Тест маппера для v1 и v2."""
    cat_id = uuid4()
    p = Product(
        name="Телефон",
        description="Смартфон",
        price=Decimal("19990.00"),
        quantity=5,
        category_ids=[cat_id],
    )

    doc_v1 = ProductCouchDbMapper.to_doc(
        p,
        categories=[
            {"id": str(cat_id), "name": "Гаджеты", "slug": "gadgets", "description": ""}
        ],
        schema_version=1,
    )
    assert "categories" in doc_v1
    assert "category_ids" not in doc_v1
    assert len(doc_v1["categories"]) == 1
    assert doc_v1["categories"][0]["id"] == str(cat_id)

    restored_v1 = ProductCouchDbMapper.from_doc(doc_v1)
    assert restored_v1.category_ids == [cat_id]

    doc_v2 = ProductCouchDbMapper.to_doc(p, schema_version=2)
    assert "categories" not in doc_v2
    assert "category_ids" in doc_v2
    assert doc_v2["category_ids"] == [str(cat_id)]
    assert doc_v2["schema_version"] == 2

    restored_v2 = ProductCouchDbMapper.from_doc(doc_v2)
    assert restored_v2.category_ids == [cat_id]


def test_lazy_migration_on_read() -> None:
    """Тест ленивой миграции при чтении v1 в режиме v2."""
    mock_client = MockCouchDbClient()
    prod_id = uuid4()
    cat_id = uuid4()

    v1_doc = {
        "_id": str(prod_id),
        "type": "product",
        "name": "Ноутбук",
        "description": "Игровой",
        "price": 89990.0,
        "price_str": "89990.00",
        "quantity": 3,
        "categories": [
            {
                "id": str(cat_id),
                "name": "Компьютеры",
                "slug": "computers",
                "description": "ПК и ноутбуки",
            }
        ],
    }
    mock_client.save_doc(settings.couchdb.products_db, v1_doc)

    old_version = settings.app_version
    settings.app_version = 2
    try:
        repo = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]
        product = repo.get_by_id(prod_id)

        assert product is not None
        assert product.name == "Ноутбук"
        assert product.category_ids == [cat_id]

        updated_doc = mock_client.get_doc(settings.couchdb.products_db, str(prod_id))
        assert updated_doc is not None
        assert "categories" not in updated_doc
        assert updated_doc.get("category_ids") == [str(cat_id)]
        assert updated_doc.get("schema_version") == 2

        cat_doc = mock_client.get_doc(settings.couchdb.categories_db, str(cat_id))
        assert cat_doc is not None
        assert cat_doc["name"] == "Компьютеры"
        assert cat_doc["slug"] == "computers"
    finally:
        settings.app_version = old_version


def test_active_background_migration() -> None:
    """Тест фоновой миграции v1 -> v2."""
    mock_client = MockCouchDbClient()
    cat1_id = uuid4()
    cat2_id = uuid4()

    for i in range(3):
        pid = uuid4()
        doc = {
            "_id": str(pid),
            "type": "product",
            "name": f"Товар {i}",
            "description": f"Описание {i}",
            "price": 100.0 * (i + 1),
            "quantity": 10,
            "categories": [
                {
                    "id": str(cat1_id),
                    "name": "Одежда",
                    "slug": "clothes",
                    "description": "",
                },
                {
                    "id": str(cat2_id),
                    "name": "Обувь",
                    "slug": "shoes",
                    "description": "",
                },
            ],
        }
        mock_client.save_doc(settings.couchdb.products_db, doc)

    migrator = CategoryMigrator(client=mock_client)  # type: ignore[arg-type]
    stats = migrator.migrate_all()

    assert stats.total_scanned == 3
    assert stats.migrated_products == 3
    assert stats.migrated_categories == 6
    assert len(stats.errors) == 0

    c1 = mock_client.get_doc(settings.couchdb.categories_db, str(cat1_id))
    c2 = mock_client.get_doc(settings.couchdb.categories_db, str(cat2_id))
    assert c1 is not None and c1["name"] == "Одежда"
    assert c2 is not None and c2["name"] == "Обувь"

    # Идемпотентность
    stats2 = migrator.migrate_all()
    assert stats2.total_scanned == 0
    assert stats2.migrated_products == 0


def test_referenced_category_repository_crud() -> None:
    """Тест CRUD и отвязки в репозитории v2."""
    mock_client = MockCouchDbClient()
    repo = CouchDbReferencedCategoryRepository(client=mock_client)  # type: ignore[arg-type]

    prod_id = uuid4()
    cat = Category(
        name="Книги",
        slug="books",
        description="Художественная литература",
    )

    # Создаем документ товара в products_db
    mock_client.save_doc(
        settings.couchdb.products_db,
        {
            "_id": str(prod_id),
            "type": "product",
            "name": "Книга",
            "price": 500.0,
            "quantity": 10,
            "category_ids": [],
            "schema_version": 2,
        },
    )

    # 1. ADD
    saved_cat = repo.add(prod_id, cat)
    assert saved_cat.name == "Книги"

    # Проверяем наличие в categories_db и связь в products_db
    cat_doc = mock_client.get_doc(settings.couchdb.categories_db, str(cat.id))
    assert cat_doc is not None
    assert cat_doc["name"] == "Книги"

    prod_doc = mock_client.get_doc(settings.couchdb.products_db, str(prod_id))
    assert prod_doc is not None
    assert str(cat.id) in prod_doc["category_ids"]

    # 2. GET_BY_ID
    retrieved = repo.get_by_id(prod_id, cat.id)
    assert retrieved is not None
    assert retrieved.slug == "books"

    # 3. LIST
    cat_list = repo.list(prod_id)
    assert len(cat_list) == 1
    assert cat_list[0].id == cat.id

    # 4. UPDATE
    cat.description = "Научная и художественная литература"
    updated = repo.update(prod_id, cat)
    assert updated is not None
    assert updated.description == "Научная и художественная литература"

    cat_doc_updated = mock_client.get_doc(settings.couchdb.categories_db, str(cat.id))
    assert cat_doc_updated is not None
    assert cat_doc_updated["description"] == "Научная и художественная литература"

    # 5. DELETE (Unlinking)
    deleted = repo.delete(prod_id, cat.id)
    assert deleted is True

    # Проверяем: ID удален из товара, но документ категории в categories_db остался
    prod_doc_after = mock_client.get_doc(settings.couchdb.products_db, str(prod_id))
    assert prod_doc_after is not None
    assert str(cat.id) not in prod_doc_after["category_ids"]

    cat_doc_persists = mock_client.get_doc(settings.couchdb.categories_db, str(cat.id))
    assert cat_doc_persists is not None
    assert cat_doc_persists["name"] == "Книги"


def test_v1_embedded_category_repository() -> None:
    """Тест классического встроенного репозитория v1."""
    mock_client = MockCouchDbClient()
    repo = CouchDbEmbeddedCategoryRepository(client=mock_client)  # type: ignore[arg-type]

    prod_id = uuid4()
    mock_client.save_doc(
        settings.couchdb.products_db,
        {
            "_id": str(prod_id),
            "type": "product",
            "name": "Чайник",
            "price": 2000.0,
            "quantity": 5,
            "categories": [],
        },
    )

    cat = Category(name="Бытовая техника", slug="appliances", description="")
    repo.add(prod_id, cat)

    # Проверяем, что категория встроена в документ товара, а categories_db пуста
    prod_doc = mock_client.get_doc(settings.couchdb.products_db, str(prod_id))
    assert prod_doc is not None
    assert len(prod_doc["categories"]) == 1
    assert prod_doc["categories"][0]["name"] == "Бытовая техника"

    assert len(mock_client.dbs.get(settings.couchdb.categories_db, {})) == 0


def test_bidirectional_lazy_migration() -> None:
    """Тест двусторонней ленивой миграции: v1 -> v2 -> v1."""
    mock_client = MockCouchDbClient()
    prod_id = uuid4()
    cat_id = uuid4()

    # Создаем товар в v1 со встроенной категорией
    mock_client.save_doc(
        settings.couchdb.products_db,
        {
            "_id": str(prod_id),
            "type": "product",
            "name": "Планшет",
            "description": "Новый",
            "price": 35000.0,
            "quantity": 3,
            "categories": [
                {
                    "id": str(cat_id),
                    "name": "Электроника",
                    "slug": "electronics",
                    "description": "Гаджеты",
                }
            ],
            "schema_version": 1,
        },
    )

    # 1. Читаем при app_version = 2 -> миграция в v2
    settings.app_version = 2
    repo_v2 = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]
    prod = repo_v2.get_by_id(prod_id)
    assert prod is not None
    assert prod.category_ids == [cat_id]

    doc_after_v2 = mock_client.get_doc(settings.couchdb.products_db, str(prod_id))
    assert doc_after_v2 is not None
    assert doc_after_v2.get("schema_version") == 2
    assert doc_after_v2.get("category_ids") == [str(cat_id)]
    assert "categories" not in doc_after_v2

    cat_doc = mock_client.get_doc(settings.couchdb.categories_db, str(cat_id))
    assert cat_doc is not None
    assert cat_doc["name"] == "Электроника"

    # 2. Переключаем app_version = 1 -> читаем -> автоматический откат в v1
    settings.app_version = 1
    repo_v1 = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]
    prod_v1 = repo_v1.get_by_id(prod_id)
    assert prod_v1 is not None
    assert prod_v1.category_ids == [cat_id]

    doc_after_v1 = mock_client.get_doc(settings.couchdb.products_db, str(prod_id))
    assert doc_after_v1 is not None
    assert doc_after_v1.get("schema_version") == 1
    assert "category_ids" not in doc_after_v1
    assert "categories" in doc_after_v1
    assert len(doc_after_v1["categories"]) == 1
    assert doc_after_v1["categories"][0]["name"] == "Электроника"
    assert doc_after_v1["categories"][0]["id"] == str(cat_id)


def test_active_background_rollback_to_v1() -> None:
    """Тест фоновой миграции v2 -> v1 (откат всех товаров)."""
    mock_client = MockCouchDbClient()
    cat_id = uuid4()
    mock_client.save_doc(
        settings.couchdb.categories_db,
        {
            "_id": str(cat_id),
            "type": "category",
            "name": "Одежда",
            "slug": "clothing",
            "description": "Стильная одежда",
        },
    )

    for i in range(3):
        pid = uuid4()
        mock_client.save_doc(
            settings.couchdb.products_db,
            {
                "_id": str(pid),
                "type": "product",
                "name": f"Товар {i}",
                "price": 100.0 * (i + 1),
                "quantity": 10,
                "category_ids": [str(cat_id)],
                "schema_version": 2,
            },
        )

    migrator = CategoryMigrator(client=mock_client)  # type: ignore[arg-type]
    stats = migrator.migrate_all_to_v1()

    assert stats.migrated_products == 3
    assert stats.migrated_categories == 3
    assert len(stats.errors) == 0

    # Проверяем, что все документы теперь v1
    for pdoc in mock_client.dbs[settings.couchdb.products_db].values():
        assert pdoc.get("schema_version") == 1
        assert "category_ids" not in pdoc
        assert len(pdoc.get("categories", [])) == 1
        assert pdoc["categories"][0]["name"] == "Одежда"


def test_composite_category_repository() -> None:
    """Тест работы CompositeCategoryRepository и маршрутизации v1/v2."""
    mock_client = MockCouchDbClient()
    v1_repo = CouchDbEmbeddedCategoryRepository(client=mock_client)  # type: ignore[arg-type]
    v2_repo = CouchDbReferencedCategoryRepository(client=mock_client)  # type: ignore[arg-type]
    migrator = CategoryMigrator(client=mock_client)  # type: ignore[arg-type]
    composite_repo = CompositeCategoryRepository(
        v1_repo=v1_repo,
        v2_repo=v2_repo,
        migrator=migrator,
        client=mock_client,  # type: ignore[arg-type]
    )

    prod_id = uuid4()
    mock_client.save_doc(
        settings.couchdb.products_db,
        {
            "_id": str(prod_id),
            "type": "product",
            "name": "Монитор",
            "price": 25000.0,
            "quantity": 4,
            "categories": [],
            "schema_version": 1,
        },
    )

    # 1. В v1 добавляем категорию через композит
    settings.app_version = 1
    cat1 = Category(name="Компьютеры", slug="pc", description="ПК")
    composite_repo.add(prod_id, cat1)

    cats_v1 = composite_repo.list(prod_id)
    assert len(cats_v1) == 1
    assert cats_v1[0].name == "Компьютеры"

    doc_v1 = mock_client.get_doc(settings.couchdb.products_db, str(prod_id))
    assert doc_v1 is not None
    assert "categories" in doc_v1

    # 2. Переключаем на v2 -> чтение через композит триггерит ленивую миграцию
    settings.app_version = 2
    cats_v2 = composite_repo.list(prod_id)
    assert len(cats_v2) == 1
    assert cats_v2[0].name == "Компьютеры"

    doc_v2 = mock_client.get_doc(settings.couchdb.products_db, str(prod_id))
    assert doc_v2 is not None
    assert doc_v2.get("schema_version") == 2
    assert "category_ids" in doc_v2

    # 3. В v2 добавляем ещё категорию
    cat2 = Category(name="Периферия", slug="peripherals", description="")
    composite_repo.add(prod_id, cat2)

    cats_all = composite_repo.list(prod_id)
    assert len(cats_all) == 2


def test_product_repository_category_delegation() -> None:
    """Тест делегирования операций над категориями из ProductRepository в CompositeCategoryRepository."""
    mock_client = MockCouchDbClient()
    prod_repo = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]

    prod_id = uuid4()
    mock_client.save_doc(
        settings.couchdb.products_db,
        {
            "_id": str(prod_id),
            "type": "product",
            "name": "Мышь",
            "price": 1500.0,
            "quantity": 10,
            "category_ids": [],
            "schema_version": 2,
        },
    )

    settings.app_version = 2
    cat = Category(name="Аксессуары", slug="accessories", description="")

    # add_category
    updated = prod_repo.add_category(prod_id, cat)
    assert updated is not None

    # get_categories
    cats = prod_repo.get_categories(prod_id)
    assert len(cats) == 1
    assert cats[0].name == "Аксессуары"

    # remove_category
    updated2 = prod_repo.remove_category(prod_id, cat.id)
    assert updated2 is not None

    cats_after = prod_repo.get_categories(prod_id)
    assert len(cats_after) == 0


def test_v2_create_and_update_category_handling() -> None:
    """Тест: create и update не мутируют существующие категории, создают недостающие и прикрепляют только валидные."""
    mock_client = MockCouchDbClient()
    settings.app_version = 2
    repo = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]

    # 1. Существующая категория
    existing_cat_id = uuid4()
    mock_client.save_doc(
        settings.couchdb.categories_db,
        {
            "_id": str(existing_cat_id),
            "type": "category",
            "name": "Оригинал",
            "slug": "orig",
            "description": "Исходное описание",
        },
    )

    # 2. Категории для создания:
    # - существующая с попыткой перезаписать поля (НЕ должна мутировать)
    # - новая категория (должна создаться в categories_db)
    cat_existing = Category(
        id=existing_cat_id,
        name="Попытка перезаписи",
        slug="changed",
        description="Новое описание",
    )
    new_cat = Category(
        name="Новая категория",
        slug="new-cat",
        description="Создается",
    )

    prod = Product(
        name="Тестовый товар",
        description="Описание",
        price=Decimal("199.99"),
        quantity=10,
    )

    # CREATE
    created = repo.create(
        prod,
        categories=[cat_existing, new_cat],
    )

    # Прикрепились существующая и новая категория
    assert created.category_ids == [existing_cat_id, new_cat.id]

    # Существующая в базе НЕ мутировала
    cat_doc = mock_client.get_doc(settings.couchdb.categories_db, str(existing_cat_id))
    assert cat_doc is not None
    assert cat_doc["name"] == "Оригинал"
    assert cat_doc["description"] == "Исходное описание"

    # Новая категория создалась в базе categories
    new_doc = mock_client.get_doc(settings.couchdb.categories_db, str(new_cat.id))
    assert new_doc is not None
    assert new_doc["name"] == "Новая категория"

    # UPDATE
    another_new_cat = Category(name="Вторая новая", slug="second")
    created.name = "Обновленный товар"
    updated = repo.update(
        created,
        categories=[cat_existing, another_new_cat],
    )
    assert updated is not None
    assert updated.category_ids == [existing_cat_id, another_new_cat.id]

    # Существующая все еще НЕ мутировала
    cat_doc_after = mock_client.get_doc(
        settings.couchdb.categories_db, str(existing_cat_id)
    )
    assert cat_doc_after is not None
    assert cat_doc_after["name"] == "Оригинал"

    # Вторая новая создалась
    sec_doc = mock_client.get_doc(
        settings.couchdb.categories_db, str(another_new_cat.id)
    )
    assert sec_doc is not None
    assert sec_doc["name"] == "Вторая новая"


def test_transition_between_v1_and_v2_on_product_operations() -> None:
    """Тест: корректный переход товара от версии 1 к 2 и от 2 к 1 при CRUD-операциях."""
    mock_client = MockCouchDbClient()

    # Шаг 1: Создаем товар в v1 со встроенной категорией
    settings.app_version = 1
    repo_v1 = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]

    cat_v1 = Category(name="Книги", slug="books", description="Бумажные книги")
    prod = Product(
        name="Война и мир",
        description="Том 1",
        price=Decimal("500.00"),
        quantity=5,
    )
    saved_v1 = repo_v1.create(prod, categories=[cat_v1])
    assert saved_v1.category_ids == [cat_v1.id]

    doc_v1 = mock_client.get_doc(settings.couchdb.products_db, str(saved_v1.id))
    assert doc_v1 is not None
    assert doc_v1.get("schema_version") == 1
    assert "categories" in doc_v1
    assert "category_ids" not in doc_v1

    # Шаг 2: Переключаемся на v2 -> обновляем товар (переход 1 -> 2)
    settings.app_version = 2
    repo_v2 = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]

    saved_v1.name = "Война и мир (юбилейное издание)"
    new_cat_v2 = Category(name="Классика", slug="classic", description="Шедевры")
    updated_v2 = repo_v2.update(saved_v1, categories=[cat_v1, new_cat_v2])
    assert updated_v2 is not None
    assert updated_v2.category_ids == [cat_v1.id, new_cat_v2.id]

    doc_v2 = mock_client.get_doc(settings.couchdb.products_db, str(saved_v1.id))
    assert doc_v2 is not None
    assert doc_v2.get("schema_version") == 2
    assert "categories" not in doc_v2
    assert doc_v2.get("category_ids") == [str(cat_v1.id), str(new_cat_v2.id)]

    # Обе категории должны быть в базе categories_db
    c1 = mock_client.get_doc(settings.couchdb.categories_db, str(cat_v1.id))
    c2 = mock_client.get_doc(settings.couchdb.categories_db, str(new_cat_v2.id))
    assert c1 is not None and c1["name"] == "Книги"
    assert c2 is not None and c2["name"] == "Классика"

    # Шаг 3: Переключаемся обратно на v1 -> обновляем товар (переход 2 -> 1)
    settings.app_version = 1
    updated_v2.description = "Все 4 тома"
    updated_v1_again = repo_v1.update(updated_v2)
    assert updated_v1_again is not None
    assert updated_v1_again.category_ids == [cat_v1.id, new_cat_v2.id]

    doc_v1_again = mock_client.get_doc(settings.couchdb.products_db, str(saved_v1.id))
    assert doc_v1_again is not None
    assert doc_v1_again.get("schema_version") == 1
    assert "category_ids" not in doc_v1_again
    assert "categories" in doc_v1_again
    assert len(doc_v1_again["categories"]) == 2


def test_product_list_sorting_by_price() -> None:
    """Тест: запрос товаров с сортировкой по цене (возрастание и убывание)."""
    mock_client = MockCouchDbClient()
    settings.app_version = 2
    repo = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]

    p1 = Product(name="Дешевый", description="...", price=Decimal("100.00"), quantity=5)
    p2 = Product(name="Средний", description="...", price=Decimal("500.00"), quantity=3)
    p3 = Product(
        name="Дорогой", description="...", price=Decimal("1500.00"), quantity=1
    )

    repo.create(p2)
    repo.create(p1)
    repo.create(p3)

    # 1. Сортировка по цене ASC
    dto_asc = ProductFilterDto(sort_by=ProductSortBy.PRICE_ASC)
    res_asc = repo.list(dto_asc)
    assert len(res_asc) == 3
    assert [p.price for p in res_asc] == [
        Decimal("100.00"),
        Decimal("500.00"),
        Decimal("1500.00"),
    ]
    assert mock_client.last_query.get("sort") == [{"price": "asc"}]
    assert mock_client.last_query.get("selector", {}).get("price", {}).get("$gte") == 0

    # 2. Сортировка по цене DESC
    dto_desc = ProductFilterDto(sort_by=ProductSortBy.PRICE_DESC)
    res_desc = repo.list(dto_desc)
    assert len(res_desc) == 3
    assert [p.price for p in res_desc] == [
        Decimal("1500.00"),
        Decimal("500.00"),
        Decimal("100.00"),
    ]
    assert mock_client.last_query.get("sort") == [{"price": "desc"}]


def test_product_list_sorting_all() -> None:
    """Тест: сортировка по названию (ASC/DESC) и по новизне (NEWEST)."""
    from datetime import datetime, timedelta

    mock_client = MockCouchDbClient()
    settings.app_version = 2
    repo = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]

    now = datetime.now(UTC)
    p_a = Product(
        name="Apple",
        description="...",
        price=Decimal(100),
        quantity=5,
        created_at=now - timedelta(days=2),
        orders_count=10,
    )
    p_b = Product(
        name="Banana",
        description="...",
        price=Decimal(200),
        quantity=5,
        created_at=now - timedelta(days=1),
        orders_count=50,
    )
    p_c = Product(
        name="Cherry",
        description="...",
        price=Decimal(300),
        quantity=5,
        created_at=now,
        orders_count=5,
    )

    repo.create(p_b)
    repo.create(p_a)
    repo.create(p_c)

    # 1. POPULARITY (orders_count DESC)
    res_pop = repo.list(ProductFilterDto(sort_by=ProductSortBy.POPULARITY))
    assert [p.name for p in res_pop] == ["Banana", "Apple", "Cherry"]
    assert mock_client.last_query.get("sort") == [{"orders_count": "desc"}]
    assert (
        mock_client.last_query.get("selector", {}).get("orders_count", {}).get("$gte")
        == 0
    )

    # 2. NAME_ASC
    res_name_asc = repo.list(ProductFilterDto(sort_by=ProductSortBy.NAME_ASC))
    assert [p.name for p in res_name_asc] == ["Apple", "Banana", "Cherry"]
    assert mock_client.last_query.get("sort") == [{"name": "asc"}]

    # 3. NAME_DESC
    res_name_desc = repo.list(ProductFilterDto(sort_by=ProductSortBy.NAME_DESC))
    assert [p.name for p in res_name_desc] == ["Cherry", "Banana", "Apple"]
    assert mock_client.last_query.get("sort") == [{"name": "desc"}]

    # 4. NEWEST
    res_newest = repo.list(ProductFilterDto(sort_by=ProductSortBy.NEWEST))
    assert [p.name for p in res_newest] == ["Cherry", "Banana", "Apple"]
    assert mock_client.last_query.get("sort") == [{"created_at": "desc"}]


def test_product_list_filter_by_category() -> None:
    """Тест: фильтрация товаров по категории (поиск по category_id и category_ids)."""
    mock_client = MockCouchDbClient()
    settings.app_version = 2
    repo = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]

    cat_books = uuid4()
    cat_games = uuid4()
    cat_music = uuid4()

    for cid, name in [
        (cat_books, "Книги"),
        (cat_games, "Игры"),
        (cat_music, "Музыка"),
    ]:
        mock_client.save_doc(
            settings.couchdb.categories_db,
            {"_id": str(cid), "type": "category", "name": name, "slug": name.lower()},
        )

    p1 = Product(
        name="Python Book",
        description="Programming",
        price=Decimal(500),
        quantity=10,
        category_ids=[cat_books],
    )
    p2 = Product(
        name="Witcher 3",
        description="RPG game",
        price=Decimal(1000),
        quantity=5,
        category_ids=[cat_games],
    )
    p3 = Product(
        name="Soundtrack CD",
        description="Game Music and Book",
        price=Decimal(300),
        quantity=3,
        category_ids=[cat_books, cat_music],
    )

    repo.create(p1)
    repo.create(p2)
    repo.create(p3)

    # 1. Поиск по одной категории (cat_books)
    res_books = repo.list(ProductFilterDto(category_ids=[cat_books]))
    assert len(res_books) == 2
    book_names = {p.name for p in res_books}
    assert book_names == {"Python Book", "Soundtrack CD"}

    # 2. Поиск по категории игр (cat_games)
    res_games = repo.list(ProductFilterDto(category_ids=[cat_games]))
    assert len(res_games) == 1
    assert res_games[0].name == "Witcher 3"

    # 3. Поиск по списку категорий (cat_games ИЛИ cat_music)
    res_multi = repo.list(ProductFilterDto(category_ids=[cat_games, cat_music]))
    assert len(res_multi) == 2
    multi_names = {p.name for p in res_multi}
    assert multi_names == {"Witcher 3", "Soundtrack CD"}


def test_product_service_nested_categories_and_attachments() -> None:
    """Тест создания и обновления товара с вложенными категориями и вложениями через ProductService."""
    from application.product.dto import ProductCreateDto
    from application.product.service import ProductService
    from domain.attachment import AttachmentMetadata
    from domain.category import Category
    from infrastructure.http.product.schemas import (
        CreateProductRequest,
        ProductAttachmentInput,
        ProductCategoryInput,
        ProductResponse,
        UpdateProductRequest,
    )

    mock_client = MockCouchDbClient()
    settings.app_version = 2
    repo = CouchDbProductRepository(client=mock_client)  # type: ignore[arg-type]
    service = ProductService(product_repository=repo)

    # 1. Создание через DTO со вложенными данными
    cat1 = Category(name="Ноутбуки", slug="laptops")
    att1 = AttachmentMetadata(
        filename="manual.pdf", content_type="application/pdf", size_bytes=1024
    )
    create_dto = ProductCreateDto(
        name="MacBook Pro",
        description="M3 Pro",
        price=Decimal("199990.00"),
        quantity=5,
        categories=[cat1],
        attachments=[att1],
    )
    resp_dto = service.create(create_dto)
    assert resp_dto.name == "MacBook Pro"
    assert len(resp_dto.categories) == 1
    assert resp_dto.categories[0].name == "Ноутбуки"
    assert len(resp_dto.attachments) == 1
    assert resp_dto.attachments[0].filename == "manual.pdf"

    # Проверка схемы ProductResponse
    resp_schema = ProductResponse.from_dto(resp_dto)
    assert len(resp_schema.categories) == 1
    assert resp_schema.categories[0].name == "Ноутбуки"
    assert len(resp_schema.attachments) == 1
    assert resp_schema.attachments[0].filename == "manual.pdf"

    # 2. Создание через CreateProductRequest (HTTP schema)
    req = CreateProductRequest(
        name="Dell XPS",
        description="Ultrabook",
        price=Decimal("150000.00"),
        quantity=3,
        categories=[
            ProductCategoryInput(
                name="Ультрабуки", slug="ultrabooks", description="Тонкие ноутбуки"
            )
        ],
        attachments=[
            ProductAttachmentInput(
                filename="photo.png", content_type="image/png", size_bytes=2048
            )
        ],
    )
    req_dto = req.to_dto()
    assert len(req_dto.categories) == 1
    assert req_dto.categories[0].name == "Ультрабуки"
    assert len(req_dto.attachments) == 1
    assert req_dto.attachments[0].filename == "photo.png"

    created_prod = service.create(req_dto)
    assert len(created_prod.categories) == 1
    assert created_prod.categories[0].name == "Ультрабуки"
    assert len(created_prod.attachments) == 1
    assert created_prod.attachments[0].filename == "photo.png"

    # 3. Обновление через UpdateProductRequest (HTTP schema)
    update_req = UpdateProductRequest(
        name="Dell XPS 15",
        categories=[ProductCategoryInput(name="Премиум ноутбуки", slug="premium")],
        attachments=[
            ProductAttachmentInput(
                filename="spec.pdf", content_type="application/pdf", size_bytes=5000
            )
        ],
    )
    update_dto = update_req.to_dto()
    updated_prod = service.update(created_prod.id, update_dto)
    assert updated_prod.name == "Dell XPS 15"
    assert len(updated_prod.categories) == 1
    assert updated_prod.categories[0].name == "Премиум ноутбуки"
    assert len(updated_prod.attachments) == 1
    assert updated_prod.attachments[0].filename == "spec.pdf"


if __name__ == "__main__":
    test_product_couchdb_mapper_v1_and_v2()
    print("PASS: test_product_couchdb_mapper_v1_and_v2")
    test_lazy_migration_on_read()
    print("PASS: test_lazy_migration_on_read")
    test_active_background_migration()
    print("PASS: test_active_background_migration")
    test_referenced_category_repository_crud()
    print("PASS: test_referenced_category_repository_crud")
    test_v1_embedded_category_repository()
    print("PASS: test_v1_embedded_category_repository")
    test_bidirectional_lazy_migration()
    print("PASS: test_bidirectional_lazy_migration")
    test_active_background_rollback_to_v1()
    print("PASS: test_active_background_rollback_to_v1")
    test_composite_category_repository()
    print("PASS: test_composite_category_repository")
    test_product_repository_category_delegation()
    print("PASS: test_product_repository_category_delegation")
    test_v2_create_and_update_category_handling()
    print("PASS: test_v2_create_and_update_category_handling")
    test_transition_between_v1_and_v2_on_product_operations()
    print("PASS: test_transition_between_v1_and_v2_on_product_operations")
    test_product_list_sorting_by_price()
    print("PASS: test_product_list_sorting_by_price")
    test_product_list_sorting_all()
    print("PASS: test_product_list_sorting_all")
    test_product_list_filter_by_category()
    print("PASS: test_product_list_filter_by_category")
    test_product_service_nested_categories_and_attachments()
    print("PASS: test_product_service_nested_categories_and_attachments")
    print("\nALL 15 TESTS PASSED SUCCESSFULLY!")
