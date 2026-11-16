"""NextBurn Coverage Console, live mode: serves index.html plus a small JSON API so the page can change settings and rerun the scripts.

Usage:
  python console/console_server.py                     then open http://127.0.0.1:8770
  python console/console_server.py --port 9000
  python console/console_server.py --host 0.0.0.0 --token SECRET    share on a network (a token is then required)

Standard library only. The server:
  * listens on this computer only unless --host is given, and then requires a token for every change;
  * runs only the actions listed in console/settings_schema.json (run_targets), one at a time;
  * accepts only the settings listed in the schema, checks each value's range and backs up the old file;
  * serves only result files (html, json, csv, md, txt, png, svg) from the project folder, never hidden folders or the console history.
"""
import argparse
import hmac
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import console_lib as L  # noqa: E402

APP = "nextburn-console"
VERSION = "1.0"
STATIC = {".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8", ".csv": "text/csv; charset=utf-8",
          ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml"}
BLOCKED = ("console/history",)
MAX_BODY = 64 * 1024
JOB_TIMEOUT_S = 3600
LOOPBACK = {"127.0.0.1", "localhost", "::1"}

JOBS = {}
JOBS_LOCK = threading.Lock()
STATE = {"running": None, "token": "", "allowed_hosts": None}


def _targets():
    return {t["id"]: t for t in L.schema().get("run_targets", [])}


def _run_job(job, target):
    logdir = os.path.join(L.HISTORY, "jobs")
    os.makedirs(logdir, exist_ok=True)
    logpath = os.path.join(logdir, job["id"] + ".log")
    job["log_path"] = os.path.relpath(logpath, L.ROOT)
    steps = [target["command"]] + list(target.get("then", []))
    if target["id"] != "tests":
        steps += [["-c", "import sys; sys.path.insert(0, '.'); from nextburn import dashboard; dashboard.build()"], ["console/build_console.py"]]
    t0 = time.time()
    try:
        with open(logpath, "w", encoding="utf-8") as log:
            for cmd in steps:
                log.write("$ python %s\n" % " ".join(cmd))
                log.flush()
                left = max(1, JOB_TIMEOUT_S - (time.time() - t0))
                try:
                    p = subprocess.run([sys.executable] + cmd, cwd=L.ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=left)
                    code = p.returncode
                except subprocess.TimeoutExpired:
                    log.write("Stopped: the job ran longer than %d s\n" % JOB_TIMEOUT_S)
                    code = -1
                job["steps"].append({"cmd": " ".join(cmd), "exit": code})
                log.write("(exit %d)\n" % code)
                log.flush()
                if code != 0:
                    break
        job["status"] = "ok" if all(s["exit"] == 0 for s in job["steps"]) else "failed"
    except Exception as e:  # noqa: BLE001 - report any failure to the page instead of dying silently
        job["status"] = "failed"
        job["error"] = str(e)
    job["finished_utc"] = L.now()
    job["seconds"] = round(time.time() - t0, 1)
    L._log(L.RUN_LOG, {k: job[k] for k in ("id", "target", "label", "status", "started_utc", "finished_utc", "seconds", "steps")})
    with JOBS_LOCK:
        STATE["running"] = None


def start_job(target_id, confirm=None):
    targets = _targets()
    t = targets.get(target_id)
    if not t:
        raise L.SettingsError("unknown action %r" % target_id)
    if t.get("confirm") and confirm != t["confirm"]:
        raise L.SettingsError("type %s to confirm this action" % t["confirm"])
    with JOBS_LOCK:
        if STATE["running"]:
            raise RuntimeError("another job is running (%s)" % STATE["running"])
        jid = time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + "_" + uuid.uuid4().hex[:6]
        job = {"id": jid, "target": t["id"], "label": t["label"], "status": "running", "started_utc": L.now(), "finished_utc": None, "seconds": None, "steps": []}
        JOBS[jid] = job
        STATE["running"] = jid
    threading.Thread(target=_run_job, args=(job, t), daemon=True).start()
    return job


def job_view(job):
    out = dict(job)
    lp = os.path.join(L.ROOT, job.get("log_path", "")) if job.get("log_path") else None
    if lp and os.path.isfile(lp):
        with open(lp, encoding="utf-8", errors="replace") as fh:
            out["log_tail"] = L.scrub(fh.read()[-6000:])
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "NextBurnConsole/" + VERSION
    sys_version = ""

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    # ---------------------------------------------------------------- helpers
    def _headers(self, code, ctype, length):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self._headers(code, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _host_ok(self):
        allowed = STATE["allowed_hosts"]
        return allowed is None or (self.headers.get("Host", "") in allowed)

    def _token_ok(self):
        tok = STATE["token"]
        return not tok or hmac.compare_digest(self.headers.get("X-NextBurn-Token", ""), tok)

    def _read_json(self):
        ctype = self.headers.get("Content-Type", "")
        if not ctype.lower().startswith("application/json"):
            raise L.SettingsError("send JSON (Content-Type: application/json)")
        origin = self.headers.get("Origin")
        if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get("Host", ""):
            raise PermissionError("requests from other web pages are refused")
        n = int(self.headers.get("Content-Length", "0") or 0)
        if n > MAX_BODY:
            raise L.SettingsError("request too large")
        raw = self.rfile.read(n) if n else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise L.SettingsError("send a JSON object")
        return data

    # ---------------------------------------------------------------- GET
    def do_GET(self):
        if not self._host_ok():
            return self.send_json(403, {"error": "host not allowed"})
        url = urllib.parse.urlsplit(self.path)
        p = url.path
        try:
            if p == "/api/health":
                return self.send_json(200, {"ok": True, "app": APP, "version": VERSION, "job_running": STATE["running"], "token_required": bool(STATE["token"])})
            if p == "/api/bundle":
                b, _ = L.bundle(images=False)
                return self.send_json(200, b)
            if p == "/api/settings":
                return self.send_json(200, L.scrub(L.current_settings()))
            if p == "/api/verify":
                return self.send_json(200, L.verify_fm2())
            if p == "/api/history":
                return self.send_json(200, L.scrub(L.history()))
            if p == "/api/jobs":
                with JOBS_LOCK:
                    jobs = sorted(JOBS.values(), key=lambda j: j["started_utc"], reverse=True)[:20]
                return self.send_json(200, {"jobs": jobs, "running": STATE["running"]})
            m = re.match(r"^/api/jobs/([\w\-]+)$", p)
            if m:
                job = JOBS.get(m.group(1))
                return self.send_json(200, job_view(job)) if job else self.send_json(404, {"error": "no such job"})
            if p.startswith("/api/"):
                return self.send_json(404, {"error": "unknown endpoint"})
            return self._static(p)
        except Exception as e:  # noqa: BLE001
            return self.send_json(500, {"error": str(e)})

    def _static(self, path):
        rel = urllib.parse.unquote(path).lstrip("/") or "index.html"
        norm = os.path.normpath(rel).replace(os.sep, "/")
        parts = norm.split("/")
        if norm.startswith("..") or os.path.isabs(norm) or any(x.startswith(".") for x in parts) or any(norm.startswith(b) for b in BLOCKED):
            return self.send_json(404, {"error": "not found"})
        full = os.path.join(L.ROOT, norm)
        ext = os.path.splitext(full)[1].lower()
        real_root = os.path.realpath(L.ROOT)
        if ext not in STATIC or not os.path.isfile(full) or not os.path.realpath(full).startswith(real_root + os.sep):
            return self.send_json(404, {"error": "not found"})
        with open(full, "rb") as fh:
            body = fh.read()
        self._headers(200, STATIC[ext], len(body))
        self.wfile.write(body)

    # ---------------------------------------------------------------- POST
    def do_POST(self):
        if not self._host_ok():
            return self.send_json(403, {"error": "host not allowed"})
        if not self._token_ok():
            return self.send_json(401, {"error": "a valid X-NextBurn-Token header is required"})
        p = urllib.parse.urlsplit(self.path).path
        try:
            data = self._read_json()
            if p == "/api/settings":
                rec = L.apply_changes(str(data.get("file", "")), data.get("changes"), source="console server")
                return self.send_json(200, L.scrub(rec))
            if p == "/api/restore":
                rec = L.restore_backup(str(data.get("backup", "")), source="console server")
                return self.send_json(200, rec)
            if p == "/api/run":
                return self.send_json(202, start_job(str(data.get("target", "")), data.get("confirm")))
            return self.send_json(404, {"error": "unknown endpoint"})
        except PermissionError as e:
            return self.send_json(403, {"error": str(e)})
        except L.SettingsError as e:
            return self.send_json(400, {"error": str(e)})
        except RuntimeError as e:
            return self.send_json(409, {"error": str(e)})
        except ValueError as e:
            return self.send_json(400, {"error": "bad request: %s" % e})
        except Exception as e:  # noqa: BLE001
            return self.send_json(500, {"error": str(e)})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--token", default=os.environ.get("NEXTBURN_TOKEN", ""), help="required for changes when set (also read from NEXTBURN_TOKEN)")
    ap.add_argument("--no-build", action="store_true", help="do not rebuild index.html at start")
    a = ap.parse_args(argv)
    if a.host not in LOOPBACK and not a.token:
        print("Refusing to listen on %s without --token: anyone on the network could change settings and run scripts." % a.host)
        return 2
    STATE["token"] = a.token
    STATE["allowed_hosts"] = {"%s:%d" % (h, a.port) for h in ("127.0.0.1", "localhost", "[::1]")} if a.host in LOOPBACK else None
    if not a.no_build or not os.path.exists(L.INDEX_PATH):
        info = L.write_index(images=True)
        print("Built %s (%d bytes)" % (info["index"], info["bytes"]))
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print("NextBurn Coverage Console: http://%s:%d  (Ctrl+C to stop)" % ("127.0.0.1" if a.host in LOOPBACK else a.host, a.port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
