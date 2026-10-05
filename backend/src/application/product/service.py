import builtins
from decimal import Decimal
from uuid import UUID

from application.attachment.dto import AttachmentResponseDto
from application.category.dto import CategoryResponseDto
from domain.product import Product

from .dto import (
    ProductCreateDto,
    ProductFilterDto,
    ProductListResponseDto,
    ProductResponseDto,
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
    ) -> None:
        self._product_repository = product_repository

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
        saved_product = self._product_repository.save(product)
        return ProductResponseDto.from_domain(saved_product)

    def get_by_id(self, product_id: UUID) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)
        return ProductResponseDto.from_domain(product)

    def get_by_ids(self, product_ids: list[UUID]) -> dict[UUID, ProductResponseDto]:
        if not product_ids:
            return {}
        products = self._product_repository.get_by_ids(product_ids)
        return {p.id: ProductResponseDto.from_domain(p) for p in products}

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
        return ProductListResponseDto(
            items=[ProductResponseDto.from_domain(p) for p in items],
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

        saved_product = self._product_repository.save(product)
        return ProductResponseDto.from_domain(saved_product)

    def add_category(self, product_id: UUID, category_id: UUID) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        if category_id not in product.category_ids:
            product.category_ids.append(category_id)
            self._product_repository.save(product)

        return ProductResponseDto.from_domain(product)

    def remove_category(self, product_id: UUID, category_id: UUID) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        if category_id in product.category_ids:
            product.category_ids.remove(category_id)
            self._product_repository.save(product)

        return ProductResponseDto.from_domain(product)

    def get_product_categories(self, product_id: UUID) -> builtins.list[CategoryResponseDto]:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        cats = self._product_repository.get_categories(product_id)
        return [CategoryResponseDto.from_domain(c) for c in cats]

    def add_attachment(self, product_id: UUID, attachment_id: UUID) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        if attachment_id not in product.attachment_ids:
            product.attachment_ids.append(attachment_id)
            self._product_repository.save(product)

        return ProductResponseDto.from_domain(product)

    def remove_attachment(self, product_id: UUID, attachment_id: UUID) -> ProductResponseDto:
        product = self._product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundException(product_id)

        if attachment_id in product.attachment_ids:
            product.attachment_ids.remove(attachment_id)
            self._product_repository.save(product)

        return ProductResponseDto.from_domain(product)

    def get_product_attachments(self, product_id: UUID) -> builtins.list[AttachmentResponseDto]:
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
