from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import ReviewStatus


Price = Annotated[
    Decimal,
    Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    ),
]


class SchemaBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class ProductBase(SchemaBase):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    price: Price


class ProductCreate(ProductBase):
    pass


class ProductUpdate(SchemaBase):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    price: Price | None = None


class ReviewBase(SchemaBase):
    product_id: UUID
    text: str = Field(min_length=1, max_length=3000)
    author: Optional[str] = Field(default=None, max_length=100)


class ReviewCreate(ReviewBase):
    pass


class ReviewUpdate(SchemaBase):
    text: Optional[str] = Field(default=None, min_length=1, max_length=3000)
    author: Optional[str] = Field(default=None, max_length=100)


class ReviewOut(SchemaBase):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: UUID
    product_id: UUID
    text: str
    author: Optional[str]
    rating: Optional[int] = Field(default=None, ge=1, le=3)
    status: ReviewStatus
    moderation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProductOut(SchemaBase):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    id: UUID
    name: str
    description: Optional[str]
    price: Price
    created_at: datetime
    reviews: list[ReviewOut] = Field(default_factory=list)
