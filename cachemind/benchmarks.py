"""
Benchmarking Engine & Comparative Evaluation for Cache Replacement Algorithms
Generates quantitative metrics and publication-ready matplotlib visual charts.
"""

from __future__ import annotations
from typing import Dict, List, Any
import os
import matplotlib
matplotlib.use("Agg")  # Headless backend for server environments
import matplotlib.pyplot as plt
import numpy as np

from .base import Priority, BaseCache
from .algorithms.fifo import FIFOCache
from .algorithms.lru import LRUCache
from .algorithms.lfu import LFUCache
from .algorithms.arc import ARCCache
from .algorithms.cachemind import CacheMind
from .workloads import WorkloadGenerator, AccessEvent


class BenchmarkSuite:
    """Executes comparative simulations and aggregates performance statistics."""

    @staticmethod
    def run_workload(
        cache: BaseCache,
        events: List[AccessEvent],
        track_trajectory: bool = False,
    ) -> Dict[str, Any]:
        p_trajectory = []
        hit_trajectory = []

        for idx, event in enumerate(events):
            # Check read or write
            if event.is_write:
                cache.put(
                    key=event.key,
                    value=f"val_{event.key}",
                    priority=event.priority,
                    is_write=True,
                    process_id=event.process_id,
                )
            else:
                val = cache.get(event.key)
                if val is None:
                    cache.put(
                        key=event.key,
                        value=f"val_{event.key}",
                        priority=event.priority,
                        is_write=False,
                        process_id=event.process_id,
                    )

            if track_trajectory:
                if isinstance(cache, (ARCCache, CacheMind)):
                    p_trajectory.append(cache.p)
                hit_trajectory.append(cache.stats.hit_ratio * 100)

        result = cache.stats.to_dict()
        result["algorithm"] = cache.name
        result["final_size"] = cache.size()
        if track_trajectory:
            result["p_trajectory"] = p_trajectory
            result["hit_trajectory"] = hit_trajectory
        return result

    @classmethod
    def compare_all(
        cls,
        events: List[AccessEvent],
        capacity: int = 50,
        workload_name: str = "Workload",
    ) -> List[Dict[str, Any]]:
        algorithms: List[BaseCache] = [
            FIFOCache(capacity=capacity),
            LRUCache(capacity=capacity),
            LFUCache(capacity=capacity),
            ARCCache(capacity=capacity),
            CacheMind(capacity=capacity, enable_scan_shield=True, enable_priority_shielding=True),
        ]

        results = []
        for algo in algorithms:
            res = cls.run_workload(algo, events)
            res["workload"] = workload_name
            results.append(res)
        return results

    @classmethod
    def run_full_benchmark(cls, output_dir: str = "benchmarks") -> Dict[str, Any]:
        os.makedirs(output_dir, exist_ok=True)
        capacity = 40

        # 1. Multi-Process Mixed OS Workload
        mixed_events = WorkloadGenerator.multi_process_mixed_workload(num_requests=2500, cache_capacity=capacity)
        mixed_results = cls.compare_all(mixed_events, capacity=capacity, workload_name="Multi-Process Mixed OS")

        # 2. Sequential Scan Pollution Workload
        # First warm up with hot items, then blast with cold scan
        hot_events = WorkloadGenerator.zipfian_workload(num_requests=800, universe_size=35, alpha=1.2, priority=Priority.HIGH)
        scan_events = WorkloadGenerator.sequential_scan_workload(scan_length=150, start_index=10000, priority=Priority.LOW)
        post_scan_probe = WorkloadGenerator.zipfian_workload(num_requests=400, universe_size=35, alpha=1.2, priority=Priority.HIGH)
        pollution_events = hot_events + scan_events + post_scan_probe
        pollution_results = cls.compare_all(pollution_events, capacity=capacity, workload_name="Cache Pollution Attack")

        # 3. Looping Workload
        loop_events = WorkloadGenerator.looping_workload(loop_size=48, iterations=25)
        loop_results = cls.compare_all(loop_events, capacity=capacity, workload_name="Looping Access")

        # Generate Visual Charts
        cls._plot_hit_ratio_comparison(
            {"Mixed OS": mixed_results, "Pollution Attack": pollution_results, "Looping": loop_results},
            os.path.join(output_dir, "hit_ratio_comparison.png"),
        )
        cls._plot_pollution_resilience(
            pollution_results,
            os.path.join(output_dir, "pollution_resilience_comparison.png"),
        )
        cls._plot_priority_breakdown(
            mixed_results,
            os.path.join(output_dir, "priority_qos_breakdown.png"),
        )

        return {
            "mixed_results": mixed_results,
            "pollution_results": pollution_results,
            "loop_results": loop_results,
            "charts_generated": [
                os.path.join(output_dir, "hit_ratio_comparison.png"),
                os.path.join(output_dir, "pollution_resilience_comparison.png"),
                os.path.join(output_dir, "priority_qos_breakdown.png"),
            ],
        }

    @staticmethod
    def _plot_hit_ratio_comparison(data_map: Dict[str, List[Dict[str, Any]]], save_path: str) -> None:
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)

        workloads = list(data_map.keys())
        algos = [r["algorithm"] for r in data_map[workloads[0]]]
        x = np.arange(len(workloads))
        width = 0.15

        colors = ["#94a3b8", "#f59e0b", "#3b82f6", "#8b5cf6", "#10b981"]

        for idx, algo in enumerate(algos):
            hit_ratios = [
                next(item["hit_ratio"] for item in data_map[w] if item["algorithm"] == algo)
                for w in workloads
            ]
            rects = ax.bar(x + (idx - 2) * width, hit_ratios, width, label=algo, color=colors[idx % len(colors)], edgecolor="#1e293b", linewidth=0.8)
            # Add value labels above bars
            for rect in rects:
                height = rect.get_height()
                ax.annotate(f'{height:.1f}%',
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=7, fontweight='bold')

        ax.set_ylabel("Cache Hit Ratio (%)", fontsize=11, fontweight="bold")
        ax.set_title("CacheMind vs Baseline OS Cache Replacement Algorithms", fontsize=13, fontweight="bold", pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(workloads, fontsize=10, fontweight="bold")
        ax.legend(frameon=True, loc="upper right", shadow=True)
        ax.set_ylim(0, 100)
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close(fig)

    @staticmethod
    def _plot_pollution_resilience(results: List[Dict[str, Any]], save_path: str) -> None:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), dpi=300)

        algos = [r["algorithm"] for r in results]
        hit_ratios = [r["hit_ratio"] for r in results]
        evictions = [r["evictions"] for r in results]

        colors = ["#94a3b8", "#f59e0b", "#3b82f6", "#8b5cf6", "#10b981"]
        ax1.bar(algos, hit_ratios, color=colors, edgecolor="#1e293b", linewidth=0.8)
        ax1.set_ylabel("Hit Ratio During & After Scan (%)", fontsize=10, fontweight="bold")
        ax1.set_title("Hit Ratio Under Scan Attack", fontsize=11, fontweight="bold")
        ax1.set_ylim(0, 80)
        for i, v in enumerate(hit_ratios):
            ax1.text(i, v + 1.5, f"{v:.1f}%", ha='center', fontweight='bold', fontsize=9)

        ax2.bar(algos, evictions, color=colors, edgecolor="#1e293b", linewidth=0.8)
        ax2.set_ylabel("Total Page Evictions", fontsize=10, fontweight="bold")
        ax2.set_title("Cache Page Churn (Lower is Better)", fontsize=11, fontweight="bold")
        for i, v in enumerate(evictions):
            ax2.text(i, v + 5, f"{v}", ha='center', fontweight='bold', fontsize=9)

        plt.suptitle("Cache Pollution Resilience Evaluation (OS Memory Protection)", fontsize=12, fontweight="bold")
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close(fig)

    @staticmethod
    def _plot_priority_breakdown(results: List[Dict[str, Any]], save_path: str) -> None:
        """Visualizes Hit Ratio by Process Priority Class (CRITICAL vs HIGH vs NORMAL vs LOW)."""
        fig, ax = plt.subplots(figsize=(10, 5), dpi=300)

        # Focus on LRU vs CacheMind
        lru_res = next(r for r in results if r["algorithm"] == "LRU")
        cm_res = next(r for r in results if r["algorithm"] == "CacheMind")

        priorities = ["CRITICAL", "HIGH", "NORMAL", "LOW"]
        x = np.arange(len(priorities))
        width = 0.35

        def get_pri_hit_rate(res: Dict[str, Any], pri: str) -> float:
            hits = res["priority_hit_breakdown"].get(pri, 0)
            misses = res["priority_miss_breakdown"].get(pri, 0)
            total = hits + misses
            return (hits / total * 100) if total > 0 else 0.0

        lru_pri_hits = [get_pri_hit_rate(lru_res, p) for p in priorities]
        cm_pri_hits = [get_pri_hit_rate(cm_res, p) for p in priorities]

        b1 = ax.bar(x - width/2, lru_pri_hits, width, label="Standard LRU", color="#f59e0b", edgecolor="#1e293b")
        b2 = ax.bar(x + width/2, cm_pri_hits, width, label="CacheMind (Priority-Shielded)", color="#10b981", edgecolor="#1e293b")

        for rect in b1 + b2:
            h = rect.get_height()
            ax.annotate(f'{h:.1f}%',
                        xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 2),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=8, fontweight='bold')

        ax.set_ylabel("Hit Ratio (%)", fontsize=11, fontweight="bold")
        ax.set_title("QoS Isolation: Hit Ratio by Process Priority Level", fontsize=12, fontweight="bold", pad=12)
        ax.set_xticks(x)
        ax.set_xticklabels(["Kernel / Real-Time\n(CRITICAL)", "Foreground UI\n(HIGH)", "Normal Apps\n(NORMAL)", "Background Batch\n(LOW)"], fontsize=9, fontweight="bold")
        ax.legend(frameon=True, loc="upper right")
        ax.set_ylim(0, 100)
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close(fig)
