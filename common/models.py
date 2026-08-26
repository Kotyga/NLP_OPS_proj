import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    published = "published"
    rejected = "rejected"


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_products_price_non_negative"),
        Index("ix_products_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    reviews = relationship(
        "Review",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Review.created_at.desc()",
    )


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 3",
            name="ck_reviews_rating_range",
        ),
        Index("ix_reviews_product_status", "product_id", "status"),
        Index("ix_reviews_created_at", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    author = Column(String(100), nullable=True)
    text = Column(Text, nullable=False)
    rating = Column(SmallInteger, nullable=True)
    status = Column(
        Enum(ReviewStatus, name="review_status"),
        default=ReviewStatus.pending,
        nullable=False,
    )
    moderation_reason = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    product = relationship("Product", back_populates="reviews")
