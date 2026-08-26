import json
import logging
from uuid import UUID

import pika

from common.config import settings


logger = logging.getLogger(__name__)


class QueuePublishError(RuntimeError):
    pass


def _connection() -> pika.BlockingConnection:
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


def publish_review_task(review_id: UUID | str) -> None:
    review_id_value = str(review_id)
    connection: pika.BlockingConnection | None = None

    try:
        connection = _connection()
        channel = connection.channel()

        channel.queue_declare(
            queue=settings.rabbit_queue,
            durable=True,
        )
        channel.confirm_delivery()

        body = json.dumps(
            {"review_id": review_id_value},
            ensure_ascii=False,
        ).encode("utf-8")

        channel.basic_publish(
            exchange="",
            routing_key=settings.rabbit_queue,
            body=body,
            mandatory=True,
            properties=pika.BasicProperties(
                content_type="application/json",
                content_encoding="utf-8",
                delivery_mode=pika.DeliveryMode.Persistent,
                message_id=review_id_value,
                type="review_evaluation",
            ),
        )

        logger.info(
            "Review %s was published to queue %s",
            review_id_value,
            settings.rabbit_queue,
        )
    except (pika.exceptions.AMQPError, OSError) as error:
        logger.exception(
            "Failed to publish review %s to queue %s",
            review_id_value,
            settings.rabbit_queue,
        )
        raise QueuePublishError(
            f"Failed to publish review {review_id_value}"
        ) from error
    finally:
        if connection is not None and connection.is_open:
            try:
                connection.close()
            except (pika.exceptions.AMQPError, OSError):
                logger.warning(
                    "Failed to close RabbitMQ connection",
                    exc_info=True,
                )
