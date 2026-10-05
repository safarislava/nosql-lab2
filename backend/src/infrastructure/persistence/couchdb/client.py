import hashlib
import json
import logging
from collections.abc import Callable
from functools import cache
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx

from infrastructure.environment.settings import settings

from .exceptions import (
    CouchDbConflictException,
    CouchDbConnectionException,
    CouchDbException,
    CouchDbNotFoundException,
)

logger = logging.getLogger(__name__)


class CouchDbClient:
    """HTTP-клиент для Apache CouchDB с поддержкой шардирования и отказоустойчивости."""

    def __init__(self) -> None:
        self.nodes: list[str] = [url.rstrip("/") for url in settings.couchdb.nodes]
        self.timeout = settings.couchdb.timeout
        self._clients: dict[str, httpx.Client] = {
            url: httpx.Client(
                base_url=url,
                auth=(settings.couchdb.user, settings.couchdb.password),
                timeout=self.timeout,
                headers={"Accept": "application/json, */*"},
            )
            for url in self.nodes
        }

    def close(self) -> None:
        """Закрыть HTTP-клиенты."""
        for client in self._clients.values():
            client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def get_node_for_doc(self, doc_id: str) -> int:
        """Целевой узел для doc_id: hash(doc_id) % len(nodes) -> 0 или 1."""
        return int(hashlib.md5(doc_id.encode()).hexdigest(), 16) % len(self.nodes)

    def _request(
        self,
        method: str,
        path: str,
        *,
        doc_id: str = "",
        node: int = -1,
        **kwargs: Any,
    ) -> httpx.Response:
        """Выполнить запрос с автоматическим переключением на соседний узел при сбое."""
        if node not in (0, 1):
            target_node = self.get_node_for_doc(doc_id) if doc_id else 0
            try:
                return self._request(method, path, node=target_node, **kwargs)
            except CouchDbConnectionException:
                alt_node = 1 - target_node
                logger.warning(
                    "Узел %d недоступен, переключение на узел %d для [%s %s]",
                    target_node,
                    alt_node,
                    method,
                    path,
                )
                return self._request(method, path, node=alt_node, **kwargs)

        url = self.nodes[node]
        client = self._clients[url]
        try:
            return client.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.error("CouchDB connection error [%s %s on %s]: %s", method, path, url, exc)
            raise CouchDbConnectionException(url, str(exc)) from exc
        except httpx.HTTPError as exc:
            logger.error("CouchDB HTTP error [%s %s]: %s", method, path, exc)
            raise CouchDbException(f"Сетевая ошибка CouchDB: {exc}") from exc

    def ping(self, *, node: int = -1) -> bool:
        """Проверить доступность узла или любого доступного."""
        if node not in (0, 1):
            return any(self.ping(node=n) for n in range(len(self.nodes)))

        try:
            resp = self._clients[self.nodes[node]].get("/")
            return resp.status_code == 200 and "couchdb" in resp.json()
        except Exception:  # noqa: BLE001
            return False

    def get_server_info(self, *, node: int = -1) -> dict[str, Any]:
        """Получить информацию об узлах."""
        if node not in (0, 1):
            return {f"node{n}": self.get_server_info(node=n) for n in range(len(self.nodes))}

        resp = self._request("GET", "/", node=node)
        if resp.status_code != 200:
            raise CouchDbException(f"Не удалось получить информацию о сервере: {resp.text}")
        return resp.json()

    def database_exists(self, db: str, *, node: int = -1) -> bool:
        """Проверить существование базы данных."""
        if node not in (0, 1):
            return all(self.database_exists(db, node=n) for n in range(len(self.nodes)))

        resp = self._request("HEAD", f"/{quote(db, safe='')}", node=node)
        return resp.status_code == 200

    def create_database(self, db: str, *, node: int = -1) -> bool:
        """Создать базу данных (на указанном узле или на обоих)."""
        if node not in (0, 1):
            return all(self.create_database(db, node=n) for n in range(len(self.nodes)))

        resp = self._request("PUT", f"/{quote(db, safe='')}", node=node)
        if resp.status_code in (200, 201):
            return True
        if resp.status_code == 412:
            return False
        raise CouchDbException(f"Не удалось создать базу '{db}' на узле {node}: {resp.text}")

    def ensure_database(self, db: str, *, node: int = -1) -> bool:
        """Создать базу данных, если она еще не создана."""
        if node not in (0, 1):
            return all(self.ensure_database(db, node=n) for n in range(len(self.nodes)))

        if not self.database_exists(db, node=node):
            return self.create_database(db, node=node)
        return True

    def delete_database(self, db: str, *, node: int = -1) -> bool:
        """Удалить базу данных."""
        if node not in (0, 1):
            return all(self.delete_database(db, node=n) for n in range(len(self.nodes)))

        resp = self._request("DELETE", f"/{quote(db, safe='')}", node=node)
        return resp.status_code == 200

    def get_doc(
        self,
        db: str,
        doc_id: str,
        *,
        rev: str = "",
        conflicts: bool = False,
        node: int = -1,
    ) -> dict[str, Any] | None:
        """Получить документ по ID."""
        params: dict[str, Any] = {}
        if rev:
            params["rev"] = rev
        if conflicts:
            params["conflicts"] = "true"

        path = f"/{quote(db, safe='')}/{quote(doc_id, safe='')}"
        resp = self._request("GET", path, doc_id=doc_id, node=node, params=params)

        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            return resp.json()

        raise CouchDbException(f"Ошибка при получении документа '{doc_id}': {resp.text}")

    def save_doc(
        self,
        db: str,
        doc: dict[str, Any],
        *,
        batch: bool = False,
        node: int = -1,
    ) -> dict[str, Any]:
        """Сохранить документ."""
        params: dict[str, str] = {}
        if batch:
            params["batch"] = "ok"

        doc_id = str(doc.get("_id", ""))

        if doc_id:
            path = f"/{quote(db, safe='')}/{quote(doc_id, safe='')}"
            resp = self._request("PUT", path, doc_id=doc_id, node=node, json=doc, params=params)
        else:
            path = f"/{quote(db, safe='')}"
            resp = self._request("POST", path, node=node, json=doc, params=params)

        if resp.status_code in (200, 201, 202):
            return resp.json()

        if resp.status_code == 409:
            raise CouchDbConflictException(doc_id or "unknown", resp.text)

        if resp.status_code == 404:
            raise CouchDbNotFoundException(f"{db}/{doc_id}")

        raise CouchDbException(f"Ошибка при сохранении документа: {resp.text}")

    def mutate_doc(
        self,
        db: str,
        doc_id: str,
        mutator: Callable[[dict[str, Any]], bool],
        *,
        create_if_missing: bool = False,
        max_retries: int = 5,
    ) -> bool:
        """Атомарно модифицировать документ с повторами при MVCC-конфликтах."""
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

        raise CouchDbConflictException(
            doc_id, "Превышено число попыток обновления из-за конфликта ревизий."
        )

    def delete_doc(
        self,
        db: str,
        doc_id: str,
        rev: str,
        *,
        node: int = -1,
    ) -> bool:
        """Удалить документ по ID и ревизии."""
        path = f"/{quote(db, safe='')}/{quote(doc_id, safe='')}"
        resp = self._request("DELETE", path, doc_id=doc_id, node=node, params={"rev": rev})

        if resp.status_code in (200, 202):
            return True
        if resp.status_code == 404:
            return False
        if resp.status_code == 409:
            raise CouchDbConflictException(doc_id, "Нельзя удалить устаревшую ревизию (409 Conflict).")

        raise CouchDbException(f"Ошибка при удалении документа '{doc_id}': {resp.text}")

    def bulk_docs(
        self,
        db: str,
        docs: list[dict[str, Any]],
        *,
        all_or_nothing: bool = False,
        node: int = -1,
    ) -> list[dict[str, Any]]:
        """Пакетное сохранение документов."""
        body: dict[str, Any] = {"docs": docs}
        if all_or_nothing:
            body["all_or_nothing"] = True

        path = f"/{quote(db, safe='')}/_bulk_docs"
        resp = self._request("POST", path, node=node, json=body)

        if resp.status_code in (200, 201):
            return resp.json()

        raise CouchDbException(f"Ошибка при пакетной вставке в базу '{db}': {resp.text}")

    def create_index(
        self,
        db: str,
        index_def: dict[str, Any],
        *,
        node: int = -1,
    ) -> dict[str, Any]:
        """Создать Mango-индекс."""
        if node not in (0, 1):
            return {f"node{n}": self.create_index(db, index_def, node=n) for n in range(len(self.nodes))}

        path = f"/{quote(db, safe='')}/_index"
        resp = self._request("POST", path, node=node, json=index_def)
        if resp.status_code in (200, 201):
            return resp.json()
        raise CouchDbException(f"Ошибка при создании индекса в базе '{db}': {resp.text}")

    def list_indexes(self, db: str, *, node: int = -1) -> list[dict[str, Any]]:
        """Список существующих индексов."""
        path = f"/{quote(db, safe='')}/_index"
        resp = self._request("GET", path, node=node)

        if resp.status_code == 200:
            return resp.json().get("indexes", [])

        raise CouchDbException(f"Ошибка при получении индексов базы '{db}': {resp.text}")

    def find(
        self,
        db: str,
        query: dict[str, Any],
        *,
        node: int = -1,
    ) -> list[dict[str, Any]]:
        """Поиск документов по Mango-селектору."""
        path = f"/{quote(db, safe='')}/_find"
        resp = self._request("POST", path, node=node, json=query)

        if resp.status_code == 200:
            return resp.json().get("docs", [])

        raise CouchDbException(f"Ошибка выполнения Mango-запроса: {resp.text}")

    def explain(
        self,
        db: str,
        query: dict[str, Any],
        *,
        node: int = -1,
    ) -> dict[str, Any]:
        """Исследовать план выполнения Mango-запроса."""
        path = f"/{quote(db, safe='')}/_explain"
        resp = self._request("POST", path, node=node, json=query)

        if resp.status_code == 200:
            return resp.json()

        raise CouchDbException(f"Ошибка получения _explain для запроса: {resp.text}")

    def save_design_doc(
        self,
        db: str,
        ddoc_name: str,
        ddoc: dict[str, Any],
        *,
        node: int = -1,
    ) -> dict[str, Any]:
        """Сохранить дизайн-документ."""
        if node not in (0, 1):
            return {f"node{n}": self.save_design_doc(db, ddoc_name, ddoc, node=n) for n in range(len(self.nodes))}

        clean_name = ddoc_name if ddoc_name.startswith("_design/") else f"_design/{ddoc_name}"
        path = f"/{quote(db, safe='')}/{clean_name}"
        resp = self._request("PUT", path, node=node, json=ddoc)
        if resp.status_code in (200, 201):
            return resp.json()
        if resp.status_code == 409:
            raise CouchDbConflictException(clean_name, "Дизайн-документ уже существует или ревизия устарела.")
        raise CouchDbException(f"Ошибка сохранения дизайн-документа '{clean_name}': {resp.text}")

    def get_design_doc(
        self,
        db: str,
        ddoc_name: str,
        *,
        node: int = -1,
    ) -> dict[str, Any] | None:
        """Получить дизайн-документ."""
        clean_name = ddoc_name if ddoc_name.startswith("_design/") else f"_design/{ddoc_name}"
        path = f"/{quote(db, safe='')}/{clean_name}"
        resp = self._request("GET", path, node=node)

        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            return resp.json()

        raise CouchDbException(f"Ошибка получения дизайн-документа '{clean_name}': {resp.text}")

    def query_view(
        self,
        db: str,
        ddoc_name: str,
        view_name: str,
        *,
        node: int = -1,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """Выполнить MapReduce view."""
        clean_ddoc = ddoc_name.removeprefix("_design/")
        path = f"/{quote(db, safe='')}/_design/{quote(clean_ddoc, safe='')}/_view/{quote(view_name, safe='')}"

        query_params: dict[str, str] = {}
        for key, value in params.items():
            if isinstance(value, bool):
                query_params[key] = "true" if value else "false"
            elif isinstance(value, (dict, list)):
                query_params[key] = json.dumps(value)
            elif isinstance(value, str):
                if key in ("key", "startkey", "endkey", "start_key", "end_key"):
                    query_params[key] = json.dumps(value)
                else:
                    query_params[key] = value
            else:
                query_params[key] = str(value)

        resp = self._request("GET", path, node=node, params=query_params)

        if resp.status_code == 200:
            return resp.json().get("rows", [])

        raise CouchDbException(f"Ошибка выполнения MapReduce view '{clean_ddoc}/{view_name}': {resp.text}")

    def replicate(
        self,
        source: str,
        target: str,
        *,
        continuous: bool = True,
        create_target: bool = True,
        cancel: bool = False,
        node: int = 0,
    ) -> dict[str, Any]:
        """Запустить репликацию."""
        body: dict[str, Any] = {
            "source": source,
            "target": target,
            "continuous": continuous,
            "create_target": create_target,
        }
        if cancel:
            body["cancel"] = True

        resp = self._request("POST", "/_replicate", node=node, json=body)

        if resp.status_code in (200, 202):
            return resp.json()

        raise CouchDbException(f"Ошибка запуска репликации ({source} -> {target}): {resp.text}")

    def setup_two_way_replication(self, db: str) -> dict[str, Any]:
        """Настроить двустороннюю непрерывную репликацию между узлами."""
        user = settings.couchdb.user
        password = settings.couchdb.password
        node0_target = f"http://{user}:{password}@{self.nodes[0].split('://')[-1]}/{quote(db, safe='')}"
        node1_target = f"http://{user}:{password}@{self.nodes[1].split('://')[-1]}/{quote(db, safe='')}"

        rep0 = self.replicate(
            source=db,
            target=node1_target,
            continuous=True,
            create_target=True,
            node=0,
        )
        rep1 = self.replicate(
            source=db,
            target=node0_target,
            continuous=True,
            create_target=True,
            node=1,
        )
        return {"node0_to_node1": rep0, "node1_to_node0": rep1}

    def get_conflicts(self, db: str, doc_id: str, *, node: int = -1) -> list[str]:
        """Получить список конфликтующих ревизий документа (_conflicts)."""
        doc = self.get_doc(db, doc_id, conflicts=True, node=node)
        if not doc:
            return []
        return doc.get("_conflicts", [])

    def resolve_conflict(
        self,
        db: str,
        doc_id: str,
        winning_doc: dict[str, Any],
        losing_revs: list[str],
        *,
        node: int = -1,
    ) -> dict[str, Any]:
        """Сохранить победившую ревизию и удалить проигравшие."""
        result = self.save_doc(db, winning_doc, node=node)
        for rev in losing_revs:
            try:
                self.delete_doc(db, doc_id, rev, node=node)
            except CouchDbException as exc:
                logger.warning("Не удалось удалить конфликтующую ревизию %s: %s", rev, exc)
        return result


@cache
def get_couchdb_client() -> CouchDbClient:
    """Синглтон CouchDbClient."""
    return CouchDbClient()


def close_couchdb_client() -> None:
    """Закрыть клиент CouchDB."""
    get_couchdb_client().close()

