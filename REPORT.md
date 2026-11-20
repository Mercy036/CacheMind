# Academic Project Report: CacheMind

## Project Title
**CacheMind: An Intelligent Cache Manager that Prevents Cache Pollution and Optimizes Memory Allocation using Priority Scheduling and Adaptive LRU/LFU Algorithms**

### Course & Group Information
* **Course:** Operating Systems Laboratory / Course Project
* **Group:** Group 17
* **Faculty Guide:** Akanksha Ma'am
* **Student Contributors:**
  - Dhruv Arora (Enrollment: 992401040023)
  - Ansh Mahajan (Enrollment: 992401040030)
  - Shourya Singh (Enrollment: 992401040036)

---

## 1. Abstract
In modern multiprogrammed operating systems, memory caching plays an indispensable role in bridging the speed gap between high-speed processor caches/RAM and secondary storage. Traditional page replacement algorithms (such as Least Recently Used - LRU, Least Frequently Used - LFU, and First-In First-Out - FIFO) suffer from critical limitations when handling heterogeneous multi-process workloads. Specifically, large sequential scans (e.g., file backups, disk indexing) cause severe *cache pollution*, evicting active working sets and degrading system-wide hit rates. Furthermore, traditional caches lack process awareness, leading to *priority inversion* where low-priority background jobs evict high-priority kernel or real-time pages. 

This project presents **CacheMind**, an intelligent operating system cache manager. CacheMind integrates three architectural pillars: (1) self-tuning dual-queue Adaptive Replacement Caching (ARC), (2) admission control via a scan-pollution probation shield, and (3) priority-aware eviction scheduling with dynamic soft quotas and dirty writeback optimization. Both high-performance systems-level C++17 and Python simulation environments were engineered alongside an interactive web visualizer. Experimental benchmarks show that CacheMind achieves a 100% survival rate for hot working sets under sequential scan attacks (compared to 0% for standard LRU) and reduces overall memory churn by 63.8% in multi-process OS workloads.

---

## 2. Introduction & Problem Statement

### 2.1 The Memory Hierarchy and Page Replacement
An operating system's virtual memory manager abstracts physical RAM into page frames. When all frames are occupied and a page fault occurs, a page replacement algorithm must determine which page frame to evict.

### 2.2 Flaws in Existing Approaches
1. **The Cache Pollution Problem in LRU:**
   LRU relies entirely on temporal locality. When a thread reads a large file sequentially (e.g. `cat file.iso` or database scan), each page is accessed exactly once. Standard LRU unconditionally inserts each page into the Most Recently Used (MRU) position, evicting the entire existing working set. Once the scan finishes, subsequent accesses to previously hot pages experience 100% cache misses.
2. **Frequency Starvation in LFU:**
   LFU tracks historical access counts. However, LFU accumulates stale frequency counts over time, causing previously popular pages to remain resident long after they are no longer needed (the cache pollution of historical pages), while new pages are immediately evicted before they can establish frequency.
3. **Priority Agnosticism (Priority Inversion):**
   Existing replacement algorithms treat all pages identically, irrespective of whether the owning process is an interactive GUI thread, an OS kernel scheduler structure, or an asynchronous background backup job.

---

## 3. System Architecture & Methodology

CacheMind introduces a multi-tier memory management architecture:

### 3.1 Dual-Queue Adaptive Core (ARC Mechanism)
CacheMind maintains two active doubly-linked queues of total capacity $C$:
- **Queue $T_1$ (Recency Queue):** Contains pages that have been referenced only once recently. Target capacity is dynamically bounded by parameter $p \in [0, C]$.
- **Queue $T_2$ (Frequency Queue):** Contains pages that have been referenced two or more times. Target capacity is $(C - p)$.

To adapt $p$ without keeping full data payloads in memory, CacheMind maintains two ghost caches:
- **Ghost $B_1$:** Tracks keys evicted from $T_1$.
- **Ghost $B_2$:** Tracks keys evicted from $T_2$.

Dynamic adaptation formula:
- On hit in $B_1$: $\delta_1 = \max(1, |B_2| / |B_1|)$; $p \leftarrow \min(C, p + \delta_1)$ (Favors recency)
- On hit in $B_2$: $\delta_2 = \max(1, |B_1| / |B_2|)$; $p \leftarrow \max(0, p - \delta_2)$ (Favors frequency)

### 3.2 Scan Pollution Shield (Admission Control)
To defeat scan pollution, CacheMind implements an access stride and miss-burst detector. When sequential accesses or requests from Priority `LOW` processes occur, pages are routed to an ephemeral **Probation Buffer** (~15% of cache size).
- Single-access cold scan pages stay in the probation buffer and are discarded without polluting $T_1$ or $T_2$.
- If a page in the probation buffer receives a second hit, it graduates to the active frequent list $T_2$.

### 3.3 Priority QoS Scheduling & Quotas
Processes are classified into 4 priority classes:
- `CRITICAL` (Weight 15.0): OS Kernel structures, interrupt tables, real-time threads (25% reserved quota).
- `HIGH` (Weight 6.0): Interactive foreground apps, window managers (35% reserved quota).
- `NORMAL` (Weight 2.5): Standard user applications (25% quota).
- `LOW` (Weight 1.0): Background batch jobs, antivirus indexers (15% quota cap).

The eviction score for candidate pages near queue tails is computed as:
$$\text{Score} = \frac{\text{BaseRank} + \text{Aging} - \text{DirtyBonus}}{\text{PriorityWeight} \times \text{QuotaMultiplier}}$$

High-priority pages receive shielding, forcing lower-priority candidate eviction.

---

## 4. Implementation Details

1. **Native C++17 Core (`core_cpp/`):**
   - Implemented with custom $O(1)$ Doubly-Linked Lists and `std::unordered_map`.
   - Thread safety enforced using `std::mutex` and `std::lock_guard`.
   - Concurrency benchmark running 4 simultaneous worker threads (Kernel, UI, Worker, Background Scanner).
2. **Python Benchmarking & Simulation Suite (`cachemind/`):**
   - Object-oriented baseline models: `FIFOCache`, `LRUCache`, `LFUCache`, `ARCCache`, `CacheMind`.
   - Synthetic & realistic trace generators: Zipfian (power law), Sequential Scan, and Multi-Process OS.
   - Automated Matplotlib figure generation.
3. **Interactive Visualizer & REST API (`web/` & `cachemind/server.py`):**
   - Multi-threaded Python HTTP REST API server.
   - Interactive UI with Chart.js showing real-time queue states and animated memory block allocations.

---

## 5. Experimental Results & Analysis

### Experiment 1: Multi-Process OS Mixed Workload (2,500 Requests, Capacity = 40)
| Algorithm | Hit Ratio | Evictions | Kernel Hits | Dirty Writebacks |
| :--- | :---: | :---: | :---: | :---: |
| FIFO | 18.18% | 1,964 | 89 | 286 |
| LRU | 20.20% | 1,883 | 92 | 241 |
| LFU | 29.98% | 1,526 | 185 | 128 |
| ARC | 28.81% | 1,567 | 120 | 164 |
| **CacheMind** | **29.64%** | **682** | **215** | **167** |

*Analysis:* CacheMind achieves comparable or higher hit rates to ARC/LFU while reducing total evictions by **63.8%** (from 1,883 down to 682). It delivered **215 Kernel Hits**, demonstrating superior QoS retention.

### Experiment 2: Cache Pollution Attack Resilience
- **LRU:** 100 sequential scan pages evicted 100% of the active working set (0/15 hot pages survived).
- **CacheMind:** 100% of the active working set survived (15/15 hot pages remained resident) because all 100 scan pages were isolated in the probation buffer.

---

## 6. Conclusion
CacheMind demonstrates an intelligent, adaptive, and priority-aware memory management strategy for modern operating systems. By marrying the self-tuning capabilities of ARC with admission control and priority scheduling, it eliminates the long-standing vulnerabilities of cache pollution and priority inversion while maintaining $O(1)$ time complexity.

---

## 7. References
1. Megiddo, N., & Modha, D. S. (2003). *ARC: A Self-Tuning, Low Overhead Replacement Cache*. In FAST (Vol. 3, pp. 115-130).
2. Silberschatz, A., Galvin, P. B., & Gagne, G. *Operating System Concepts* (10th Edition). Wiley.
3. Tanenbaum, A. S., & Bos, H. *Modern Operating Systems* (4th Edition). Pearson.
4. Intel Corporation. *Intel Resource Director Technology (Intel RDT) Architecture Specification*.
