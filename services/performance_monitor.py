import threading
import time


class PerformanceMonitor:
    """Thread-safe monitoring of server request performance."""

    def __init__(self):
        self._lock = threading.Lock()
        self._started_at = time.monotonic()

        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0

        self._total_duration_ms = 0.0
        self._max_duration_ms = 0.0

        self._actions = {}

    def record(self, action, success, duration_ms):

        if not isinstance(action, str) or not action:
            raise ValueError("Invalid action name.")

        if not isinstance(success, bool):
            raise ValueError("Success must be a boolean.")

        if duration_ms < 0:
            raise ValueError("Duration cannot be negative.")

        with self._lock:

            self._total_requests += 1
            self._total_duration_ms += duration_ms

            self._max_duration_ms = max(
                self._max_duration_ms,
                duration_ms
            )

            if success:
                self._successful_requests += 1
            else:
                self._failed_requests += 1

            action_stats = self._actions.setdefault(
                action,
                {
                    "requests": 0,
                    "successful": 0,
                    "failed": 0,
                    "total_duration_ms": 0.0
                }
            )

            action_stats["requests"] += 1
            action_stats["total_duration_ms"] += duration_ms

            if success:
                action_stats["successful"] += 1
            else:
                action_stats["failed"] += 1

    def get_statistics(self):

        with self._lock:

            uptime = time.monotonic() - self._started_at

            total = self._total_requests

            average_duration = (
                self._total_duration_ms / total
                if total else 0.0
            )

            failure_rate = (
                self._failed_requests / total * 100
                if total else 0.0
            )

            throughput = (
                total / uptime
                if uptime > 0 else 0.0
            )

            actions = {}

            for action, stats in self._actions.items():

                actions[action] = {
                    "requests": stats["requests"],
                    "successful": stats["successful"],
                    "failed": stats["failed"],
                    "average_duration_ms": round(
                        stats["total_duration_ms"]
                        / stats["requests"],
                        3
                    )
                }

            return {
                "uptime_seconds": round(uptime, 3),
                "total_requests": total,
                "successful_requests": self._successful_requests,
                "failed_requests": self._failed_requests,
                "failure_rate_percent": round(failure_rate, 3),
                "average_duration_ms": round(average_duration, 3),
                "max_duration_ms": round(self._max_duration_ms, 3),
                "requests_per_second": round(throughput, 3),
                "actions": actions
            }