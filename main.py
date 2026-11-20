"""
CacheMind: Intelligent Adaptive Cache Manager
Operating Systems Project - Group 17
Members: Dhruv Arora (992401040023), Ansh Mahajan (992401040030), Shourya Singh (992401040036)
Faculty Guide: Akanksha Ma'am

Unified Entry Point CLI:
  python main.py --demo       # Live Rich interactive terminal demonstration
  python main.py --benchmark  # Run full benchmark evaluation & export PNG plots
  python main.py --web        # Launch interactive Web Visualizer Dashboard
  python main.py --cpp        # Run systems-level multi-threaded C++ engine
"""

from __future__ import annotations
import sys
import argparse
import os
import subprocess
import time

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from cachemind.base import Priority
from cachemind.algorithms.fifo import FIFOCache
from cachemind.algorithms.lru import LRUCache
from cachemind.algorithms.lfu import LFUCache
from cachemind.algorithms.arc import ARCCache
from cachemind.algorithms.cachemind import CacheMind
from cachemind.workloads import WorkloadGenerator
from cachemind.benchmarks import BenchmarkSuite

console = Console()


def print_header():
    console.print(
        Panel.fit(
            "[bold green]🧠 CACHEMIND: INTELLIGENT OS CACHE MANAGER[/bold green]\n"
            "[cyan]Adaptive LRU/LFU Replacement • Process Priority Scheduling • Scan Pollution Shield[/cyan]\n\n"
            "[bold white]College OS Project — Group 17[/bold white]\n"
            "• [yellow]Dhruv Arora[/yellow] (992401040023)\n"
            "• [yellow]Ansh Mahajan[/yellow] (992401040030)\n"
            "• [yellow]Shourya Singh[/yellow] (992401040036)\n"
            "Faculty Guide: [magenta bold]Akanksha Ma'am[/magenta bold]",
            border_style="green",
            box=box.DOUBLE,
            padding=(1, 3),
        )
    )


def run_demo():
    print_header()
    console.print("\n[bold cyan]▶ STEP 1: Demonstrating the Cache Pollution Problem in Traditional LRU[/bold cyan]")
    console.print(
        "[dim]Scenario: 15 critical working-set pages are actively used by Kernel and UI processes.\n"
        "A background backup thread then scans 100 sequential pages (zero temporal reuse).[/dim]\n"
    )

    cap = 20
    lru = LRUCache(capacity=cap)
    cm = CacheMind(capacity=cap, enable_scan_shield=True, enable_priority_shielding=True)

    hot_pages = [f"page_{i}" for i in range(1, 16)]

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        t = progress.add_task("[green]Warming up cache with hot working set...", total=None)
        time.sleep(0.6)
        for p in hot_pages:
            lru.put(p, f"val_{p}", priority=Priority.HIGH)
            cm.put(p, f"val_{p}", priority=Priority.HIGH)
            lru.get(p)
            cm.get(p)

        progress.update(t, description="[red]Injecting 100-page sequential scan attack (Cache Pollution)...")
        time.sleep(0.8)
        scan_events = WorkloadGenerator.sequential_scan_workload(scan_length=100, start_index=8000, priority=Priority.LOW)
        for event in scan_events:
            lru.put(event.key, "scan_val", priority=event.priority)
            cm.put(event.key, "scan_val", priority=event.priority)

        progress.update(t, description="[yellow]Probing hot working set post-attack...")
        time.sleep(0.5)

    lru_survived = sum(1 for p in hot_pages if lru.get(p) is not None)
    cm_survived = sum(1 for p in hot_pages if cm.get(p) is not None)

    tbl = Table(title="🛡️ Cache Pollution Resilience Benchmark (Survival of Hot Working Set)", box=box.ROUNDED)
    tbl.add_column("Cache Algorithm", style="bold")
    tbl.add_column("Initial Working Set", justify="center")
    tbl.add_column("Scan Length (Intruders)", justify="center")
    tbl.add_column("Surviving Hot Pages", justify="center", style="bold")
    tbl.add_column("Survival Rate (%)", justify="center")
    tbl.add_column("Pollution Filtered", justify="center", style="green")

    tbl.add_row(
        "Standard LRU",
        "15 pages",
        "100 pages",
        f"[red]{lru_survived} / 15[/red]",
        f"[red]{(lru_survived/15)*100:.1f}%[/red]",
        "[red]0 (Wiped Out!)[/red]"
    )
    tbl.add_row(
        "CacheMind (Ours)",
        "15 pages",
        "100 pages",
        f"[green]{cm_survived} / 15[/green]",
        f"[green]{(cm_survived/15)*100:.1f}%[/green]",
        f"[green]{cm.stats.pollution_filtered} attacks quarantined[/green]"
    )
    console.print(tbl)

    console.print("\n[bold cyan]▶ STEP 2: Multi-Process OS Simulation (Kernel vs UI vs Background)[/bold cyan]")
    events = WorkloadGenerator.multi_process_mixed_workload(num_requests=1800, cache_capacity=cap)
    results = BenchmarkSuite.compare_all(events, capacity=cap, workload_name="Mixed OS")

    tbl2 = Table(title="📊 Comparative Algorithm Performance on Multi-Process OS Workload", box=box.ROUNDED)
    tbl2.add_column("Algorithm", style="bold")
    tbl2.add_column("Hit Ratio (%)", justify="right", style="cyan")
    tbl2.add_column("Hits", justify="right")
    tbl2.add_column("Misses", justify="right")
    tbl2.add_column("Evictions", justify="right")
    tbl2.add_column("Kernel/RT Hits", justify="right", style="magenta")
    tbl2.add_column("Dirty Writebacks", justify="right")

    for r in results:
        is_cm = r["algorithm"] == "CacheMind"
        algo_name = f"[bold green]{r['algorithm']} ⭐[/bold green]" if is_cm else r['algorithm']
        kernel_hits = r["priority_hit_breakdown"].get("CRITICAL", 0)
        tbl2.add_row(
            algo_name,
            f"{r['hit_ratio']:.2f}%",
            str(r["hits"]),
            str(r["misses"]),
            str(r["evictions"]),
            str(kernel_hits),
            str(r["dirty_writebacks"]),
        )
    console.print(tbl2)
    console.print("\n[bold green]✓ Demo completed successfully![/bold green] Run [cyan]python main.py --web[/cyan] to open the interactive UI dashboard.")


def run_benchmarks():
    print_header()
    console.print("\n[bold cyan]🚀 Running Automated Benchmark Sweeps & Generating Matplotlib Visuals...[/bold cyan]")
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("[yellow]Executing multi-workload simulations...", total=None)
        res = BenchmarkSuite.run_full_benchmark(output_dir="benchmarks")
        progress.update(task, description="[green]Exporting visual comparison charts...")
        time.sleep(0.5)

    console.print("\n[bold green]✓ Benchmark Evaluation Finished![/bold green]")
    console.print("Generated Publication-Quality Figures in [cyan]benchmarks/[/cyan]:")
    for chart in res["charts_generated"]:
        console.print(f"  • [yellow]{chart}[/yellow]")

    console.print("\n[dim]Summary table for Multi-Process Mixed OS Workload:[/dim]")
    tbl = Table(box=box.SIMPLE_HEAD)
    tbl.add_column("Algorithm", style="bold")
    tbl.add_column("Hit Ratio (%)", justify="right")
    tbl.add_column("Evictions", justify="right")
    tbl.add_column("Dirty Writes", justify="right")
    for r in res["mixed_results"]:
        tbl.add_row(r["algorithm"], f"{r['hit_ratio']:.2f}%", str(r["evictions"]), str(r["dirty_writebacks"]))
    console.print(tbl)


def run_web():
    from cachemind.server import run_server
    print_header()
    console.print("[bold green]Starting CacheMind Interactive Web Dashboard...[/bold green]")
    run_server(host="127.0.0.1", port=8000)


def run_cpp():
    print_header()
    cpp_bin = os.path.join("core_cpp", "cachemind_cpp.exe")
    if not os.path.exists(cpp_bin):
        console.print("[yellow]C++ binary not found. Compiling with g++...[/yellow]")
        cmd = "g++ -O3 -std=c++17 core_cpp/cachemind.cpp -o core_cpp/cachemind_cpp.exe"
        subprocess.run(cmd, shell=True, check=True)

    console.print("[bold green]Executing Systems-Level C++ Multi-Threaded Engine...[/bold green]\n")
    subprocess.run([cpp_bin])


def main():
    parser = argparse.ArgumentParser(description="CacheMind: Intelligent OS Cache Manager")
    parser.add_argument("--demo", action="store_true", help="Run animated terminal demonstration")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmarks & generate matplotlib charts")
    parser.add_argument("--web", action="store_true", help="Launch interactive web dashboard")
    parser.add_argument("--cpp", action="store_true", help="Compile and run high-performance C++ engine")

    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.benchmark:
        run_benchmarks()
    elif args.web:
        run_web()
    elif args.cpp:
        run_cpp()
    else:
        # Default: run demo and show usage options
        run_demo()
        console.print("\n[dim]Tip: You can also run:[/dim]")
        console.print("  [cyan]python main.py --web[/cyan]        (Starts Interactive Web GUI)")
        console.print("  [cyan]python main.py --benchmark[/cyan]  (Generates comparison graphs)")
        console.print("  [cyan]python main.py --cpp[/cyan]        (Runs C++ Multi-threaded engine)")


if __name__ == "__main__":
    main()
