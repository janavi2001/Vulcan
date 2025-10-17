import os, re, time, json, difflib, requests
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = ROOT / "service"
ENV_TEST = SERVICE_DIR / ".env.test"
ENV_PROD = SERVICE_DIR / ".env.prod"
REPORTS_DIR = Path(__file__).resolve().parent / "knowledge"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

APP_USERS_URL = "http://127.0.0.1:8000/api/users"
METRICS_URL = "http://127.0.0.1:8000/metrics"


def _read(p: Path) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def _write(p: Path, s: str) -> None:
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def _service_up() -> bool:
    try:
        return requests.get(METRICS_URL, timeout=1.5).status_code == 200
    except Exception:
        return False


def _endpoint_ok() -> bool:
    try:
        r = requests.get(APP_USERS_URL, timeout=2.0)
        return r.status_code == 200 and isinstance(r.json(), list)
    except Exception:
        return False


def _failure_text() -> str:
    try:
        r = requests.get(APP_USERS_URL, timeout=2.0)
        return "" if r.status_code == 200 else r.text
    except Exception as e:
        return str(e)


def _patch_env_host(src: str) -> str:
    pattern = r"(?m)^DB_HOST\s*=\s*.*$"
    if re.search(pattern, src):
        return re.sub(pattern, "DB_HOST=postgres", src)
    return src


def _write_report(stage: str, before_err: str, after_ok: bool) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = REPORTS_DIR / f"case-db-conn-{stage}-{ts}.md"
    _write(
        path,
        f"""# Auto-Resolution Report — {stage.upper()}

**Timestamp (UTC):** {datetime.utcnow().isoformat()}
**Alert:** DBConnectionErrorsHigh
**Stage:** {stage}

## Failure Signature

{before_err.strip()[:400]}


## Action Taken
- Patched `.env.{stage}` → `DB_HOST=postgres`.

## Verification
- `/api/users` OK after fix: {after_ok}
""",
    )
    return path


def _write_diff(stage: str, before: str, after: str, filename: str) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    diff_path = REPORTS_DIR / f"patch-{stage}-{ts}.patch"
    diff = difflib.unified_diff(
        before.splitlines(True),
        after.splitlines(True),
        fromfile=f"{filename} (before)",
        tofile=f"{filename} (after)",
    )
    _write(diff_path, "".join(diff))
    return diff_path


def main() -> None:
    if not _service_up():
        print("[agent] Service not responding at /metrics. Start it before running the agent.")
        return

    stage = os.getenv("AGENT_STAGE", "test")
    target_env = ENV_TEST if stage == "test" else ENV_PROD

    before_err = _failure_text()
    looks_like_conn = (
    "could not connect" in before_err.lower()
    or "connection refused" in before_err.lower()
    or "could not translate host name" in before_err.lower()
    )

    if not looks_like_conn:
        print("[agent] No DB-connection signature detected; nothing to do.")
        return

    before_txt = _read(target_env)
    after_txt = _patch_env_host(before_txt)
    changed = before_txt != after_txt
    if changed:
        _write(target_env, after_txt)

    time.sleep(1.0)
    ok = _endpoint_ok()

    report_path = _write_report(stage, before_err, ok)
    diff_path = _write_diff(stage, before_txt, after_txt, f".env.{stage}") if changed else None

    payload = {
        "stage": stage,
        "changed": changed,
        "ok": ok,
        "report_path": str(report_path),
        "diff_path": str(diff_path) if diff_path else None,
    }

    print("\n===AGENT_JSON_START===")
    print(json.dumps(payload))
    print("===AGENT_JSON_END===\n")


if __name__ == "__main__":
    main()
