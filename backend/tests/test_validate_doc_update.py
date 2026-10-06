from __future__ import annotations

import json
import subprocess
from typing import Any

from infrastructure.environment.settings import settings
from infrastructure.persistence.couchdb.design_documents import (
    CATEGORY_VALIDATE_DOC_UPDATE_JS,
    PRODUCT_VALIDATE_DOC_UPDATE_JS,
    ensure_validation_design_docs,
)
from infrastructure.persistence.couchdb.exceptions import CouchDbConflictException


class MockCouchDbClientWithDDoc:
    """Mock-клиент с поддержкой дизайн-документов."""

    def __init__(self) -> None:
        self.dbs: dict[str, dict[str, dict[str, Any]]] = {}
        self.nodes = ["node0", "node1"]

    def ensure_database(self, db: str, *, node: int = -1) -> None:
        if db not in self.dbs:
            self.dbs[db] = {}

    def get_design_doc(
        self, db: str, ddoc_name: str, *, node: int = -1
    ) -> dict[str, Any] | None:
        self.ensure_database(db)
        clean = (
            ddoc_name if ddoc_name.startswith("_design/") else f"_design/{ddoc_name}"
        )
        doc = self.dbs[db].get(clean)
        return dict(doc) if doc is not None else None

    def save_design_doc(
        self, db: str, ddoc_name: str, ddoc: dict[str, Any], *, node: int = -1
    ) -> dict[str, Any]:
        self.ensure_database(db)
        clean = (
            ddoc_name if ddoc_name.startswith("_design/") else f"_design/{ddoc_name}"
        )
        existing = self.dbs[db].get(clean)
        if existing and existing.get("_rev") != ddoc.get("_rev"):
            raise CouchDbConflictException(clean, "Revision conflict")
        doc_copy = dict(ddoc)
        doc_copy["_id"] = clean
        doc_copy["_rev"] = "1-mockrev"
        self.dbs[db][clean] = doc_copy
        return doc_copy


def run_js_validator(
    js_function_code: str, new_doc: dict[str, Any]
) -> tuple[bool, str]:
    """Запустить JS-функцию validate_doc_update через Node.js и вернуть (passed, error_message)."""
    script = f"""
    const validate = {js_function_code};
    const newDoc = {json.dumps(new_doc)};
    try {{
        validate(newDoc, null, {{}}, {{}});
        console.log(JSON.stringify({{ok: true}}));
    }} catch (err) {{
        console.log(JSON.stringify({{ok: false, error: err.forbidden || err.message || String(err)}}));
    }}
    """
    proc = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(proc.stdout.strip())
    return result["ok"], result.get("error", "")


def test_ensure_validation_design_docs_deployment() -> None:
    """Тест: установка дизайн-документов валидации на все базы."""
    client = MockCouchDbClientWithDDoc()
    ensure_validation_design_docs(client)  # type: ignore[arg-type]

    # Проверяем, что дизайн-документ validation появился в базе products
    prod_ddoc = client.get_design_doc(settings.couchdb.products_db, "validation")
    assert prod_ddoc is not None
    assert prod_ddoc["language"] == "javascript"
    assert prod_ddoc["validate_doc_update"] == PRODUCT_VALIDATE_DOC_UPDATE_JS

    # Проверяем базу categories
    cat_ddoc = client.get_design_doc(settings.couchdb.categories_db, "validation")
    assert cat_ddoc is not None
    assert cat_ddoc["language"] == "javascript"
    assert cat_ddoc["validate_doc_update"] == CATEGORY_VALIDATE_DOC_UPDATE_JS

    # Идемпотентность: повторный запуск не вызывает ошибок
    ensure_validation_design_docs(client)  # type: ignore[arg-type]


def test_product_validate_doc_update_valid_cases() -> None:
    """Тест: валидные документы товара v1 и v2 проходят валидацию."""
    # 1. Валидный товар v1 (встроенные категории)
    v1_doc = {
        "_id": "p1",
        "type": "product",
        "name": "Тестовый товар v1",
        "price": 199.99,
        "quantity": 10,
        "attachments": [],
        "categories": [{"id": "c1", "name": "Книги"}],
    }
    ok, err = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, v1_doc)
    assert ok, f"Ожидался успех, получена ошибка: {err}"

    # 2. Валидный товар v2 (ссылочные category_ids)
    v2_doc = {
        "_id": "p2",
        "type": "product",
        "name": "Тестовый товар v2",
        "price": 0.0,
        "quantity": 0,
        "schema_version": 2,
        "category_ids": ["c1", "c2"],
        "attachments": [{"id": "a1", "filename": "photo.jpg"}],
    }
    ok, err = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, v2_doc)
    assert ok, f"Ожидался успех, получена ошибка: {err}"

    # 3. Дизайн-документы и удаление пропускаются
    ddoc = {"_id": "_design/test", "type": "anything"}
    ok, _ = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, ddoc)
    assert ok

    deleted_doc = {"_id": "p1", "_deleted": True}
    ok, _ = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, deleted_doc)
    assert ok


def test_product_validate_doc_update_invalid_cases() -> None:
    """Тест: некорректные документы товара отклоняются функцией validate_doc_update."""
    base_valid = {
        "_id": "p1",
        "type": "product",
        "name": "Товар",
        "price": 100.0,
        "quantity": 5,
    }

    # Неверный тип
    bad_type = dict(base_valid, type="order")
    ok, err = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, bad_type)
    assert not ok and 'type обязательно и должно быть равно "product"' in err

    # Пустое имя
    bad_name = dict(base_valid, name="   ")
    ok, err = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, bad_name)
    assert not ok and 'Поле "name" обязательно' in err

    # Отрицательная цена
    bad_price = dict(base_valid, price=-10.0)
    ok, err = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, bad_price)
    assert not ok and 'Поле "price" обязательно' in err

    # Дробное количество
    bad_qty = dict(base_valid, quantity=3.5)
    ok, err = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, bad_qty)
    assert not ok and "целым числом" in err

    # Не массив в attachments
    bad_atts = dict(base_valid, attachments="not-an-array")
    ok, err = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, bad_atts)
    assert not ok and 'Поле "attachments" должно быть массивом' in err

    # v2 с embedded categories (нарушение схемы v2)
    bad_v2 = dict(base_valid, schema_version=2, categories=[{"id": "c1"}])
    ok, err = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, bad_v2)
    assert not ok and 'В схеме v2 поле "categories" недопустимо' in err

    # v1 с category_ids (нарушение схемы v1)
    bad_v1 = dict(base_valid, schema_version=1, category_ids=["c1"])
    ok, err = run_js_validator(PRODUCT_VALIDATE_DOC_UPDATE_JS, bad_v1)
    assert not ok and 'В схеме v1 поле "category_ids" недопустимо' in err


def test_category_validate_doc_update() -> None:
    """Тест: валидация документов в базе categories."""
    # Валидная категория
    valid_cat = {
        "_id": "c1",
        "type": "category",
        "name": "Электроника",
        "slug": "electronics",
    }
    ok, err = run_js_validator(CATEGORY_VALIDATE_DOC_UPDATE_JS, valid_cat)
    assert ok, f"Ожидался успех: {err}"

    # Неверный тип
    bad_type = dict(valid_cat, type="product")
    ok, err = run_js_validator(CATEGORY_VALIDATE_DOC_UPDATE_JS, bad_type)
    assert not ok and 'type обязательно и должно быть равно "category"' in err

    # Пустой slug
    bad_slug = dict(valid_cat, slug="")
    ok, err = run_js_validator(CATEGORY_VALIDATE_DOC_UPDATE_JS, bad_slug)
    assert not ok and 'Поле "slug" обязательно' in err


if __name__ == "__main__":
    test_ensure_validation_design_docs_deployment()
    print("PASS: test_ensure_validation_design_docs_deployment")
    test_product_validate_doc_update_valid_cases()
    print("PASS: test_product_validate_doc_update_valid_cases")
    test_product_validate_doc_update_invalid_cases()
    print("PASS: test_product_validate_doc_update_invalid_cases")
    test_category_validate_doc_update()
    print("PASS: test_category_validate_doc_update")
    print("\nALL VALIDATE_DOC_UPDATE TESTS PASSED!")
