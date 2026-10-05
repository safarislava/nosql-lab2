from __future__ import annotations

import builtins
import logging
from typing import Any
from uuid import UUID

from application.attachment.repository import IAttachmentRepository
from application.product.exceptions import ProductNotFoundException
from domain.attachment import AttachmentMetadata
from infrastructure.environment.settings import settings
from infrastructure.persistence.couchdb.attachment_mapper import (
    AttachmentCouchDbMapper,
)
from infrastructure.persistence.couchdb.client import CouchDbClient

logger = logging.getLogger(__name__)


class CouchDbAttachmentRepository(IAttachmentRepository):
    """Гранулярный CRUD-репозиторий вложений в CouchDB.

    Вложения хранятся непосредственно как встроенный массив `attachments`
    внутри документа товара в базе `products`.
    """

    def __init__(
        self,
        client: CouchDbClient,
    ) -> None:
        self._client = client
        self._db = settings.couchdb.products_db
        self._ensure_db_initialized()

    def _ensure_db_initialized(self) -> None:
        """Гарантировать существование базы данных товаров."""
        try:
            self._client.ensure_database(self._db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось инициализировать базу '%s': %s", self._db, exc)

    def get_by_id(
        self, product_id: UUID, attachment_id: UUID
    ) -> AttachmentMetadata | None:
        """Получить встроенное вложение товара по ID."""
        doc = self._client.get_doc(self._db, str(product_id))
        if not doc or doc.get("type") != "product":
            return None

        att_id_str = str(attachment_id)
        for a in doc.get("attachments", []):
            if isinstance(a, dict) and a.get("id") == att_id_str:
                return AttachmentCouchDbMapper.from_dict(a)

        return None

    def list(self, product_id: UUID) -> builtins.list[AttachmentMetadata]:
        """Получить список всех встроенных вложений конкретного товара."""
        doc = self._client.get_doc(self._db, str(product_id))
        if not doc or doc.get("type") != "product":
            return []

        attachments = [
            AttachmentCouchDbMapper.from_dict(a)
            for a in doc.get("attachments", [])
            if isinstance(a, dict)
        ]
        attachments.sort(key=lambda a: a.order)
        return attachments

    def add(
        self, product_id: UUID, attachment: AttachmentMetadata
    ) -> AttachmentMetadata:
        """Добавить вложение во встроенный массив товара."""
        att_dict = AttachmentCouchDbMapper.to_dict(attachment)
        att_id_str = str(attachment.id)

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            atts = doc.setdefault("attachments", [])
            for i, a in enumerate(atts):
                if isinstance(a, dict) and a.get("id") == att_id_str:
                    atts[i] = att_dict
                    return True
            atts.append(att_dict)
            return True

        if not self._client.mutate_doc(self._db, str(product_id), mutator):
            raise ProductNotFoundException(product_id)
        return attachment

    def update(
        self, product_id: UUID, attachment: AttachmentMetadata
    ) -> AttachmentMetadata | None:
        """Обновить существующее встроенное вложение товара."""
        att_dict = AttachmentCouchDbMapper.to_dict(attachment)
        att_id_str = str(attachment.id)

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            atts = doc.get("attachments", [])
            for i, a in enumerate(atts):
                if isinstance(a, dict) and a.get("id") == att_id_str:
                    atts[i] = att_dict
                    return True
            return False

        if not self._client.mutate_doc(self._db, str(product_id), mutator):
            return None
        return attachment

    def delete(self, product_id: UUID, attachment_id: UUID) -> bool:
        """Удалить встроенное вложение из товара по ID."""
        att_id_str = str(attachment_id)

        def mutator(doc: dict[str, Any]) -> bool:
            if doc.get("type") != "product":
                return False
            atts = doc.get("attachments", [])
            new_atts = [
                a
                for a in atts
                if not (isinstance(a, dict) and a.get("id") == att_id_str)
            ]
            if len(new_atts) == len(atts):
                return False
            doc["attachments"] = new_atts
            return True

        return self._client.mutate_doc(self._db, str(product_id), mutator)
