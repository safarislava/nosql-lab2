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


category_to_dict = CategoryCouchDbMapper.to_dict
dict_to_category = CategoryCouchDbMapper.from_dict
