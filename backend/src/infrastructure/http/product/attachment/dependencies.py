from functools import cache
from typing import Annotated

from fastapi import Depends

from application.attachment.repository import IAttachmentRepository
from application.attachment.service import AttachmentService
from infrastructure.persistence.couchdb.attachment_repository import (
    CouchDbAttachmentRepository,
)
from infrastructure.persistence.couchdb.client import get_couchdb_client


@cache
def get_attachment_repository() -> IAttachmentRepository:
    return CouchDbAttachmentRepository(client=get_couchdb_client())


AttachmentRepositoryDep = Annotated[
    IAttachmentRepository, Depends(get_attachment_repository)
]


def get_attachment_service(
    attachment_repository: AttachmentRepositoryDep,
) -> AttachmentService:
    return AttachmentService(attachment_repository=attachment_repository)


AttachmentServiceDep = Annotated[AttachmentService, Depends(get_attachment_service)]
