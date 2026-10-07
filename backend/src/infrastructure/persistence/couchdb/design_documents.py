from __future__ import annotations

import logging

from infrastructure.environment.settings import settings
from infrastructure.persistence.couchdb.client import CouchDbClient

logger = logging.getLogger(__name__)

PRODUCT_VALIDATE_DOC_UPDATE_JS = """
function(newDoc, oldDoc, userCtx, secObj) {
    if (newDoc._id && newDoc._id.indexOf('_design/') === 0) {
        return;
    }
    if (newDoc._deleted) {
        return;
    }
    if (!newDoc.type || newDoc.type !== 'product') {
        throw({forbidden: 'Поле type обязательно и должно быть равно "product"'});
    }
    if (typeof newDoc.name !== 'string' || newDoc.name.trim().length === 0) {
        throw({forbidden: 'Поле "name" обязательно и не должно быть пустым'});
    }
    if (typeof newDoc.price !== 'number' || isNaN(newDoc.price) || newDoc.price < 0) {
        throw({forbidden: 'Поле "price" обязательно и должно быть неотрицательным числом'});
    }
    if (typeof newDoc.quantity !== 'number' || newDoc.quantity < 0 || Math.floor(newDoc.quantity) !== newDoc.quantity) {
        throw({forbidden: 'Поле "quantity" обязательно и должно быть неотрицательным целым числом'});
    }
    if (newDoc.attachments && !Array.isArray(newDoc.attachments)) {
        throw({forbidden: 'Поле "attachments" должно быть массивом'});
    }
    var schemaVersion = newDoc.schema_version || 1;
    if (schemaVersion >= 2) {
        if (newDoc.category_ids && !Array.isArray(newDoc.category_ids)) {
            throw({forbidden: 'В схеме v2 поле "category_ids" должно быть массивом'});
        }
        if (newDoc.categories && newDoc.categories.length > 0) {
            throw({forbidden: 'В схеме v2 поле "categories" недопустимо (используйте category_ids)'});
        }
    } else {
        if (newDoc.categories && !Array.isArray(newDoc.categories)) {
            throw({forbidden: 'В схеме v1 поле "categories" должно быть массивом'});
        }
        if (newDoc.category_ids && newDoc.category_ids.length > 0) {
            throw({forbidden: 'В схеме v1 поле "category_ids" недопустимо (используйте categories)'});
        }
    }
}
""".strip()

PRODUCT_CHANGES_BY_STATE_MAP_JS = """
function(doc) {
    if (doc._deleted) {
        return;
    }
    if (!doc.type || doc.type !== 'product') {
        return;
    }
    var generation = 1;
    if (typeof doc._rev === 'string') {
        var parsed = parseInt(doc._rev.split('-')[0], 10);
        if (!isNaN(parsed) && parsed > 0) {
            generation = parsed;
        }
    }
    var changes = generation - 1;
    var state = (typeof doc.quantity === 'number' && doc.quantity > 0)
        ? 'in_stock'
        : 'out_of_stock';
    emit(state, changes);
}
""".strip()

CATEGORY_VALIDATE_DOC_UPDATE_JS = """
function(newDoc, oldDoc, userCtx, secObj) {
    if (newDoc._id && newDoc._id.indexOf('_design/') === 0) {
        return;
    }
    if (newDoc._deleted) {
        return;
    }
    if (!newDoc.type || newDoc.type !== 'category') {
        throw({forbidden: 'Поле type обязательно и должно быть равно "category"'});
    }
    if (typeof newDoc.name !== 'string' || newDoc.name.trim().length === 0) {
        throw({forbidden: 'Поле "name" обязательно и не должно быть пустым'});
    }
    if (typeof newDoc.slug !== 'string' || newDoc.slug.trim().length === 0) {
        throw({forbidden: 'Поле "slug" обязательно и не должно быть пустым'});
    }
}
""".strip()


def ensure_validation_design_docs(client: CouchDbClient) -> None:
    """Установить дизайн-документы валидации для баз products и categories."""
    validators = {
        settings.couchdb.products_db: PRODUCT_VALIDATE_DOC_UPDATE_JS,
        settings.couchdb.categories_db: CATEGORY_VALIDATE_DOC_UPDATE_JS,
    }

    for db, js in validators.items():
        try:
            client.ensure_database(db)
            existing = client.get_design_doc(db, "validation")
            if existing and existing.get("validate_doc_update") == js:
                continue

            ddoc = {
                "language": "javascript",
                "validate_doc_update": js,
            }
            if existing:
                ddoc["_rev"] = existing["_rev"]

            client.save_design_doc(db, "validation", ddoc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось установить валидацию для базы '%s': %s", db, exc)


def ensure_product_analytics_view(client: CouchDbClient) -> None:
    """Установить MapReduce-view среднего числа правок товара по состояниям."""
    db = settings.couchdb.products_db
    view = {
        "map": PRODUCT_CHANGES_BY_STATE_MAP_JS,
        "reduce": "_stats",
    }
    try:
        client.ensure_database(db)
        existing = client.get_design_doc(db, "analytics")
        views = (existing or {}).get("views") or {}
        current = views.get("changes_by_state") or {}
        same_map = current.get("map") == view["map"]
        same_reduce = current.get("reduce") == view["reduce"]
        if same_map and same_reduce:
            return

        ddoc = {
            "language": "javascript",
            "views": {"changes_by_state": view},
        }
        if existing and existing.get("_rev"):
            ddoc["_rev"] = existing["_rev"]
        client.save_design_doc(db, "analytics", ddoc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось установить аналитический view товаров: %s", exc)


def ensure_product_indexes(client: CouchDbClient) -> None:
    """Установить необходимые Mango-индексы для базы товаров."""
    if not hasattr(client, "create_index"):
        return
    indexes = [
        {
            "index": {"fields": ["orders_count"]},
            "name": "idx_products_orders_count",
            "type": "json",
        },
        {
            "index": {"fields": ["price"]},
            "name": "idx_products_price",
            "type": "json",
        },
        {
            "index": {"fields": ["name"]},
            "name": "idx_products_name",
            "type": "json",
        },
        {
            "index": {"fields": ["created_at"]},
            "name": "idx_products_created_at",
            "type": "json",
        },
        {
            "index": {"fields": ["category_ids"]},
            "name": "idx_products_category_ids",
            "type": "json",
        },
        {
            "index": {"fields": ["category_ids", "created_at"]},
            "name": "idx_products_category_created_at",
            "type": "json",
        },
    ]
    try:
        client.ensure_database(settings.couchdb.products_db)
        for idx in indexes:
            client.create_index(settings.couchdb.products_db, idx)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось создать индексы для товаров: %s", exc)


def ensure_category_indexes(client: CouchDbClient) -> None:
    """Установить необходимые Mango-индексы для базы категорий."""
    if not hasattr(client, "create_index"):
        return
    indexes = [
        {
            "index": {"fields": ["name"]},
            "name": "idx_categories_name",
            "type": "json",
        },
        {
            "index": {"fields": ["type"]},
            "name": "idx_categories_type",
            "type": "json",
        },
    ]
    try:
        client.ensure_database(settings.couchdb.categories_db)
        for idx in indexes:
            client.create_index(settings.couchdb.categories_db, idx)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось создать индексы для категорий: %s", exc)
