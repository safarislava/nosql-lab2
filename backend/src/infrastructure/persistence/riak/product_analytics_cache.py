from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from application.product.analytics_cache import IProductAnalyticsCache
from application.product.dto import PRODUCT_STOCK_STATES, ProductStateChangesDto
from infrastructure.persistence.riak.client import (
    RiakClient,
    RiakObject,
    get_riak_client,
)

logger = logging.getLogger(__name__)

BUCKET = "product_analytics"
CACHE_KEY = "changes_by_state"
TTL_SECONDS = 60


class RiakProductAnalyticsCache(IProductAnalyticsCache):
    """Кэш аналитики товаров в Riak: TTL бакета и явный сброс ключа."""

    def __init__(
        self,
        client: RiakClient | None = None,
        ttl_seconds: int = TTL_SECONDS,
        bucket: str = BUCKET,
        key: str = CACHE_KEY,
    ) -> None:
        self._client = client or get_riak_client()
        self._ttl_seconds = ttl_seconds
        self._bucket = bucket
        self._key = key
        self._generation = 0
        self._lock = threading.Lock()
        self._ensure_bucket_ttl()

    def _ensure_bucket_ttl(self) -> None:
        try:
            self._client.set_bucket_props(self._bucket, {"ttl": self._ttl_seconds})
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Не удалось задать TTL бакета '%s': %s",
                self._bucket,
                exc,
            )

    def get(self) -> list[ProductStateChangesDto] | None:
        try:
            obj = self._client.get(bucket=self._bucket, key=self._key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось прочитать кэш аналитики товаров: %s", exc)
            return None
        if obj is None or not isinstance(obj.data, dict):
            return None

        expires_at = _parse_expires_at(obj.data.get("expires_at"))
        raw_states = obj.data.get("by_state")
        expired = expires_at is None or expires_at <= datetime.now(UTC)
        if expired or not isinstance(raw_states, list):
            self.invalidate()
            return None

        try:
            stats = [
                ProductStateChangesDto(
                    state=str(item["state"]),
                    average_changes=float(item["average_changes"]),
                    product_count=int(item["product_count"]),
                )
                for item in raw_states
            ]
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Кэш аналитики товаров повреждён: %s", exc)
            self.invalidate()
            return None
        if len(stats) != len(PRODUCT_STOCK_STATES):
            self.invalidate()
            return None
        return stats

    def set(self, stats: list[ProductStateChangesDto]) -> None:
        with self._lock:
            generation = self._generation
        payload = {
            "expires_at": (
                datetime.now(UTC) + timedelta(seconds=self._ttl_seconds)
            ).isoformat(),
            "by_state": [
                {
                    "state": item.state,
                    "average_changes": item.average_changes,
                    "product_count": item.product_count,
                }
                for item in stats
            ],
        }
        try:
            self._client.put(
                RiakObject(bucket=self._bucket, key=self._key, data=payload)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось записать кэш аналитики товаров: %s", exc)
            return

        with self._lock:
            stale = generation != self._generation
        if stale:
            self._delete_quiet()

    def invalidate(self) -> None:
        with self._lock:
            self._generation += 1
        self._delete_quiet()

    def _delete_quiet(self) -> None:
        try:
            self._client.delete(bucket=self._bucket, key=self._key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось сбросить кэш аналитики товаров: %s", exc)


def _parse_expires_at(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
