from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from api.deps import get_db
from common import crud
from common.models import Product, ReviewStatus
from common.schemas import ProductCreate, ProductOut, ProductUpdate


router = APIRouter(prefix="/products", tags=["products"])

DbSession = Annotated[Session, Depends(get_db)]


def serialize_product(product: Product) -> ProductOut:
    published_reviews = [
        review
        for review in product.reviews
        if review.status == ReviewStatus.published
    ]

    return ProductOut(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price,
        created_at=product.created_at,
        reviews=published_reviews,
    )


@router.post(
    "",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    payload: ProductCreate,
    db: DbSession,
) -> ProductOut:
    product = crud.create_product(db, payload)
    return serialize_product(product)


@router.get(
    "",
    response_model=list[ProductOut],
    status_code=status.HTTP_200_OK,
)
def list_products(db: DbSession) -> list[ProductOut]:
    products = crud.list_products(db)
    return [serialize_product(product) for product in products]


@router.get(
    "/{product_id}",
    response_model=ProductOut,
    status_code=status.HTTP_200_OK,
)
def get_product(
    product_id: UUID,
    db: DbSession,
) -> ProductOut:
    product = crud.get_product(
        db,
        product_id,
        published_only=True,
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Фильм не найден",
        )

    return serialize_product(product)


@router.patch(
    "/{product_id}",
    response_model=ProductOut,
    status_code=status.HTTP_200_OK,
)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: DbSession,
) -> ProductOut:
    product = crud.update_product(db, product_id, payload)

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Фильм не найден",
        )

    product = crud.get_product(
        db,
        product_id,
        published_only=True,
    )

    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Фильм не найден",
        )

    return serialize_product(product)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_product(
    product_id: UUID,
    db: DbSession,
) -> Response:
    deleted = crud.delete_product(db, product_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Фильм не найден",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
