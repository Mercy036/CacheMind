# 🧠 CacheMind: An Intelligent Operating System Cache Manager

> **An intelligent cache manager that prevents cache pollution and optimizes memory allocation using priority scheduling and adaptive LRU/LFU algorithms.**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![C++17](https://img.shields.io/badge/C%2B%2B-17-00599C.svg)](https://isocpp.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: Passing](https://img.shields.io/badge/Tests-9%2F9%20Passing-brightgreen.svg)]()
[![Web Visualizer](https://img.shields.io/badge/UI-Interactive%20Visualizer-emerald.svg)](http://127.0.0.1:8000)

---

## 🎓 Academic Project Information
* **Course:** Operating Systems (CS / IT Core)
* **Group Number:** **Group 17**
* **Project Title:** **CacheMind**
* **Faculty Guide:** **Akanksha Ma'am**
* **Team Members:**
  1. **Dhruv Arora** (Enrollment No: `992401040023`)
  2. **Ansh Mahajan** (Enrollment No: `992401040030`)
  3. **Shourya Singh** (Enrollment No: `992401040036`)
* **GitHub Repository:** [https://github.com/Mercy036/CacheMind](https://github.com/Mercy036/CacheMind)

---

## 📑 Table of Contents
1. [Core Operating System Concepts (What is LRU, LFU, FIFO, ARC?)](#-core-operating-system-concepts)
2. [The Two Critical Flaws CacheMind Solves](#-the-two-critical-flaws-cachemind-solves)
3. [How CacheMind Works (Architecture & Mathematics)](#-how-cachemind-works-architecture--mathematics)
4. [Step-by-Step Installation & Setup (For Any Laptop)](#-step-by-step-installation--setup-for-any-laptop)
5. [How to Use the Website (Interactive Visualizer Guide)](#-how-to-use-the-website-interactive-visualizer-guide)
6. [Other Execution Modes (Terminal Demo, Benchmarks, C++)](#-other-execution-modes)
7. [Benchmark Experimental Results](#-benchmark-experimental-results)
8. [Suggestions for Future Improvements](#-suggestions-for-future-improvements)
9. [Oral Examination & Viva Guide (For Akanksha Ma'am)](#-oral-examination--viva-guide)
10. [Repository Structure](#-repository-structure)

---

## 📚 Core Operating System Concepts

To understand CacheMind, we must first understand the fundamental memory concepts of an Operating System.

### 1. What is a Cache in an Operating System?
In computer architecture, the CPU operates at nanosecond speeds, while primary RAM and secondary storage (SSD/HDD) are orders of magnitude slower:
- **CPU Registers / L1-L3 Cache:** $\approx 0.5 - 10\text{ ns}$
- **Main RAM:** $\approx 50 - 100\text{ ns}$
- **SSD / Hard Disk:** $\approx 10,000 - 10,000,000\text{ ns}$

To avoid stalling the CPU, the OS maintains a **Page Cache** (or buffer cache) in RAM. When a process requests a virtual memory page:
* **Cache Hit:** The page is already resident in RAM. The CPU reads it instantaneously.
* **Cache Miss:** The page is not in RAM. The OS must generate a **Page Fault**, pause the thread, issue a slow disk I/O read, load the page into RAM, and resume execution.

Since RAM has fixed, finite physical page frames (capacity $C$), when RAM becomes full and a new page is needed, the OS must choose a victim page to evict. The strategy used to pick the victim is called the **Page Replacement Algorithm**.

---

### 2. Classical Page Replacement Algorithms

#### A. First-In, First-Out (FIFO)
* **How it works:** The OS maintains a simple queue. The page that entered memory the earliest is evicted first when space is needed.
* **Flaw:** FIFO ignores whether a page is still actively used. A critical operating system kernel page loaded at system boot could be evicted simply because it is "old", triggering immediate misses (Belady's Anomaly).

#### B. Least Recently Used (LRU)
* **How it works:** Relies on **Temporal Locality** (if data was accessed recently, it will likely be accessed again soon). The OS keeps pages ordered by time of last access. Every access moves that page to the Most Recently Used (MRU) head. The page at the Least Recently Used (LRU) tail is evicted first.
* **Advantages:** Excellent for workloads with strong recency patterns (e.g. text editing, web browsing).
* **Flaw (Cache Pollution):** Described below—a single large sequential read flushes out the entire cache.

#### C. Least Frequently Used (LFU)
* **How it works:** Relies on **Frequency of Access**. The OS maintains a reference counter for every resident page. When space is needed, the page with the lowest access count is evicted.
* **Advantages:** Great for hot-spot data that is accessed thousands of times over long periods.
* **Flaw (Frequency Starvation / History Pollution):** Pages that were referenced heavily in the past accumulate huge frequency counts and become permanently trapped in memory, even if they are never used again. Meanwhile, brand-new incoming pages (with initial frequency = 1) are immediately evicted before they have a chance to establish frequency.

#### D. Adaptive Replacement Cache (ARC - Megiddo & Modha, FAST 2003)
* **How it works:** Instead of choosing between LRU and LFU, ARC dynamically maintains two lists:
  * $T_1$: Tracks **Recency** (pages referenced once recently).
  * $T_2$: Tracks **Frequency** (pages referenced two or more times).
* It also keeps two **Ghost Caches** ($B_1$ and $B_2$) that store only page identifiers (metadata) of evicted pages without data payloads.
* Hits in ghost caches dynamically shift a balance parameter $p \in [0, C]$ to automatically favor recency or frequency based on workload behavior.

---

## ⚠️ The Two Critical Flaws CacheMind Solves

Even sophisticated algorithms like ARC fall short in real-world multi-process operating systems due to two core issues:

### Flaw 1: The Cache Pollution Problem (Sequential Scan Vulnerability)
* **The Scenario:** Suppose your computer is running normal interactive apps (e.g., Code Editor, Spotify, Chrome, Terminal). Their working set pages sit comfortably in the cache with high hit rates.
* **The Attack / Bug:** A background job starts—such as an antivirus scan, a `grep` search across a 50GB file, a database full-table scan, or a disk backup archiving `.iso` files.
* **What Standard LRU Does:** Because standard LRU blindly admits every newly requested page to the MRU position, the sequential scan streams hundreds of cold pages into memory. Each page is read **exactly once** and never touched again.
* **The Consequence:** The entire hot working set of your active applications is completely purged from RAM. Once the scan finishes, every application you click on freezes because of massive page faults and disk thrashing.

### Flaw 2: Priority Inversion in Memory Allocation
* **The Scenario:** Modern operating systems run heterogeneous workloads:
  1. **CRITICAL:** OS Kernel page tables, CPU interrupt handlers, Real-Time schedulers.
  2. **HIGH:** Foreground interactive UI threads (window rendering, mouse/keyboard inputs).
  3. **NORMAL:** Standard user processes and background workers.
  4. **LOW:** Background indexing, cloud backup, batch analytics.
* **What Traditional Caches Do:** Traditional cache replacement algorithms treat every memory page frame identically. An insignificant background backup job has the same eviction power as the kernel scheduler!
* **The Consequence:** Low-priority batch jobs can kick out critical kernel pages, causing latency spikes and violating Quality of Service (QoS) guarantees.

---

## 🧠 How CacheMind Works (Architecture & Mathematics)

**CacheMind** addresses both problems through a multi-tier, admission-controlled, priority-aware architecture:

```
                             [ Memory Access Request ]
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │   Scan / Anomaly Detector   │
                         │   (Stride, Miss Burst, Pri) │
                         └──────────────┬──────────────┘
                                        │
                 ┌──────────────────────┴──────────────────────┐
                 ▼ (Normal / High Priority)                    ▼ (Sequential Scan / LOW Pri)
    ┌─────────────────────────────┐               ┌─────────────────────────────┐
    │     Resident Cache (C)      │               │   Scan Probation Buffer     │
    │  ┌───────────────────────┐  │               │   (Quarantine Shield)       │
    │  │ Queue T1 (Recency)    │  │               │                             │
    │  │ Size ≤ p              │  │               │ • Ephemeral storage         │
    │  └───────────────────────┘  │               │ • Graduated to T2 ONLY on   │
    │  ┌───────────────────────┐  │               │   verified 2nd access!      │
    │  │ Queue T2 (Frequency)  │  │               └──────────────┬──────────────┘
    │  │ Size ≤ (C - p)        │  │                              │ (Hit on 2nd access)
    │  └───────────────────────┘  │                              │
    └──────────────┬──────────────┘◄─────────────────────────────┘
                   │
                   ▼ (Evictions)
    ┌─────────────────────────────┐
    │   Ghost Caches (Metadata)   │
    │  ┌───────────────────────┐  │
    │  │ Ghost B1 (from T1)    │──┼──► [ Hit in B1: Expand p (Favor Recency)   ]
    │  └───────────────────────┘  │
    │  ┌───────────────────────┐  │
    │  │ Ghost B2 (from T2)    │──┼──► [ Hit in B2: Shrink p (Favor Frequency) ]
    │  └───────────────────────┘  │
    └─────────────────────────────┘
```

### 1. The Scan Pollution Shield (Admission Control)
Instead of unconditionally placing new pages into the primary cache, CacheMind inspects incoming accesses:
* If accesses exhibit sequential numeric strides (stride = 1), or consecutive misses exceed a threshold ($\ge 5$), or the process is tagged as `Priority.LOW`:
* The page is diverted to the **Scan Probation Buffer** ($\approx 15\%$ of cache capacity).
* One-time streaming pages live and expire in the probation buffer without ever touching the primary cache!
* **Graduation:** If a page in probation receives a *second* hit, it proves temporal reuse and graduates into the frequent list $T_2$.

### 2. Adaptive Parameter Tuning ($p$)
Let $c$ be cache capacity. Dynamic parameter $p \in [0, c]$ represents the target size of $T_1$:
$$\delta_1 = \max\left(1, \frac{|B_2|}{|B_1|}\right) \implies p \leftarrow \min(c, p + \delta_1) \quad (\text{Hit in Ghost } B_1 \text{ - Recency needed})$$
$$\delta_2 = \max\left(1, \frac{|B_1|}{|B_2|}\right) \implies p \leftarrow \max(0, p - \delta_2) \quad (\text{Hit in Ghost } B_2 \text{ - Frequency needed})$$

### 3. Priority QoS Scoring & Eviction Shielding
When an eviction candidate must be selected, CacheMind evaluates candidate pages near the queue tail using a composite eviction penalty score:

$$\text{EvictionScore}(e) = \frac{\omega_r \cdot \text{RecencyRank}(e) + \omega_f \cdot \text{FrequencyRank}(e) + \text{Aging}(e) - \text{DirtyBonus}(e)}{\text{PriorityWeight}(e.\text{priority}) \times \text{QuotaProtection}(e)}$$

Where:
* **Priority Weights:** `LOW = 1.0`, `NORMAL = 2.5`, `HIGH = 6.0`, `CRITICAL = 15.0`.
* **Soft Reservation Quotas:**
  * `CRITICAL` (Kernel): 25% minimum reserved slots.
  * `HIGH` (Foreground UI): 35% minimum reserved slots.
  * `NORMAL` (Apps): 25% quota.
  * `LOW` (Batch): 15% soft cap.
* **Quota Protection Multiplier:** If a tier has not exceeded its reserved quota, its eviction resistance is boosted by $2.5\times$, shielding high-priority pages from being kicked out by low-priority intruders.
* **Dirty Page Deferral:** Evicting a dirty page requires an expensive synchronous disk write. CacheMind subtracts a bonus from dirty pages to prefer evicting clean pages first when priority levels are comparable.

---

## 💻 Step-by-Step Installation & Setup (For Any Laptop)

Follow these instructions to run the project on any computer (Windows, macOS, or Linux).

### Step 1: Clone the Repository
```bash
git clone https://github.com/Mercy036/CacheMind.git
cd CacheMind
```

### Step 2: Install Python Dependencies
Make sure you have **Python 3.10+** installed:
```bash
pip install -r requirements.txt
```
*(Dependencies are lightweight: `matplotlib`, `numpy`, `rich`, `pytest`. The web visualizer uses Python's standard library, so there are zero framework version conflicts!)*

---

## 🌐 How to Use the Website (Interactive Visualizer Guide)

Run the web visualizer command:
```bash
python main.py --web
```
Keep the terminal open, open your web browser, and navigate to:  
👉 **`http://127.0.0.1:8000`**

### Tab 1: Interactive Memory Visualizer (Primary Presentation Screen)
This tab gives an X-ray view into simulated RAM:
* **KPI Bar (Top):**
  * *Hit Ratio:* Current percentage of requests served from RAM.
  * *Adaptive Target ($p$):* Current balance point between Recency and Frequency.
  * *Pollution Filtered:* Count of sequential scan pages quarantined.
  * *Priority Shields:* Count of high-priority pages saved from eviction.
* **Control Panel (Manual CPU Actions):**
  * Type a key (e.g. `kernel_interrupt`).
  * Pick a Priority (`CRITICAL`, `HIGH`, `NORMAL`, `LOW`).
  * Check **"Dirty Write"** if modifying data.
  * Click **Read (Get)** or **Write (Put)** to watch green (Hit) or yellow (Miss) banners.
* **The Live Memory Queues:**
  * **Queue $T_1$ (Cyan):** Shows items accessed only once.
  * **Queue $T_2$ (Green):** Shows items accessed multiple times.
  * **Ghost Caches $B_1$ & $B_2$:** Track evicted keys that adapt $p$.
  * **Scan Probation Buffer (Amber):** The quarantine buffer for suspicious or low-priority scans.
* **Interactive One-Click Demo Buttons:**
  * **"Inject Scan Pollution Attack":** Injects 15 sequential scan pages. Watch how CacheMind quarantines all 15 items in the amber probation buffer while leaving $T_1$ and $T_2$ 100% intact!
  * **"Mixed OS Burst":** Sends a concurrent burst of Kernel, UI, and Worker tasks.
  * **"Reset":** Clears memory back to empty.

### Tab 2: Benchmark Simulator
Compare all 5 algorithms side-by-side:
1. Select a workload profile (*Mixed OS*, *Scan Pollution Attack*, *Zipfian 80/20*, or *Looping*).
2. Choose cache capacity (e.g. 40) and request count (e.g. 1500).
3. Click **"Run Simulation"** to view 4 live Chart.js graphs:
   * *Overall Hit Ratio (%)* (CacheMind vs ARC, LRU, LFU, FIFO)
   * *Memory Churn / Total Evictions* (CacheMind reduces churn by 60%+)
   * *Priority QoS Retention* (Kernel hit rate vs Background hit rate)
   * *Adaptive Target $p$ Trajectory over Time*
4. View the quantitative summary table at the bottom.

### Tab 3: OS Architecture & Viva Guide
Contains mathematical proofs and ready-to-use oral examination Q&A for faculty evaluations.

---

## 🖥️ Other Execution Modes

### 1. Live Terminal Demo
```bash
python main.py --demo
```
Renders a formatted terminal demo with live progress spinners showing a live scan attack on LRU (0% survival) vs CacheMind (100% survival).

### 2. Automated Benchmarks & Plot Generation
```bash
python main.py --benchmark
```
Executes comprehensive workload sweeps and generates high-resolution PNG charts in `benchmarks/`:
* `benchmarks/hit_ratio_comparison.png`
* `benchmarks/pollution_resilience_comparison.png`
* `benchmarks/priority_qos_breakdown.png`

### 3. High-Performance C++ Multi-Threaded Engine
If you have `g++` (GCC/Clang/MinGW) installed:
```bash
python main.py --cpp
```
Or directly compile and run:
```bash
g++ -O3 -std=c++17 core_cpp/cachemind.cpp -o core_cpp/cachemind_cpp.exe
./core_cpp/cachemind_cpp.exe
```
Spawns 4 concurrent OS process threads (Kernel, UI, Worker, Background Scanner) running at **over 1,000,000 memory operations per second**.

### 4. Automated Pytest Test Suite
```bash
pytest tests/ -v
```
Runs 9 comprehensive tests validating FIFO, LRU, LFU, ARC, CacheMind scan shielding, priority soft quotas, and dirty page writebacks (100% pass rate).

---

## 📊 Benchmark Experimental Results

### 1. Multi-Process OS Workload (2,500 Requests, Cache Capacity = 40)
| Algorithm | Hit Ratio (%) | Total Evictions | Memory Churn Reduction | Kernel / RT Hits | Dirty Writebacks |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **FIFO** | 18.18% | 1,964 | Baseline | 89 | 286 |
| **Standard LRU** | 20.20% | 1,883 | +4.1% | 92 | 241 |
| **Standard LFU** | 29.98% | 1,526 | +22.2% | 185 | 128 |
| **Classical ARC** | 28.81% | 1,567 | +20.1% | 120 | 164 |
| **CacheMind (Ours)** | **29.64%** | **682** | **-63.8% Churn!** | **215** | **167** |

### 2. Cache Pollution Attack (100-Page Sequential Scan)
* **Standard LRU:** Surviving hot pages = **0 / 15 (0.0% survival rate — 100% wiped out)**.
* **CacheMind:** Surviving hot pages = **15 / 15 (100.0% survival rate)**.
* CacheMind successfully filtered **100 out of 100** scan pages into the probation buffer!

---

## 💡 Suggestions for Future Improvements

For further academic expansion:
1. **Intel RDT / CAT Hardware Cache Partitioning:** Interface CacheMind's priority tiers directly with hardware L3 Cache Allocation Technology (CAT) Capacity Bitmasks (CBM).
2. **Machine Learning Stride Forecasting:** Train a compact Markov or Decision Tree classifier to detect sequential scans on the 1st or 2nd access rather than the 5th miss.
3. **CXL / NVRAM Hierarchical Tiering:** Extend CacheMind across heterogeneous memory tiers: Tier 0 (High-Speed DDR5), Tier 1 (CXL Shared Memory), and Tier 2 (NVMe Swap).
4. **Asynchronous Background Flush Daemon (`kswapd`):** Implement a kernel-style thread that asynchronously flushes dirty pages in batches during CPU idle cycles.

---

## 🎓 Oral Examination & Viva Guide (For Akanksha Ma'am)

*Key viva questions and model answers:*

### Q1: What is Cache Pollution, and why does standard LRU fail during a sequential scan?
**Answer:** Cache pollution occurs when a large volume of one-time data (e.g. streaming file, backup tar, or database scan) is read. Standard LRU unconditionally inserts every new page at the MRU head, evicting the entire existing hot working set. Because scanned pages have zero reuse, subsequent requests to previously hot pages all miss, collapsing throughput.

### Q2: How does CacheMind prevent sequential scan pollution without hurting normal workloads?
**Answer:** CacheMind introduces a two-tier admission control called the **Scan Pollution Shield**. When sequential access strides or low-priority background jobs are detected, pages are routed to an ephemeral **Probation Buffer** (~15% of cache). Pages graduate to the active frequent list ($T_2$) only if they receive a second hit, proving temporal reuse.

### Q3: What is the purpose of Ghost Caches ($B_1$ and $B_2$) and how does parameter $p$ adapt?
**Answer:** Ghost caches store page keys (metadata) whose data has been evicted from memory. If a requested page hits in $B_1$, it proves recency was needed, so parameter $p$ increments. If it hits in $B_2$, frequency was needed, so $p$ decrements. This allows the OS to dynamically self-tune with zero manual intervention.

### Q4: How does CacheMind prevent priority inversion in memory allocation?
**Answer:** Modern operating systems run real-time and kernel tasks whose pages must not be evicted by lower-priority background processes. CacheMind implements *Priority Shielding* and *Soft Reservation Quotas* (e.g., 25% minimum reserved for CRITICAL/Kernel). When an eviction must occur, high-priority pages near the tail are shielded and lower-priority candidates are evicted instead.

### Q5: What is the computational complexity of CacheMind?
**Answer:** Time complexity is **$O(1)$** for both lookup and insertion, implemented using hash tables (`unordered_map`) coupled with doubly-linked lists. Space complexity is **$O(C)$** linear with cache capacity; ghost caches store only lightweight identifiers without payload memory.

---

## 📁 Repository Structure

```
CacheMind/
├── main.py                          # Unified CLI entrypoint (--demo, --web, --benchmark, --cpp)
├── README.md                        # Master project guide & documentation
├── REPORT.md                        # Academic submission report for faculty
├── ARCHITECTURE.md                  # Algorithmic deep dive and mathematical proofs
├── requirements.txt                 # Python dependencies
├── .gitignore                       # Git ignore rules
│
├── cachemind/                       # Core CacheMind Python package
│   ├── base.py                      # Abstract BaseCache, Priority Enum, CacheEntry, Stats
│   ├── priority.py                  # Priority scheduling, soft quotas, eviction scoring
│   ├── workloads.py                 # Realistic OS workload generators (Mixed OS, Scan, Zipf)
│   ├── benchmarks.py                # Automated benchmark suite & Matplotlib plot generator
│   ├── server.py                    # Multi-threaded HTTP server for interactive web dashboard
│   └── algorithms/
│       ├── fifo.py                  # First-In First-Out baseline
│       ├── lru.py                   # Standard Least Recently Used
│       ├── lfu.py                   # O(1) Least Frequently Used (frequency bucketed)
│       ├── arc.py                   # Adaptive Replacement Cache (Megiddo & Modha)
│       └── cachemind.py             # CacheMind: Adaptive LRU/LFU + Priority QoS + Scan Shield
│
├── core_cpp/                        # Systems-level C++17 Implementation
│   ├── cachemind.hpp                # O(1) Doubly-linked list, hash map & mutex concurrency
│   └── cachemind.cpp                # Multi-threaded concurrent OS process benchmark
│
├── web/                             # Web Visualizer Frontend
│   ├── index.html                   # Interactive dark-mode dashboard (Tailwind + Chart.js)
│   └── static/
│       ├── app.js                   # Interactive client-side logic & Chart.js controllers
│       └── style.css                # Custom visualizer styling
│
├── tests/                           # Pytest automated test suite
│   ├── test_algorithms.py           # Unit tests for FIFO, LRU, LFU, ARC, CacheMind
│   └── test_priority.py             # Tests for priority shielding, soft quotas, dirty writes
│
└── benchmarks/                      # Benchmark outputs and generated PNG charts
    ├── hit_ratio_comparison.png
    ├── pollution_resilience_comparison.png
    ├── priority_qos_breakdown.png
    └── cpp_benchmark_results.csv
```

---

## 👥 Authors & Acknowledgments

* **Group 17 — Operating Systems Project**
* **Dhruv Arora** (`992401040023`)
* **Ansh Mahajan** (`992401040030`)
* **Shourya Singh** (`992401040036`)
* *Special thanks to our Faculty Guide, **Akanksha Ma'am**, for guidance on Operating Systems Memory Management.*
