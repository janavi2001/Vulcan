from fastapi import FastAPI
from fastapi.responses import JSONResponse
import pathlib, sys

app = FastAPI()

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "agent"))
import cpu_resolve  # noqa: E402

@app.post("/cpu/fix-test")
def cpu_fix_test():
    res = cpu_resolve.run("test")
    return JSONResponse({"ok": True, "stage": "test", "meta": res})

@app.post("/cpu/promote-prod")
def cpu_promote_prod():
    res = cpu_resolve.run("prod")
    return JSONResponse({"ok": True, "stage": "prod", "meta": res})
