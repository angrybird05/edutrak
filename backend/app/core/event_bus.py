"""
Internal Async Event Bus for cross-module communication.

This replaces direct module-to-module service imports with a publish/subscribe
pattern. Events are processed in-process (no external broker needed), keeping
the simplicity of a monolith while achieving the decoupling of microservices.

Usage:
    # Publisher (in assessment module):
    from app.core.event_bus import event_bus
    await event_bus.emit("assessment.marks_recorded", {
        "student_ids": [str(sid) for sid in student_ids],
        "exam_id": str(exam_id),
        "actor_id": str(current_user.id),
    })

    # Subscriber (in analytics module):
    from app.core.event_bus import event_bus

    @event_bus.on("assessment.marks_recorded")
    async def handle_marks_recorded(payload: dict):
        student_ids = [UUID(sid) for sid in payload["student_ids"]]
        await ai_insight_task_queue.enqueue_students(student_ids)

Why an event bus instead of direct imports?
    - Modules don't need to know about each other's internals
    - Adding a new subscriber (e.g., "send SMS on low attendance") requires
      zero changes to the publishing module
    - When you're ready to extract a service, the event bus becomes a message
      queue (Redis Streams, RabbitMQ) with minimal code changes
"""
import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

EventHandler = Callable[[Dict[str, Any]], Awaitable[None]]


class EventBus:
    """
    In-process async event bus with fire-and-forget semantics.

    Events are processed concurrently via asyncio.gather. If a subscriber
    fails, the error is logged but does not block other subscribers or
    the publisher.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._middleware: List[Callable] = []

    def on(self, event_name: str) -> Callable:
        """Decorator to register an event handler."""
        def decorator(func: EventHandler) -> EventHandler:
            self._handlers[event_name].append(func)
            logger.debug("Registered handler %s for event '%s'", func.__name__, event_name)
            return func
        return decorator

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Programmatic subscription (alternative to decorator)."""
        self._handlers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Remove a handler from an event."""
        if handler in self._handlers[event_name]:
            self._handlers[event_name].remove(handler)

    async def emit(self, event_name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        """
        Emit an event to all registered handlers.

        Handlers are executed concurrently. Failures are logged but do not
        propagate to the caller (fire-and-forget).
        """
        handlers = self._handlers.get(event_name, [])
        if not handlers:
            logger.debug("No handlers registered for event '%s'", event_name)
            return

        payload = payload or {}
        payload["_event_name"] = event_name

        logger.info(
            "Emitting event '%s' to %d handler(s)", event_name, len(handlers)
        )

        results = await asyncio.gather(
            *[self._safe_call(handler, payload) for handler in handlers],
            return_exceptions=True,
        )

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Event handler '%s' failed for event '%s': %s",
                    handlers[i].__name__,
                    event_name,
                    result,
                    exc_info=result,
                )

    async def _safe_call(self, handler: EventHandler, payload: Dict[str, Any]) -> None:
        """Execute a handler with error isolation."""
        try:
            await handler(payload)
        except Exception as e:
            # Re-raise so asyncio.gather captures it
            raise

    def list_events(self) -> Dict[str, List[str]]:
        """List all registered events and their handler names (for debugging)."""
        return {
            event: [h.__name__ for h in handlers]
            for event, handlers in self._handlers.items()
        }


# ---------------------------------------------------------------------------
# Singleton instance — import this throughout the application
# ---------------------------------------------------------------------------
event_bus = EventBus()
