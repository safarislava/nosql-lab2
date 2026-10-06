from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from domain.attachment import AttachmentMetadata


class CreateAttachmentRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=100)
    size_bytes: int = Field(default=0, ge=0)
    order: int = Field(default=0, ge=0)
    checksum: str = Field(default="")
    description: str = Field(default="", max_length=1000)


class UpdateAttachmentRequest(BaseModel):
    filename: str | None = Field(default=None, min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=100)
    size_bytes: int | None = Field(default=None, ge=0)
    order: int | None = Field(default=None, ge=0)
    checksum: str | None = Field(default=None)
    description: str | None = Field(default=None, max_length=1000)


class AttachmentResponse(BaseModel):
    id: UUID
    filename: str
    content_type: str
    size_bytes: int
    order: int
    upload_date: datetime
    checksum: str
    description: str


class ProductAttachmentInput(BaseModel):
    id: UUID | None = Field(
        default=None, description="ID существующего вложения (если есть)"
    )
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=100)
    size_bytes: int = Field(default=0, ge=0)
    order: int = Field(default=0, ge=0)
    checksum: str = Field(default="")
    description: str = Field(default="", max_length=1000)

    def to_domain(self) -> AttachmentMetadata:
        return AttachmentMetadata(
            id=self.id or uuid4(),
            filename=self.filename,
            content_type=self.content_type,
            size_bytes=self.size_bytes,
            order=self.order,
            checksum=self.checksum,
            description=self.description,
        )
