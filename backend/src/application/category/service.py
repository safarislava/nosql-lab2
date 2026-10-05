from __future__ import annotations

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

    def add_category(
        self, product_id: UUID, dto: CategoryCreateDto
    ) -> CategoryResponseDto:
        if not dto.name.strip():
            raise EmptyCategoryNameException()

        category = Category(
            name=dto.name.strip(),
            slug=dto.slug.strip(),
            description=dto.description.strip(),
        )
        saved = self._category_repository.add(product_id, category)
        return CategoryResponseDto.from_domain(saved)

    def get_by_id(self, product_id: UUID, category_id: UUID) -> CategoryResponseDto:
        category = self._category_repository.get_by_id(product_id, category_id)
        if category is None:
            raise CategoryNotFoundException(category_id)
        return CategoryResponseDto.from_domain(category)

    def list(self, product_id: UUID) -> CategoryListResponseDto:
        """Получить список категорий конкретного товара."""
        items = self._category_repository.list(product_id)
        return CategoryListResponseDto(
            items=[CategoryResponseDto.from_domain(c) for c in items],
            total=len(items),
        )

    def update_category(
        self, product_id: UUID, category_id: UUID, dto: CategoryUpdateDto
    ) -> CategoryResponseDto:
        category = self._category_repository.get_by_id(product_id, category_id)
        if category is None:
            raise CategoryNotFoundException(category_id)

        name = dto.name.strip() if dto.name is not None else category.name
        if dto.name is not None and not name:
            raise EmptyCategoryNameException()

        slug = dto.slug.strip() if dto.slug is not None else category.slug
        description = (
            dto.description.strip()
            if dto.description is not None
            else category.description
        )

        updated = Category(
            id=category.id,
            name=name,
            slug=slug,
            description=description,
        )
        saved = self._category_repository.update(product_id, updated)
        if saved is None:
            raise CategoryNotFoundException(category_id)
        return CategoryResponseDto.from_domain(saved)

    def remove_category(self, product_id: UUID, category_id: UUID) -> bool:
        if not self._category_repository.delete(product_id, category_id):
            raise CategoryNotFoundException(category_id)
        return True
