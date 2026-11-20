/**
 * CacheMind: High-Performance C++ Core Cache Management Engine
 * Operating Systems Project - Group 17
 * Demonstrates kernel-level data structures: O(1) Doubly-Linked Lists, Hash Indexing,
 * Adaptive ARC balancing, Scan Shielding, and Thread-Safe Mutex Concurrency.
 */

#pragma once

#include <iostream>
#include <string>
#include <unordered_map>
#include <mutex>
#include <vector>
#include <chrono>
#include <algorithm>

namespace cachemind {

enum class Priority {
    LOW = 1,
    NORMAL = 2,
    HIGH = 3,
    CRITICAL = 4
};

inline const char* priorityToString(Priority p) {
    switch (p) {
        case Priority::LOW: return "LOW";
        case Priority::NORMAL: return "NORMAL";
        case Priority::HIGH: return "HIGH";
        case Priority::CRITICAL: return "CRITICAL";
    }
    return "UNKNOWN";
}

struct Node {
    std::string key;
    std::string value;
    Priority priority;
    int frequency{1};
    bool is_dirty{false};
    uint64_t last_accessed{0};
    int in_list{0}; // 0 = none, 1 = T1, 2 = T2, 3 = Probation
    Node* prev{nullptr};
    Node* next{nullptr};

    Node(std::string k, std::string v, Priority p, bool dirty = false)
        : key(std::move(k)), value(std::move(v)), priority(p), is_dirty(dirty) {
        last_accessed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
    }
};

class DoublyLinkedList {
private:
    Node* head;
    Node* tail;
    size_t count;

public:
    DoublyLinkedList() : count(0) {
        head = new Node("", "", Priority::NORMAL);
        tail = new Node("", "", Priority::NORMAL);
        head->next = tail;
        tail->prev = head;
    }

    ~DoublyLinkedList() {
        // Only delete sentinels; active node payloads are owned by CacheMindCore lookup
        delete head;
        delete tail;
    }

    DoublyLinkedList(const DoublyLinkedList&) = delete;
    DoublyLinkedList& operator=(const DoublyLinkedList&) = delete;

    void push_front(Node* node) {
        if (!node) return;
        node->next = head->next;
        node->prev = head;
        head->next->prev = node;
        head->next = node;
        count++;
    }

    void remove(Node* node) {
        if (!node || !node->prev || !node->next) return;
        node->prev->next = node->next;
        node->next->prev = node->prev;
        node->prev = nullptr;
        node->next = nullptr;
        if (count > 0) count--;
    }

    Node* pop_back() {
        if (empty()) return nullptr;
        Node* node = tail->prev;
        remove(node);
        return node;
    }

    bool empty() const {
        return count == 0;
    }

    size_t size() const {
        return count;
    }

    std::vector<Node*> get_tail_candidates(size_t k) {
        std::vector<Node*> candidates;
        Node* curr = tail->prev;
        while (curr != head && candidates.size() < k) {
            candidates.push_back(curr);
            curr = curr->prev;
        }
        return candidates;
    }
};

struct Stats {
    uint64_t requests{0};
    uint64_t hits{0};
    uint64_t misses{0};
    uint64_t evictions{0};
    uint64_t dirty_writebacks{0};
    uint64_t pollution_shields{0};
    uint64_t priority_shields{0};

    double hit_ratio() const {
        return requests > 0 ? (static_cast<double>(hits) / requests) * 100.0 : 0.0;
    }
};

class CacheMindCore {
private:
    size_t capacity;
    double target_p;
    mutable std::mutex mtx;

    // Active Cache Queues
    DoublyLinkedList T1; // Recency list
    DoublyLinkedList T2; // Frequency list
    std::unordered_map<std::string, Node*> lookup;

    // Ghost Caches (keys only)
    std::unordered_map<std::string, Priority> B1;
    std::unordered_map<std::string, Priority> B2;
    std::vector<std::string> B1_order;
    std::vector<std::string> B2_order;

    // Scan Probation Buffer
    size_t probation_capacity;
    DoublyLinkedList probation;
    std::unordered_map<std::string, Node*> probation_lookup;

    Stats stats;
    int consecutive_misses{0};

    void erase_from_b1(const std::string& key) {
        B1.erase(key);
        B1_order.erase(std::remove(B1_order.begin(), B1_order.end(), key), B1_order.end());
    }

    void erase_from_b2(const std::string& key) {
        B2.erase(key);
        B2_order.erase(std::remove(B2_order.begin(), B2_order.end(), key), B2_order.end());
    }

    void add_to_b1(const std::string& key, Priority p) {
        if (B1.size() >= capacity && !B1_order.empty()) {
            std::string oldest = B1_order.front();
            B1_order.erase(B1_order.begin());
            B1.erase(oldest);
        }
        B1[key] = p;
        B1_order.push_back(key);
    }

    void add_to_b2(const std::string& key, Priority p) {
        if (B2.size() >= capacity && !B2_order.empty()) {
            std::string oldest = B2_order.front();
            B2_order.erase(B2_order.begin());
            B2.erase(oldest);
        }
        B2[key] = p;
        B2_order.push_back(key);
    }

    Node* select_priority_aware_eviction(DoublyLinkedList& list, Priority incoming_p) {
        auto candidates = list.get_tail_candidates(4);
        if (candidates.empty()) return nullptr;

        Node* best_node = candidates[0];
        if (candidates.size() > 1) {
            double highest_score = -1e9;
            for (size_t i = 0; i < candidates.size(); ++i) {
                Node* n = candidates[i];
                double recency_score = 1.0 - (static_cast<double>(i) / (candidates.size() - 1));
                double pri_weight = 1.0;
                switch (n->priority) {
                    case Priority::LOW: pri_weight = 1.0; break;
                    case Priority::NORMAL: pri_weight = 2.5; break;
                    case Priority::HIGH: pri_weight = 6.0; break;
                    case Priority::CRITICAL: pri_weight = 15.0; break;
                }

                if (n->priority > incoming_p) {
                    stats.priority_shields++;
                    pri_weight *= 3.0;
                }

                double score = (recency_score + (1.0 / n->frequency)) / pri_weight;
                if (score > highest_score) {
                    highest_score = score;
                    best_node = n;
                }
            }
        }

        list.remove(best_node);
        best_node->in_list = 0;
        return best_node;
    }

    void replace(bool in_b2, Priority incoming_p) {
        size_t t1_sz = T1.size();
        Node* evicted = nullptr;

        if (t1_sz > 0 && ((t1_sz > static_cast<size_t>(target_p)) || (in_b2 && t1_sz == static_cast<size_t>(target_p)))) {
            evicted = select_priority_aware_eviction(T1, incoming_p);
            if (evicted) {
                lookup.erase(evicted->key);
                add_to_b1(evicted->key, evicted->priority);
            }
        } else if (T2.size() > 0) {
            evicted = select_priority_aware_eviction(T2, incoming_p);
            if (evicted) {
                lookup.erase(evicted->key);
                add_to_b2(evicted->key, evicted->priority);
            }
        } else if (t1_sz > 0) {
            evicted = select_priority_aware_eviction(T1, incoming_p);
            if (evicted) {
                lookup.erase(evicted->key);
                add_to_b1(evicted->key, evicted->priority);
            }
        }

        if (evicted) {
            stats.evictions++;
            if (evicted->is_dirty) stats.dirty_writebacks++;
            delete evicted;
        }
    }

public:
    explicit CacheMindCore(size_t cap)
        : capacity(cap), target_p(cap * 0.5), probation_capacity(std::max<size_t>(2, cap * 0.15)) {}

    ~CacheMindCore() {
        for (auto& pair : lookup) delete pair.second;
        for (auto& pair : probation_lookup) delete pair.second;
    }

    bool get(const std::string& key, std::string& out_value) {
        std::lock_guard<std::mutex> lock(mtx);
        stats.requests++;

        // Hit in active cache
        auto it = lookup.find(key);
        if (it != lookup.end()) {
            Node* node = it->second;
            node->frequency++;
            node->last_accessed = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now().time_since_epoch()).count();

            // Promote to head of T2
            if (node->in_list == 1) {
                T1.remove(node);
                T2.push_front(node);
                node->in_list = 2;
            } else if (node->in_list == 2) {
                T2.remove(node);
                T2.push_front(node);
            }

            out_value = node->value;
            stats.hits++;
            consecutive_misses = 0;
            return true;
        }

        // Hit in Probation Buffer
        auto pit = probation_lookup.find(key);
        if (pit != probation_lookup.end()) {
            Node* node = pit->second;
            probation.remove(node);
            probation_lookup.erase(pit);

            while ((T1.size() + T2.size()) >= capacity && (T1.size() + T2.size()) > 0) {
                replace(false, node->priority);
            }
            T2.push_front(node);
            node->in_list = 2;
            lookup[node->key] = node;

            out_value = node->value;
            stats.hits++;
            consecutive_misses = 0;
            return true;
        }

        stats.misses++;
        consecutive_misses++;
        return false;
    }

    void put(const std::string& key, const std::string& value, Priority priority = Priority::NORMAL, bool is_write = false) {
        std::lock_guard<std::mutex> lock(mtx);
        stats.requests++;

        // 1. Existing Active Key
        auto it = lookup.find(key);
        if (it != lookup.end()) {
            Node* node = it->second;
            node->value = value;
            node->frequency++;
            node->is_dirty = node->is_dirty || is_write;
            if (priority > node->priority) node->priority = priority;

            if (node->in_list == 1) {
                T1.remove(node);
                T2.push_front(node);
                node->in_list = 2;
            } else if (node->in_list == 2) {
                T2.remove(node);
                T2.push_front(node);
            }
            stats.hits++;
            consecutive_misses = 0;
            return;
        }

        // 2. Probation Key
        auto pit = probation_lookup.find(key);
        if (pit != probation_lookup.end()) {
            Node* node = pit->second;
            probation.remove(node);
            probation_lookup.erase(pit);
            node->value = value;
            node->frequency++;
            node->is_dirty = node->is_dirty || is_write;

            while ((T1.size() + T2.size()) >= capacity && (T1.size() + T2.size()) > 0) {
                replace(false, node->priority);
            }
            T2.push_front(node);
            node->in_list = 2;
            lookup[node->key] = node;
            stats.hits++;
            consecutive_misses = 0;
            return;
        }

        stats.misses++;
        consecutive_misses++;

        // 3. Scan Pollution Detection
        if (priority == Priority::LOW || consecutive_misses >= 5) {
            stats.pollution_shields++;
            if (probation.size() >= probation_capacity) {
                Node* old_prob = probation.pop_back();
                if (old_prob) {
                    probation_lookup.erase(old_prob->key);
                    if (old_prob->is_dirty) stats.dirty_writebacks++;
                    delete old_prob;
                }
            }
            Node* new_node = new Node(key, value, priority, is_write);
            new_node->in_list = 3;
            probation.push_front(new_node);
            probation_lookup[key] = new_node;
            return;
        }

        // 4. Hit in Ghost Cache B1
        if (B1.find(key) != B1.end()) {
            double delta = B1.empty() ? 1.0 : std::max(1.0, static_cast<double>(B2.size()) / B1.size());
            target_p = std::min(static_cast<double>(capacity), target_p + delta);
            replace(false, priority);
            erase_from_b1(key);

            Node* new_node = new Node(key, value, priority, is_write);
            new_node->frequency = 2;
            new_node->in_list = 2;
            T2.push_front(new_node);
            lookup[key] = new_node;
            return;
        }

        // 5. Hit in Ghost Cache B2
        if (B2.find(key) != B2.end()) {
            double delta = B2.empty() ? 1.0 : std::max(1.0, static_cast<double>(B1.size()) / B2.size());
            target_p = std::max(0.0, target_p - delta);
            replace(true, priority);
            erase_from_b2(key);

            Node* new_node = new Node(key, value, priority, is_write);
            new_node->frequency = 2;
            new_node->in_list = 2;
            T2.push_front(new_node);
            lookup[key] = new_node;
            return;
        }

        // 6. Complete Miss
        size_t total_l1 = T1.size() + B1.size();
        size_t total_all = total_l1 + T2.size() + B2.size();

        if (total_l1 == capacity) {
            if (T1.size() < capacity) {
                if (!B1_order.empty()) {
                    std::string old_b1 = B1_order.front();
                    erase_from_b1(old_b1);
                }
                replace(false, priority);
            } else {
                Node* n = T1.pop_back();
                if (n) {
                    lookup.erase(n->key);
                    add_to_b1(n->key, n->priority);
                    stats.evictions++;
                    if (n->is_dirty) stats.dirty_writebacks++;
                    delete n;
                }
            }
        } else if (total_l1 < capacity && total_all >= capacity) {
            if (total_all == 2 * capacity && !B2_order.empty()) {
                std::string old_b2 = B2_order.front();
                erase_from_b2(old_b2);
            }
            replace(false, priority);
        } else if ((T1.size() + T2.size()) >= capacity) {
            replace(false, priority);
        }

        Node* new_node = new Node(key, value, priority, is_write);
        new_node->in_list = 1;
        T1.push_front(new_node);
        lookup[key] = new_node;
    }

    Stats get_stats() const {
        std::lock_guard<std::mutex> lock(mtx);
        return stats;
    }

    size_t size() const {
        std::lock_guard<std::mutex> lock(mtx);
        return lookup.size();
    }
};

} // namespace cachemind
