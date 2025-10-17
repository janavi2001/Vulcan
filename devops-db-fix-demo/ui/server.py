from flask import Flask, render_template, request, redirect, url_for
import json, os, subprocess, pathlib

app = Flask(__name__, template_folder="templates")

ROOT = pathlib.Path(__file__).resolve().parents[1]
ALERT_FILE = ROOT / "alerts" / "sample_alert.json"
AGENT = ROOT / "agent" / "resolve.py"

def run_agent(stage: str):
    env = os.environ.copy()
    env["AGENT_STAGE"] = stage
    completed = subprocess.run(["python", str(AGENT)], capture_output=True, text=True, env=env)
    stdout = completed.stdout
    start = stdout.find("===AGENT_JSON_START===")
    end   = stdout.find("===AGENT_JSON_END===")
    meta = {}
    if start != -1 and end != -1:
        meta = json.loads(stdout[start + len("===AGENT_JSON_START==="):end].strip())
    diff_text = ""
    if meta.get("diff_path"):
        diff_text = pathlib.Path(meta["diff_path"]).read_text(encoding="utf-8")
    return stdout, meta, diff_text

@app.route("/", methods=["GET"])
def index():
    payload = json.loads(ALERT_FILE.read_text(encoding="utf-8"))
    logs = request.args.get("logs") or ""
    diff  = request.args.get("diff") or ""
    meta  = json.loads(request.args.get("meta") or "{}")
    return render_template("index.html", payload=payload, logs=logs, diff=diff, meta=meta)

@app.route("/fix-test", methods=["POST"])
def fix_test():
    logs, meta, diff = run_agent("test")
    return redirect(url_for("index", logs=logs, diff=diff, meta=json.dumps(meta)))

@app.route("/promote-prod", methods=["POST"])
def promote_prod():
    logs, meta, diff = run_agent("prod")
    return redirect(url_for("index", logs=logs, diff=diff, meta=json.dumps(meta)))

if __name__ == "__main__":
    app.run(port=5050, debug=True)
