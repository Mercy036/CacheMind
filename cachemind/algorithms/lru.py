"""Least Recently Used (LRU) Cache."""

from collections import OrderedDict
from typing import Any, Optional
from ..base import BaseCache, CacheEntry, Priority


class LRUCache(BaseCache):
    def __init__(self, capacity: int):
        super().__init__(capacity, name="LRU")
        self.cache: OrderedDict[Any, CacheEntry] = OrderedDict()

    def get(self, key: Any) -> Optional[Any]:
        if key in self.cache:
            entry = self.cache[key]
            entry.touch(is_write=False)
            self.cache.move_to_end(key, last=True)
            self.stats.record_hit(entry.priority)
            return entry.value
        self.stats.record_miss(Priority.NORMAL)
        return None

    def put(
        self,
        key: Any,
        value: Any,
        priority: Priority = Priority.NORMAL,
        is_write: bool = False,
        size_bytes: int = 4096,
        process_id: Optional[int] = None,
    ) -> Optional[CacheEntry]:
        evicted = None
        if key in self.cache:
            entry = self.cache[key]
            entry.value = value
            entry.priority = priority
            entry.touch(is_write=is_write)
            self.cache.move_to_end(key, last=True)
            self.stats.record_hit(priority)
            return None

        self.stats.record_miss(priority)
        if len(self.cache) >= self.capacity:
            _, evicted = self.cache.popitem(last=False)
            self.stats.evictions += 1
            if evicted.is_dirty:
                self.stats.dirty_writebacks += 1

        new_entry = CacheEntry(
            key=key,
            value=value,
            priority=priority,
            is_dirty=is_write,
            size_bytes=size_bytes,
            process_id=process_id,
        )
        self.cache[key] = new_entry
        return evicted

    def contains(self, key: Any) -> bool:
        return key in self.cache

    def clear(self) -> None:
        self.cache.clear()

    def size(self) -> int:
        return len(self.cache)
