"""Long-running NATS worker process, started by start_nats_worker.sh alongside -
not instead of - the existing API and Celery beat/worker processes.

Ported from orcha's run_nats_worker.py (~/sites/linden-family/orcha): subscribes via
JetStream to the shared Linden event stream (EVT_LINDEN, config'd via
NATS_STREAM_NAME) on the wildcard subject "com.>" (NATS_SUBJECTS), with a durable,
Looply-specific queue group (NATS_QUEUE) so Looply gets its own full copy of every
message independent of what orcha or any other consumer does with it.

See docs/prds/0002-contact-custom-fields-and-events.md, "Custom Events" ->
"Ingestion transport".
"""

import asyncio
import logging
import sys

from faststream import FastStream
from faststream.nats import JStream, NatsBroker
from nats.js.api import DeliverPolicy

from app.config import get_settings
from app.core.logging_config import LoggingConfig
from app.tasks.process_nats_event_task import process_nats_event_task

LoggingConfig()
logger = logging.getLogger("nats_worker")


async def _run_async() -> None:
    """Async function that runs the FastStream application."""
    settings = get_settings()
    logger.info("Starting NATS worker...")
    logger.info(f"NATS URL: {settings.nats_url}")
    logger.info(f"NATS Enabled: {settings.nats_enabled}")

    if not settings.nats_enabled:
        logger.error("NATS is not enabled in settings!")
        sys.exit(1)

    broker = NatsBroker(settings.nats_url)
    app = FastStream(broker)

    @app.on_startup
    async def on_startup():
        logger.info(f"NATS worker started, subscribed to: {settings.nats_subjects}")
        logger.info(f"Using queue: {settings.nats_queue}")

    js_stream = JStream(
        name=settings.nats_stream_name,  # must match the JetStream stream name
        declare=False,
    )

    @broker.subscriber(
        settings.nats_subjects,
        stream=js_stream,  # THIS makes it JetStream
        durable=settings.nats_queue,  # durable consumer name
        queue=settings.nats_queue,
        deliver_policy=DeliverPolicy.LAST,
    )
    async def handler(msg: dict) -> None:
        """Handle incoming NATS events and dispatch them to the ingestion task."""
        logger.debug(f"Received message: {msg}")

        # Dispatch to Celery for async processing - this lets the NATS handler
        # quickly acknowledge the message while the DB work happens in the background.
        try:
            process_nats_event_task.delay(msg)
        except Exception:
            logger.exception(f"Error dispatching event task for message: {msg}")
            raise

    logger.info("Running FastStream app...")
    await app.run()


def main() -> None:
    """Synchronous entry point for process managers."""
    asyncio.run(_run_async())


if __name__ == "__main__":
    main()
