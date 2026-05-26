import pytest

from scripts.benchmark_performance import p99


class TestP99:
    def test_100_values_returns_99(self):
        values = list(range(1, 101))
        assert p99(values) == 99

    def test_empty_returns_zero(self):
        assert p99([]) == 0.0

    def test_single_value(self):
        assert p99([42.0]) == 42.0

    def test_50_values(self):
        values = list(range(1, 51))
        assert p99(values) == 50

    def test_200_values(self):
        values = list(range(1, 201))
        assert p99(values) == 198

    def test_unsorted_input(self):
        values = list(range(100, 0, -1))
        assert p99(values) == 99
