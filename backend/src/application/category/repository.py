from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from domain.category import Category


class ICategoryRepository(ABC):
    """Гранулярный интерфейс репозитория категорий конкретного товара."""

    @abstractmethod
    def get_by_id(
        self, product_id: UUID, category_id: UUID
    ) -> Category | None:
        """Получить встроенную категорию товара по ID."""
        raise NotImplementedError

    @abstractmethod
    def list_by_product_id(
        self, product_id: UUID
    ) -> list[Category]:
        """Получить список всех категорий конкретного товара."""
        raise NotImplementedError

    @abstractmethod
    def add_to_product(
        self, product_id: UUID, category: Category
    ) -> Category:
        """Встроить категорию в товар."""
        raise NotImplementedError

    @abstractmethod
    def save(
        self, product_id: UUID, category: Category
    ) -> Category:
        """Сохранить встроенную категорию товара (upsert: создание или обновление)."""
        raise NotImplementedError

    @abstractmethod
    def update_category(
        self, product_id: UUID, category: Category
    ) -> Category | None:
        """Обновить встроенную категорию товара."""
        raise NotImplementedError

    @abstractmethod
    def remove_from_product(
        self, product_id: UUID, category_id: UUID
    ) -> bool:
        """Удалить категорию из встроенных у товара."""
        raise NotImplementedError
