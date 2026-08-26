from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import get_db
from api.queue import publish_review_task
from common import crud
from common.models import ReviewStatus
from common.schemas import ReviewCreate, ReviewOut, ReviewUpdate


router = APIRouter(prefix="/reviews", tags=["reviews"])

DbSession = Annotated[Session, Depends(get_db)]


class ReviewStatusOut(BaseModel):
    status: ReviewStatus
    rating: int | None = Field(default=None, ge=1, le=3)


def enqueue_review(review_id: UUID) -> None:
    try:
        publish_review_task(str(review_id))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис оценки отзывов временно недоступен",
        ) from error


@router.post(
    "/publish",
    response_model=ReviewOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def publish_review(
    payload: ReviewCreate,
    db: DbSession,
) -> ReviewOut:
    product = crud.get_product(
        db,
        payload.product_id,
        published_only=True,
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Фильм не найден",
        )

    review = crud.create_review(db, payload)
    enqueue_review(review.id)

    return ReviewOut.model_validate(review)


@router.patch(
    "/{review_id}",
    response_model=ReviewOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def update_review(
    review_id: UUID,
    payload: ReviewUpdate,
    db: DbSession,
) -> ReviewOut:
    review = crud.update_review(db, review_id, payload)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Отзыв не найден",
        )

    enqueue_review(review.id)

    return ReviewOut.model_validate(review)


@router.get(
    "",
    response_model=list[ReviewOut],
    status_code=status.HTTP_200_OK,
)
def list_reviews(
    db: DbSession,
    product_id: UUID | None = None,
) -> list[ReviewOut]:
    reviews = crud.list_reviews(
        db,
        product_id=product_id,
        published_only=True,
    )

    return [ReviewOut.model_validate(review) for review in reviews]


@router.get(
    "/{review_id}",
    response_model=ReviewOut,
    status_code=status.HTTP_200_OK,
)
def get_review(
    review_id: UUID,
    db: DbSession,
) -> ReviewOut:
    review = crud.get_review(db, review_id)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Отзыв не найден",
        )

    return ReviewOut.model_validate(review)


@router.get(
    "/{review_id}/status",
    response_model=ReviewStatusOut,
    status_code=status.HTTP_200_OK,
)
def get_review_status(
    review_id: UUID,
    db: DbSession,
) -> ReviewStatusOut:
    review = crud.get_review(db, review_id)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Отзыв не найден",
        )

    return ReviewStatusOut(
        status=review.status,
        rating=review.rating,
    )


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_review(
    review_id: UUID,
    db: DbSession,
) -> Response:
    review = crud.get_review(db, review_id)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Отзыв не найден",
        )

    try:
        db.delete(review)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)
