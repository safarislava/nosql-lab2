from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from application.product.dto import ProductFilterDto, ProductSortBy
from domain.user import UserRole
from infrastructure.http.auth.dependencies import require_roles
from infrastructure.http.cart.dependencies import CartServiceDep
from infrastructure.http.favourites.dependencies import FavouritesServiceDep
from infrastructure.http.middleware.authentication_middleware import (
    OptionalCurrentUserDep,
)
from infrastructure.http.product.schemas import (
    CreateProductRequest,
    ProductAnalyticsResponse,
    ProductListResponse,
    ProductResponse,
    StockOperationRequest,
    UpdateProductRequest,
)

from .dependencies import ProductServiceDep

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "",
    response_model=ProductListResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить каталог товаров с фильтрацией и пагинацией",
)
def list_products(
    service: ProductServiceDep,
    query: Annotated[
        str | None,
        Query(description="Поисковый запрос по названию или описанию"),
    ] = None,
    min_price: Annotated[
        Decimal | None,
        Query(ge=0, description="Минимальная цена"),
    ] = None,
    max_price: Annotated[
        Decimal | None,
        Query(ge=0, description="Максимальная цена"),
    ] = None,
    in_stock_only: Annotated[
        bool,
        Query(description="Только товары в наличии"),
    ] = False,
    sort_by: Annotated[
        ProductSortBy,
        Query(description="Сортировка товаров"),
    ] = ProductSortBy.POPULARITY,
    category_ids: Annotated[
        list[UUID] | None,
        Query(description="Фильтр по категориям"),
    ] = None,
    created_from: Annotated[
        datetime | None,
        Query(description="Дата создания от, включительно"),
    ] = None,
    created_to: Annotated[
        datetime | None,
        Query(description="Дата создания до, включительно"),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Смещение (offset)"),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Лимит на страницу"),
    ] = 50,
) -> ProductListResponse:
    filter_dto = ProductFilterDto(
        query=query,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
        sort_by=sort_by,
        category_ids=category_ids,
        created_from=created_from,
        created_to=created_to,
        offset=offset,
        limit=limit,
    )
    result = service.list(filter_dto)
    return ProductListResponse.from_dto(result)


@router.get(
    "/analytics",
    dependencies=[require_roles(UserRole.ADMIN)],
    response_model=ProductAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Среднее количество изменений товара по состояниям наличия",
)
def get_product_analytics(service: ProductServiceDep) -> ProductAnalyticsResponse:
    return ProductAnalyticsResponse.from_stats(service.average_changes_by_state())


@router.post(
    "",
    dependencies=[require_roles(UserRole.ADMIN)],
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать новый товар",
)
def create_product(
    request: CreateProductRequest,
    service: ProductServiceDep,
) -> ProductResponse:
    product_dto = service.create(request.to_dto())
    return ProductResponse.from_dto(product_dto)


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Получить товар по ID",
)
def get_product_by_id(
    product_id: UUID,
    service: ProductServiceDep,
    cart_service: CartServiceDep,
    favourites_service: FavouritesServiceDep,
    current_user: OptionalCurrentUserDep,
) -> ProductResponse:
    product_dto = service.get_by_id(product_id)
    is_in_cart = False
    is_in_favourites = False

    if current_user is not None:
        is_in_cart = cart_service.is_in_cart(current_user.id, product_id)
        is_in_favourites = favourites_service.is_in_favourites(
            current_user.id, product_id
        )

    return ProductResponse.from_dto(
        product_dto,
        is_in_cart=is_in_cart,
        is_in_favourites=is_in_favourites,
    )


@router.patch(
    "/{product_id}",
    dependencies=[require_roles(UserRole.ADMIN)],
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Обновить данные товара",
)
def update_product(
    product_id: UUID,
    request: UpdateProductRequest,
    service: ProductServiceDep,
) -> ProductResponse:
    product_dto = service.update(product_id, request.to_dto())
    return ProductResponse.from_dto(product_dto)


@router.delete(
    "/{product_id}",
    dependencies=[require_roles(UserRole.ADMIN)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить товар",
)
def delete_product(
    product_id: UUID,
    service: ProductServiceDep,
) -> None:
    service.delete(product_id)


@router.post(
    "/{product_id}/reserve",
    dependencies=[require_roles(UserRole.ADMIN)],
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Зарезервировать количество товара на складе",
)
def reserve_stock(
    product_id: UUID,
    request: StockOperationRequest,
    service: ProductServiceDep,
) -> ProductResponse:
    product_dto = service.reserve_stock(product_id, request.amount)
    return ProductResponse.from_dto(product_dto)


@router.post(
    "/{product_id}/restore",
    dependencies=[require_roles(UserRole.ADMIN)],
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Вернуть зарезервированное количество товара на склад",
)
def restore_stock(
    product_id: UUID,
    request: StockOperationRequest,
    service: ProductServiceDep,
) -> ProductResponse:
    product_dto = service.restore_stock(product_id, request.amount)
    return ProductResponse.from_dto(product_dto)
