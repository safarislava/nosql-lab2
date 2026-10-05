from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.attachment import AttachmentMetadata


@dataclass(frozen=True)
class AttachmentCreateDto:
    filename: str
    content_type: str
    size_bytes: int
    order: int = 0
    checksum: str = ""
    description: str = ""


@dataclass(frozen=True)
class AttachmentUpdateDto:
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    order: int | None = None
    checksum: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class AttachmentResponseDto:
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    order: int
    upload_date: datetime
    checksum: str
    description: str

    @classmethod
    def from_domain(cls, attachment: AttachmentMetadata) -> "AttachmentResponseDto":
        return cls(
            id=attachment.id,
            filename=attachment.filename,
            content_type=attachment.content_type,
            size_bytes=attachment.size_bytes,
            order=attachment.order,
            upload_date=attachment.upload_date,
            checksum=attachment.checksum,
            description=attachment.description,
        )


@dataclass(frozen=True)
class AttachmentListResponseDto:
    items: list[AttachmentResponseDto]
    total: int
