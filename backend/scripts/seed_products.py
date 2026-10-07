#!/usr/bin/env python3
"""Загрузить 20 тестовых товаров в CouchDB.

Повторный запуск не создает дубликаты: уже существующий _id пропускается.
Поле changes — сколько раз документ перезаписывается после создания,
чтобы у аналитики были ненулевые средние.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def main() -> int:
    base_url = os.environ.get("COUCHDB_URL", "http://127.0.0.1:5984").rstrip("/")
    user = os.environ.get("COUCHDB_USER", "admin")
    password = os.environ.get("COUCHDB_PASSWORD", "password")
    db = os.environ.get("COUCHDB_PRODUCTS_DB", "products")
    dataset_path = Path(__file__).with_name("products_seed.json")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    categories: dict[str, dict[str, Any]] = dataset["categories"]
    products: list[dict[str, Any]] = dataset["products"]

    auth = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
    opener = urllib.request.build_opener()
    opener.addheaders = [("Authorization", f"Basic {auth}")]

    try:
        _request(opener, "PUT", f"{base_url}/{db}")
    except urllib.error.HTTPError as exc:
        if exc.code != 412:
            _fail(exc)
    except urllib.error.URLError as exc:
        print(f"CouchDB недоступен по {base_url}: {exc.reason}", file=sys.stderr)
        return 1

    created = 0
    skipped = 0
    for product in products:
        doc_id = product["id"]
        existing = _get_doc(opener, base_url, db, doc_id)
        if existing is not None:
            skipped += 1
            print(f"пропуск  {product['name']}")
            continue

        doc = _to_doc(product, categories)
        saved = _request(opener, "PUT", f"{base_url}/{db}/{doc_id}", doc)
        rev = saved["rev"]
        for _ in range(int(product.get("changes", 0))):
            doc["_rev"] = rev
            saved = _request(opener, "PUT", f"{base_url}/{db}/{doc_id}", doc)
            rev = saved["rev"]
        created += 1
        print(f"создан   {product['name']}  правок={product.get('changes', 0)}")

    print(f"Готово: создано {created}, уже было {skipped}, всего в наборе {len(products)}")
    return 0


def _to_doc(product: dict[str, Any], categories: dict[str, dict[str, Any]]) -> dict[str, Any]:
    embedded = []
    for slug in product["categories"]:
        category = categories[slug]
        embedded.append(
            {
                "_id": category["id"],
                "type": "category",
                "id": category["id"],
                "name": category["name"],
                "slug": category["slug"],
                "description": category["description"],
            }
        )
    price = product["price"]
    return {
        "_id": product["id"],
        "type": "product",
        "name": product["name"],
        "description": product["description"],
        "price": float(price),
        "price_str": str(price),
        "quantity": int(product["quantity"]),
        "orders_count": int(product["orders_count"]),
        "attachments": [],
        "created_at": product["created_at"],
        "categories": embedded,
    }


def _get_doc(opener: urllib.request.OpenerDirector, base_url: str, db: str, doc_id: str) -> dict[str, Any] | None:
    try:
        return _request(opener, "GET", f"{base_url}/{db}/{doc_id}")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        _fail(exc)
    return None


def _request(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    for header, value in opener.addheaders:
        request.add_header(header, value)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with opener.open(request, timeout=10) as response:
            raw = response.read()
    except urllib.error.HTTPError:
        raise
    if not raw:
        return {}
    parsed = json.loads(raw.decode("utf-8"))
    return parsed if isinstance(parsed, dict) else {}


def _fail(exc: urllib.error.HTTPError) -> None:
    detail = exc.read().decode("utf-8", errors="replace")
    print(f"Ошибка CouchDB {exc.code} {exc.reason}: {detail}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    raise SystemExit(main())
