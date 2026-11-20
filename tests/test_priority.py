"""
Tests for OS Priority Scheduling, Soft Quotas, Dirty Writebacks, and Concurrency
"""

import pytest
from cachemind.base import Priority
from cachemind.algorithms.cachemind import CacheMind
from cachemind.priority import PriorityManager


def test_priority_soft_quota_reservation():
    # Cache with 10 slots
    cm = CacheMind(capacity=10, enable_scan_shield=False, enable_priority_shielding=True)

    # Insert 2 CRITICAL kernel pages
    cm.put("kernel_1", "k_data1", priority=Priority.CRITICAL)
    cm.put("kernel_2", "k_data2", priority=Priority.CRITICAL)

    # Insert 8 NORMAL pages to fill cache
    for i in range(1, 9):
        cm.put(f"normal_{i}", f"data_{i}", priority=Priority.NORMAL)

    assert cm.size() == 10

    # Flood with 20 LOW priority batch jobs
    for j in range(1, 21):
        cm.put(f"batch_{j}", f"batch_val_{j}", priority=Priority.LOW)

    # Both kernel pages must remain resident!
    assert cm.get("kernel_1") == "k_data1"
    assert cm.get("kernel_2") == "k_data2"
    assert cm.stats.priority_shields > 0


def test_dirty_page_writeback_accounting():
    cm = CacheMind(capacity=4, enable_scan_shield=False)

    # Put 4 dirty pages
    for i in range(1, 5):
        cm.put(f"page_{i}", f"val_{i}", priority=Priority.NORMAL, is_write=True)

    # Add 5th page to trigger eviction
    cm.put("page_5", "val_5", priority=Priority.NORMAL, is_write=False)

    assert cm.stats.dirty_writebacks >= 1
    assert cm.stats.evictions >= 1


def test_probation_graduation():
    """Verify that an item in the probation buffer graduates to main cache upon a second hit."""
    cm = CacheMind(capacity=10, enable_scan_shield=True)

    # Put low priority item -> goes to probation buffer
    cm.put("backup_doc", "doc_data", priority=Priority.LOW)
    assert "backup_doc" in cm.probation
    assert "backup_doc" not in cm.t1
    assert "backup_doc" not in cm.t2

    # Second access (Hit in probation buffer!)
    val = cm.get("backup_doc")
    assert val == "doc_data"

    # Graduated from probation into active frequent list T2!
    assert "backup_doc" not in cm.probation
    assert "backup_doc" in cm.t2
