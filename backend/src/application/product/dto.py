from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from domain.product import Product


@dataclass(frozen=True)
class ProductCreateDto:
    name: str
    description: str
    price: Decimal
    quantity: int = 0
    category_ids: list[UUID] = field(default_factory=list)
    attachment_ids: list[UUID] = field(default_factory=list)


@dataclass(frozen=True)
class ProductUpdateDto:
    name: str | None = None
    description: str | None = None
    price: Decimal | None = None
    quantity: int | None = None
    category_ids: list[UUID] | None = None
    attachment_ids: list[UUID] | None = None


from enum import StrEnum


class ProductSortBy(StrEnum):
    POPULARITY = "popularity"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    NEWEST = "newest"


@dataclass(frozen=True)
class ProductFilterDto:
    query: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock_only: bool = False
    sort_by: ProductSortBy = ProductSortBy.POPULARITY
    category_ids: list[UUID] | None = None
    offset: int = 0
    limit: int = 50


@dataclass(frozen=True)
class ProductResponseDto:
    id: UUID
    name: str
    description: str
    price: Decimal
    quantity: int
    is_in_stock: bool
    category_ids: list[UUID] = field(default_factory=list)
    attachment_ids: list[UUID] = field(default_factory=list)

    @classmethod
    def from_domain(cls, product: Product) -> "ProductResponseDto":
        return cls(
            id=product.id,
            name=product.name,
            description=product.description,
            price=product.price,
            quantity=product.quantity,
            is_in_stock=product.is_in_stock(),
            category_ids=list(product.category_ids),
            attachment_ids=list(product.attachment_ids),
        )


@dataclass(frozen=True)
class ProductListResponseDto:
    items: list[ProductResponseDto]
    offset: int
    limit: int
