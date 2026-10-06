from uuid import UUID

from fastapi import APIRouter, status

from application.category.dto import CategoryCreateDto, CategoryUpdateDto
from domain.user import UserRole
from infrastructure.http.auth.dependencies import require_roles
from infrastructure.http.product.category.dependencies import CategoryServiceDep
from infrastructure.http.product.category.schemas import (
    CategoryResponse,
    CreateCategoryRequest,
    UpdateCategoryRequest,
)

router = APIRouter(prefix="/products", tags=["Product Categories"])


@router.get(
    "/{product_id}/categories",
    response_model=list[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Получить список категорий товара",
)
def list_product_categories(
    product_id: UUID,
    service: CategoryServiceDep,
) -> list[CategoryResponse]:
    result = service.list(product_id)
    return [
        CategoryResponse(
            id=c.id,
            name=c.name,
            slug=c.slug,
            description=c.description,
        )
        for c in result.items
    ]


@router.post(
    "/{product_id}/categories",
    dependencies=[require_roles(UserRole.ADMIN)],
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить категорию к товару",
)
def add_product_category(
    product_id: UUID,
    request: CreateCategoryRequest,
    service: CategoryServiceDep,
) -> CategoryResponse:
    dto = CategoryCreateDto(
        name=request.name,
        slug=request.slug,
        description=request.description,
    )
    result = service.add_category(product_id, dto)
    return CategoryResponse(
        id=result.id,
        name=result.name,
        slug=result.slug,
        description=result.description,
    )


@router.patch(
    "/{product_id}/categories/{category_id}",
    dependencies=[require_roles(UserRole.ADMIN)],
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить категорию товара",
)
def update_product_category(
    product_id: UUID,
    category_id: UUID,
    request: UpdateCategoryRequest,
    service: CategoryServiceDep,
) -> CategoryResponse:
    dto = CategoryUpdateDto(
        name=request.name,
        slug=request.slug,
        description=request.description,
    )
    result = service.update_category(product_id, category_id, dto)
    return CategoryResponse(
        id=result.id,
        name=result.name,
        slug=result.slug,
        description=result.description,
    )


@router.delete(
    "/{product_id}/categories/{category_id}",
    dependencies=[require_roles(UserRole.ADMIN)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить категорию у товара",
)
def delete_product_category(
    product_id: UUID,
    category_id: UUID,
    service: CategoryServiceDep,
) -> None:
    service.remove_category(product_id, category_id)
