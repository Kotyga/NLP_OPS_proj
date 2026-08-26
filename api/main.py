import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import health, products, reviews
from common.config import settings
from common.db import engine, init_db


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Initializing database")
    init_db()
    logger.info(
        "Application started. RabbitMQ host=%s port=%s queue=%s",
        settings.rabbit_host,
        settings.rabbit_port,
        settings.rabbit_queue,
    )

    try:
        yield
    finally:
        engine.dispose()
        logger.info("Application stopped")


app = FastAPI(
    title="Три кадра API",
    description="API для публикации и автоматической оценки отзывов о фильмах",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

app.include_router(health.router)
app.include_router(products.router)
app.include_router(reviews.router)
