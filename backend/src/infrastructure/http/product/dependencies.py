from functools import cache
from typing import Annotated

from fastapi import Depends

from application.product.analytics_cache import IProductAnalyticsCache
from application.product.repository import IProductRepository
from application.product.service import ProductService
from infrastructure.http.product.category.dependencies import (
    get_category_repository,
)
from infrastructure.persistence.couchdb.client import get_couchdb_client
from infrastructure.persistence.couchdb.product_repository import (
    CouchDbProductRepository,
)
from infrastructure.persistence.riak.product_analytics_cache import (
    RiakProductAnalyticsCache,
)


@cache
def get_product_analytics_cache() -> IProductAnalyticsCache:
    cache = RiakProductAnalyticsCache()
    get_couchdb_client().add_products_changed_listener(cache.invalidate)
    return cache


@cache
def get_product_repository() -> IProductRepository:
    return CouchDbProductRepository(
        client=get_couchdb_client(),
        category_repo=get_category_repository(),
    )


ProductRepositoryDep = Annotated[IProductRepository, Depends(get_product_repository)]


def get_product_service(
    product_repository: ProductRepositoryDep,
) -> ProductService:
    return ProductService(
        product_repository=product_repository,
        analytics_cache=get_product_analytics_cache(),
    )


ProductServiceDep = Annotated[ProductService, Depends(get_product_service)]
