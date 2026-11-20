"""O(1) Least Frequently Used (LFU) Cache."""

from collections import OrderedDict, defaultdict
from typing import Any, Dict, Optional
from ..base import BaseCache, CacheEntry, Priority


class LFUCache(BaseCache):
    def __init__(self, capacity: int):
        super().__init__(capacity, name="LFU")
        self.cache: Dict[Any, CacheEntry] = {}
        self.freq_buckets: Dict[int, OrderedDict[Any, CacheEntry]] = defaultdict(OrderedDict)
        self.min_freq: int = 0

    def get(self, key: Any) -> Optional[Any]:
        if key not in self.cache:
            self.stats.record_miss(Priority.NORMAL)
            return None

        entry = self.cache[key]
        self._update_freq(entry, is_write=False)
        self.stats.record_hit(entry.priority)
        return entry.value

    def _update_freq(self, entry: CacheEntry, is_write: bool = False) -> None:
        old_freq = entry.frequency
        del self.freq_buckets[old_freq][entry.key]
        if not self.freq_buckets[old_freq] and self.min_freq == old_freq:
            self.min_freq += 1

        entry.touch(is_write=is_write)
        new_freq = entry.frequency
        self.freq_buckets[new_freq][entry.key] = entry

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
            self._update_freq(entry, is_write=is_write)
            self.stats.record_hit(priority)
            return None

        self.stats.record_miss(priority)
        if len(self.cache) >= self.capacity:
            evict_key, evicted = self.freq_buckets[self.min_freq].popitem(last=False)
            del self.cache[evict_key]
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
        self.min_freq = 1
        self.freq_buckets[1][key] = new_entry
        return evicted

    def contains(self, key: Any) -> bool:
        return key in self.cache

    def clear(self) -> None:
        self.cache.clear()
        self.freq_buckets.clear()
        self.min_freq = 0

    def size(self) -> int:
        return len(self.cache)
