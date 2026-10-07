from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Any

from application.product.dto import (
    IN_STOCK_STATE,
    OUT_OF_STOCK_STATE,
    ProductStateChangesDto,
)
from application.product.service import ProductService
from infrastructure.environment.settings import settings
from infrastructure.persistence.couchdb.design_documents import (
    PRODUCT_CHANGES_BY_STATE_MAP_JS,
    ensure_product_analytics_view,
)
from infrastructure.persistence.couchdb.product_repository import (
    CouchDbProductRepository,
)
from infrastructure.persistence.riak.client import RiakObject
from infrastructure.persistence.riak.product_analytics_cache import (
    RiakProductAnalyticsCache,
)
from tests.test_validate_doc_update import MockCouchDbClientWithDDoc


class FakeViewClient:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    def ensure_database(self, db: str, *, node: int = -1) -> bool:
        return True

    def query_view(
        self,
        db: str,
        ddoc_name: str,
        view_name: str,
        **params: Any,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {"db": db, "ddoc": ddoc_name, "view": view_name, "params": params}
        )
        return self.rows


class FakeRiak:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], Any] = {}
        self.props: dict[str, dict[str, Any]] = {}

    def set_bucket_props(
        self,
        bucket: str,
        props: dict[str, Any],
        bucket_type: str = "default",
    ) -> None:
        self.props[bucket] = props

    def get(self, bucket: str, key: str, bucket_type: str = "default") -> RiakObject | None:
        data = self.objects.get((bucket, key))
        if data is None:
            return None
        return RiakObject(bucket=bucket, key=key, data=data, bucket_type=bucket_type)

    def put(self, obj: RiakObject) -> RiakObject:
        self.objects[(obj.bucket, obj.key)] = obj.data
        return obj

    def delete(self, bucket: str, key: str, bucket_type: str = "default") -> bool:
        self.objects.pop((bucket, key), None)
        return True


class FakeProductRepository:
    def __init__(self, stats: list[ProductStateChangesDto]) -> None:
        self.stats = stats
        self.calls = 0

    def average_changes_by_state(self) -> list[ProductStateChangesDto]:
        self.calls += 1
        return self.stats


def test_analytics_view_is_installed_once() -> None:
    client = MockCouchDbClientWithDDoc()
    ensure_product_analytics_view(client)
    ensure_product_analytics_view(client)

    doc = client.get_design_doc(settings.couchdb.products_db, "analytics")
    assert doc is not None
    view = doc["views"]["changes_by_state"]
    assert view["map"] == PRODUCT_CHANGES_BY_STATE_MAP_JS
    assert view["reduce"] == "_stats"
    assert doc["_rev"] == "1-mockrev"


def test_average_changes_by_state_from_view_rows() -> None:
    client = FakeViewClient(
        [
            {
                "key": IN_STOCK_STATE,
                "value": {"sum": 5, "count": 2, "min": 1, "max": 4, "sumsqr": 17},
            },
            {
                "key": OUT_OF_STOCK_STATE,
                "value": {"sum": 0, "count": 1, "min": 0, "max": 0, "sumsqr": 0},
            },
        ]
    )
    repo = CouchDbProductRepository(client=client, category_repo=object())  # type: ignore[arg-type]

    stats = repo.average_changes_by_state()

    assert client.calls[0]["ddoc"] == "analytics"
    assert client.calls[0]["view"] == "changes_by_state"
    assert client.calls[0]["params"]["group"] is True
    assert stats == [
        ProductStateChangesDto(
            state=IN_STOCK_STATE,
            average_changes=2.5,
            product_count=2,
        ),
        ProductStateChangesDto(
            state=OUT_OF_STOCK_STATE,
            average_changes=0.0,
            product_count=1,
        ),
    ]


def test_missing_state_is_reported_as_zero() -> None:
    client = FakeViewClient([])
    repo = CouchDbProductRepository(client=client, category_repo=object())  # type: ignore[arg-type]

    stats = repo.average_changes_by_state()

    assert [item.product_count for item in stats] == [0, 0]
    assert [item.average_changes for item in stats] == [0.0, 0.0]


def test_service_uses_cache_until_it_is_invalidated() -> None:
    stats = [
        ProductStateChangesDto(IN_STOCK_STATE, 1.0, 1),
        ProductStateChangesDto(OUT_OF_STOCK_STATE, 0.0, 0),
    ]
    repo = FakeProductRepository(stats)
    riak = FakeRiak()
    cache = RiakProductAnalyticsCache(client=riak, ttl_seconds=60)  # type: ignore[arg-type]
    service = ProductService(product_repository=repo, analytics_cache=cache)  # type: ignore[arg-type]

    assert service.average_changes_by_state() == stats
    assert service.average_changes_by_state() == stats
    assert repo.calls == 1
    assert riak.props["product_analytics"]["ttl"] == 60

    cache.invalidate()
    assert service.average_changes_by_state() == stats
    assert repo.calls == 2


def test_cache_expires_by_stored_deadline() -> None:
    riak = FakeRiak()
    cache = RiakProductAnalyticsCache(client=riak, ttl_seconds=60)  # type: ignore[arg-type]
    stats = [
        ProductStateChangesDto(IN_STOCK_STATE, 3.0, 4),
        ProductStateChangesDto(OUT_OF_STOCK_STATE, 1.0, 2),
    ]
    cache.set(stats)
    stored = riak.objects[("product_analytics", "changes_by_state")]
    stored["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()

    assert cache.get() is None
    assert ("product_analytics", "changes_by_state") not in riak.objects


def test_map_counts_updates_and_stock_state() -> None:
    docs = json.dumps(
        [
            {"type": "product", "_rev": "1-aaa", "quantity": 2},
            {"type": "product", "_rev": "4-bbb", "quantity": 0},
            {"type": "product", "_rev": "3-ccc", "quantity": 1, "_deleted": True},
            {"type": "category", "_rev": "8-ddd", "quantity": 5},
        ]
    )
    script = (
        "const map = "
        + PRODUCT_CHANGES_BY_STATE_MAP_JS
        + ";\n"
        + "const docs = "
        + docs
        + """;
    const rows = [];
    function emit(key, value) { rows.push([key, value]); }
    for (const doc of docs) {
        map(doc);
    }
    console.log(JSON.stringify(rows));
    """
    )
    proc = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(proc.stdout) == [
        [IN_STOCK_STATE, 0],
        [OUT_OF_STOCK_STATE, 3],
    ]
