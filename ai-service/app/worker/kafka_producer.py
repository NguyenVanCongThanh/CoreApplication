import json
import logging
import asyncio
from aiokafka import AIOKafkaProducer
import os

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None

async def get_kafka_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        brokers = os.getenv("KAFKA_BROKERS", "kafka:9092")
        _producer = AIOKafkaProducer(
            bootstrap_servers=brokers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await _producer.start()
        logger.info("Kafka Producer started")
    return _producer

async def close_kafka_producer():
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
        logger.info("Kafka Producer stopped")

async def publish_status_event(content_id: int, status: str, chunks_created: int = 0, error: str = ""):
    producer = await get_kafka_producer()
    payload = {
        "content_id": content_id,
        "status": status,
        "chunks_created": chunks_created,
        "error": error,
        "job_id": 0
    }
    
    topic = "ai.document.processed.status"
    key = str(content_id).encode("utf-8")
    
    await producer.send_and_wait(topic, value=payload, key=key)
    logger.info(f"Published status to {topic} for content {content_id}: {status}")

