"""Adaptive Replacement Cache (ARC - Megiddo & Modha, FAST '03)."""

from collections import OrderedDict
from typing import Any, Optional
from ..base import BaseCache, CacheEntry, Priority


class ARCCache(BaseCache):
    def __init__(self, capacity: int):
        super().__init__(capacity, name="ARC")
        self.c = capacity
        self.p: float = 0.0
        self.t1: OrderedDict[Any, CacheEntry] = OrderedDict()
        self.t2: OrderedDict[Any, CacheEntry] = OrderedDict()
        self.b1: OrderedDict[Any, bool] = OrderedDict()
        self.b2: OrderedDict[Any, bool] = OrderedDict()

    def _replace(self, in_b2: bool) -> Optional[CacheEntry]:
        evicted = None
        t1_len = len(self.t1)
        if t1_len > 0 and ((t1_len > self.p) or (in_b2 and t1_len == int(self.p))):
            k, evicted = self.t1.popitem(last=False)
            self.b1[k] = True
        elif len(self.t2) > 0:
            k, evicted = self.t2.popitem(last=False)
            self.b2[k] = True
        elif t1_len > 0:
            k, evicted = self.t1.popitem(last=False)
            self.b1[k] = True

        if evicted:
            self.stats.evictions += 1
            if evicted.is_dirty:
                self.stats.dirty_writebacks += 1
        return evicted

    def get(self, key: Any) -> Optional[Any]:
        if key in self.t1:
            entry = self.t1.pop(key)
            entry.touch(is_write=False)
            self.t2[key] = entry
            self.stats.record_hit(entry.priority)
            return entry.value
        elif key in self.t2:
            entry = self.t2.pop(key)
            entry.touch(is_write=False)
            self.t2[key] = entry
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

        if key in self.t1:
            entry = self.t1.pop(key)
            entry.value = value
            entry.priority = priority
            entry.touch(is_write=is_write)
            self.t2[key] = entry
            self.stats.record_hit(priority)
            return None
        elif key in self.t2:
            entry = self.t2.pop(key)
            entry.value = value
            entry.priority = priority
            entry.touch(is_write=is_write)
            self.t2[key] = entry
            self.stats.record_hit(priority)
            return None

        self.stats.record_miss(priority)

        # Case 2: Hit in B1
        if key in self.b1:
            delta = 1.0 if len(self.b1) == 0 else max(1.0, len(self.b2) / len(self.b1))
            self.p = min(float(self.c), self.p + delta)
            evicted = self._replace(in_b2=False)
            self.b1.pop(key, None)
            entry = CacheEntry(key=key, value=value, priority=priority, is_dirty=is_write, size_bytes=size_bytes, process_id=process_id)
            self.t2[key] = entry
            return evicted

        # Case 3: Hit in B2
        elif key in self.b2:
            delta = 1.0 if len(self.b2) == 0 else max(1.0, len(self.b1) / len(self.b2))
            self.p = max(0.0, self.p - delta)
            evicted = self._replace(in_b2=True)
            self.b2.pop(key, None)
            entry = CacheEntry(key=key, value=value, priority=priority, is_dirty=is_write, size_bytes=size_bytes, process_id=process_id)
            self.t2[key] = entry
            return evicted

        # Case 4: Miss in all lists
        else:
            total_l1 = len(self.t1) + len(self.b1)
            total_all = total_l1 + len(self.t2) + len(self.b2)

            if total_l1 == self.c:
                if len(self.t1) < self.c:
                    if len(self.b1) > 0:
                        self.b1.popitem(last=False)
                    evicted = self._replace(in_b2=False)
                else:
                    k, evicted = self.t1.popitem(last=False)
                    self.b1[k] = True
                    self.stats.evictions += 1
            elif total_l1 < self.c and total_all >= self.c:
                if total_all == 2 * self.c and len(self.b2) > 0:
                    self.b2.popitem(last=False)
                evicted = self._replace(in_b2=False)
            elif (len(self.t1) + len(self.t2)) >= self.c:
                evicted = self._replace(in_b2=False)

            entry = CacheEntry(key=key, value=value, priority=priority, is_dirty=is_write, size_bytes=size_bytes, process_id=process_id)
            self.t1[key] = entry
            return evicted

    def contains(self, key: Any) -> bool:
        return (key in self.t1) or (key in self.t2)

    def clear(self) -> None:
        self.t1.clear()
        self.t2.clear()
        self.b1.clear()
        self.b2.clear()
        self.p = 0.0

    def size(self) -> int:
        return len(self.t1) + len(self.t2)
