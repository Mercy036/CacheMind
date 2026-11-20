# 🧠 CacheMind: An Intelligent Operating System Cache Manager

> **An intelligent cache manager that prevents cache pollution and optimizes memory allocation using priority scheduling and adaptive LRU/LFU algorithms.**

---

### 🎓 Academic Project Information
* **Course:** Operating Systems (IT Core)
* **Group Number:** **Group 17**
* **Project Title:** **CacheMind**
* **Faculty Guide:** **Akanksha Ma'am**
* **Team Members:**
  1. **Dhruv Arora** (Enrollment No: `992401040023`)
  2. **Ansh Mahajan** (Enrollment No: `992401040030`)
  3. **Shourya Singh** (Enrollment No: `992401040036`)

---

## 🌟 Executive Summary

In modern multitasking operating systems, the virtual memory page cache and CPU buffer cache are shared among diverse processes—ranging from critical OS kernel threads and latency-sensitive interactive user interfaces to background backup workers and batch analytics.

Traditional page replacement policies (such as **LRU**, **LFU**, and **FIFO**) suffer from two critical architectural vulnerabilities:
1. **Cache Pollution (Sequential Scan Vulnerability):** When a process performs a large one-time sequential scan (e.g., database table scan, antivirus file scanner, or backup archiving), cold pages with zero temporal reuse rapidly flood the cache. This flushes out valuable hot working sets, causing cache hit ratios to collapse and triggering severe disk I/O thrashing.
2. **Priority Inversion in Memory Hierarchy:** Traditional caches treat all page frames equally. A low-priority background process can freely evict high-priority or real-time kernel pages, violating Quality of Service (QoS) guarantees.

**CacheMind** solves these challenges by combining:
- **Self-Tuning Multi-Queue Adaptive Replacement (ARC Core):** Dynamically adjusts balance between recency ($T_1$) and frequency ($T_2$) using ghost history tracking ($B_1, B_2$).
- **Scan Pollution Shield (Admission Control):** Quarantines sequential scan streams into an ephemeral probation buffer; streaming pages graduate only upon verified temporal reuse.
- **Priority-Aware Eviction Scheduling & Soft Quotas:** Enforces reservation minimums for Critical (Kernel), High (UI/Interactive), Normal (Applications), and Low (Batch) workloads.
- **Dirty Page Writeback Cost Awareness:** Minimizes synchronous disk I/O penalties by preferring clean page evictions under memory pressure.

---

## 🏗️ System Architecture & Data Structures

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

### 1. Dual-Queue Adaptive Balancing (Mathematical Formulation)
Let $c$ denote total cache capacity. CacheMind partitions active cache into two queues:
- $T_1$: Pages referenced **once** recently (captures recency / temporal locality).
- $T_2$: Pages referenced **at least twice** (captures frequency / long-term popularity).

Two ghost caches track metadata of evicted pages:
- $B_1$: Eviction history of $T_1$.
- $B_2$: Eviction history of $T_2$.

Target parameter $p \in [0, c]$ dynamically governs target size of $T_1$. Upon a ghost hit:
$$\delta_1 = \max\left(1, \frac{|B_2|}{|B_1|}\right) \implies p \leftarrow \min(c, p + \delta_1) \quad (\text{Hit in } B_1)$$
$$\delta_2 = \max\left(1, \frac{|B_1|}{|B_2|}\right) \implies p \leftarrow \max(0, p - \delta_2) \quad (\text{Hit in } B_2)$$

### 2. Priority-Aware Eviction Scoring Function
When a victim must be selected from the tail of a queue, candidate pages are evaluated using a composite eviction penalty score:

$$\text{Score}(e) = \frac{\alpha \cdot \text{RecencyRank}(e) + \beta \cdot \text{FrequencyRank}(e) + \text{AgingPenalty}(e) - \text{DirtyBonus}(e)}{\text{PriorityWeight}(e.\text{priority}) \times \text{QuotaProtection}(e)}$$

Where:
- $\text{PriorityWeight} \in \{\text{LOW}: 1.0, \text{NORMAL}: 2.5, \text{HIGH}: 6.0, \text{CRITICAL}: 15.0\}$
- $\text{QuotaProtection} = 2.5\times$ if the priority class is currently below its soft reservation threshold.
- Candidates with higher scores are evicted first; high-priority pages are shielded.

---

## 💻 Technologies Used

| Layer / Component | Technology | Purpose |
| :--- | :--- | :--- |
| **High-Performance Core** | **C++17 (MSYS2 g++ 15.1)** | Low-level systems engine with $O(1)$ custom doubly-linked lists, hash indexing, and mutex synchronization |
| **Simulation Framework** | **Python 3.11** | High-level simulation harness, modular cache algorithms, and synthetic trace generators |
| **Interactive Web UI** | **Python Threading HTTP Engine** | Zero-dependency high-concurrency HTTP server serving real-time REST API and static visualizer |
| **Frontend Visualizer** | **HTML5, Tailwind CSS, Chart.js** | Interactive live visualizer displaying $T_1$, $T_2$, $B_1$, $B_2$, and probation buffers |
| **Benchmarking & Plots** | **Matplotlib, NumPy** | Automated comparative evaluation and publication-grade plot generation |
| **CLI & Terminal UI** | **Rich (Textualize)** | Formatted terminal progress bars, ASCII charts, and colored tabular data |
| **Quality & Testing** | **Pytest** | Automated unit and integration test suite (100% pass rate) |

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
- Python 3.10+ (Installed on system)
- C++ Compiler: `g++` with C++17 support (optional for C++ engine)

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Running Modes

#### Mode A: Interactive Terminal Demo
Runs a side-by-side terminal demonstration comparing CacheMind against standard LRU under a live cache pollution attack:
```powershell
python main.py --demo
```

#### Mode B: Interactive Web Dashboard (Recommended for Presentation!)
Launches the full interactive browser-based visualizer:
```powershell
python main.py --web
```
Open your browser and navigate to:
```
http://127.0.0.1:8000
```
**Features of the Web Dashboard:**
- **Live Memory Layout:** Watch blocks move in real time between $T_1$, $T_2$, $B_1$, $B_2$, and the Quarantine Buffer.
- **Manual Page Access:** Input custom keys, choose Priority (Critical, High, Normal, Low), and toggle dirty writes.
- **Pollution Attack Button:** Inject 15 sequential scan pages and see how CacheMind isolates them.
- **Benchmark Simulator:** Select workload profiles and compare CacheMind, ARC, LRU, LFU, and FIFO with animated Chart.js graphs.
- **Viva Cheat Sheet Tab:** Built-in oral examination questions and answers.

#### Mode C: Automated Benchmark Suite & Chart Generation
Runs performance sweeps across mixed multi-process workloads, scan attacks, and looping access streams:
```powershell
python main.py --benchmark
```
*Generated plots are saved directly to `benchmarks/`:*
- `benchmarks/hit_ratio_comparison.png`
- `benchmarks/pollution_resilience_comparison.png`
- `benchmarks/priority_qos_breakdown.png`

#### Mode D: Multi-Threaded C++ Systems Engine
Executes the native C++17 multi-threaded engine demonstrating concurrent OS thread simulation:
```powershell
python main.py --cpp
```
Or directly via shell:
```powershell
g++ -O3 -std=c++17 core_cpp/cachemind.cpp -o core_cpp/cachemind_cpp.exe
.\core_cpp\cachemind_cpp.exe
```

#### Mode E: Run Automated Unit Tests
```powershell
pytest tests/ -v
```

---

## 📊 Experimental Results & Comparison

### 1. Quantitative Performance Benchmark (Multi-Process OS Workload)
*Test Conditions: Cache capacity = 40 blocks, 2500 memory requests from 4 concurrent process priority tiers.*

| Cache Algorithm | Hit Ratio (%) | Total Evictions | Memory Churn Reduction | Kernel / RT Hits | Dirty Writebacks |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **FIFO** | 18.18% | 1,964 | Baseline | 89 | 286 |
| **Standard LRU** | 20.20% | 1,883 | +4.1% | 92 | 241 |
| **Standard LFU** | 29.98% | 1,526 | +22.2% | 185 | 128 |
| **Classical ARC** | 28.81% | 1,567 | +20.1% | 120 | 164 |
| **CacheMind (Ours)** | **29.64%** | **682** | **-63.8% Churn!** | **215** | **167** |

### 2. Cache Pollution Resilience (Under 100-Page Scan Attack)
- **Standard LRU:** Surviving hot pages = **0 / 15 (0% survival rate - 100% wiped out)**.
- **CacheMind:** Surviving hot pages = **15 / 15 (100% survival rate)**.
- *Scan Quarantine:* CacheMind successfully filtered **100 out of 100** scanning pages into the probation buffer!

---

## 💡 Suggestions for Future Improvements & Advanced OS Features

To make this project even more impressive for university evaluations and research publications:

1. **Hardware-Assisted Cache Allocation (Intel RDT / CAT Integration):**
   - Modern server CPUs feature Intel Cache Allocation Technology (CAT), which enables hardware-enforced L3 cache partitioning per Class of Service (CLOS). CacheMind's priority tiers can map directly to hardware CLOS masks.
2. **Machine-Learning Powered Access Stride Predictor:**
   - Integrate a lightweight Markov model or LSTM/Decision Forest to forecast future access stride distances, predicting whether an incoming page fault belongs to an algorithmic scan before the 3rd miss.
3. **Non-Volatile Memory (NVRAM / CXL Tiering):**
   - Modern OS architectures incorporate Compute Express Link (CXL) and persistent memory. CacheMind could be extended into a multi-tier memory hierarchy: Tier 0 (Fast DRAM), Tier 1 (CXL Shared Memory), and Tier 2 (NVMe SSD).
4. **Asynchronous Background Flush Daemon (kswapd / pdflush):**
   - Implement an asynchronous kernel-style writeback daemon that flushes dirty pages in batches during idle CPU cycles, reducing latency on foreground page allocations.

---

## 🎓 Oral Examination & Viva Preparation Guide

*Key questions faculty evaluators (such as Akanksha Ma'am) frequently ask:*

### Q1: What is Cache Pollution, and why does standard LRU fail during a sequential scan?
**Answer:** Cache pollution occurs when a large volume of one-time data (e.g., video streaming, file backup, or virus scan) is read. Standard LRU unconditionally inserts every new page at the Most Recently Used (MRU) position, evicting the entire existing hot working set. Because the scanned pages have zero temporal reuse, subsequent requests to previously hot pages all miss, collapsing system throughput.

### Q2: How does CacheMind prevent sequential scan pollution without hurting normal workloads?
**Answer:** CacheMind introduces a two-tier admission control called the **Scan Pollution Shield**. When consecutive misses exceed an access threshold or when accesses originate from background/low-priority processes, pages are routed to an ephemeral *Probation Buffer* (occupying ~15% of cache). The page does not enter the primary active queues ($T_1/T_2$) unless it receives a second access, proving temporal reuse.

### Q3: What is the purpose of Ghost Caches ($B_1$ and $B_2$) and how does parameter $p$ adapt?
**Answer:** Ghost caches store only page keys (metadata) whose data payloads have been evicted from physical memory. If a requested page hits in $B_1$, it proves that recency was needed, so we increment target parameter $p$. If it hits in $B_2$, frequency was needed, so we decrement $p$. This allows the OS to dynamically self-tune with zero manual intervention.

### Q4: How does CacheMind prevent priority inversion in memory allocation?
**Answer:** Modern operating systems run real-time and kernel tasks whose pages must not be evicted by lower-priority background processes. CacheMind implements *Priority Shielding* and *Soft Reservation Quotas* (e.g., 25% minimum reserved for CRITICAL/Kernel). When an eviction must occur, high-priority pages near the tail are shielded and lower-priority candidates are evicted instead.

### Q5: What is the computational complexity of CacheMind?
**Answer:** Time complexity is **$O(1)$** for both lookup and insertion, implemented using hash tables (`unordered_map`) combined with doubly-linked lists. Space complexity is **$O(C)$** where $C$ is cache capacity; ghost caches store only lightweight identifiers without payload memory.

---

## 📁 Repository Structure

```
os_assn/
├── main.py                          # Unified CLI entrypoint (--demo, --web, --benchmark, --cpp)
├── README.md                        # Master project guide & documentation
├── REPORT.md                        # Academic submission report for faculty
├── ARCHITECTURE.md                  # Algorithmic deep dive and mathematical proofs
├── requirements.txt                 # Python dependencies
│
├── cachemind/                       # Core Python engine
│   ├── base.py                      # Abstract BaseCache, Priority Enum, CacheEntry, Stats
│   ├── priority.py                  # Priority scheduling, soft quotas, eviction scoring
│   ├── workloads.py                 # Realistic OS workload generators (Mixed OS, Scan, Zipf)
│   ├── benchmarks.py                # Automated benchmark suite & Matplotlib plot generator
│   ├── server.py                    # Multi-threaded HTTP server for interactive web dashboard
│   └── algorithms/
│       ├── fifo.py                  # First-In First-Out baseline
│       ├── lru.py                   # Least Recently Used baseline
│       ├── lfu.py                   # Least Frequently Used baseline (O(1) bucketed)
│       ├── arc.py                   # Canonical Adaptive Replacement Cache (Megiddo & Modha)
│       └── cachemind.py             # CacheMind Adaptive Priority-Aware Engine
│
├── core_cpp/                        # Systems-level C++17 Implementation
│   ├── cachemind.hpp                # Header with custom O(1) doubly-linked list & mutex lock
│   ├── cachemind.cpp                # Multi-threaded concurrent OS process benchmark
│   └── cachemind_cpp.exe            # Compiled native binary
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
