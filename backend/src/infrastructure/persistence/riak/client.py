import logging
from dataclasses import dataclass
from functools import cache
from typing import Any

import httpx

from infrastructure.environment.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class RiakObject:
    bucket: str
    key: str
    data: Any
    bucket_type: str = "default"


def _build_kv_url(bucket: str, key: str, bucket_type: str = "default") -> str:
    return f"/types/{bucket_type}/buckets/{bucket}/keys/{key}"


def _build_bucket_props_url(bucket: str, bucket_type: str = "default") -> str:
    return f"/types/{bucket_type}/buckets/{bucket}/props"


def _build_datatype_url(bucket: str, key: str, bucket_type: str) -> str:
    return f"/types/{bucket_type}/buckets/{bucket}/datatypes/{key}"


class RiakClient:
    """HTTP-клиент для Riak KV."""

    def __init__(self) -> None:
        self.base_url = settings.riak.base_url.rstrip("/")
        self.timeout = settings.riak.timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Accept": "application/json, */*"},
        )

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            response = self._client.request(method, url, **kwargs)
            if response.status_code != 404:
                response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            logger.error("Riak error [%s %s]: %s", method, url, exc)
            raise

    def ping(self) -> bool:
        try:
            response = self._client.get("/ping")
            return response.status_code == 200 and response.text.strip() == "OK"
        except httpx.RequestError as exc:
            logger.warning("Riak ping failed: %s", exc)
            return False

    def get(
        self,
        bucket: str,
        key: str,
        bucket_type: str = "default",
    ) -> RiakObject | None:
        url = _build_kv_url(bucket, key, bucket_type)
        response = self._request("GET", url)
        if response.status_code == 404:
            return None

        return RiakObject(
            bucket=bucket,
            key=key,
            data=response.json(),
            bucket_type=bucket_type,
        )

    def set_bucket_props(
        self,
        bucket: str,
        props: dict[str, Any],
        bucket_type: str = "default",
    ) -> None:
        """Задать свойства бакета, в том числе TTL объектов."""
        url = _build_bucket_props_url(bucket, bucket_type)
        self._request(
            "PUT",
            url,
            json={"props": props},
            headers={"Content-Type": "application/json"},
        )

    def put(self, obj: RiakObject) -> RiakObject:
        url = _build_kv_url(obj.bucket, obj.key, obj.bucket_type)
        self._request(
            "PUT",
            url,
            json=obj.data,
            headers={"Content-Type": "application/json"},
        )
        return RiakObject(
            bucket=obj.bucket,
            key=obj.key,
            data=obj.data,
            bucket_type=obj.bucket_type,
        )

    def delete(self, bucket: str, key: str, bucket_type: str = "default") -> bool:
        url = _build_kv_url(bucket, key, bucket_type)
        response = self._request("DELETE", url)
        return response.status_code in (204, 404) or response.is_success

    def counter_increment(
        self,
        bucket: str,
        key: str,
        amount: int = 1,
        bucket_type: str = "counters",
        return_body: bool = True,
    ) -> int:
        url = _build_datatype_url(bucket, key, bucket_type)
        if return_body:
            url = f"{url}?returnbody=true"
        response = self._request(
            "POST",
            url,
            json={"increment": amount},
            headers={"Content-Type": "application/json"},
        )
        if return_body:
            if response.status_code == 200:
                try:
                    return int(response.json().get("value", 0))
                except (ValueError, TypeError):
                    pass
            return self.counter_get(bucket, key, bucket_type)
        return 0

    def counter_get(
        self,
        bucket: str,
        key: str,
        bucket_type: str = "counters",
    ) -> int:
        url = _build_datatype_url(bucket, key, bucket_type)
        response = self._request("GET", url)
        if response.status_code == 404:
            return 0
        return int(response.json().get("value", 0))

    def _extract_set_value(
        self,
        response: httpx.Response,
        bucket: str,
        key: str,
        bucket_type: str,
        return_body: bool,
    ) -> set[str]:
        if return_body:
            if response.status_code == 200:
                try:
                    return set(response.json().get("value", []))
                except (ValueError, TypeError):
                    pass
            return self.set_get(bucket, key, bucket_type)
        return set()

    def _extract_map_value(
        self,
        response: httpx.Response,
        bucket: str,
        key: str,
        bucket_type: str,
        return_body: bool,
    ) -> dict[str, Any]:
        if return_body:
            if response.status_code == 200:
                try:
                    val = response.json().get("value")
                    if isinstance(val, dict):
                        return val
                except (ValueError, TypeError):
                    pass
            return self.map_get(bucket, key, bucket_type) or {}
        return {}

    def set_add(
        self,
        bucket: str,
        key: str,
        elements: str | list[str],
        bucket_type: str = "sets",
        return_body: bool = False,
    ) -> set[str]:
        url = _build_datatype_url(bucket, key, bucket_type)
        if return_body:
            url = f"{url}?returnbody=true"
        payload = (
            {"add": elements} if isinstance(elements, str) else {"add_all": elements}
        )
        response = self._request(
            "POST",
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        return self._extract_set_value(
            response=response,
            bucket=bucket,
            key=key,
            bucket_type=bucket_type,
            return_body=return_body,
        )

    def set_remove(
        self,
        bucket: str,
        key: str,
        elements: str | list[str],
        bucket_type: str = "sets",
        return_body: bool = False,
    ) -> set[str]:
        url = _build_datatype_url(bucket, key, bucket_type)
        if return_body:
            url = f"{url}?returnbody=true"
        payload = (
            {"remove": elements}
            if isinstance(elements, str)
            else {"remove_all": elements}
        )
        response = self._request(
            "POST",
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        return self._extract_set_value(
            response=response,
            bucket=bucket,
            key=key,
            bucket_type=bucket_type,
            return_body=return_body,
        )

    def set_get(
        self,
        bucket: str,
        key: str,
        bucket_type: str = "sets",
    ) -> set[str]:
        url = _build_datatype_url(bucket, key, bucket_type)
        response = self._request("GET", url)
        if response.status_code == 404:
            return set()
        return set(response.json().get("value", []))

    def map_update(
        self,
        bucket: str,
        key: str,
        update_spec: dict[str, Any],
        bucket_type: str = "maps",
        return_body: bool = False,
    ) -> dict[str, Any]:
        url = _build_datatype_url(bucket, key, bucket_type)
        if return_body:
            url = f"{url}?returnbody=true"
        response = self._request(
            "POST",
            url,
            json={"update": update_spec},
            headers={"Content-Type": "application/json"},
        )
        return self._extract_map_value(
            response=response,
            bucket=bucket,
            key=key,
            bucket_type=bucket_type,
            return_body=return_body,
        )

    def map_remove(
        self,
        bucket: str,
        key: str,
        fields: str | list[str],
        bucket_type: str = "maps",
        return_body: bool = False,
    ) -> dict[str, Any]:
        url = _build_datatype_url(bucket, key, bucket_type)
        if return_body:
            url = f"{url}?returnbody=true"
        field_list = [fields] if isinstance(fields, str) else list(fields)
        response = self._request(
            "POST",
            url,
            json={"remove": field_list},
            headers={"Content-Type": "application/json"},
        )
        return self._extract_map_value(
            response=response,
            bucket=bucket,
            key=key,
            bucket_type=bucket_type,
            return_body=return_body,
        )

    def map_get(
        self,
        bucket: str,
        key: str,
        bucket_type: str = "maps",
    ) -> dict[str, Any] | None:
        url = _build_datatype_url(bucket, key, bucket_type)
        response = self._request("GET", url)
        if response.status_code == 404:
            return None
        return response.json().get("value", {})


@cache
def get_riak_client() -> RiakClient:
    """Синглтон RiakClient."""
    return RiakClient()


def close_riak_client() -> None:
    """Закрыть клиент Riak."""
    get_riak_client().close()
