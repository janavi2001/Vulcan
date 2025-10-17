import os, re, time, json, difflib, requests
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = ROOT / "service"
TASK_FILE = SERVICE_DIR / "cpu_task.py"
REPORTS_DIR = Path(__file__).resolve().parent / "knowledge"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

HEAVY_URL = "http://127.0.0.1:8000/api/heavy"
THRESHOLD_MS = 1500.0

def _read(p: Path) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return f.read()

def _write(p: Path, s: str) -> None:
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)

def _measure() -> float:
    try:
        r = requests.get(HEAVY_URL, timeout=10)
        r.raise_for_status()
        return r.json().get("elapsed_ms", 9999)
    except Exception:
        return 9999

def _patch_code(src: str) -> str:
    """
    Replace recursive fib() with an iterative version.
    """
    pattern = re.compile(r"def fib\(.*?\):.*?return fib\(n-1\) \+ fib\(n-2\)", re.S)
    replacement = (
        "def fib(n: int) -> int:\n"
        "    if n <= 1:\n"
        "        return n\n"
        "    a, b = 0, 1\n"
        "    for _ in range(2, n + 1):\n"
        "        a, b = b, a + b\n"
        "    return b"
    )
    return re.sub(pattern, replacement, src)

def _write_diff(before: str, after: str, filename: str) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    diff_path = REPORTS_DIR / f"cpu-fix-{ts}.patch"
    diff = difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                fromfile=f"{filename} (before)", tofile=f"{filename} (after)")
    _write(diff_path, "".join(diff))
    return diff_path

def _write_report(stage: str, before_ms: float, after_ms: float, changed: bool) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = REPORTS_DIR / f"cpu-report-{stage}-{ts}.md"
    _write(path, f"""# CPU Auto-Resolution Report — {stage.upper()}

**Timestamp (UTC):** {datetime.utcnow().isoformat()}
**Stage:** {stage}

## Measurements
- Before fix: {before_ms:.1f} ms
- After fix:  {after_ms:.1f} ms

## Action Taken
- {'Rewrote' if changed else 'Skipped rewrite'} cpu_task.py function fib()

## Verification
- {'✅ Improvement detected' if after_ms < before_ms else '❌ No improvement'}
""")
    return path

def run(stage: str):
    before_ms = _measure()
    print(f"[agent] Stage={stage}, Before={before_ms:.1f} ms")

    if stage == "test" and before_ms <= THRESHOLD_MS:
        return {"stage": stage, "changed": False, "before_ms": before_ms, "after_ms": before_ms}

    before_src = _read(TASK_FILE)
    after_src = _patch_code(before_src)
    changed = after_src != before_src

    if changed:
        _write(TASK_FILE, after_src)

    time.sleep(1)
    after_ms = _measure()
    print(f"[agent] After={after_ms:.1f} ms")

    diff_path = _write_diff(before_src, after_src, "cpu_task.py") if changed else None
    report_path = _write_report(stage, before_ms, after_ms, changed)

    return {
        "stage": stage,
        "changed": changed,
        "before_ms": before_ms,
        "after_ms": after_ms,
        "diff_path": str(diff_path) if diff_path else None,
        "report_path": str(report_path)
    }
