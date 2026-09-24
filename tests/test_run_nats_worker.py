from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from nats.js.api import DeliverPolicy

import run_nats_worker


def test_new_durable_starts_after_existing_stream_tail():
    assert run_nats_worker.NATS_DELIVER_POLICY is DeliverPolicy.NEW


@pytest.mark.asyncio
async def test_disabled_worker_does_not_log_nats_credentials(monkeypatch):
    settings = SimpleNamespace(
        nats_url="nats://linden_app:secret-password@nats1:4222",
        nats_enabled=False,
        nats_subjects="com.>",
        nats_queue="looply_worker_all",
        nats_stream_name="EVT_LINDEN",
    )
    test_logger = Mock()
    monkeypatch.setattr(run_nats_worker, "get_settings", lambda: settings)
    monkeypatch.setattr(run_nats_worker, "logger", test_logger)

    with pytest.raises(SystemExit):
        await run_nats_worker._run_async()

    logged_messages = " ".join(
        str(call.args[0])
        for method in (test_logger.info, test_logger.error)
        for call in method.call_args_list
    )
    assert settings.nats_url not in logged_messages
    assert "secret-password" not in logged_messages
    assert "NATS connection endpoint configured" in logged_messages
