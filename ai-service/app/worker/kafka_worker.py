import asyncio
import json
import logging
import os
from aiokafka import AIOKafkaConsumer
import traceback

from app.core.config import get_settings
from app.core.database import init_ai_pool, close_ai_pool
from app.services.qdrant_service import qdrant_service
from app.worker.kafka_producer import publish_status_event, close_kafka_producer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kafka_worker")
settings = get_settings()

async def process_document_event(payload: dict):
    # Payload Enrichment format from LMS
    content_id = payload.get("content_id")
    course_id = payload.get("course_id")
    file_url = payload.get("file_url")
    content_type = payload.get("content_type", "")
    text_content = payload.get("text_content", "") # If it's a direct text indexing

    logger.info(f"Processing event for content: {content_id}, type {content_type}")
    
    # We will reuse the auto_index_service logic but pass our enriched fields.
    from app.services.auto_index_service import auto_index_service
    
    try:
        if content_type == "text/markdown" or content_type == "TEXT":
            resp = await auto_index_service.auto_index_text(
                content_id=content_id,
                course_id=course_id,
                title=payload.get("title", ""),
                text_content=text_content,
            )
        else:
            file_bytes = await auto_index_service._download_bytes(file_url)
            resp = await auto_index_service.auto_index(
                content_id=content_id,
                course_id=course_id,
                file_url=file_url,
                content_type=content_type,
                file_bytes=file_bytes
            )
            
        chunks = resp.get("chunks_created", 0) if isinstance(resp, dict) else 0
        await publish_status_event(content_id, "success", chunks)
        
    except Exception as e:
        logger.error(f"Error processing content {content_id}: {e}")
        logger.error(traceback.format_exc())
        await publish_status_event(content_id, "failed", 0, str(e))

async def main():
    logger.info("Initializing AI Kafka Worker...")

    # Initialize AI DB and Qdrant
    await init_ai_pool()
    if settings.use_qdrant:
        await qdrant_service.init_collections()
        
    from app.core.embeddings import warm_up_models
    import concurrent.futures
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, warm_up_models)

    brokers = os.getenv("KAFKA_BROKERS", "kafka:9092")
    topic = "lms.document.uploaded"
    
    consumer = AIOKafkaConsumer(
        topic,
        bootstrap_servers=brokers,
        group_id="ai-service-group",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        auto_offset_reset="earliest"
    )

    await consumer.start()
    logger.info(f"Kafka Consumer started, listening to {topic}")

    try:
        async for msg in consumer:
            logger.info("Received message on topic: %s", msg.topic)
            payload = msg.value
            if not payload or "content_id" not in payload:
                continue
                
            # Process strictly one by one or create task
            # Using asyncio.create_task to process multiple if wanted, but auto_index is memory intensive.
            # We process sequentially here.
            await process_document_event(payload)
            
    except asyncio.CancelledError:
        logger.info("Worker cancelled.")
    finally:
        await consumer.stop()
        await close_kafka_producer()
        await close_ai_pool()
        if settings.use_qdrant:
            await qdrant_service.close()

if __name__ == "__main__":
    asyncio.run(main())
