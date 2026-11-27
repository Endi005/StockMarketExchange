import unittest
from concurrent.futures import ThreadPoolExecutor

from services.performance_monitor import PerformanceMonitor


class TestPerformanceMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = PerformanceMonitor()

    def test_initial_statistics(self):
        stats = self.monitor.get_statistics()

        self.assertEqual(stats["total_requests"], 0)
        self.assertEqual(stats["successful_requests"], 0)
        self.assertEqual(stats["failed_requests"], 0)
        self.assertEqual(stats["average_duration_ms"], 0)
        self.assertEqual(stats["failure_rate_percent"], 0)
        self.assertEqual(stats["actions"], {})

    def test_successful_request(self):
        self.monitor.record("get_price", True, 10.0)

        stats = self.monitor.get_statistics()

        self.assertEqual(stats["total_requests"], 1)
        self.assertEqual(stats["successful_requests"], 1)
        self.assertEqual(stats["failed_requests"], 0)

    def test_failed_request(self):
        self.monitor.record("login", False, 5.0)

        stats = self.monitor.get_statistics()

        self.assertEqual(stats["failed_requests"], 1)
        self.assertEqual(stats["failure_rate_percent"], 100)

    def test_duration_statistics(self):
        self.monitor.record("get_price", True, 10.0)
        self.monitor.record("get_price", True, 20.0)
        self.monitor.record("get_price", False, 30.0)

        stats = self.monitor.get_statistics()

        self.assertEqual(stats["average_duration_ms"], 20.0)
        self.assertEqual(stats["max_duration_ms"], 30.0)
        self.assertAlmostEqual(
            stats["failure_rate_percent"],
            33.333,
            places=3
        )

    def test_statistics_by_action(self):
        self.monitor.record("login", True, 10.0)
        self.monitor.record("login", False, 20.0)
        self.monitor.record("buy", True, 30.0)

        actions = self.monitor.get_statistics()["actions"]

        self.assertEqual(actions["login"]["requests"], 2)
        self.assertEqual(actions["login"]["successful"], 1)
        self.assertEqual(actions["login"]["failed"], 1)
        self.assertEqual(
            actions["login"]["average_duration_ms"], 15.0
        )

        self.assertEqual(actions["buy"]["requests"], 1)
        self.assertEqual(actions["buy"]["successful"], 1)

    def test_invalid_action(self):
        with self.assertRaises(ValueError):
            self.monitor.record("", True, 10.0)

    def test_invalid_success_value(self):
        with self.assertRaises(ValueError):
            self.monitor.record("login", "yes", 10.0)

    def test_negative_duration(self):
        with self.assertRaises(ValueError):
            self.monitor.record("login", True, -5.0)

    def test_statistics_are_independent_copies(self):
        self.monitor.record("login", True, 10.0)

        stats = self.monitor.get_statistics()
        stats["actions"]["login"]["requests"] = 999

        fresh_stats = self.monitor.get_statistics()

        self.assertEqual(
            fresh_stats["actions"]["login"]["requests"], 1
        )

    def test_concurrent_requests(self):

        def record_requests(worker_id):
            for index in range(100):
                self.monitor.record(
                    "get_price",
                    index % 2 == 0,
                    10.0
                )

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(record_requests, range(10)))

        stats = self.monitor.get_statistics()

        self.assertEqual(stats["total_requests"], 1000)
        self.assertEqual(stats["successful_requests"], 500)
        self.assertEqual(stats["failed_requests"], 500)
        self.assertEqual(stats["failure_rate_percent"], 50.0)
        self.assertEqual(stats["average_duration_ms"], 10.0)
        self.assertEqual(
            stats["actions"]["get_price"]["requests"], 1000
        )


if __name__ == "__main__":
    unittest.main()