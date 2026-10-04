from uuid import UUID

from domain.category import Category

from .dto import (
    CategoryCreateDto,
    CategoryListResponseDto,
    CategoryResponseDto,
    CategoryUpdateDto,
)
from .exceptions import (
    CategoryNotFoundException,
    EmptyCategoryNameException,
)
from .repository import ICategoryRepository


class CategoryService:
    def __init__(self, category_repository: ICategoryRepository) -> None:
        self._category_repository = category_repository

    def create(self, dto: CategoryCreateDto) -> CategoryResponseDto:
        if not dto.name.strip():
            raise EmptyCategoryNameException()

        category = Category(
            name=dto.name.strip(),
            slug=dto.slug.strip(),
            description=dto.description.strip(),
        )
        saved = self._category_repository.save(category)
        return CategoryResponseDto.from_domain(saved)

    def get_by_id(self, category_id: UUID) -> CategoryResponseDto:
        category = self._category_repository.get_by_id(category_id)
        if category is None:
            raise CategoryNotFoundException(category_id)
        return CategoryResponseDto.from_domain(category)

    def get_by_ids(self, category_ids: list[UUID]) -> dict[UUID, CategoryResponseDto]:
        if not category_ids:
            return {}
        categories = self._category_repository.get_by_ids(category_ids)
        return {c.id: CategoryResponseDto.from_domain(c) for c in categories}

    def exists_by_id(self, category_id: UUID) -> bool:
        return self._category_repository.exists_by_id(category_id)

    def ensure_exists(self, category_id: UUID) -> None:
        if not self._category_repository.exists_by_id(category_id):
            raise CategoryNotFoundException(category_id)

    def list(self) -> CategoryListResponseDto:
        items = self._category_repository.list()
        return CategoryListResponseDto(
            items=[CategoryResponseDto.from_domain(c) for c in items],
            total=len(items),
        )

    def update(self, category_id: UUID, dto: CategoryUpdateDto) -> CategoryResponseDto:
        category = self._category_repository.get_by_id(category_id)
        if category is None:
            raise CategoryNotFoundException(category_id)

        if dto.name is not None:
            if not dto.name.strip():
                raise EmptyCategoryNameException()
            category.name = dto.name.strip()

        if dto.slug is not None:
            category.slug = dto.slug.strip()

        if dto.description is not None:
            category.description = dto.description.strip()

        saved = self._category_repository.save(category)
        return CategoryResponseDto.from_domain(saved)

    def delete(self, category_id: UUID) -> bool:
        if not self._category_repository.delete(category_id):
            raise CategoryNotFoundException(category_id)
        return True
