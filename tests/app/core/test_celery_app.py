import importlib
import logging
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock


def test_celery_uses_sdk_redis_connection_url(monkeypatch):
    redis_url = "redis://looply:test-password@redis:6379/0"
    monkeypatch.setenv("REDIS_URL", redis_url)

    from app.core import celery_app as celery_module

    celery_module = importlib.reload(celery_module)

    assert celery_module.celery_app.conf.broker_url == redis_url
    assert celery_module.celery_app.conf.result_backend == redis_url


def test_importing_celery_app_loads_the_rollbar_logger_submodule():
    # Run in a fresh interpreter: once anything in this test process imports
    # rollbar.logger, the attribute exists and the regression is hidden.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.core.celery_app, rollbar; "
            "assert hasattr(rollbar, 'logger'), 'rollbar.logger not loaded'",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_init_rollbar_attaches_error_handler_in_production(monkeypatch):
    from app.core import celery_app as celery_module
    from rollbar.logger import RollbarHandler

    monkeypatch.setattr(
        celery_module,
        "settings",
        SimpleNamespace(
            is_production=True,
            rollbar_access_token="test-token",
            environment="production",
        ),
    )
    rollbar_init = Mock()
    monkeypatch.setattr(celery_module.rollbar, "init", rollbar_init)

    root = logging.getLogger()
    before = list(root.handlers)
    try:
        celery_module.init_rollbar()
        added = [handler for handler in root.handlers if handler not in before]
    finally:
        for handler in root.handlers[:]:
            if handler not in before:
                root.removeHandler(handler)

    rollbar_init.assert_called_once_with("test-token", environment="production")
    assert len(added) == 1
    assert isinstance(added[0], RollbarHandler)
    # RollbarHandler.setLevel sets notify_level (what is sent to Rollbar); the
    # handler level stays at DEBUG so recent records are kept as history.
    assert added[0].notify_level == logging.ERROR
