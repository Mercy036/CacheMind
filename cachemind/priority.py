"""
Priority Scheduling, Quotas, and Shielding for Operating System Cache Management
"""

from __future__ import annotations
from typing import Dict, List, Optional
from .base import Priority, CacheEntry


class PriorityManager:
    """
    Manages process priority partitioning, dynamic reservation quotas,
    aging to prevent starvation, and weighted eviction score calculation.
    """

    def __init__(
        self,
        capacity: int,
        quota_reservations: Optional[Dict[Priority, float]] = None,
        aging_interval_s: float = 30.0,
    ):
        self.capacity = capacity
        # Soft reservation targets (% of cache reserved for each tier minimum)
        self.quota_reservations = quota_reservations or {
            Priority.CRITICAL: 0.25,  # 25% minimum reserved for Kernel/Real-Time
            Priority.HIGH: 0.35,      # 35% reserved for High-Priority Foreground
            Priority.NORMAL: 0.25,    # 25% for Normal user apps
            Priority.LOW: 0.15,       # 15% soft cap for background batch / scans
        }
        self.aging_interval_s = aging_interval_s

    def compute_eviction_score(
        self,
        entry: CacheEntry,
        current_time: float,
        current_tier_counts: Dict[Priority, int],
        recency_rank: float,  # 0.0 (most recent) to 1.0 (least recent)
        frequency_rank: float,  # 0.0 (highest freq) to 1.0 (lowest freq)
    ) -> float:
        """
        Higher eviction score = MORE likely to be evicted.
        Lower eviction score = SHIELDED from eviction.

        Formula:
        Score = (w_recency * recency_rank + w_frequency * frequency_rank)
                / PriorityMultiplier
                + QuotaDeficitDiscount
                + DirtyPenalty (dirty writes require disk I/O)
        """
        # Base algorithmic eviction tendency (0.0 to 1.0)
        base_algo_score = (0.55 * recency_rank) + (0.45 * frequency_rank)

        # Priority shield factor (Critical has high weight, dramatically reducing score)
        pri_factor = entry.priority.weight

        # Check soft quota occupancy: if a tier is under its reservation, strongly protect it
        reserved_slots = self.quota_reservations.get(entry.priority, 0.1) * self.capacity
        current_count = current_tier_counts.get(entry.priority, 0)
        quota_protection = 1.0
        if current_count <= reserved_slots:
            # Under quota! Grant additional 2.5x eviction resistance
            quota_protection = 2.5

        # Dirty penalty: evicting a dirty page causes synchronous disk writeback.
        # Prefer keeping dirty page unless memory pressure is severe.
        dirty_penalty = -0.2 if entry.is_dirty else 0.0

        # Aging factor: prevent priority inversion / permanent residency of stale pages
        age = max(0.0, current_time - entry.last_accessed)
        aging_boost = min(1.5, age / self.aging_interval_s) * 0.3

        # Final composite score
        score = ((base_algo_score + aging_boost + dirty_penalty) / (pri_factor * quota_protection))
        return score

    def should_shield(
        self,
        candidate: CacheEntry,
        incoming_priority: Priority,
        current_tier_counts: Dict[Priority, int],
    ) -> bool:
        """
        Returns True if the candidate has higher priority than the incoming request
        and candidate belongs to a tier that hasn't exceeded its quota.
        """
        if candidate.priority > incoming_priority:
            reserved = self.quota_reservations.get(candidate.priority, 0.2) * self.capacity
            if current_tier_counts.get(candidate.priority, 0) <= reserved:
                return True
        return False
