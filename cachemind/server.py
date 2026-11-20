"""
High-Performance, Zero-Dependency HTTP Server for CacheMind Interactive Web Visualizer.
Uses Python's built-in ThreadingHTTPServer and BaseHTTPRequestHandler for 100% compatibility across all Python versions.
"""

from __future__ import annotations
import http.server
import json
import os
import urllib.parse
from typing import Dict, Any, List, Optional

from .base import Priority
from .algorithms.fifo import FIFOCache
from .algorithms.lru import LRUCache
from .algorithms.lfu import LFUCache
from .algorithms.arc import ARCCache
from .algorithms.cachemind import CacheMind
from .workloads import WorkloadGenerator
from .benchmarks import BenchmarkSuite

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")

# Global interactive cache instance
interactive_cache = CacheMind(capacity=16, enable_scan_shield=True, enable_priority_shielding=True)


class CacheMindHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    """Handles REST API and Static UI file delivery."""

    def _set_headers(self, status_code: int = 200, content_type: str = "text/html; charset=utf-8"):
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def send_json(self, data: dict, status_code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self._set_headers(status_code, "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            index_path = os.path.join(STATIC_DIR, "index.html")
            if os.path.exists(index_path):
                with open(index_path, "rb") as f:
                    content = f.read()
                self._set_headers(200, "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_json({"status": "error", "message": "index.html not found"}, 404)
            return

        elif path == "/api/state":
            self.send_json({
                "status": "success",
                "state": interactive_cache.get_state(),
            })
            return

        elif path == "/api/benchmark":
            res = BenchmarkSuite.run_full_benchmark(output_dir="benchmarks")
            self.send_json({"status": "success", "data": res})
            return

        elif path.startswith("/static/"):
            rel_path = path[len("/static/"):].replace("/", os.sep)
            file_path = os.path.join(STATIC_DIR, "static", rel_path)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                content_type = "text/plain; charset=utf-8"
                if file_path.endswith(".css"):
                    content_type = "text/css; charset=utf-8"
                elif file_path.endswith(".js"):
                    content_type = "application/javascript; charset=utf-8"
                elif file_path.endswith(".png"):
                    content_type = "image/png"

                with open(file_path, "rb") as f:
                    content = f.read()
                self._set_headers(200, content_type)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_json({"status": "error", "message": f"File {rel_path} not found"}, 404)
                return

        self.send_json({"status": "error", "message": f"Path {path} not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"

        try:
            req_json = json.loads(post_data) if post_data else {}
        except json.JSONDecodeError:
            req_json = {}

        if path == "/api/reset":
            global interactive_cache
            query = urllib.parse.parse_qs(parsed.query)
            capacity = int(query.get("capacity", [16])[0])
            interactive_cache = CacheMind(capacity=capacity, enable_scan_shield=True, enable_priority_shielding=True)
            self.send_json({
                "status": "success",
                "message": f"Cache reset with capacity {capacity}",
                "state": interactive_cache.get_state()
            })
            return

        elif path == "/api/manual_op":
            op = req_json.get("operation", "get").lower()
            key = str(req_json.get("key", ""))
            value = req_json.get("value") or f"val_{key}"
            pri_str = str(req_json.get("priority", "NORMAL")).upper()
            is_write = bool(req_json.get("is_write", False))

            pri_map = {
                "LOW": Priority.LOW,
                "NORMAL": Priority.NORMAL,
                "HIGH": Priority.HIGH,
                "CRITICAL": Priority.CRITICAL,
            }
            priority = pri_map.get(pri_str, Priority.NORMAL)

            result_type = "hit"
            evicted_key = None

            if op == "get":
                val = interactive_cache.get(key)
                if val is None:
                    result_type = "miss"
                    evicted = interactive_cache.put(key, value, priority=priority, is_write=is_write)
                    if evicted:
                        evicted_key = str(evicted.key)
                else:
                    result_type = "hit"
            else:
                was_hit = interactive_cache.contains(key)
                evicted = interactive_cache.put(key, value, priority=priority, is_write=is_write)
                result_type = "hit" if was_hit else "miss"
                if evicted:
                    evicted_key = str(evicted.key)

            self.send_json({
                "status": "success",
                "result_type": result_type,
                "evicted_key": evicted_key,
                "operation": op,
                "key": key,
                "priority": priority.name,
                "state": interactive_cache.get_state(),
            })
            return

        elif path == "/api/simulate":
            workload_type = req_json.get("workload_type", "mixed")
            cap = int(req_json.get("capacity", 40))
            count = int(req_json.get("num_requests", 1500))
            algorithms = req_json.get("algorithms", ["CacheMind", "ARC", "LRU", "LFU", "FIFO"])

            if workload_type == "scan_attack":
                hot = WorkloadGenerator.zipfian_workload(num_requests=int(count * 0.4), universe_size=int(cap * 0.8), alpha=1.2, priority=Priority.HIGH)
                scan = WorkloadGenerator.sequential_scan_workload(scan_length=int(count * 0.3), start_index=8000, priority=Priority.LOW)
                post = WorkloadGenerator.zipfian_workload(num_requests=int(count * 0.3), universe_size=int(cap * 0.8), alpha=1.2, priority=Priority.HIGH)
                events = hot + scan + post
            elif workload_type == "zipfian":
                events = WorkloadGenerator.zipfian_workload(num_requests=count, universe_size=int(cap * 2.5), alpha=1.0)
            elif workload_type == "looping":
                loop_size = int(cap * 1.3)
                iterations = max(5, count // loop_size)
                events = WorkloadGenerator.looping_workload(loop_size=loop_size, iterations=iterations)
            else:
                events = WorkloadGenerator.multi_process_mixed_workload(num_requests=count, cache_capacity=cap)

            algo_map = {
                "FIFO": lambda: FIFOCache(capacity=cap),
                "LRU": lambda: LRUCache(capacity=cap),
                "LFU": lambda: LFUCache(capacity=cap),
                "ARC": lambda: ARCCache(capacity=cap),
                "CacheMind": lambda: CacheMind(capacity=cap, enable_scan_shield=True, enable_priority_shielding=True),
            }

            results = []
            for name in algorithms:
                if name in algo_map:
                    cache = algo_map[name]()
                    res = BenchmarkSuite.run_workload(cache, events, track_trajectory=(name in ["CacheMind", "ARC", "LRU"]))
                    res["algorithm"] = name
                    results.append(res)

            self.send_json({
                "status": "success",
                "workload": workload_type,
                "total_events": len(events),
                "capacity": cap,
                "results": results,
            })
            return

        self.send_json({"status": "error", "message": f"Endpoint {path} not found"}, 404)

    def log_message(self, format, *args):
        # Clean terminal output (suppress noisy per-request logs unless debug)
        return


def run_server(host: str = "127.0.0.1", port: int = 8000):
    server_address = (host, port)
    httpd = http.server.ThreadingHTTPServer(server_address, CacheMindHTTPRequestHandler)
    print(f"\n==================================================================")
    print(f"  🧠 CacheMind Web Visualizer Dashboard Running")
    print(f"  🔗 URL: http://{host}:{port}")
    print(f"  👉 Open the link above in your web browser to explore!")
    print(f"  🛑 Press Ctrl+C in this terminal to stop the server")
    print(f"==================================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[+] CacheMind server shutting down gracefully.")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
