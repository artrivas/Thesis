import unittest
from dataclasses import replace

from experimentation.config import (
    DEBUG_SEED_COUNT,
    REPLICATION_SEED_COUNT,
    debug_config,
    full_synthetic_config,
    replication_config,
    seeds_from_count,
)
from experimentation.runner import _resolve_seeds


class SeedsFromCountTests(unittest.TestCase):
    def test_expands_to_contiguous_range(self) -> None:
        self.assertEqual(seeds_from_count(5), (0, 1, 2, 3, 4))
        self.assertEqual(seeds_from_count(3, base_seed=10), (10, 11, 12))

    def test_is_deterministic(self) -> None:
        self.assertEqual(seeds_from_count(30), seeds_from_count(30))

    def test_requires_at_least_one(self) -> None:
        with self.assertRaises(ValueError):
            seeds_from_count(0)


class ResolvedSeedsTests(unittest.TestCase):
    def test_seed_count_takes_precedence_over_seeds(self) -> None:
        config = replace(full_synthetic_config(), seeds=(100, 200, 300), seed_count=4)
        self.assertEqual(config.resolved_seeds(), (0, 1, 2, 3))

    def test_explicit_seeds_used_when_no_seed_count(self) -> None:
        config = replace(full_synthetic_config(), seeds=(7, 8, 9), seed_count=None)
        self.assertEqual(config.resolved_seeds(), (7, 8, 9))

    def test_missing_both_raises(self) -> None:
        config = replace(full_synthetic_config(), seeds=None, seed_count=None)
        with self.assertRaises(ValueError):
            config.resolved_seeds()


class NamedConfigSeedTests(unittest.TestCase):
    def test_debug_and_replication_resolve_to_expected_lists(self) -> None:
        self.assertEqual(debug_config().resolved_seeds(), tuple(range(DEBUG_SEED_COUNT)))
        self.assertEqual(replication_config().resolved_seeds(), tuple(range(REPLICATION_SEED_COUNT)))

    def test_replication_is_in_the_20_to_30_band(self) -> None:
        self.assertTrue(20 <= REPLICATION_SEED_COUNT <= 30)

    def test_seed_count_30_resolves_to_thirty_seeds(self) -> None:
        config = replace(replication_config(), seed_count=30)
        self.assertEqual(config.resolved_seeds(), tuple(range(30)))
        self.assertEqual(len(config.resolved_seeds()), 30)


class SeedRangeSliceTests(unittest.TestCase):
    def test_seed_range_slice_equals_sublist(self) -> None:
        seeds = replication_config().resolved_seeds()
        self.assertEqual(_resolve_seeds(seeds, (0, 10)), seeds[0:10])
        self.assertEqual(_resolve_seeds(seeds, (10, 24)), seeds[10:24])
        # Disjoint shards exactly partition the resolved list.
        self.assertEqual(_resolve_seeds(seeds, (0, 12)) + _resolve_seeds(seeds, (12, 24)), seeds)


if __name__ == "__main__":
    unittest.main()
