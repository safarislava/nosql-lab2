from functools import cache
from typing import Annotated

from fastapi import Depends

from application.category.repository import ICategoryRepository
from application.category.service import CategoryService
from infrastructure.persistence.composite.category_repository import (
    CompositeCategoryRepository,
)
from infrastructure.persistence.couchdb.category_embedded_repository import (
    CouchDbEmbeddedCategoryRepository,
)
from infrastructure.persistence.couchdb.category_migrator import (
    CategoryMigrator,
)
from infrastructure.persistence.couchdb.category_referenced_repository import (
    CouchDbReferencedCategoryRepository,
)
from infrastructure.persistence.couchdb.client import get_couchdb_client


@cache
def get_category_migrator() -> CategoryMigrator:
    return CategoryMigrator(client=get_couchdb_client())


@cache
def get_category_repository() -> ICategoryRepository:
    client = get_couchdb_client()
    return CompositeCategoryRepository(
        v1_repo=CouchDbEmbeddedCategoryRepository(client=client),
        v2_repo=CouchDbReferencedCategoryRepository(client=client),
        migrator=get_category_migrator(),
        client=client,
    )


CategoryRepositoryDep = Annotated[ICategoryRepository, Depends(get_category_repository)]


def get_category_service(
    category_repository: CategoryRepositoryDep,
) -> CategoryService:
    return CategoryService(category_repository=category_repository)


CategoryServiceDep = Annotated[CategoryService, Depends(get_category_service)]
