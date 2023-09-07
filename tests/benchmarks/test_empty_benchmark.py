import pytest
from pytest_codspeed.plugin import BenchmarkFixture


@pytest.mark.benchmark
def test_hello_world(benchmark: BenchmarkFixture):
    # This is just a placeholder until we have a real benchmark.
    benchmark(lambda: None)
