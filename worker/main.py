import json
import logging
import time
from uuid import UUID

import pika

from common.config import settings
from common.crud import (
    get_review,
    set_review_evaluation,
    set_review_status,
)
from common.db import init_db, session_scope
from common.models import ReviewStatus
from worker.moderation import moderate_text


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def handle_message(
    channel,
    method,
    _properties,
    body: bytes,
) -> None:
    try:
        payload = json.loads(body.decode("utf-8"))
        review_id = UUID(payload["review_id"])
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        logger.error(
            "Invalid RabbitMQ message %r: %s",
            body,
            error,
        )
        
        channel.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        with session_scope() as db:
            review = get_review(db, review_id)

            if review is None:
                logger.warning("Review %s not found", review_id)

                channel.basic_ack(delivery_tag=method.delivery_tag)
                return

            status, reason, rating = moderate_text(review.text)

            if status == ReviewStatus.published:
                if rating not in {1, 2, 3}:
                    raise ValueError(
                        "Published review must have a rating from 1 to 3; "
                        f"received: {rating!r}"
                    )

                updated_review = set_review_evaluation(
                    db=db,
                    review_id=review_id,
                    rating=rating,
                    status=ReviewStatus.published,
                    reason=reason,
                )
            else:
                updated_review = set_review_status(
                    db=db,
                    review_id=review_id,
                    status=status,
                    reason=reason,
                )

            if updated_review is None:
                logger.warning(
                    "Review %s disappeared during processing",
                    review_id,
                )
                channel.basic_ack(delivery_tag=method.delivery_tag)
                return

            logger.info(
                "Review %s processed: status=%s rating=%s reason=%s",
                review_id,
                status.value,
                rating if status == ReviewStatus.published else None,
                reason or "approved",
            )

        channel.basic_ack(delivery_tag=method.delivery_tag)

    except Exception:
        logger.exception(
            "Failed to process review %s",
            review_id,
        )

        channel.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True,
        )


def create_connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(
        username=settings.rabbit_user,
        password=settings.rabbit_password,
    )

    parameters = pika.ConnectionParameters(
        host=settings.rabbit_host,
        port=settings.rabbit_port,
        credentials=credentials,
        heartbeat=30,
        connection_attempts=3,
        retry_delay=2,
        socket_timeout=5,
        blocked_connection_timeout=10,
    )

    return pika.BlockingConnection(parameters)


def main() -> None:
    init_db()

    while True:
        connection: pika.BlockingConnection | None = None

        try:
            connection = create_connection()
            channel = connection.channel()

            channel.queue_declare(
                queue=settings.rabbit_queue,
                durable=True,
            )

            channel.basic_qos(prefetch_count=1)

            channel.basic_consume(
                queue=settings.rabbit_queue,
                on_message_callback=handle_message,
                auto_ack=False,
            )

            logger.info(
                "Worker is listening on queue %s",
                settings.rabbit_queue,
            )

            channel.start_consuming()

        except KeyboardInterrupt:
            logger.info("Worker shutdown requested")
            break

        except (
            pika.exceptions.AMQPError,
            OSError,
        ):
            logger.warning(
                "RabbitMQ connection failed; retrying in 5 seconds",
                exc_info=True,
            )
            time.sleep(5)

        except Exception:
            logger.exception(
                "Unexpected worker error; retrying in 5 seconds"
            )
            time.sleep(5)

        finally:
            if connection is not None and connection.is_open:
                try:
                    connection.close()
                except (pika.exceptions.AMQPError, OSError):
                    logger.warning(
                        "Failed to close RabbitMQ connection",
                        exc_info=True,
                    )

    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
