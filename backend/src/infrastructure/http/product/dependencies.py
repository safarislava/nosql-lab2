from typing import Annotated

from fastapi import Depends

from application.attachment.repository import IAttachmentRepository
from application.attachment.service import AttachmentService
from application.category.repository import ICategoryRepository
from application.category.service import CategoryService
from application.product.repository import IProductRepository
from application.product.service import ProductService
from infrastructure.persistence.postgres.product_repository import (
    PostgresProductRepository,
)

_product_repository: IProductRepository = PostgresProductRepository()
_category_repository: ICategoryRepository = ICategoryRepository()
_attachment_repository: IAttachmentRepository = IAttachmentRepository()


def get_product_repository() -> IProductRepository:
    return _product_repository


def get_category_repository() -> ICategoryRepository:
    return _category_repository


def get_attachment_repository() -> IAttachmentRepository:
    return _attachment_repository


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
    category_service: CategoryServiceDep,
    attachment_service: AttachmentServiceDep,
) -> ProductService:
    return ProductService(
        product_repository=product_repository,
        category_service=category_service,
        attachment_service=attachment_service,
    )


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
