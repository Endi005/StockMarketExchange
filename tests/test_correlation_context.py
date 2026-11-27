import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from services.correlation_context import (
    generate_correlation_id,
    validate_correlation_id,
    get_correlation_id,
    correlation_scope
)


class TestCorrelationContext(unittest.TestCase):

    def test_generated_id_is_valid(self):

        correlation_id = generate_correlation_id()

        self.assertEqual(len(correlation_id), 32)

        self.assertEqual(
            validate_correlation_id(correlation_id),
            correlation_id
        )

    def test_generated_ids_are_unique(self):

        identifiers = {
            generate_correlation_id()
            for _ in range(100)
        }

        self.assertEqual(len(identifiers), 100)

    def test_invalid_ids_are_rejected(self):

        invalid_ids = [
            None,
            123,
            "",
            "invalid",
            "g" * 32,
            "a" * 31,
            "a" * 33,
            "a" * 32 + "\n"
        ]

        for correlation_id in invalid_ids:

            with self.subTest(correlation_id=correlation_id):

                with self.assertRaises(ValueError):

                    validate_correlation_id(correlation_id)

    def test_default_context_is_empty(self):

        self.assertIsNone(get_correlation_id())

    def test_scope_generates_identifier(self):

        with correlation_scope() as correlation_id:

            self.assertEqual(
                get_correlation_id(),
                correlation_id
            )

        self.assertIsNone(get_correlation_id())

    def test_scope_accepts_existing_identifier(self):

        correlation_id = generate_correlation_id()

        with correlation_scope(correlation_id):

            self.assertEqual(
                get_correlation_id(),
                correlation_id
            )

        self.assertIsNone(get_correlation_id())

    def test_nested_scopes_restore_previous_identifier(self):

        outer_id = generate_correlation_id()
        inner_id = generate_correlation_id()

        with correlation_scope(outer_id):

            self.assertEqual(
                get_correlation_id(),
                outer_id
            )

            with correlation_scope(inner_id):

                self.assertEqual(
                    get_correlation_id(),
                    inner_id
                )

            self.assertEqual(
                get_correlation_id(),
                outer_id
            )

        self.assertIsNone(get_correlation_id())

    def test_context_is_restored_after_exception(self):

        with self.assertRaises(RuntimeError):

            with correlation_scope():

                raise RuntimeError("Simulated failure.")

        self.assertIsNone(get_correlation_id())

    def test_concurrent_threads_have_independent_contexts(self):

        barrier = threading.Barrier(10, timeout=5)

        def worker():

            with correlation_scope() as correlation_id:

                barrier.wait()

                observed_id = get_correlation_id()

            return (
                correlation_id,
                observed_id,
                get_correlation_id()
            )

        with ThreadPoolExecutor(max_workers=10) as executor:

            results = list(
                executor.map(
                    lambda _: worker(),
                    range(10)
                )
            )

        identifiers = set()

        for expected, observed, after_scope in results:

            self.assertEqual(expected, observed)
            self.assertIsNone(after_scope)

            identifiers.add(expected)

        self.assertEqual(len(identifiers), 10)


if __name__ == "__main__":
    unittest.main()