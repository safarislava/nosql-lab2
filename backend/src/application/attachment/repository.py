from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from uuid import UUID

from domain.attachment import AttachmentMetadata


class IAttachmentRepository(ABC):
    """Гранулярный CRUD-интерфейс репозитория метаданных вложений конкретного товара."""

    @abstractmethod
    def get_by_id(
        self, product_id: UUID, attachment_id: UUID
    ) -> AttachmentMetadata | None:
        """Получить вложение товара по ID."""
        raise NotImplementedError

    @abstractmethod
    def list(
        self, product_id: UUID
    ) -> builtins.list[AttachmentMetadata]:
        """Получить список всех вложений конкретного товара."""
        raise NotImplementedError

    @abstractmethod
    def add(
        self, product_id: UUID, attachment: AttachmentMetadata
    ) -> AttachmentMetadata:
        """Добавить вложение к товару."""
        raise NotImplementedError

    @abstractmethod
    def update(
        self, product_id: UUID, attachment: AttachmentMetadata
    ) -> AttachmentMetadata | None:
        """Обновить метаданные существующего вложения товара."""
        raise NotImplementedError

    @abstractmethod
    def delete(
        self, product_id: UUID, attachment_id: UUID
    ) -> bool:
        """Удалить вложение из товара по ID."""
        raise NotImplementedError
