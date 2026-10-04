from abc import ABC, abstractmethod
from uuid import UUID

from domain.attachment import AttachmentMetadata


class IAttachmentRepository(ABC):
    """Интерфейс репозитория метаданных вложений."""

    @abstractmethod
    def get_by_id(self, attachment_id: UUID) -> AttachmentMetadata | None:
        """Получить вложение по ID."""
        raise NotImplementedError

    @abstractmethod
    def get_by_ids(self, attachment_ids: list[UUID]) -> list[AttachmentMetadata]:
        """Получить список вложений по их ID."""
        raise NotImplementedError

    @abstractmethod
    def exists_by_id(self, attachment_id: UUID) -> bool:
        """Проверить существование вложения."""
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[AttachmentMetadata]:
        """Получить список всех вложений."""
        raise NotImplementedError

    @abstractmethod
    def save(self, attachment: AttachmentMetadata) -> AttachmentMetadata:
        """Сохранить метаданные вложения."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, attachment_id: UUID) -> bool:
        """Удалить метаданные вложения."""
        raise NotImplementedError
