from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Dict, Optional, Set, Tuple


class SSEManager:
    """Lightweight server-sent event subscription hub."""

    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue[Tuple[str, str]]] = set()
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[Tuple[str, str]]:
        queue: asyncio.Queue[Tuple[str, str]] = asyncio.Queue()
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Tuple[str, str]]) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event: str, payload: Dict[str, Any]) -> None:
        message = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            await queue.put((event, message))

    def publish_from_thread(self, event: str, payload: Dict[str, Any]) -> None:
        loop = self._loop
        if not loop or not loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(self.publish(event, payload), loop)


event_manager = SSEManager()
