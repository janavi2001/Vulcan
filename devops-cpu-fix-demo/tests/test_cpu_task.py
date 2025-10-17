import time
import sys
from pathlib import Path

# Import from the service directory
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "service"))

import cpu_task  # noqa: E402

def test_fib_correctness():
    """Ensure the Fibonacci logic is mathematically correct."""
    assert cpu_task.fib(0) == 0
    assert cpu_task.fib(1) == 1
    assert cpu_task.fib(5) == 5
    assert cpu_task.fib(10) == 55

def test_cpu_performance():
    """Ensure the fib() function runs below threshold for moderate input."""
    start = time.perf_counter()
    _ = cpu_task.fib(35)
    elapsed = (time.perf_counter() - start) * 1000
    assert elapsed < 500.0, f"Function still too slow: {elapsed:.1f} ms"
