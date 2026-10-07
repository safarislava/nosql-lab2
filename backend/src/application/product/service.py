import builtins
from decimal import Decimal
from uuid import UUID

from application.attachment.dto import AttachmentResponseDto
from application.category.dto import CategoryResponseDto
from application.product.analytics_cache import IProductAnalyticsCache
from domain.product import Product

from .dto import (
    ProductCreateDto,
    ProductFilterDto,
    ProductListResponseDto,
    ProductResponseDto,
    ProductStateChangesDto,
    ProductUpdateDto,
)
from .exceptions import (
    EmptyProductNameException,
    InsufficientStockException,
    InvalidStockAmountException,
    NegativeProductPriceException,
    NegativeProductQuantityException,
    ProductNotFoundException,
)
from .repository import IProductRepository


class ProductService:
    def __init__(
        self,
        product_repository: IProductRepository,
        analytics_cache: IProductAnalyticsCache | None = None,
    ) -> None:
        self._product_repository = product_repository
        self._analytics_cache = analytics_cache

    def create(self, dto: ProductCreateDto) -> ProductResponseDto:
        if not dto.name.strip():
            raise EmptyProductNameException()
        if dto.price < Decimal("0.00"):
            raise NegativeProductPriceException()
        if dto.quantity < 0:
            raise NegativeProductQuantityException()

        product = Product(
            name=dto.name.strip(),
            description=dto.description.strip(),
            price=dto.price,
            quantity=dto.quantity,
            category_ids=list(dto.category_ids),
            attachment_ids=list(dto.attachment_ids),
        )
        saved_product = self._product_repository.create(
            product,
            categories=dto.categories if dto.categories else None,
            attachments=dto.attachments if dto.attachments else None,
        )
        cats = self._product_repository.get_categories(saved_product.id)
        atts = self._product_repository.get_attachments(saved_product.id)
        return ProductResponseDto.from_domain(
            saved_product, categories=cats, attachments=atts
        )

    def get_by_id(self, product_id: UUID) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)
        cats = self._product_repository.get_categories(product.id)
        atts = self._product_repository.get_attachments(product.id)
        return ProductResponseDto.from_domain(
            product, categories=cats, attachments=atts
        )

    def get_by_ids(self, product_ids: list[UUID]) -> dict[UUID, ProductResponseDto]:
        if not product_ids:
            return {}
        products = self._product_repository.get_by_ids(product_ids)
        result: dict[UUID, ProductResponseDto] = {}
        for p in products:
            cats = self._product_repository.get_categories(p.id)
            atts = self._product_repository.get_attachments(p.id)
            result[p.id] = ProductResponseDto.from_domain(
                p, categories=cats, attachments=atts
            )
        return result

    def exists_by_id(self, product_id: UUID) -> bool:
        return self._product_repository.exists_by_id(product_id)

    def ensure_exists(self, product_id: UUID) -> None:
        if not self._product_repository.exists_by_id(product_id):
            raise ProductNotFoundException(product_id)

    def list(
        self,
        filter_dto: ProductFilterDto | None = None,
    ) -> ProductListResponseDto:
        if filter_dto is None:
            filter_dto = ProductFilterDto()

        items = self._product_repository.list(filter_dto=filter_dto)
        response_items: list[ProductResponseDto] = []
        for p in items:
            cats = self._product_repository.get_categories(p.id)
            atts = self._product_repository.get_attachments(p.id)
            response_items.append(
                ProductResponseDto.from_domain(p, categories=cats, attachments=atts)
            )
        return ProductListResponseDto(
            items=response_items,
            offset=filter_dto.offset,
            limit=filter_dto.limit,
        )

    def update(self, product_id: UUID, dto: ProductUpdateDto) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        if dto.name is not None:
            if not dto.name.strip():
                raise EmptyProductNameException()
            product.name = dto.name.strip()

        if dto.description is not None:
            product.description = dto.description.strip()

        if dto.price is not None:
            if dto.price < Decimal("0.00"):
                raise NegativeProductPriceException()
            product.price = dto.price

        if dto.quantity is not None:
            if dto.quantity < 0:
                raise NegativeProductQuantityException()
            product.quantity = dto.quantity

        if dto.category_ids is not None:
            product.category_ids = list(dto.category_ids)

        if dto.attachment_ids is not None:
            product.attachment_ids = list(dto.attachment_ids)

        saved_product = self._product_repository.update(
            product,
            categories=dto.categories,
            attachments=dto.attachments,
        )
        if saved_product is None:
            raise ProductNotFoundException(product_id)
        cats = self._product_repository.get_categories(saved_product.id)
        atts = self._product_repository.get_attachments(saved_product.id)
        return ProductResponseDto.from_domain(
            saved_product, categories=cats, attachments=atts
        )

    def add_category(self, product_id: UUID, category_id: UUID) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        if category_id not in product.category_ids:
            product.category_ids.append(category_id)
            self._product_repository.update(product)

        return ProductResponseDto.from_domain(product)

    def remove_category(
        self, product_id: UUID, category_id: UUID
    ) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        if category_id in product.category_ids:
            product.category_ids.remove(category_id)
            self._product_repository.update(product)

        return ProductResponseDto.from_domain(product)

    def get_product_categories(
        self, product_id: UUID
    ) -> builtins.list[CategoryResponseDto]:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        cats = self._product_repository.get_categories(product_id)
        return [CategoryResponseDto.from_domain(c) for c in cats]

    def add_attachment(
        self, product_id: UUID, attachment_id: UUID
    ) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        if attachment_id not in product.attachment_ids:
            product.attachment_ids.append(attachment_id)
            self._product_repository.update(product)

        return ProductResponseDto.from_domain(product)

    def remove_attachment(
        self, product_id: UUID, attachment_id: UUID
    ) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        if attachment_id in product.attachment_ids:
            product.attachment_ids.remove(attachment_id)
            self._product_repository.update(product)

        return ProductResponseDto.from_domain(product)

    def get_product_attachments(
        self, product_id: UUID
    ) -> builtins.list[AttachmentResponseDto]:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        atts = self._product_repository.get_attachments(product_id)
        attachments = [AttachmentResponseDto.from_domain(a) for a in atts]
        return sorted(attachments, key=lambda a: a.order)

    def delete(self, product_id: UUID) -> bool:
        if not self._product_repository.delete(product_id):
            raise ProductNotFoundException(product_id)
        return True

    def reserve_stock(self, product_id: UUID, amount: int) -> ProductResponseDto:
        if amount <= 0:
            raise InvalidStockAmountException()

        updated_product = self._product_repository.update_stock_and_get(
            product_id, -amount
        )
        if updated_product is not None:
            return ProductResponseDto.from_domain(updated_product)

        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        raise InsufficientStockException(
            product_id=product_id,
            requested=amount,
            available=product.quantity,
        )

    def restore_stock(self, product_id: UUID, amount: int) -> ProductResponseDto:
        if amount <= 0:
            raise InvalidStockAmountException()

        updated_product = self._product_repository.update_stock_and_get(
            product_id, amount
        )
        if updated_product is None:
            raise ProductNotFoundException(product_id)

        return ProductResponseDto.from_domain(updated_product)

    def increment_orders_count(self, product_id: UUID, delta: int = 1) -> bool:
        return self._product_repository.increment_orders_count(product_id, delta)

    def decrement_orders_count(self, product_id: UUID, delta: int = 1) -> bool:
        return self._product_repository.decrement_orders_count(product_id, delta)

    def average_changes_by_state(self) -> builtins.list[ProductStateChangesDto]:
        """Среднее число правок товара по состояниям наличия.

        Повторный вызов в пределах TTL отдаёт значение из кэша.
        Запись товара сбрасывает кэш отдельно, на клиенте CouchDB.
        """
        if self._analytics_cache is not None:
            cached = self._analytics_cache.get()
            if cached is not None:
                return cached

        stats = self._product_repository.average_changes_by_state()
        if self._analytics_cache is not None:
            self._analytics_cache.set(stats)
        return stats
