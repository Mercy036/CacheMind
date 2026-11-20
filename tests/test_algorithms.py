"""
Unit and Integration Tests for CacheMind & Baseline Replacement Algorithms
"""

import pytest
from cachemind.base import Priority
from cachemind.algorithms.fifo import FIFOCache
from cachemind.algorithms.lru import LRUCache
from cachemind.algorithms.lfu import LFUCache
from cachemind.algorithms.arc import ARCCache
from cachemind.algorithms.cachemind import CacheMind
from cachemind.workloads import WorkloadGenerator


def test_fifo_basic():
    cache = FIFOCache(capacity=3)
    cache.put("A", 1)
    cache.put("B", 2)
    cache.put("C", 3)
    assert cache.get("A") == 1
    cache.put("D", 4)
    assert cache.get("A") is None
    assert cache.get("B") == 2
    assert cache.get("C") == 3
    assert cache.get("D") == 4


def test_lru_basic():
    cache = LRUCache(capacity=3)
    cache.put("A", 1)
    cache.put("B", 2)
    cache.put("C", 3)
    assert cache.get("A") == 1
    cache.put("D", 4)
    assert cache.get("B") is None
    assert cache.get("A") == 1
    assert cache.get("C") == 3
    assert cache.get("D") == 4


def test_lfu_basic():
    cache = LFUCache(capacity=3)
    cache.put("A", 1)
    cache.put("B", 2)
    cache.put("C", 3)
    cache.get("A")
    cache.get("A")
    cache.get("B")
    cache.put("D", 4)
    assert cache.get("C") is None
    assert cache.get("A") == 1
    assert cache.get("B") == 2
    assert cache.get("D") == 4


def test_arc_adaptive_tuning():
    cache = ARCCache(capacity=4)
    for i in range(1, 5):
        cache.put(f"k{i}", i)
    assert cache.size() == 4
    # Evict k1
    cache.put("k5", 5)
    assert cache.get("k1") is None
    assert "k1" in cache.b1  # In ghost cache B1
    old_p = cache.p
    # Re-access k1 (hit in B1) -> p should increase!
    cache.put("k1", 1)
    assert cache.p >= old_p


def test_cachemind_scan_pollution_shield():
    cache_capacity = 20
    lru = LRUCache(capacity=cache_capacity)
    mind = CacheMind(capacity=cache_capacity, enable_scan_shield=True)

    # 1. Warm up both caches with 15 critical working-set pages
    hot_pages = [f"hot_page_{i}" for i in range(15)]
    for p in hot_pages:
        lru.put(p, f"val_{p}", priority=Priority.HIGH)
        mind.put(p, f"val_{p}", priority=Priority.HIGH)
        lru.get(p)
        mind.get(p)

    # 2. Inject massive sequential scan of 100 cold pages (simulating database backup)
    scan_events = WorkloadGenerator.sequential_scan_workload(
        scan_length=100,
        start_index=5000,
        priority=Priority.LOW
    )

    for event in scan_events:
        lru.put(event.key, "scan_val", priority=event.priority)
        mind.put(event.key, "scan_val", priority=event.priority)

    # 3. Test resilience: How many hot pages survived in LRU vs CacheMind?
    lru_survived = sum(1 for p in hot_pages if lru.get(p) is not None)
    mind_survived = sum(1 for p in hot_pages if mind.get(p) is not None)

    assert lru_survived == 0, f"Expected LRU to be polluted, but {lru_survived} survived"
    assert mind_survived >= 12, f"Expected CacheMind hot pages to survive, got {mind_survived}"
    assert mind.stats.pollution_filtered > 50


def test_cachemind_priority_shielding():
    # With scan shield disabled, low priority items directly compete for eviction
    mind = CacheMind(capacity=5, enable_scan_shield=False, enable_priority_shielding=True)
    # Insert Critical kernel page
    mind.put("kernel_page_1", "sys_data", priority=Priority.CRITICAL)

    # Fill remainder with normal pages
    for i in range(2, 6):
        mind.put(f"normal_page_{i}", f"val_{i}", priority=Priority.NORMAL)

    # Now low priority batch process inserts new items competing for cache slots
    for j in range(10, 20):
        mind.put(f"low_page_{j}", f"batch_{j}", priority=Priority.LOW)

    # Critical kernel page MUST NOT be evicted by low priority pages!
    assert mind.get("kernel_page_1") == "sys_data"
    assert mind.stats.priority_shields > 0
