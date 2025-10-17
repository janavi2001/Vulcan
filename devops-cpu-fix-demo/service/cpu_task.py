import os, time
from functools import lru_cache

# A deliberately slow Fibonacci implementation (recursive)
def fib(n: int) -> int:
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

# Return value type: dict
def busy_cpu_task():
    n = int(os.getenv("FIB_N", "35"))  # large n = high CPU
    start = time.perf_counter()
    value = fib(n)
    elapsed = (time.perf_counter() - start) * 1000
    return {"elapsed_ms": elapsed, "result": value}
