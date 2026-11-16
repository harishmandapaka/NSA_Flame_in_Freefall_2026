"""Self-test for the live console: copies the project to a temporary folder, starts the server there and checks the API.

Usage: python console/selftest_server.py [--with-jobs]
Nothing in this folder is changed; all writes happen in the temporary copy, which is deleted at the end.
"""
import argparse
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def req(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    h = {"Host": "127.0.0.1:%d" % port}
    h.update(headers or {})
    data = None
    if body is not None:
        data = body if isinstance(body, (bytes, str)) else json.dumps(body)
        h.setdefault("Content-Type", "application/json")
    c.request(method, path, body=data, headers=h)
    r = c.getresponse()
    raw = r.read()
    c.close()
    try:
        return r.status, json.loads(raw.decode("utf-8"))
    except ValueError:
        return r.status, raw


def wait_job(port, jid, limit=900):
    t0 = time.time()
    while time.time() - t0 < limit:
        s, j = req(port, "GET", "/api/jobs/" + jid)
        if j.get("status") != "running":
            return j
        time.sleep(1)
    return {"status": "timeout"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-jobs", action="store_true", help="also run the regression tests and Experiment 3 through the server")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix="nextburn_selftest_")
    copy = os.path.join(tmp, "nextburn")
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", "history", "__pycache__", "*.zip"))
    port = free_port()
    srv = subprocess.Popen([sys.executable, "console/console_server.py", "--port", str(port), "--no-build"], cwd=copy, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(50):
            try:
                s, h = req(port, "GET", "/api/health")
                break
            except OSError:
                time.sleep(0.2)
        check(s == 200 and h.get("app") == "nextburn-console", "health answers")
        s, b = req(port, "GET", "/")
        check(s == 200 and isinstance(b, bytes) and b"NextBurn Coverage Console" in b, "index.html is served")
        s, b = req(port, "GET", "/api/bundle")
        check(s == 200 and len(b.get("ledger", [])) > 0, "bundle has the ledger")
        check(ROOT not in json.dumps(b) and copy not in json.dumps(b), "bundle has no local folder paths")
        for p in ("/.git/config", "/console/history/change_log.jsonl", "/../../etc/passwd", "/nextburn/boundary.py", "/%2e%2e/%2e%2e/etc/passwd"):
            s, _ = req(port, "GET", p)
            check(s == 404, "refuses %s (%d)" % (p, s))
        s, _ = req(port, "GET", "/results/exp2/chart.png")
        check(s == 200, "serves result charts")
        s, _ = req(port, "GET", "/api/health", headers={"Host": "evil.example:%d" % port})
        check(s == 403, "refuses a foreign Host header")
        s, r = req(port, "POST", "/api/run", body='{"target":"tests"}', headers={"Content-Type": "text/plain"})
        check(s == 400, "refuses a non-JSON post")
        s, r = req(port, "POST", "/api/run", body={"target": "tests"}, headers={"Origin": "https://evil.example"})
        check(s == 403, "refuses a post from another web page")
        s, r = req(port, "POST", "/api/run", body={"target": "rm -rf /"})
        check(s == 400, "refuses an unknown action")
        s, r = req(port, "POST", "/api/run", body={"target": "refreeze"})
        check(s == 400 and "REFREEZE" in r.get("error", ""), "re-freeze needs the confirmation word")
        s, r = req(port, "POST", "/api/settings", body={"file": "config/weights.json", "changes": [{"path": "oxygen_exponent", "value": -1}]})
        check(s == 400, "refuses a value below its minimum")
        s, r = req(port, "POST", "/api/settings", body={"file": "config/test_outcomes.json", "changes": [{"path": "version", "value": 2}]})
        check(s == 400, "refuses a file that is not editable")
        s, r = req(port, "POST", "/api/settings", body={"file": "config/weights.json", "changes": [{"path": "__class__", "value": 1}]})
        check(s == 400, "refuses a setting that is not in the schema")
        s, r = req(port, "POST", "/api/settings", body={"file": "config/boundary_model.json", "changes": [{"path": "unknown_pressure_range_kpa[0]", "value": 110}]})
        check(s == 400, "cross-check: low end above high end refused")
        before = open(os.path.join(copy, "config", "coverage.json")).read()
        s, r = req(port, "POST", "/api/settings", body={"file": "config/coverage.json", "changes": [{"path": "default_o2_pts", "value": 4}]})
        now = json.load(open(os.path.join(copy, "config", "coverage.json")))
        check(s == 200 and now["default_o2_pts"] == 4 and r.get("backup"), "valid change saved with a backup")
        check(r.get("suggested_runs") == ["exp3"], "suggests rerunning Experiment 3")
        cov_backup = r.get("backup")
        s, r = req(port, "POST", "/api/settings", body={"file": "config/boundary_model.json", "changes": [{"path": "decline.support_max_distance", "value": 1.5}]})
        check(s == 200 and r.get("frozen_input") is True, "boundary model change is flagged as a frozen FM2 input")
        s, v = req(port, "GET", "/api/verify")
        check(v.get("sums_match") is True and v.get("all_inputs_unchanged") is False, "integrity check shows the changed input and the untouched predictions")
        s, r = req(port, "POST", "/api/restore", body={"backup": r.get("backup")})
        s, v = req(port, "GET", "/api/verify")
        check(s == 200 and v.get("all_inputs_unchanged") is True, "restore brings the frozen input back byte for byte")
        s, r = req(port, "POST", "/api/restore", body={"backup": "../../etc/passwd"})
        check(s == 400, "refuses a backup name outside the backup folder")
        s, h = req(port, "GET", "/api/history")
        check(len(h.get("changes", [])) == 3, "history lists the three changes")
        if a.with_jobs:
            s, j = req(port, "POST", "/api/run", body={"target": "tests"})
            check(s == 202, "starts the regression tests")
            s2, _ = req(port, "POST", "/api/run", body={"target": "exp2"})
            check(s2 == 409, "a second job is refused while one runs")
            j = wait_job(port, j["id"])
            check(j.get("status") == "ok", "regression tests pass through the server")
            mtime = os.path.getmtime(os.path.join(copy, "index.html"))
            s, j = req(port, "POST", "/api/run", body={"target": "exp3"})
            j = wait_job(port, j["id"])
            check(j.get("status") == "ok" and os.path.getmtime(os.path.join(copy, "index.html")) > mtime, "Experiment 3 reruns and index.html is rebuilt")
            res = json.load(open(os.path.join(copy, "dashboard_data", "exp3_coverage.json")))
            check(res.get("headline", {}).get("holds_in_all_runs") is True, "Experiment 3 result after the change: Moon-base gap still holds")
        s, r = req(port, "POST", "/api/restore", body={"backup": cov_backup})
        check(open(os.path.join(copy, "config", "coverage.json")).read() == before, "coverage settings restored")
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=10)
        except subprocess.TimeoutExpired:
            srv.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%s" % ("All live-console checks passed" if not FAILS else "%d check(s) failed" % len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
