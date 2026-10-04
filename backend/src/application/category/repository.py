from abc import ABC, abstractmethod
from uuid import UUID

from domain.category import Category


class ICategoryRepository(ABC):
    """Интерфейс репозитория категорий."""

    @abstractmethod
    def get_by_id(self, category_id: UUID) -> Category | None:
        """Получить категорию по ID."""
        raise NotImplementedError

    @abstractmethod
    def get_by_ids(self, category_ids: list[UUID]) -> list[Category]:
        """Получить список категорий по их ID."""
        raise NotImplementedError

    @abstractmethod
    def exists_by_id(self, category_id: UUID) -> bool:
        """Проверить существование категории."""
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[Category]:
        """Получить список всех категорий."""
        raise NotImplementedError

    @abstractmethod
    def save(self, category: Category) -> Category:
        """Сохранить категорию."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, category_id: UUID) -> bool:
        """Удалить категорию."""
        raise NotImplementedError
