from functools import cache
from typing import Annotated

from fastapi import Depends

from application.event_bus import IEventBus
from infrastructure.event_bus.in_memory_event_bus import InMemoryEventBus


@cache
def get_event_bus() -> IEventBus:
    """Синглтон шины событий."""
    return InMemoryEventBus()


EventBusDep = Annotated[IEventBus, Depends(get_event_bus)]
