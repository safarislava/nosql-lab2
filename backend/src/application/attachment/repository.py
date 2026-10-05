from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from domain.attachment import AttachmentMetadata


class IAttachmentRepository(ABC):
    """Гранулярный интерфейс репозитория метаданных вложений конкретного товара."""

    @abstractmethod
    def get_by_id(
        self, product_id: UUID, attachment_id: UUID
    ) -> AttachmentMetadata | None:
        """Получить вложение товара по ID."""
        raise NotImplementedError

    @abstractmethod
    def list_by_product_id(
        self, product_id: UUID
    ) -> list[AttachmentMetadata]:
        """Получить список всех вложений конкретного товара."""
        raise NotImplementedError

    @abstractmethod
    def save(
        self, product_id: UUID, attachment: AttachmentMetadata
    ) -> AttachmentMetadata:
        """Сохранить метаданные вложения внутри товара."""
        raise NotImplementedError

    @abstractmethod
    def update_attachment(
        self, product_id: UUID, attachment: AttachmentMetadata
    ) -> AttachmentMetadata | None:
        """Обновить метаданные встроенного вложения."""
        raise NotImplementedError

    @abstractmethod
    def delete(
        self, product_id: UUID, attachment_id: UUID
    ) -> bool:
        """Удалить метаданные вложения из товара."""
        raise NotImplementedError
