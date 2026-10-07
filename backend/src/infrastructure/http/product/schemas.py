from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from application.product.dto import (
    ProductCreateDto,
    ProductListResponseDto,
    ProductResponseDto,
    ProductStateChangesDto,
    ProductUpdateDto,
)
from infrastructure.http.product.attachment.schemas import (
    AttachmentResponse,
    ProductAttachmentInput,
)
from infrastructure.http.product.category.schemas import (
    CategoryResponse,
    ProductCategoryInput,
)


class CreateProductRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["Ноутбук ThinkPad"])
    description: str = Field(
        default="", max_length=2000, examples=["Ноутбук для программирования и учебы"]
    )
    price: Decimal = Field(..., ge=0, examples=[Decimal("79990.00")])
    quantity: int = Field(default=0, ge=0, examples=[10])
    categories: list[ProductCategoryInput] = Field(default_factory=list)
    attachments: list[ProductAttachmentInput] = Field(default_factory=list)

    def to_dto(self) -> ProductCreateDto:
        cats = [c.to_domain() for c in self.categories]
        atts = [a.to_domain() for a in self.attachments]
        cat_ids = [c.id for c in cats]
        att_ids = [a.id for a in atts]

        return ProductCreateDto(
            name=self.name,
            description=self.description,
            price=self.price,
            quantity=self.quantity,
            category_ids=cat_ids,
            attachment_ids=att_ids,
            categories=cats,
            attachments=atts,
        )


class UpdateProductRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal | None = Field(default=None, ge=0)
    quantity: int | None = Field(default=None, ge=0)
    categories: list[ProductCategoryInput] | None = Field(default=None)
    attachments: list[ProductAttachmentInput] | None = Field(default=None)

    def to_dto(self) -> ProductUpdateDto:
        cats = (
            [c.to_domain() for c in self.categories]
            if self.categories is not None
            else None
        )
        atts = (
            [a.to_domain() for a in self.attachments]
            if self.attachments is not None
            else None
        )
        cat_ids = [c.id for c in cats] if cats is not None else None
        att_ids = [a.id for a in atts] if atts is not None else None

        return ProductUpdateDto(
            name=self.name,
            description=self.description,
            price=self.price,
            quantity=self.quantity,
            category_ids=cat_ids,
            attachment_ids=att_ids,
            categories=cats,
            attachments=atts,
        )


class StockOperationRequest(BaseModel):
    amount: int = Field(..., gt=0, examples=[1])


class ProductResponse(BaseModel):
    id: UUID
    name: str
    description: str
    price: Decimal
    quantity: int
    is_in_stock: bool
    is_in_cart: bool = False
    is_in_favourites: bool = False
    categories: list[CategoryResponse] = Field(default_factory=list)
    attachments: list[AttachmentResponse] = Field(default_factory=list)

    @classmethod
    def from_dto(
        cls,
        dto: ProductResponseDto,
        is_in_cart: bool = False,
        is_in_favourites: bool = False,
    ) -> "ProductResponse":
        cats = [
            CategoryResponse(
                id=c.id,
                name=c.name,
                slug=c.slug,
                description=c.description,
            )
            for c in dto.categories
        ]
        atts = [
            AttachmentResponse(
                id=a.id,
                filename=a.filename,
                content_type=a.content_type,
                size_bytes=a.size_bytes,
                order=a.order,
                upload_date=a.upload_date,
                checksum=a.checksum,
                description=a.description,
            )
            for a in dto.attachments
        ]

        return cls(
            id=dto.id,
            name=dto.name,
            description=dto.description,
            price=dto.price,
            quantity=dto.quantity,
            is_in_stock=dto.is_in_stock,
            is_in_cart=is_in_cart,
            is_in_favourites=is_in_favourites,
            categories=cats,
            attachments=atts,
        )


class ProductStateChangesResponse(BaseModel):
    state: str
    average_changes: float
    product_count: int


class ProductAnalyticsResponse(BaseModel):
    by_state: list[ProductStateChangesResponse]

    @classmethod
    def from_stats(
        cls, stats: list[ProductStateChangesDto]
    ) -> "ProductAnalyticsResponse":
        return cls(
            by_state=[
                ProductStateChangesResponse(
                    state=item.state,
                    average_changes=item.average_changes,
                    product_count=item.product_count,
                )
                for item in stats
            ]
        )


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    offset: int
    limit: int

    @classmethod
    def from_dto(cls, dto: ProductListResponseDto) -> "ProductListResponse":
        return cls(
            items=[ProductResponse.from_dto(p) for p in dto.items],
            offset=dto.offset,
            limit=dto.limit,
        )
