from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from domain.category import Category


class CategoryCouchDbMapper:
    """Маппер категории для CouchDB."""

    @staticmethod
    def to_dict(category: Category) -> dict[str, Any]:
        """Преобразовать Category в словарь для сохранения или встраивания."""
        return {
            "_id": str(category.id),
            "type": "category",
            "id": str(category.id),
            "name": category.name,
            "slug": category.slug,
            "description": category.description,
            "updated_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Category:
        """Восстановить Category из словаря CouchDB."""
        raw_id = data.get("id") or data.get("_id")
        cat_id = UUID(str(raw_id)) if raw_id else uuid4()
        return Category(
            id=cat_id,
            name=str(data.get("name", "")),
            slug=str(data.get("slug", "")),
            description=str(data.get("description", "")),
        )

    @staticmethod
    def mutator(category: Category) -> Callable[[dict[str, Any]], bool]:
        """Создать функцию-мутатор для сохранения категории в базу categories."""
        name = category.name
        slug = category.slug
        desc = category.description

        def _mutator(doc: dict[str, Any]) -> bool:
            doc["type"] = "category"
            doc["name"] = name
            doc["slug"] = slug
            doc["description"] = desc
            return True

        return _mutator

    @staticmethod
    def find_by_ids_query(category_ids: Sequence[UUID | str]) -> dict[str, Any]:
        """Mango-запрос для поиска списка категорий по ID."""
        cids = [str(cid) for cid in category_ids if cid]
        return {
            "selector": {
                "type": "category",
                "_id": {"$in": cids},
            },
            "limit": len(cids) or 1,
        }


category_to_dict = CategoryCouchDbMapper.to_dict
dict_to_category = CategoryCouchDbMapper.from_dict
