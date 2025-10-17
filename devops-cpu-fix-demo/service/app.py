import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from dotenv import load_dotenv
from cpu_task import busy_cpu_task

ENV_FILE = os.path.join(os.path.dirname(__file__), f".env.{os.getenv('ENVIRONMENT', 'test')}")
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE)

app = FastAPI()
ENV = os.getenv("ENVIRONMENT", "test")
TASK_MS = Gauge("task_elapsed_ms", "Elapsed time per request", ["env"])

@app.get("/api/heavy")
def heavy():
    result = busy_cpu_task()
    TASK_MS.labels(env=ENV).set(result["elapsed_ms"])
    return JSONResponse({"env": ENV, **result})

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
