from functools import cache
from typing import Annotated

from fastapi import Depends

from application.attachment.repository import IAttachmentRepository
from application.attachment.service import AttachmentService
from application.category.repository import ICategoryRepository
from application.category.service import CategoryService
from application.product.repository import IProductRepository
from application.product.service import ProductService
from infrastructure.persistence.couchdb.attachment_repository import (
    CouchDbAttachmentRepository,
)
from infrastructure.persistence.couchdb.category_repository import (
    CouchDbCategoryRepository,
)
from infrastructure.persistence.couchdb.client import get_couchdb_client
from infrastructure.persistence.couchdb.product_repository import (
    CouchDbProductRepository,
)


@cache
def get_product_repository() -> IProductRepository:
    return CouchDbProductRepository(client=get_couchdb_client())


@cache
def get_category_repository() -> ICategoryRepository:
    return CouchDbCategoryRepository(client=get_couchdb_client())


@cache
def get_attachment_repository() -> IAttachmentRepository:
    return CouchDbAttachmentRepository(client=get_couchdb_client())


ProductRepositoryDep = Annotated[IProductRepository, Depends(get_product_repository)]
CategoryRepositoryDep = Annotated[ICategoryRepository, Depends(get_category_repository)]
AttachmentRepositoryDep = Annotated[IAttachmentRepository, Depends(get_attachment_repository)]


def get_category_service(
    category_repository: CategoryRepositoryDep,
) -> CategoryService:
    return CategoryService(category_repository=category_repository)


def get_attachment_service(
    attachment_repository: AttachmentRepositoryDep,
) -> AttachmentService:
    return AttachmentService(attachment_repository=attachment_repository)


CategoryServiceDep = Annotated[CategoryService, Depends(get_category_service)]
AttachmentServiceDep = Annotated[AttachmentService, Depends(get_attachment_service)]


def get_product_service(
    product_repository: ProductRepositoryDep,
) -> ProductService:
    return ProductService(
        product_repository=product_repository,
    )


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
