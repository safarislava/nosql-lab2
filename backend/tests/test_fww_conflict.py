from typing import Any

from infrastructure.persistence.couchdb.client import (
    CouchDbClient,
    first_write_stamp,
    select_first_write,
)


def test_select_first_write_prefers_earliest_stamp() -> None:
    """FWW оставляет ветку с минимальным updated_at, а не текущую победившую."""
    later = {
        "_id": "p",
        "_rev": "4-new",
        "name": "позже",
        "updated_at": "2026-03-01T00:00:00+00:00",
    }
    earlier = {
        "_id": "p",
        "_rev": "2-old",
        "name": "раньше",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    chosen = select_first_write([later, earlier])
    assert chosen["name"] == "раньше"
    assert first_write_stamp(chosen) == "2026-01-01T00:00:00+00:00"


def test_resolve_conflicts_fww_keeps_earliest_branch() -> None:
    """Конфликт репликации переписывается телом самой ранней ветки."""
    client = object.__new__(CouchDbClient)
    current = {
        "_id": "p",
        "_rev": "4-win",
        "name": "позже",
        "updated_at": "2026-03-01T00:00:00+00:00",
        "_conflicts": ["2-old"],
    }
    older = {
        "_id": "p",
        "_rev": "2-old",
        "name": "раньше",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    saved: dict[str, Any] = {}

    def get_doc(
        db: str,
        doc_id: str,
        *,
        rev: str = "",
        conflicts: bool = False,
        node: int = -1,
    ) -> dict[str, Any] | None:
        if rev == "2-old":
            return dict(older)
        if saved:
            return dict(saved["stored"])
        return dict(current)

    def resolve_conflict(
        db: str,
        doc_id: str,
        winning_doc: dict[str, Any],
        losing_revs: list[str],
        *,
        node: int = -1,
    ) -> dict[str, Any]:
        saved["doc"] = dict(winning_doc)
        saved["losers"] = list(losing_revs)
        stored = dict(winning_doc)
        stored["_rev"] = "5-resolved"
        saved["stored"] = stored
        return {"rev": "5-resolved"}

    client.get_doc = get_doc  # type: ignore[method-assign]
    client.resolve_conflict = resolve_conflict  # type: ignore[method-assign]

    result = CouchDbClient.resolve_conflicts_fww(client, "products", "p")

    assert saved["losers"] == ["2-old"]
    assert saved["doc"]["name"] == "раньше"
    assert saved["doc"]["_rev"] == "4-win"
    assert saved["doc"]["updated_at"] == "2026-01-01T00:00:00+00:00"
    assert "_conflicts" not in saved["doc"]
    assert result is not None
    assert result["name"] == "раньше"


def test_resolve_conflicts_fww_without_conflicts_reads_doc() -> None:
    """Без _conflicts документ возвращается как есть и не перезаписывается."""
    client = object.__new__(CouchDbClient)
    doc = {
        "_id": "p",
        "_rev": "1-a",
        "name": "один",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }

    def get_doc(
        db: str,
        doc_id: str,
        *,
        rev: str = "",
        conflicts: bool = False,
        node: int = -1,
    ) -> dict[str, Any]:
        return dict(doc)

    def resolve_conflict(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("resolve_conflict не должен вызываться")

    client.get_doc = get_doc  # type: ignore[method-assign]
    client.resolve_conflict = resolve_conflict  # type: ignore[method-assign]

    result = CouchDbClient.resolve_conflicts_fww(client, "products", "p")
    assert result == doc
