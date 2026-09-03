# pyright: reportMissingTypeStubs=false
import logging

import rollbar
from celery import Celery
from celery.signals import task_failure, worker_process_init

from app.config import get_settings

settings = get_settings()

celery_app = Celery("looply-worker")


@worker_process_init.connect
def init_rollbar(**kwargs):
    """Initialize Rollbar in each worker process so task errors are reported."""
    if settings.is_production:
        rollbar.init(settings.rollbar_access_token, environment=settings.environment)

        handler = rollbar.logger.RollbarHandler()
        handler.setLevel(logging.ERROR)
        logging.getLogger().addHandler(handler)


@task_failure.connect
def report_task_failure(
    sender=None, exception=None, traceback=None, einfo=None, **kwargs
):
    """Explicitly report failed Celery tasks to Rollbar."""
    if settings.is_production:
        rollbar.report_exc_info(
            einfo, extra_data={"task": getattr(sender, "name", None)}
        )


celery_app.conf.update(
    broker_url=f"redis://{settings.redis_host}:{settings.redis_port}/0",
    result_backend=f"redis://{settings.redis_host}:{settings.redis_port}/0",
    task_default_queue="looply",  # Use dedicated queue for looply tasks
    task_routes={
        "app.tasks.*": {"queue": "looply"},  # Route all app.tasks.* to looply queue
    },
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

celery_app.autodiscover_tasks(["app.tasks"])  # ensure tasks are registered explicitly

# First beat schedule in this repo: requires a `celery -A app.tasks beat` process
# to actually be deployed/run somewhere in addition to the worker.
celery_app.conf.beat_schedule = {
    # Checks every 'sending' campaign against Sendly and marks it 'completed'
    # once the send stage finishes. Runs every 60 seconds.
    "poll-campaign-status": {
        "task": "app.tasks.poll_campaign_status",
        "schedule": 60.0,
    },
    # Refreshes opened_at/clicked_at and result counts for completed
    # campaigns still inside their bounded engagement-polling window.
    # A plain float schedule is an interval in seconds, so this runs
    # every 300 seconds (5 minutes).
    "poll-campaign-engagement": {
        "task": "app.tasks.poll_campaign_engagement",
        "schedule": 300.0,
    },
}

# # Explicitly register tasks to ensure they're available
# def register_tasks():
#     """Explicitly import tasks to ensure registration."""
#     try:
#         from app.tasks.process_import_items import process_import_items  # noqa: F401
#         from app.tasks.backfill_digests import backfill_digests_task  # noqa: F401
#         print(f"✅ Tasks registered: process_import_items, backfill_digests_task")
#     except ImportError as e:
#         print(f"⚠️  Warning: Could not import tasks: {e}")

# # Register tasks when this module is imported
# register_tasks()
