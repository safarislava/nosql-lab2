from uuid import UUID

from domain.attachment import AttachmentMetadata

from .dto import (
    AttachmentCreateDto,
    AttachmentListResponseDto,
    AttachmentResponseDto,
    AttachmentUpdateDto,
)
from .exceptions import (
    AttachmentNotFoundException,
    EmptyFilenameException,
    InvalidFileSizeException,
)
from .repository import IAttachmentRepository


class AttachmentService:
    def __init__(self, attachment_repository: IAttachmentRepository) -> None:
        self._attachment_repository = attachment_repository

    def create(self, dto: AttachmentCreateDto) -> AttachmentResponseDto:
        if not dto.filename.strip():
            raise EmptyFilenameException()
        if dto.size_bytes < 0:
            raise InvalidFileSizeException()

        attachment = AttachmentMetadata(
            filename=dto.filename.strip(),
            content_type=dto.content_type.strip(),
            size_bytes=dto.size_bytes,
            order=dto.order,
            checksum=dto.checksum.strip(),
            description=dto.description.strip(),
        )
        saved = self._attachment_repository.save(attachment)
        return AttachmentResponseDto.from_domain(saved)

    def get_by_id(self, attachment_id: UUID) -> AttachmentResponseDto:
        attachment = self._attachment_repository.get_by_id(attachment_id)
        if attachment is None:
            raise AttachmentNotFoundException(attachment_id)
        return AttachmentResponseDto.from_domain(attachment)

    def get_by_ids(self, attachment_ids: list[UUID]) -> dict[UUID, AttachmentResponseDto]:
        if not attachment_ids:
            return {}
        attachments = self._attachment_repository.get_by_ids(attachment_ids)
        return {a.id: AttachmentResponseDto.from_domain(a) for a in attachments}

    def exists_by_id(self, attachment_id: UUID) -> bool:
        return self._attachment_repository.exists_by_id(attachment_id)

    def ensure_exists(self, attachment_id: UUID) -> None:
        if not self._attachment_repository.exists_by_id(attachment_id):
            raise AttachmentNotFoundException(attachment_id)

    def list(self) -> AttachmentListResponseDto:
        items = self._attachment_repository.list()
        sorted_items = sorted(items, key=lambda a: a.order)
        return AttachmentListResponseDto(
            items=[AttachmentResponseDto.from_domain(a) for a in sorted_items],
            total=len(items),
        )

    def update(self, attachment_id: UUID, dto: AttachmentUpdateDto) -> AttachmentResponseDto:
        attachment = self._attachment_repository.get_by_id(attachment_id)
        if attachment is None:
            raise AttachmentNotFoundException(attachment_id)

        filename = dto.filename.strip() if dto.filename is not None else attachment.filename
        if dto.filename is not None and not filename:
            raise EmptyFilenameException()

        size_bytes = dto.size_bytes if dto.size_bytes is not None else attachment.size_bytes
        if size_bytes < 0:
            raise InvalidFileSizeException()

        content_type = (
            dto.content_type.strip()
            if dto.content_type is not None
            else attachment.content_type
        )
        order = dto.order if dto.order is not None else attachment.order
        checksum = dto.checksum.strip() if dto.checksum is not None else attachment.checksum
        description = (
            dto.description.strip()
            if dto.description is not None
            else attachment.description
        )

        updated = AttachmentMetadata(
            id=attachment.id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            order=order,
            upload_date=attachment.upload_date,
            checksum=checksum,
            description=description,
        )
        saved = self._attachment_repository.save(updated)
        return AttachmentResponseDto.from_domain(saved)

    def delete(self, attachment_id: UUID) -> bool:
        if not self._attachment_repository.delete(attachment_id):
            raise AttachmentNotFoundException(attachment_id)
        return True
