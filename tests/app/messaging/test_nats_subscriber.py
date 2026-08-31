from unittest.mock import AsyncMock, Mock

import pytest

from app.config import Settings
from app.messaging.nats_subscriber import NatsEventSubscriber


def test_subscribe_registers_handler_with_default_queue():
    broker = Mock()
    subscriber_decorator = Mock()
    broker.subscriber.return_value = subscriber_decorator

    handler = AsyncMock()
    settings = Settings(nats_enabled=True)
    subscriber = NatsEventSubscriber(broker=broker, settings=settings, app=Mock())

    subscriber.subscribe("events.created", handler)

    broker.subscriber.assert_called_once_with(
        "events.created", queue=settings.nats_queue
    )
    subscriber_decorator.assert_called_once_with(handler)
    assert "events.created" in subscriber.registered_subjects


def test_subscribe_bulk_registers_each_handler():
    broker = Mock()
    subscriber_decorator = Mock()
    broker.subscriber.return_value = subscriber_decorator

    handler_one = AsyncMock()
    handler_two = AsyncMock()
    settings = Settings(nats_enabled=True)
    subscriber = NatsEventSubscriber(broker=broker, settings=settings, app=Mock())

    handlers = {
        "events.created": handler_one,
        "events.deleted": handler_two,
    }
    subscriber.subscribe_bulk(handlers, queue="custom")

    assert broker.subscriber.call_count == 2
    broker.subscriber.assert_any_call("events.created", queue="custom")
    broker.subscriber.assert_any_call("events.deleted", queue="custom")
    assert subscriber_decorator.call_count == 2
    assert subscriber.registered_subjects == {"events.created", "events.deleted"}


def test_run_raises_when_disabled():
    app_mock = Mock()
    subscriber = NatsEventSubscriber(broker=Mock(), app=app_mock, settings=Settings())

    with pytest.raises(RuntimeError):
        subscriber.run()
    app_mock.run.assert_not_called()


def test_run_invokes_app_when_enabled():
    app_mock = Mock()
    settings = Settings(nats_enabled=True)
    subscriber = NatsEventSubscriber(broker=Mock(), app=app_mock, settings=settings)

    subscriber.run()
    app_mock.run.assert_called_once_with()
