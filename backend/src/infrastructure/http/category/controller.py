from typing import Annotated

from fastapi import APIRouter, Query, status

from application.category.exceptions import (
    CategorySearchNotSupportedInV1Exception,
)
from infrastructure.environment.settings import settings
from infrastructure.http.category.dependencies import CategoryServiceDep
from infrastructure.http.category.schemas import CategoryResponse

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get(
    "",
    response_model=list[CategoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Поиск категорий",
    description=(
        "Поиск категорий по названию. Доступно только для схемы версии 2. "
        "В версии 1 возвращает 400 Bad Request."
    ),
)
def search_categories(
    service: CategoryServiceDep,
    query: Annotated[
        str | None,
        Query(description="Поисковый запрос по названию категории"),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0, description="Смещение (offset)"),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Лимит на страницу"),
    ] = 50,
) -> list[CategoryResponse]:
    if settings.app_version < 2:
        raise CategorySearchNotSupportedInV1Exception()
    result = service.search_categories(query=query, offset=offset, limit=limit)
    return [
        CategoryResponse(
            id=c.id,
            name=c.name,
            slug=c.slug,
            description=c.description,
        )
        for c in result.items
    ]
