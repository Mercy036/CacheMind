# Algorithmic Architecture & Mathematical Specifications: CacheMind

## 1. Problem Formalization

Consider a cache storage system with fixed capacity of $C$ uniform page blocks. Let $R = (r_1, r_2, \dots, r_m)$ be a sequence of page requests where each request $r_t = (k_t, \pi_t, w_t)$ represents:
- $k_t \in \mathcal{U}$: Unique page identifier (key / virtual address).
- $\pi_t \in \{\text{LOW}, \text{NORMAL}, \text{HIGH}, \text{CRITICAL}\}$: Process priority level.
- $w_t \in \{0, 1\}$: Write flag ($1 =$ dirty write, $0 =$ clean read).

The objective of the cache manager is twofold:
1. Maximize the total priority-weighted hit ratio:
   $$\max \sum_{t=1}^m \mathbf{1}_{\{k_t \in \mathcal{M}_{t-1}\}} \cdot W(\pi_t)$$
2. Minimize the cache churn and I/O writeback cost:
   $$\min \sum_{t=1}^m \text{Cost}(\text{eviction}_t)$$

---

## 2. Queue Partitioning and Invariants

At any point in time, CacheMind maintains five internal queues:
1. $T_1$: Active recency queue.
2. $T_2$: Active frequency queue.
3. $B_1$: Ghost recency history (metadata only).
4. $B_2$: Ghost frequency history (metadata only).
5. $P$: Scan probation buffer.

### Fundamental Invariants:
1. **Resident Cache Capacity:**
   $$|T_1| + |T_2| \le C$$
2. **Combined Footprint with Ghost History:**
   $$|T_1| + |B_1| \le C$$
   $$|T_1| + |T_2| + |B_1| + |B_2| \le 2C$$
3. **Probation Buffer Capacity:**
   $$|P| \le \lfloor 0.15 \cdot C \rfloor$$

---

## 3. Dynamic Tuning Parameter $p$

Parameter $p \in [0, C]$ represents the target size of queue $T_1$.
The update rule balances recency vs. frequency based on the relative sizes of ghost caches $B_1$ and $B_2$:

- When a requested page $k \in B_1$:
  $$p \leftarrow \min\left(C, p + \max\left(1, \frac{|B_2|}{|B_1|}\right)\right)$$
- When a requested page $k \in B_2$:
  $$p \leftarrow \max\left(0, p - \max\left(1, \frac{|B_1|}{|B_2|}\right)\right)$$

This non-linear step size ensures rapid convergence when the cache is improperly balanced and smooth stabilization when operating near steady-state.

---

## 4. Priority Eviction Mechanics

Standard ARC arbitrarily pops from the tail of $T_1$ or $T_2$. In CacheMind, a candidate evaluation window of size $W = \min(k, 6)$ is inspected at the tail of the target list:

$$\text{CandidateScore}(e) = \frac{\omega_r \cdot \text{RecRank}(e) + \omega_f \cdot \text{FreqRank}(e) + \text{Aging}(e) - \text{DirtyBonus}(e)}{\text{Weight}(\pi(e)) \cdot \text{QuotaProtection}(e)}$$

Where:
- $\text{RecRank}(e) = 1.0 - \frac{i}{W-1}$ (Oldest candidate has rank 1.0)
- $\text{FreqRank}(e) = \frac{1}{\text{freq}(e)}$
- $\text{DirtyBonus}(e) = 0.2$ if page is dirty (avoids synchronous disk writeback)
- $\text{QuotaProtection}(e) = 2.5$ if current tier count $\le \text{ReservedQuota}(\pi(e))$

The candidate with the **highest score** is chosen for eviction.

---

## 5. Complexity Proofs

### Time Complexity: $O(1)$
- **Lookups:** Hash map lookup is average $O(1)$.
- **Insertions & Deletions:** Doubly-linked list splicing with head/tail pointers is worst-case $O(1)$.
- **Candidate Selection:** Evaluates at most $W \le 6$ nodes near the tail, giving $O(W) = O(1)$ constant time.
- **Overall Time Complexity:** **$O(1)$ per request**.

### Space Complexity: $O(C)$
- $T_1$ and $T_2$ store at most $C$ active data blocks.
- $B_1$ and $B_2$ store at most $C$ metadata keys.
- $P$ stores at most $0.15 \cdot C$ blocks.
- **Overall Space Complexity:** **$O(C)$ linear with cache capacity**.
