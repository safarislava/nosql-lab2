from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from uuid import UUID

from domain.attachment import AttachmentMetadata
from domain.category import Category
from domain.product import Product

from .dto import ProductFilterDto


class IProductRepository(ABC):
    """Интерфейс репозитория товаров (корень агрегата)."""

    @abstractmethod
    def get_by_id(self, product_id: UUID) -> Product | None:
        """Получить товар по ID."""
        raise NotImplementedError

    @abstractmethod
    def get_by_ids(self, product_ids: list[UUID]) -> list[Product]:
        """Получить список товаров по их ID."""
        raise NotImplementedError

    @abstractmethod
    def exists_by_id(self, product_id: UUID) -> bool:
        """Проверить существование товара."""
        raise NotImplementedError

    @abstractmethod
    def list(
        self,
        filter_dto: ProductFilterDto | None = None,
    ) -> list[Product]:
        """Получить список товаров с фильтрацией."""
        raise NotImplementedError

    @abstractmethod
    def create(
        self,
        product: Product,
        categories: builtins.list[Category] | None = None,
        attachments: builtins.list[AttachmentMetadata] | None = None,
    ) -> Product:
        """Создать новый товар."""
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        product: Product,
        categories: builtins.list[Category] | None = None,
        attachments: builtins.list[AttachmentMetadata] | None = None,
    ) -> Product | None:
        """Обновить существующий товар."""
        raise NotImplementedError

    @abstractmethod
    def update_stock(self, product_id: UUID, delta: int) -> bool:
        """Изменить остаток товара на складе."""
        raise NotImplementedError

    @abstractmethod
    def update_stock_and_get(self, product_id: UUID, delta: int) -> Product | None:
        """Изменить остаток товара на складе и вернуть обновленный товар в одном запросе."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, product_id: UUID) -> bool:
        """Удалить товар."""
        raise NotImplementedError

    @abstractmethod
    def get_categories(self, product_id: UUID) -> builtins.list[Category]:
        """Получить встроенные категории товара."""
        raise NotImplementedError

    @abstractmethod
    def get_attachments(self, product_id: UUID) -> builtins.list[AttachmentMetadata]:
        """Получить встроенные вложения товара."""
        raise NotImplementedError

    @abstractmethod
    def add_category(self, product_id: UUID, category: Category) -> Product | None:
        """Добавить встроенную категорию к товару."""
        raise NotImplementedError

    @abstractmethod
    def remove_category(self, product_id: UUID, category_id: UUID) -> Product | None:
        """Удалить встроенную категорию из товара."""
        raise NotImplementedError

    @abstractmethod
    def add_attachment(
        self, product_id: UUID, attachment: AttachmentMetadata
    ) -> Product | None:
        """Добавить встроенное вложение к товару."""
        raise NotImplementedError

    @abstractmethod
    def remove_attachment(
        self, product_id: UUID, attachment_id: UUID
    ) -> Product | None:
        """Удалить встроенное вложение из товара."""
        raise NotImplementedError
