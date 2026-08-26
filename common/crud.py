from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Product, Review, ReviewStatus
from .schemas import ProductCreate, ProductUpdate, ReviewCreate, ReviewUpdate


def commit_and_refresh(db: Session, instance: Product | Review) -> None:
    try:
        db.commit()
        db.refresh(instance)
    except Exception:
        db.rollback()
        raise


def create_product(db: Session, payload: ProductCreate) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    commit_and_refresh(db, product)
    return product


def list_products(db: Session) -> list[Product]:
    stmt = (
        select(Product)
        .options(
            selectinload(
                Product.reviews.and_(
                    Review.status == ReviewStatus.published,
                )
            )
        )
        .order_by(Product.created_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_product(
    db: Session,
    product_id: UUID,
    published_only: bool = True,
) -> Product | None:
    reviews_loader = selectinload(Product.reviews)

    if published_only:
        reviews_loader = selectinload(
            Product.reviews.and_(
                Review.status == ReviewStatus.published,
            )
        )

    stmt = (
        select(Product)
        .options(reviews_loader)
        .where(Product.id == product_id)
        .execution_options(populate_existing=True)
    )
    return db.scalar(stmt)


def update_product(
    db: Session,
    product_id: UUID,
    payload: ProductUpdate,
) -> Product | None:
    product = db.get(Product, product_id)

    if product is None:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(product, field, value)

    commit_and_refresh(db, product)
    return product


def delete_product(db: Session, product_id: UUID) -> bool:
    product = db.get(Product, product_id)

    if product is None:
        return False

    try:
        db.delete(product)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return True


def create_review(db: Session, payload: ReviewCreate) -> Review:
    review = Review(
        **payload.model_dump(),
        rating=None,
        status=ReviewStatus.pending,
        moderation_reason=None,
    )
    db.add(review)
    commit_and_refresh(db, review)
    return review


def update_review(
    db: Session,
    review_id: UUID,
    payload: ReviewUpdate,
) -> Review | None:
    review = db.get(Review, review_id)

    if review is None:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(review, field, value)

    review.rating = None
    review.status = ReviewStatus.pending
    review.moderation_reason = None

    commit_and_refresh(db, review)
    return review


def list_reviews(
    db: Session,
    product_id: UUID | None = None,
    published_only: bool = False,
) -> list[Review]:
    stmt = select(Review)

    if product_id is not None:
        stmt = stmt.where(Review.product_id == product_id)

    if published_only:
        stmt = stmt.where(Review.status == ReviewStatus.published)

    stmt = stmt.order_by(Review.created_at.desc())
    return list(db.scalars(stmt).all())


def get_review(db: Session, review_id: UUID) -> Review | None:
    return db.get(Review, review_id)


def set_review_status(
    db: Session,
    review_id: UUID,
    status: ReviewStatus,
    reason: str | None = None,
) -> Review | None:
    review = db.get(Review, review_id)

    if review is None:
        return None

    review.status = status
    review.moderation_reason = reason

    if status != ReviewStatus.published:
        review.rating = None

    commit_and_refresh(db, review)
    return review


def set_review_evaluation(
    db: Session,
    review_id: UUID,
    rating: int,
    status: ReviewStatus = ReviewStatus.published,
    reason: str | None = None,
) -> Review | None:
    if rating not in {1, 2, 3}:
        raise ValueError("Rating must be between 1 and 3")

    if status != ReviewStatus.published:
        raise ValueError("Only published reviews can have a rating")

    review = db.get(Review, review_id)

    if review is None:
        return None

    review.rating = rating
    review.status = status
    review.moderation_reason = reason

    commit_and_refresh(db, review)
    return review
