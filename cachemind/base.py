"""
CacheMind Base Definitions
Defines core data structures: Priority classes, CacheEntry, CacheStats, and BaseCache.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, Optional, Tuple
import time


class Priority(IntEnum):
    """
    Process / Workload Priority Levels in OS
    - CRITICAL: OS Kernel pages, Real-Time tasks, Interrupt handlers
    - HIGH: Interactive foreground applications, UI threads
    - NORMAL: Standard user processes, web services
    - LOW: Background indexing, backups, batch analytics (prime candidates for cache pollution)
    """
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

    @property
    def label(self) -> str:
        return self.name

    @property
    def weight(self) -> float:
        # Priority weight multiplier for eviction resistance
        weights = {
            Priority.LOW: 1.0,
            Priority.NORMAL: 2.5,
            Priority.HIGH: 6.0,
            Priority.CRITICAL: 15.0,
        }
        return weights[self]


@dataclass
class CacheEntry:
    key: Any
    value: Any
    priority: Priority = Priority.NORMAL
    frequency: int = 1
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    size_bytes: int = 4096  # Default 4KB virtual page frame
    is_dirty: bool = False
    process_id: Optional[int] = None
    access_history: list[float] = field(default_factory=list)

    def touch(self, is_write: bool = False) -> None:
        self.frequency += 1
        now = time.time()
        self.last_accessed = now
        self.access_history.append(now)
        if len(self.access_history) > 10:
            self.access_history.pop(0)
        if is_write:
            self.is_dirty = True


@dataclass
class CacheStats:
    total_requests: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    dirty_writebacks: int = 0
    pollution_filtered: int = 0
    priority_shields: int = 0  # Times a high-priority item was shielded from eviction
    hits_by_priority: Dict[Priority, int] = field(default_factory=lambda: {p: 0 for p in Priority})
    misses_by_priority: Dict[Priority, int] = field(default_factory=lambda: {p: 0 for p in Priority})

    @property
    def hit_ratio(self) -> float:
        return (self.hits / self.total_requests) if self.total_requests > 0 else 0.0

    @property
    def miss_ratio(self) -> float:
        return (self.misses / self.total_requests) if self.total_requests > 0 else 0.0

    def record_hit(self, priority: Priority) -> None:
        self.total_requests += 1
        self.hits += 1
        self.hits_by_priority[priority] = self.hits_by_priority.get(priority, 0) + 1

    def record_miss(self, priority: Priority) -> None:
        self.total_requests += 1
        self.misses += 1
        self.misses_by_priority[priority] = self.misses_by_priority.get(priority, 0) + 1

    def to_dict(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "dirty_writebacks": self.dirty_writebacks,
            "pollution_filtered": self.pollution_filtered,
            "priority_shields": self.priority_shields,
            "hit_ratio": round(self.hit_ratio * 100, 2),
            "miss_ratio": round(self.miss_ratio * 100, 2),
            "priority_hit_breakdown": {p.name: self.hits_by_priority.get(p, 0) for p in Priority},
            "priority_miss_breakdown": {p.name: self.misses_by_priority.get(p, 0) for p in Priority},
        }


class BaseCache:
    """
    Abstract interface for all cache implementations.
    Provides standard get/put/evict contract and stats tracking.
    """

    def __init__(self, capacity: int, name: str = "BaseCache"):
        if capacity <= 0:
            raise ValueError("Cache capacity must be strictly positive (> 0)")
        self.capacity = capacity
        self.name = name
        self.stats = CacheStats()

    def get(self, key: Any) -> Optional[Any]:
        raise NotImplementedError

    def put(
        self,
        key: Any,
        value: Any,
        priority: Priority = Priority.NORMAL,
        is_write: bool = False,
        size_bytes: int = 4096,
        process_id: Optional[int] = None,
    ) -> Optional[CacheEntry]:
        """
        Inserts or updates an entry.
        Returns the evicted entry if eviction took place, otherwise None.
        """
        raise NotImplementedError

    def contains(self, key: Any) -> bool:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def size(self) -> int:
        raise NotImplementedError

    def get_state(self) -> dict:
        """Returns snapshot of internal state for visualization/debugging."""
        return {
            "name": self.name,
            "capacity": self.capacity,
            "size": self.size(),
            "stats": self.stats.to_dict(),
        }
