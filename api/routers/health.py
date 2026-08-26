from typing import Literal
from fastapi import APIRouter, status
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: Literal["ok"]

router = APIRouter(tags=["health"])

@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
