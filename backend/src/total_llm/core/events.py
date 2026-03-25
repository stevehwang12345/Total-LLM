"""Async event bus for integration hooks."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class Event:
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    _instance = None

    def __init__(self):
        self._handlers: Dict[str, List[EventHandler]] = {}

    @classmethod
    def instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to '{event_type}'")

    async def publish(self, event: Event) -> None:
        handlers = self._handlers.get(event.type, [])
        if not handlers:
            return

        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Event handler error for '{event.type}': {result}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]


def get_event_bus() -> EventBus:
    return EventBus.instance()


class EventTypes:
    DOCUMENT_INDEXED = "document.indexed"
    DOCUMENT_DELETED = "document.deleted"
    ANALYSIS_COMPLETED = "analysis.completed"
    ALERT_RAISED = "alert.raised"
    DEVICE_COMMAND = "device.command"
    DEVICE_STATUS_CHANGED = "device.status_changed"
    CACHE_INVALIDATED = "cache.invalidated"
