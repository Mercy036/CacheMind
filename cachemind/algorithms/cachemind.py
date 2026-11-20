"""
CacheMind: Intelligent Adaptive Cache Manager
Combines:
1. Adaptive Replacement Cache (ARC) self-tuning (dynamic p target)
2. Priority Scheduling & Process Soft Quotas (Kernel/Critical/High/Normal/Low)
3. Scan Pollution Shield (Probation buffer for sequential/batch one-hit-wonders)
4. Dirty Page Writeback Cost Awareness
"""

from __future__ import annotations
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
import time

from ..base import BaseCache, CacheEntry, Priority
from ..priority import PriorityManager


class CacheMind(BaseCache):
    """
    CacheMind Intelligent Cache Manager.
    Solves cache pollution and priority inversion in operating system memory management.
    """

    def __init__(
        self,
        capacity: int,
        enable_scan_shield: bool = True,
        enable_priority_shielding: bool = True,
        probation_ratio: float = 0.15,  # 15% of cache allocated for probation/scan shield
        quota_reservations: Optional[Dict[Priority, float]] = None,
    ):
        super().__init__(capacity, name="CacheMind")
        self.c = capacity
        self.enable_scan_shield = enable_scan_shield
        self.enable_priority_shielding = enable_priority_shielding

        # Adaptive tuning parameter p (target size for T1)
        self.p: float = capacity * 0.5

        # Active resident cache lists
        self.t1: OrderedDict[Any, CacheEntry] = OrderedDict()  # Recency list (visited once)
        self.t2: OrderedDict[Any, CacheEntry] = OrderedDict()  # Frequency list (visited multiple times)

        # Ghost history caches (keys only, no data payload)
        self.b1: OrderedDict[Any, Priority] = OrderedDict()    # History of T1 evictions
        self.b2: OrderedDict[Any, Priority] = OrderedDict()    # History of T2 evictions

        # Scan Pollution Shield: Probation buffer for suspicious/low-priority one-hit items
        self.probation_capacity = max(2, int(capacity * probation_ratio))
        self.probation: OrderedDict[Any, CacheEntry] = OrderedDict()

        # Priority manager for soft quotas and eviction scoring
        self.priority_mgr = PriorityManager(capacity, quota_reservations)

        # Sequential scan detector heuristics
        self._consecutive_misses: int = 0
        self._scan_mode_active: bool = False
        self._last_access_key: Optional[int] = None

    def _get_tier_counts(self) -> Dict[Priority, int]:
        """Counts resident pages per priority class across T1, T2, and probation."""
        counts = {p: 0 for p in Priority}
        for entry in self.t1.values():
            counts[entry.priority] += 1
        for entry in self.t2.values():
            counts[entry.priority] += 1
        for entry in self.probation.values():
            counts[entry.priority] += 1
        return counts

    def _detect_scan(self, key: Any, priority: Priority) -> bool:
        """
        Heuristic to detect sequential scans or cache pollution attempts:
        - Workloads flagged as Priority.LOW (background backups/indexers)
        - Sequential numeric access keys (stride 1)
        - Burst of consecutive misses exceeding scan threshold
        """
        if priority == Priority.LOW:
            return True

        # Check numeric stride (e.g. key 101, 102, 103, 104)
        is_stride_one = False
        if isinstance(key, int) and isinstance(self._last_access_key, int):
            if key == self._last_access_key + 1:
                is_stride_one = True
        self._last_access_key = key if isinstance(key, int) else None

        if is_stride_one and self._consecutive_misses >= 3:
            self._scan_mode_active = True
            return True

        if self._consecutive_misses >= 6:
            self._scan_mode_active = True
            return True

        self._scan_mode_active = False
        return False

    def _select_eviction_candidate(
        self,
        queue: OrderedDict[Any, CacheEntry],
        incoming_priority: Priority,
        current_counts: Dict[Priority, int],
    ) -> Tuple[Any, CacheEntry]:
        """
        Priority-aware eviction candidate selector.
        Instead of strictly popping the tail (classical LRU), evaluates candidates
        near the tail with priority weights and soft quota protection.
        """
        if not self.enable_priority_shielding or len(queue) <= 1:
            return queue.popitem(last=False)

        now = time.time()
        # Inspect up to the oldest 5 candidates at the tail of the queue
        items = list(queue.items())
        window_size = min(len(items), 6)
        candidates = items[:window_size]

        best_key = None
        best_entry = None
        highest_score = -1e9

        for rank_idx, (k, entry) in enumerate(candidates):
            # Recency rank within window: 1.0 (oldest/tail) to 0.0 (newer)
            recency_rank = 1.0 - (rank_idx / max(1, window_size - 1))
            # Frequency rank: normalized inverse of frequency
            freq_rank = 1.0 / max(1, entry.frequency)

            score = self.priority_mgr.compute_eviction_score(
                entry=entry,
                current_time=now,
                current_tier_counts=current_counts,
                recency_rank=recency_rank,
                frequency_rank=freq_rank,
            )

            # Check if candidate should be actively shielded against lower priority intruder
            if self.priority_mgr.should_shield(entry, incoming_priority, current_counts):
                self.stats.priority_shields += 1
                score -= 50.0  # Heavy penalty so it won't be chosen

            if score > highest_score:
                highest_score = score
                best_key = k
                best_entry = entry

        if best_key is not None:
            del queue[best_key]
            return best_key, best_entry

        # Fallback to tail
        return queue.popitem(last=False)

    def _replace(self, in_b2: bool, incoming_priority: Priority) -> Optional[CacheEntry]:
        """
        Adaptive eviction routine balancing T1 and T2, guided by dynamic parameter p
        and priority scheduling.
        """
        evicted = None
        t1_len = len(self.t1)
        tier_counts = self._get_tier_counts()

        # Decide whether to evict from T1 or T2
        if t1_len > 0 and ((t1_len > self.p) or (in_b2 and t1_len == int(self.p))):
            # Evict from T1 into Ghost Cache B1
            k, evicted = self._select_eviction_candidate(self.t1, incoming_priority, tier_counts)
            self.b1[k] = evicted.priority
            # Cap ghost cache size to capacity
            if len(self.b1) > self.c:
                self.b1.popitem(last=False)
        elif len(self.t2) > 0:
            # Evict from T2 into Ghost Cache B2
            k, evicted = self._select_eviction_candidate(self.t2, incoming_priority, tier_counts)
            self.b2[k] = evicted.priority
            if len(self.b2) > self.c:
                self.b2.popitem(last=False)
        elif t1_len > 0:
            k, evicted = self._select_eviction_candidate(self.t1, incoming_priority, tier_counts)
            self.b1[k] = evicted.priority

        if evicted:
            self.stats.evictions += 1
            if evicted.is_dirty:
                self.stats.dirty_writebacks += 1

        return evicted

    def get(self, key: Any) -> Optional[Any]:
        # Check T1
        if key in self.t1:
            entry = self.t1.pop(key)
            entry.touch(is_write=False)
            self.t2[key] = entry  # Promote to frequent list T2
            self._consecutive_misses = 0
            self.stats.record_hit(entry.priority)
            return entry.value

        # Check T2
        if key in self.t2:
            entry = self.t2.pop(key)
            entry.touch(is_write=False)
            self.t2[key] = entry  # Move to MRU of T2
            self._consecutive_misses = 0
            self.stats.record_hit(entry.priority)
            return entry.value

        # Check Probation Buffer
        if key in self.probation:
            entry = self.probation.pop(key)
            entry.touch(is_write=False)
            # Item proved it has temporal reuse! Graduate from probation into T2
            self._admit_to_active(entry)
            self._consecutive_misses = 0
            self.stats.record_hit(entry.priority)
            return entry.value

        self._consecutive_misses += 1
        self.stats.record_miss(Priority.NORMAL)
        return None

    def _admit_to_active(self, entry: CacheEntry) -> Optional[CacheEntry]:
        """Admit a graduated entry into resident cache, evicting if full."""
        evicted = None
        while (len(self.t1) + len(self.t2)) >= self.c:
            evicted = self._replace(in_b2=False, incoming_priority=entry.priority)
        self.t2[entry.key] = entry
        return evicted

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

        # Hit in T1
        if key in self.t1:
            entry = self.t1.pop(key)
            entry.value = value
            entry.priority = max(entry.priority, priority)
            entry.touch(is_write=is_write)
            self.t2[key] = entry
            self._consecutive_misses = 0
            self.stats.record_hit(entry.priority)
            return None

        # Hit in T2
        if key in self.t2:
            entry = self.t2.pop(key)
            entry.value = value
            entry.priority = max(entry.priority, priority)
            entry.touch(is_write=is_write)
            self.t2[key] = entry
            self._consecutive_misses = 0
            self.stats.record_hit(entry.priority)
            return None

        # Hit in Probation Buffer
        if key in self.probation:
            entry = self.probation.pop(key)
            entry.value = value
            entry.priority = max(entry.priority, priority)
            entry.touch(is_write=is_write)
            evicted = self._admit_to_active(entry)
            self._consecutive_misses = 0
            self.stats.record_hit(entry.priority)
            return evicted

        # Cache Miss
        self._consecutive_misses += 1
        self.stats.record_miss(priority)

        # Scan Pollution Shield logic
        if self.enable_scan_shield and self._detect_scan(key, priority):
            self.stats.pollution_filtered += 1
            # Evict from probation if full
            if len(self.probation) >= self.probation_capacity:
                _, prob_evicted = self.probation.popitem(last=False)
                if prob_evicted.is_dirty:
                    self.stats.dirty_writebacks += 1

            new_entry = CacheEntry(
                key=key,
                value=value,
                priority=priority,
                is_dirty=is_write,
                size_bytes=size_bytes,
                process_id=process_id,
            )
            self.probation[key] = new_entry
            return None

        # Case: Hit in Ghost Cache B1
        if key in self.b1:
            delta = 1.0 if len(self.b1) == 0 else max(1.0, len(self.b2) / len(self.b1))
            self.p = min(float(self.c), self.p + delta)
            evicted = self._replace(in_b2=False, incoming_priority=priority)
            self.b1.pop(key, None)
            new_entry = CacheEntry(
                key=key,
                value=value,
                priority=priority,
                frequency=2,
                is_dirty=is_write,
                size_bytes=size_bytes,
                process_id=process_id,
            )
            self.t2[key] = new_entry
            return evicted

        # Case: Hit in Ghost Cache B2
        elif key in self.b2:
            delta = 1.0 if len(self.b2) == 0 else max(1.0, len(self.b1) / len(self.b2))
            self.p = max(0.0, self.p - delta)
            evicted = self._replace(in_b2=True, incoming_priority=priority)
            self.b2.pop(key, None)
            new_entry = CacheEntry(
                key=key,
                value=value,
                priority=priority,
                frequency=2,
                is_dirty=is_write,
                size_bytes=size_bytes,
                process_id=process_id,
            )
            self.t2[key] = new_entry
            return evicted

        # Completely Cold Miss
        else:
            total_l1 = len(self.t1) + len(self.b1)
            total_all = total_l1 + len(self.t2) + len(self.b2)

            if total_l1 == self.c:
                if len(self.t1) < self.c:
                    if len(self.b1) > 0:
                        self.b1.popitem(last=False)
                    evicted = self._replace(in_b2=False, incoming_priority=priority)
                else:
                    k, evicted = self._select_eviction_candidate(self.t1, priority, self._get_tier_counts())
                    self.stats.evictions += 1
                    if evicted.is_dirty:
                        self.stats.dirty_writebacks += 1
            elif total_l1 < self.c and total_all >= self.c:
                if total_all == 2 * self.c and len(self.b2) > 0:
                    self.b2.popitem(last=False)
                evicted = self._replace(in_b2=False, incoming_priority=priority)
            elif (len(self.t1) + len(self.t2)) >= self.c:
                evicted = self._replace(in_b2=False, incoming_priority=priority)

            new_entry = CacheEntry(
                key=key,
                value=value,
                priority=priority,
                is_dirty=is_write,
                size_bytes=size_bytes,
                process_id=process_id,
            )
            self.t1[key] = new_entry
            return evicted

    def contains(self, key: Any) -> bool:
        return (key in self.t1) or (key in self.t2) or (key in self.probation)

    def clear(self) -> None:
        self.t1.clear()
        self.t2.clear()
        self.b1.clear()
        self.b2.clear()
        self.probation.clear()
        self.p = self.c * 0.5
        self._consecutive_misses = 0

    def size(self) -> int:
        return len(self.t1) + len(self.t2)

    def get_state(self) -> dict:
        base_state = super().get_state()
        tier_counts = self._get_tier_counts()
        base_state.update({
            "target_p": round(self.p, 2),
            "t1_size": len(self.t1),
            "t2_size": len(self.t2),
            "b1_size": len(self.b1),
            "b2_size": len(self.b2),
            "probation_size": len(self.probation),
            "tier_distribution": {p.name: tier_counts[p] for p in Priority},
            "scan_mode_active": self._scan_mode_active,
            "t1_keys": [str(k) for k in self.t1.keys()],
            "t2_keys": [str(k) for k in self.t2.keys()],
            "probation_keys": [str(k) for k in self.probation.keys()],
        })
        return base_state
