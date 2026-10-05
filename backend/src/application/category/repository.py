from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from uuid import UUID

from domain.category import Category


class ICategoryRepository(ABC):
    """Гранулярный CRUD-интерфейс репозитория категорий конкретного товара."""

    @abstractmethod
    def get_by_id(self, product_id: UUID, category_id: UUID) -> Category | None:
        """Получить категорию товара по ID."""
        raise NotImplementedError

    @abstractmethod
    def list(self, product_id: UUID) -> builtins.list[Category]:
        """Получить список всех категорий конкретного товара."""
        raise NotImplementedError

    @abstractmethod
    def add(self, product_id: UUID, category: Category) -> Category:
        """Добавить категорию к товару."""
        raise NotImplementedError

    @abstractmethod
    def update(self, product_id: UUID, category: Category) -> Category | None:
        """Обновить существующую категорию товара."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, product_id: UUID, category_id: UUID) -> bool:
        """Удалить категорию из товара по ID."""
        raise NotImplementedError
