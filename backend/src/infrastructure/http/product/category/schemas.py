from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from domain.category import Category


class CreateCategoryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=1000)


class UpdateCategoryRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str


class ProductCategoryInput(BaseModel):
    id: UUID | None = Field(
        default=None, description="ID существующей категории (если есть)"
    )
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=1000)

    def to_domain(self) -> Category:
        return Category(
            id=self.id or uuid4(),
            name=self.name,
            slug=self.slug,
            description=self.description,
        )
