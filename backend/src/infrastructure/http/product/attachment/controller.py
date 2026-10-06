from uuid import UUID

from fastapi import APIRouter, status

from application.attachment.dto import AttachmentCreateDto, AttachmentUpdateDto
from domain.user import UserRole
from infrastructure.http.auth.dependencies import require_roles
from infrastructure.http.product.attachment.dependencies import AttachmentServiceDep
from infrastructure.http.product.attachment.schemas import (
    AttachmentResponse,
    CreateAttachmentRequest,
    UpdateAttachmentRequest,
)

router = APIRouter(prefix="/products", tags=["Product Attachments"])


@router.get(
    "/{product_id}/attachments",
    response_model=list[AttachmentResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить список метаданных вложений товара",
)
def list_product_attachments(
    product_id: UUID,
    service: AttachmentServiceDep,
) -> list[AttachmentResponse]:
    result = service.list(product_id)
    return [
        AttachmentResponse(
            id=a.id,
            filename=a.filename,
            content_type=a.content_type,
            size_bytes=a.size_bytes,
            order=a.order,
            upload_date=a.upload_date,
            checksum=a.checksum,
            description=a.description,
        )
        for a in result.items
    ]


@router.post(
    "/{product_id}/attachments",
    dependencies=[require_roles(UserRole.ADMIN)],
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить вложение к товару",
)
def add_product_attachment(
    product_id: UUID,
    request: CreateAttachmentRequest,
    service: AttachmentServiceDep,
) -> AttachmentResponse:
    dto = AttachmentCreateDto(
        filename=request.filename,
        content_type=request.content_type,
        size_bytes=request.size_bytes,
        order=request.order,
        checksum=request.checksum,
        description=request.description,
    )
    result = service.create(product_id, dto)
    return AttachmentResponse(
        id=result.id,
        filename=result.filename,
        content_type=result.content_type,
        size_bytes=result.size_bytes,
        order=result.order,
        upload_date=result.upload_date,
        checksum=result.checksum,
        description=result.description,
    )


@router.patch(
    "/{product_id}/attachments/{attachment_id}",
    dependencies=[require_roles(UserRole.ADMIN)],
    response_model=AttachmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить метаданные вложения товара",
)
def update_product_attachment(
    product_id: UUID,
    attachment_id: UUID,
    request: UpdateAttachmentRequest,
    service: AttachmentServiceDep,
) -> AttachmentResponse:
    dto = AttachmentUpdateDto(
        filename=request.filename,
        content_type=request.content_type,
        size_bytes=request.size_bytes,
        order=request.order,
        checksum=request.checksum,
        description=request.description,
    )
    result = service.update(product_id, attachment_id, dto)
    return AttachmentResponse(
        id=result.id,
        filename=result.filename,
        content_type=result.content_type,
        size_bytes=result.size_bytes,
        order=result.order,
        upload_date=result.upload_date,
        checksum=result.checksum,
        description=result.description,
    )


@router.delete(
    "/{product_id}/attachments/{attachment_id}",
    dependencies=[require_roles(UserRole.ADMIN)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить вложение товара",
)
def delete_product_attachment(
    product_id: UUID,
    attachment_id: UUID,
    service: AttachmentServiceDep,
) -> None:
    service.delete(product_id, attachment_id)
