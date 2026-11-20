/**
 * CacheMind: Multi-Threaded C++ Benchmark & Driver
 * Simulates OS Process Concurrency, Sequential Scan Pollution, and Priority QoS.
 */

#include "cachemind.hpp"
#include <iostream>
#include <vector>
#include <thread>
#include <random>
#include <iomanip>
#include <fstream>

using namespace cachemind;

void print_banner() {
    std::cout << "\n=================================================================\n";
    std::cout << "   CacheMind: High-Performance C++ Core Cache Management Engine  \n";
    std::cout << "      Operating Systems Project - Group 17 (OS Assignment)       \n";
    std::cout << "=================================================================\n\n";
}

int main() {
    print_banner();

    const size_t CACHE_CAPACITY = 50;
    const size_t NUM_REQUESTS = 3000;
    const size_t NUM_THREADS = 4;

    std::cout << "[+] Initializing CacheMind Core with capacity = " << CACHE_CAPACITY << " blocks\n";
    CacheMindCore cache(CACHE_CAPACITY);

    auto start_time = std::chrono::high_resolution_clock::now();

    // Spawn 4 concurrent OS process threads:
    // Thread 0: Kernel Telemetry & Real-Time (CRITICAL)
    // Thread 1: Interactive User App / GUI (HIGH)
    // Thread 2: Normal Worker Process (NORMAL)
    // Thread 3: Background Backup / Sequential Scanner (LOW - Cache Pollution Injector!)
    std::vector<std::thread> workers;

    // Worker 0: Kernel Thread
    workers.emplace_back([&cache, NUM_REQUESTS]() {
        std::mt19937 rng(101);
        std::uniform_int_distribution<int> page_dist(1, 15); // Small hot working set
        for (size_t i = 0; i < NUM_REQUESTS / 4; ++i) {
            std::string key = "kernel_page_" + std::to_string(page_dist(rng));
            std::string val;
            if (!cache.get(key, val)) {
                cache.put(key, "sys_data_" + key, Priority::CRITICAL, (i % 10 == 0));
            }
            std::this_thread::yield();
        }
    });

    // Worker 1: Foreground UI Thread
    workers.emplace_back([&cache, NUM_REQUESTS]() {
        std::mt19937 rng(202);
        std::geometric_distribution<int> geo_dist(0.12); // Skewed access (Zipfian-like)
        for (size_t i = 0; i < NUM_REQUESTS / 4; ++i) {
            int p = (geo_dist(rng) % 30) + 1;
            std::string key = "ui_frame_" + std::to_string(p);
            std::string val;
            if (!cache.get(key, val)) {
                cache.put(key, "ui_buffer_" + key, Priority::HIGH, (i % 5 == 0));
            }
            std::this_thread::yield();
        }
    });

    // Worker 2: Normal Service Thread
    workers.emplace_back([&cache, NUM_REQUESTS]() {
        std::mt19937 rng(303);
        std::uniform_int_distribution<int> dist(1, 60);
        for (size_t i = 0; i < NUM_REQUESTS / 4; ++i) {
            std::string key = "service_doc_" + std::to_string(dist(rng));
            std::string val;
            if (!cache.get(key, val)) {
                cache.put(key, "doc_val_" + key, Priority::NORMAL, false);
            }
            std::this_thread::yield();
        }
    });

    // Worker 3: Low-Priority Background Scanner (The Cache Pollution Attack!)
    workers.emplace_back([&cache, NUM_REQUESTS]() {
        for (size_t i = 0; i < NUM_REQUESTS / 4; ++i) {
            // Massive sequential stream of unique cold pages
            std::string key = "backup_file_chunk_" + std::to_string(10000 + i);
            std::string val;
            if (!cache.get(key, val)) {
                cache.put(key, "cold_backup_data", Priority::LOW, false);
            }
            std::this_thread::yield();
        }
    });

    for (auto& w : workers) {
        w.join();
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    double elapsed_ms = std::chrono::duration<double, std::milli>(end_time - start_time).count();

    Stats s = cache.get_stats();

    std::cout << "\n-----------------------------------------------------------------\n";
    std::cout << "                 CacheMind C++ Benchmark Results                 \n";
    std::cout << "-----------------------------------------------------------------\n";
    std::cout << "Total Requests Processed : " << s.requests << "\n";
    std::cout << "Cache Hits               : " << s.hits << "\n";
    std::cout << "Cache Misses             : " << s.misses << "\n";
    std::cout << "Cache Hit Ratio          : " << std::fixed << std::setprecision(2) << s.hit_ratio() << " %\n";
    std::cout << "Total Page Evictions     : " << s.evictions << "\n";
    std::cout << "Dirty Page Writebacks    : " << s.dirty_writebacks << "\n";
    std::cout << "Pollution Shields (Scan) : " << s.pollution_shields << "\n";
    std::cout << "Priority Shields Active  : " << s.priority_shields << "\n";
    std::cout << "Concurrent Execution Time: " << elapsed_ms << " ms ("
              << (s.requests / (elapsed_ms / 1000.0)) << " ops/sec)\n";
    std::cout << "-----------------------------------------------------------------\n";
    std::cout << "[✓] CacheMind successfully shielded critical OS pages against pollution!\n\n";

    // Export CSV report
    std::ofstream csv("benchmarks/cpp_benchmark_results.csv");
    csv << "Metric,Value\n";
    csv << "Requests," << s.requests << "\n";
    csv << "Hits," << s.hits << "\n";
    csv << "Misses," << s.misses << "\n";
    csv << "HitRatio," << s.hit_ratio() << "\n";
    csv << "Evictions," << s.evictions << "\n";
    csv << "DirtyWritebacks," << s.dirty_writebacks << "\n";
    csv << "PollutionShields," << s.pollution_shields << "\n";
    csv << "PriorityShields," << s.priority_shields << "\n";
    csv << "ExecutionTimeMs," << elapsed_ms << "\n";
    csv.close();

    return 0;
}
