import asyncio
import json
import logging
import os
from aiokafka import AIOKafkaConsumer
import traceback

from app.core.config import get_settings
from app.core.database import init_ai_pool, close_ai_pool
from app.services.qdrant_service import qdrant_service
from app.services.neo4j_service import neo4j_service
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

    logger.info(f"Processing document event for content: {content_id}")
    
    from app.services.auto_index_service import auto_index_service
    await auto_index_service._update_content_status(content_id, "processing")
    
    try:
        if content_type == "text/markdown" or content_type == "TEXT":
            await auto_index_service.auto_index_text(
                content_id=content_id, course_id=course_id,
                title=payload.get("title", ""), text_content=text_content,
            )
        elif _is_youtube(file_url):
            await auto_index_service.auto_index(
                content_id=content_id, course_id=course_id,
                file_url=file_url, content_type="video/youtube", file_bytes=b"",
            )
        else:
            file_bytes = await auto_index_service._download_bytes(file_url)
            await auto_index_service.auto_index(
                content_id=content_id, course_id=course_id,
                file_url=file_url, content_type=content_type, file_bytes=file_bytes
            )
        logger.info(f"Successfully processed content {content_id}")
        
    except Exception as e:
        logger.error(f"Error processing content {content_id}: {e}")
        logger.error(traceback.format_exc())
        await auto_index_service._update_content_status(content_id, "failed", str(e))


async def process_graph_command(payload: dict):
    """Handle graph maintenance tasks like GLOBAL_LINK."""
    command = payload.get("command")
    logger.info(f"Received graph command: {command}")
    
    from app.worker.kafka_producer import publish_graph_event
    
    try:
        if command == "GLOBAL_LINK":
            from app.services.graph_linker import link_global_graph
            await publish_graph_event(command, "processing")
            count = await link_global_graph()
            await publish_graph_event(command, "completed", result_count=count)
        else:
            logger.warning(f"Unknown graph command: {command}")
    except Exception as e:
        logger.error(f"Graph command {command} failed: {e}")
        await publish_graph_event(command, "failed", error=str(e))


async def process_maintenance_command(payload: dict):
    """Handle general maintenance tasks like REINDEX_CONTENT."""
    command = payload.get("command")
    logger.info(f"Received maintenance command: {command}")
    
    try:
        if command == "REINDEX_CONTENT":
            from app.services.reindex_service import reindex_service
            content_id = payload.get("content_id")
            course_id  = payload.get("course_id")
            await reindex_service.reindex_content_sync(content_id, course_id)
        else:
            logger.warning(f"Unknown maintenance command: {command}")
    except Exception as e:
        logger.error(f"Maintenance command {command} failed: {e}")


def _is_youtube(url: str) -> bool:
    import re
    return bool(url and re.search(r"(youtube\.com|youtu\.be)", url))


async def main():
    logger.info("Initializing AI Kafka Worker...")

    await init_ai_pool()
    if getattr(settings, 'neo4j_enabled', True):
        for attempt in range(1, 11):
            try:
                await neo4j_service.init()
                break
            except Exception as e:
                logger.warning("Neo4j init attempt %d/10 failed: %s", attempt, e)
                if attempt == 10:
                    logger.error("Neo4j init failed after 10 attempts")
                else:
                    await asyncio.sleep(min(attempt * 3, 30))

    if settings.use_qdrant:
        await qdrant_service.init_collections()
        
    from app.core.embeddings import warm_up_models
    import concurrent.futures
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, warm_up_models)

    brokers = os.getenv("KAFKA_BROKERS", "kafka:9092")
    
    # Subscribe to all relevant topics
    topic_doc      = "lms.document.uploaded"
    topic_graph    = "lms.graph.command"
    topic_maint    = "lms.maintenance.command"
    
    consumer = AIOKafkaConsumer(
        topic_doc, topic_graph, topic_maint,
        bootstrap_servers=brokers,
        group_id="ai-service-group",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        auto_offset_reset="earliest"
    )

    await consumer.start()
    logger.info(f"Kafka Consumer listening to document, graph, and maintenance topics.")

    try:
        async for msg in consumer:
            logger.info("Received message on topic: %s", msg.topic)
            payload = msg.value
            if not payload: continue
            
            if msg.topic == topic_doc:
                if "content_id" in payload:
                    await process_document_event(payload)
            elif msg.topic == topic_graph:
                await process_graph_command(payload)
            elif msg.topic == topic_maint:
                await process_maintenance_command(payload)
            
    except asyncio.CancelledError:
        logger.info("Worker cancelled.")
    finally:
        await consumer.stop()
        await close_kafka_producer()
        await close_ai_pool()
        if getattr(settings, 'neo4j_enabled', True):
            await neo4j_service.close()
        if settings.use_qdrant:
            await qdrant_service.close()

if __name__ == "__main__":
    asyncio.run(main())
