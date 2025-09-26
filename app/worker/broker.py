from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker
from dramatiq.middleware import AgeLimit, Retries, TimeLimit
from loguru import logger

from app.core.config import get_settings
from app.monitoring.middleware import DramatiqMonitoringMiddleware


def _create_broker() -> dramatiq.Broker:
    settings = get_settings()

    if settings.dramatiq_broker_url:
        _broker = RedisBroker(url=settings.dramatiq_broker_url.get_secret_value())
    else:
        _broker = StubBroker()
        logger.warning(
            'Dramatiq broker URL not configured; falling back to in-memory StubBroker. '
            'Tasks will be executed inline during API requests.'
        )

    _broker.add_middleware(DramatiqMonitoringMiddleware())
    _broker.add_middleware(AgeLimit(max_age=24 * 3600 * 1000))  # 24h safety net
    _broker.add_middleware(TimeLimit(time_limit=settings.dramatiq_time_limit_ms))
    _broker.add_middleware(Retries(max_retries=settings.dramatiq_max_retries))
    return _broker


broker = _create_broker()
dramatiq.set_broker(broker)
