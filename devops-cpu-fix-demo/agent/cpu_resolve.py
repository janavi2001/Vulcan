import os, time, json, difflib, ast, re
from pathlib import Path
from datetime import datetime
import requests
import subprocess

import smtplib
from email.message import EmailMessage

# ====== EMAIL CONFIG ======
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "vulcanemailpush@gmail.com"       # Replace with sender email
SENDER_PASSWORD = "vzgz ssmb kpbv atad"       # Or read from os.getenv("SMTP_PASS")
RECIPIENT_EMAIL = "thilak.shriyan43@gmail.com"  # Replace with recipient email
# ==========================

def _send_email_with_report(stage: str, report_path: Path, attachments: list[Path] | None = None) -> None:
    """Send the generated report and attachments via email."""
    try:
        msg = EmailMessage()
        msg["Subject"] = f"[Agent Report] CPU Fix Summary — {stage.upper()}"
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECIPIENT_EMAIL

        body = f"""
Hello,

The automated CPU resolution agent has completed its run for stage: {stage.upper()}.

Please find the attached report for details.

Best,
DevOps Auto-Resolution Agent
"""
        msg.set_content(body)

        # Attach main report
        with open(report_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="text",
                subtype="markdown",
                filename=report_path.name,
            )

        # Optional additional attachments
        if attachments:
            for att in attachments:
                if att.exists():
                    with open(att, "rb") as f:
                        msg.add_attachment(
                            f.read(),
                            maintype="text",
                            subtype="plain",
                            filename=att.name,
                        )

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print(f"[agent] Email sent successfully to {RECIPIENT_EMAIL}")

    except Exception as e:
        print(f"[agent] Failed to send email: {e}")


ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = ROOT / "service"
TASK_FILE = SERVICE_DIR / "cpu_task.py"
REPORTS_DIR = Path(__file__).resolve().parent / "knowledge"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

HEAVY_URL = "http://127.0.0.1:8069/api/heavy"
THRESHOLD_MS = 1500.0  # if faster than this, we consider it good

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
        return float(r.json().get("elapsed_ms", 9999.0))
    except Exception:
        return 9999.0
def _run_pytests() -> tuple[bool, str]:
    """
    Run pytest on the tests/ folder and capture its output.
    Returns (success, output_text).
    """
    try:
        completed = subprocess.run(
            ["pytest", "-q", "tests", "--maxfail=1", "--disable-warnings"],
            capture_output=True, text=True, cwd=ROOT
        )
        success = completed.returncode == 0
        output = completed.stdout + completed.stderr
        return success, output
    except Exception as e:
        return False, str(e)

def _unified_diff(before: str, after: str, filename: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True),
        fromfile=f"{filename} (before)", tofile=f"{filename} (after)"
    ))

def _write_artifacts(stage: str, before_ms: float, after_ms: float, changed: bool, diff_text: str | None) -> tuple[Path, Path | None]:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    report_path = REPORTS_DIR / f"cpu-report-{stage}-{ts}.md"
    _write(report_path, f"""# CPU Auto-Resolution Report — {stage.upper()}

**Timestamp (UTC):** {datetime.utcnow().isoformat()}
**Stage:** {stage}

## Measurements
- Before fix: {before_ms:.1f} ms
- After fix:  {after_ms:.1f} ms
- Threshold:  {THRESHOLD_MS:.0f} ms

## Action Taken
- {'Edited cpu_task.py (rewrite/annotation applied)' if changed else 'No change applied'}

## Result
- {'✅ Improvement detected' if after_ms < before_ms else '❌ No improvement'}
""")
    diff_path = None
    if diff_text:
        diff_path = REPORTS_DIR / f"cpu-fix-{stage}-{ts}.patch"
        _write(diff_path, diff_text)
    return report_path, diff_path

# ---------- AST analysis ----------

class SelfCallFinder(ast.NodeVisitor):
    def __init__(self, func_name: str):
        self.func = func_name
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call):
        # find calls like func(...)
        if isinstance(node.func, ast.Name) and node.func.id == self.func:
            self.calls.append(node)
        self.generic_visit(node)

def _get_func_source_span(src: str, fn: ast.FunctionDef) -> tuple[int, int]:
    """Return byte offsets (start, end) of a FunctionDef using lineno/end_lineno."""
    lines = src.splitlines(keepends=True)
    start_idx = sum(len(l) for l in lines[: fn.lineno - 1])
    # end_lineno is available on 3.8+, but may be None if parsed differently
    end_line = getattr(fn, "end_lineno", None)
    if end_line is None:
        # crude fallback: find next top-level def/class or EOF
        for i in range(fn.lineno, len(lines)):
            if re.match(r"^(def |class |@)", lines[i]):
                end_line = i
                break
        if end_line is None:
            end_line = len(lines)
    end_idx = sum(len(l) for l in lines[: end_line])
    return start_idx, end_idx

def _detect_hotspot(src: str):
    """
    Return a dict describing the hottest recursive function we can optimize:
    - If Fibonacci-like (two self-calls with n-1 and n-2), return {"kind":"fib_like","name":..., "arg":"n", "span":(s,e)}
    - Else if any self-recursive, return {"kind":"recursive","name":..., "span":(s,e)}
    - Else None
    """
    tree = ast.parse(src)
    candidates = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            finder = SelfCallFinder(node.name)
            finder.visit(node)
            if not finder.calls:
                continue
            # try to detect fib-like: two calls with (var-1) and (var-2)
            arg_name = None
            has_m1 = has_m2 = False
            for call in finder.calls:
                if len(call.args) != 1:
                    continue
                a = call.args[0]
                # pattern: <name> - <const>
                if isinstance(a, ast.BinOp) and isinstance(a.op, ast.Sub) and isinstance(a.left, ast.Name) and isinstance(a.right, ast.Constant):
                    if isinstance(a.right.value, int):
                        if a.right.value == 1:
                            arg_name = a.left.id
                            has_m1 = True
                        elif a.right.value == 2:
                            arg_name = a.left.id
                            has_m2 = True
            s, e = _get_func_source_span(src, node)
            if has_m1 and has_m2 and arg_name:
                candidates.append({"score": 2, "kind": "fib_like", "name": node.name, "arg": arg_name, "span": (s, e)})
            else:
                # generic self-recursive
                candidates.append({"score": 1, "kind": "recursive", "name": node.name, "span": (s, e)})

    if not candidates:
        return None
    # pick the highest score (favor fib_like), earliest in file as tie-breaker
    candidates.sort(key=lambda d: (-d["score"], d["span"][0]))
    return candidates[0]

# ---------- Patch generators ----------

def _iterative_fib_impl(func_name: str, arg_name: str) -> str:
    return (
        f"def {func_name}({arg_name}: int) -> int:\n"
        f"    if {arg_name} <= 1:\n"
        f"        return {arg_name}\n"
        f"    a, b = 0, 1\n"
        f"    for _ in range(2, {arg_name} + 1):\n"
        f"        a, b = b, a + b\n"
        f"    return b\n"
    )

def _memoize_decorator_patch(src: str, func_name: str, span: tuple[int, int]) -> str:
    """Insert @lru_cache(maxsize=None) above the function and ensure import exists."""
    before, target, after = src[: span[0]], src[span[0] : span[1]], src[span[1] :]
    # add decorator if not already present
    if "@lru_cache" not in target:
        target = "@lru_cache(maxsize=None)\n" + target
    # ensure import exists
    if "from functools import lru_cache" not in before + after:
        before = "from functools import lru_cache\n" + before
    return before + target + after

def _apply_patch(src: str, hotspot) -> tuple[str, bool]:
    """
    Return (new_src, changed)
    - fib_like: replace function body with iterative implementation
    - recursive: add @lru_cache
    """
    if hotspot["kind"] == "fib_like":
        s, e = hotspot["span"]
        before, _, after = src[: s], src[s:e], src[e:]
        new_func = _iterative_fib_impl(hotspot["name"], hotspot["arg"])
        # keep surrounding newlines neat
        return (before + new_func + after, True)
    else:
        new_src = _memoize_decorator_patch(src, hotspot["name"], hotspot["span"])
        return (new_src, new_src != src)

# ---------- Public entry ----------

def run(stage: str):
    before_ms = _measure()
    print(f"[agent] Stage={stage} | Before={before_ms:.1f} ms")

    # In test: only proceed if slow; in prod: apply the same improvement anyway.
    if stage == "test" and before_ms <= THRESHOLD_MS:
        return {
            "stage": stage,
            "changed": False,
            "before_ms": before_ms,
            "after_ms": before_ms,
            "pytest_success": None,
            "diff_path": None,
            "report_path": None,
        }

    src_before = _read(TASK_FILE)
    hotspot = _detect_hotspot(src_before)

    if hotspot is None:
        print("[agent] No obvious recursive hotspot detected; exiting.")
        report_path, _ = _write_artifacts(stage, before_ms, before_ms, False, None)
        return {
            "stage": stage,
            "changed": False,
            "before_ms": before_ms,
            "after_ms": before_ms,
            "pytest_success": None,
            "diff_path": None,
            "report_path": str(report_path),
        }

    src_after, changed = _apply_patch(src_before, hotspot)
    diff_text = _unified_diff(src_before, src_after, "cpu_task.py") if changed else None

    if changed:
        _write(TASK_FILE, src_after)

    # Give the service a moment to reload
    time.sleep(1.0)

    # ---- Run automated pytest verification (only for test environment) ----
    pytest_success = None
    pytest_output = ""
    if stage == "test":
        print("[agent] Running pytest verification...")
        pytest_success, pytest_output = _run_pytests()
        print(pytest_output)
        # Save pytest output to a log file
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        with open(
            REPORTS_DIR / f"pytest-output-{stage}-{ts}.log",
            "w",
            encoding="utf-8",
        ) as f:
            f.write(pytest_output)

    # ---- Measure performance again ----
    after_ms = _measure()
    print(f"[agent] After={after_ms:.1f} ms")

    # ---- Write summary artifacts ----
    report_path, diff_path = _write_artifacts(
        stage, before_ms, after_ms, changed, diff_text
    )

    # ---- Send report via email only in production ----
    if stage == "prod":
        attachments = []
        if diff_path and Path(diff_path).exists():
            attachments.append(Path(diff_path))
        _send_email_with_report(stage, report_path, attachments)

    return {
        "stage": stage,
        "changed": changed,
        "before_ms": before_ms,
        "after_ms": after_ms,
        "pytest_success": pytest_success,
        "diff_path": str(diff_path) if diff_path else None,
        "report_path": str(report_path),
    }

