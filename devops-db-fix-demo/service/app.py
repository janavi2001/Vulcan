import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, JSONResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from dotenv import load_dotenv
import db as dbmod

ENV_FILE = os.path.join(os.path.dirname(__file__), f".env.{os.getenv('ENVIRONMENT', 'test')}")
if os.path.exists(ENV_FILE):
    load_dotenv(ENV_FILE)

app = FastAPI()

REQUESTS_TOTAL = Counter("requests_total", "Total HTTP requests", ["path", "status"])
DB_CONN_ERRORS  = Counter("db_connection_errors_total", "DB connection errors", ["env"])

@app.get("/api/users")
def users():
    # Return value type: JSONResponse
    try:
        rows = dbmod.fetch_users()
        REQUESTS_TOTAL.labels(path="/api/users", status="200").inc()
        return JSONResponse([{"id": r[0], "name": r[1]} for r in rows])
    except Exception as e:
        DB_CONN_ERRORS.labels(env=os.getenv("ENVIRONMENT", "test")).inc()
        REQUESTS_TOTAL.labels(path="/api/users", status="500").inc()
        raise HTTPException(status_code=500, detail=f"DB connection failed: {e}")

@app.get("/metrics")
def metrics():
    # Return value type: Response
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
