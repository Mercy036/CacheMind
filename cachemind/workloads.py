"""
Workload Generator for Memory Management & Cache Replacement Simulations.
Simulates realistic operating system access patterns.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Any, Optional
import random
import numpy as np

from .base import Priority


@dataclass
class AccessEvent:
    key: Any
    priority: Priority = Priority.NORMAL
    is_write: bool = False
    process_id: int = 1
    tag: str = "general"


class WorkloadGenerator:
    """Generates synthetic and realistic OS workload traces."""

    @staticmethod
    def zipfian_workload(
        num_requests: int = 1000,
        universe_size: int = 300,
        alpha: float = 0.95,
        priority: Priority = Priority.NORMAL,
        write_ratio: float = 0.15,
        seed: int = 42,
    ) -> List[AccessEvent]:
        """
        Zipfian (power-law) distribution.
        Simulates 80/20 rule: small number of hot pages accessed frequently.
        """
        np.random.seed(seed)
        ranks = np.arange(1, universe_size + 1)
        weights = 1.0 / np.power(ranks, alpha)
        weights /= weights.sum()

        chosen_indices = np.random.choice(ranks, size=num_requests, p=weights)
        events = []
        for idx in chosen_indices:
            is_w = random.random() < write_ratio
            events.append(
                AccessEvent(
                    key=f"page_{idx}",
                    priority=priority,
                    is_write=is_w,
                    process_id=100,
                    tag="zipfian",
                )
            )
        return events

    @staticmethod
    def sequential_scan_workload(
        scan_length: int = 200,
        start_index: int = 1000,
        priority: Priority = Priority.LOW,
        process_id: int = 999,
        seed: int = 42,
    ) -> List[AccessEvent]:
        """
        Sequential scan of unique pages (zero temporal reuse).
        Classic Cache Pollution attack: e.g. large file backup, grep, or DB scan.
        """
        events = []
        for i in range(scan_length):
            events.append(
                AccessEvent(
                    key=f"scan_page_{start_index + i}",
                    priority=priority,
                    is_write=False,
                    process_id=process_id,
                    tag="scan_pollution",
                )
            )
        return events

    @staticmethod
    def looping_workload(
        loop_size: int = 60,
        iterations: int = 10,
        priority: Priority = Priority.NORMAL,
        seed: int = 42,
    ) -> List[AccessEvent]:
        """
        Cyclic access pattern: 1, 2, ..., N, 1, 2, ..., N.
        If loop_size > cache_size, LRU degenerates to 0% hit rate!
        """
        events = []
        for _ in range(iterations):
            for i in range(1, loop_size + 1):
                events.append(
                    AccessEvent(
                        key=f"loop_{i}",
                        priority=priority,
                        is_write=False,
                        process_id=200,
                        tag="loop",
                    )
                )
        return events

    @staticmethod
    def multi_process_mixed_workload(
        num_requests: int = 2000,
        cache_capacity: int = 50,
        seed: int = 42,
    ) -> List[AccessEvent]:
        """
        Realistic OS Workload:
        1. Process 1 (Kernel/Critical): Real-time telemetry, 10 hot pages accessed frequently
        2. Process 2 (Foreground User App): High priority UI rendering, 30 pages with 80/20 Zipfian
        3. Process 3 (Web Service / Worker): Normal priority standard processing
        4. Process 4 (Background Antivirus / Backup): Low priority sequential scans that pollute cache
        """
        random.seed(seed)
        np.random.seed(seed)

        events: List[AccessEvent] = []
        kernel_pages = [f"kernel_frame_{i}" for i in range(1, 15)]
        ui_pages = [f"ui_frame_{i}" for i in range(1, 40)]
        worker_pages = [f"worker_page_{i}" for i in range(1, 100)]
        scan_counter = 5000

        for step in range(num_requests):
            roll = random.random()

            # Every 250 steps, background backup does a burst scan of 40 pages (Pollution injection!)
            if step % 250 == 0:
                for _ in range(35):
                    scan_counter += 1
                    events.append(
                        AccessEvent(
                            key=f"backup_chunk_{scan_counter}",
                            priority=Priority.LOW,
                            is_write=False,
                            process_id=400,
                            tag="background_backup_scan",
                        )
                    )

            if roll < 0.20:
                # Kernel / Critical
                k = random.choice(kernel_pages)
                events.append(
                    AccessEvent(
                        key=k,
                        priority=Priority.CRITICAL,
                        is_write=(random.random() < 0.1),
                        process_id=1,
                        tag="kernel",
                    )
                )
            elif roll < 0.60:
                # High priority UI
                # Skewed selection
                weights = [1.0 / (i + 1) for i in range(len(ui_pages))]
                total_w = sum(weights)
                p_dist = [w / total_w for w in weights]
                chosen = np.random.choice(ui_pages, p=p_dist)
                events.append(
                    AccessEvent(
                        key=chosen,
                        priority=Priority.HIGH,
                        is_write=(random.random() < 0.2),
                        process_id=2,
                        tag="ui_foreground",
                    )
                )
            elif roll < 0.85:
                # Normal Worker
                chosen = random.choice(worker_pages)
                events.append(
                    AccessEvent(
                        key=chosen,
                        priority=Priority.NORMAL,
                        is_write=(random.random() < 0.15),
                        process_id=3,
                        tag="normal_worker",
                    )
                )
            else:
                # Low priority occasional background access
                scan_counter += 1
                events.append(
                    AccessEvent(
                        key=f"background_tmp_{scan_counter}",
                        priority=Priority.LOW,
                        is_write=False,
                        process_id=4,
                        tag="background_misc",
                    )
                )

        return events
