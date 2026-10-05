from dataclasses import dataclass
from uuid import UUID

from domain.category import Category


@dataclass(frozen=True)
class CategoryCreateDto:
    name: str
    slug: str = ""
    description: str = ""


@dataclass(frozen=True)
class CategoryUpdateDto:
    name: str | None = None
    slug: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class CategoryResponseDto:
    id: UUID
    name: str
    slug: str
    description: str

    @classmethod
    def from_domain(cls, category: Category) -> "CategoryResponseDto":
        return cls(
            id=category.id,
            name=category.name,
            slug=category.slug,
            description=category.description,
        )


@dataclass(frozen=True)
class CategoryListResponseDto:
    items: list[CategoryResponseDto]
    total: int
