from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from domain.attachment import AttachmentMetadata


class AttachmentCouchDbMapper:
    """Маппер метаданных вложений для CouchDB."""

    @staticmethod
    def to_dict(attachment: AttachmentMetadata) -> dict[str, Any]:
        """Преобразовать AttachmentMetadata в словарь для сохранения или встраивания."""
        return {
            "_id": str(attachment.id),
            "type": "attachment",
            "id": str(attachment.id),
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "size_bytes": attachment.size_bytes,
            "order": attachment.order,
            "upload_date": attachment.upload_date.isoformat(),
            "checksum": attachment.checksum,
            "description": attachment.description,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AttachmentMetadata:
        """Восстановить AttachmentMetadata из словаря CouchDB."""
        raw_id = data.get("id") or data.get("_id")
        att_id = UUID(str(raw_id)) if raw_id else uuid4()
        upload_date_raw = data.get("upload_date")
        if upload_date_raw:
            try:
                upload_date = datetime.fromisoformat(str(upload_date_raw))
            except (ValueError, TypeError):
                upload_date = datetime.now(UTC)
        else:
            upload_date = datetime.now(UTC)

        return AttachmentMetadata(
            id=att_id,
            filename=str(data.get("filename", "")),
            content_type=str(data.get("content_type", "")),
            size_bytes=int(data.get("size_bytes", 0)),
            order=int(data.get("order", 0)),
            upload_date=upload_date,
            checksum=str(data.get("checksum", "")),
            description=str(data.get("description", "")),
        )


attachment_to_dict = AttachmentCouchDbMapper.to_dict
dict_to_attachment = AttachmentCouchDbMapper.from_dict
