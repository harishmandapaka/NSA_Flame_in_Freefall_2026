#!/usr/bin/env python3
"""NextBurn setup: get a clone of this repository ready, rerun the experiments and refresh the dashboard.

Run it from a terminal. It works in the folder that holds this file:

    python3 setup_nextburn.py             macOS and Linux (or: sh setup.sh)
    py setup_nextburn.py                  Windows (or: setup.cmd)

Options:
    --serve            afterwards, start the live console at http://127.0.0.1:8770, where you can
                       change settings and rerun the scripts from the browser (Ctrl+C stops it)
    --pull             first get the latest version from GitHub (git pull --ff-only)
    --full             also rerun the full Experiment 6 simulation (the slow step)
    --no-run           install and check only; do not rerun the experiments (index.html is rebuilt)
    --no-venv          use the Python that runs this script instead of a private .venv folder
    --system-packages  let .venv use packages already installed on this computer (helps offline)
    --no-open          do not open the dashboard in a browser
    --port N           port for --serve (default 8770)

Steps: check Python, (pull), make .venv and install requirements.txt into it, run the regression
tests, rerun Experiments 2 to 7 and the six-step method (run_all.py, which ends by rebuilding
index.html), check the frozen FM2 predictions, show the results, then open the dashboard.
This script never re-freezes the FM2 predictions.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(ROOT, ".venv")
MIN_PY = (3, 9)
DEFAULT_PORT = 8770

# Runs inside the chosen Python: lists packages from requirements.txt that are missing or too old.
CHECK_PACKAGES = r"""
import json, re, sys
from importlib.metadata import version, PackageNotFoundError
def key(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])
problems = []
for name, low in json.loads(sys.argv[1]):
    try:
        v = version(name)
    except PackageNotFoundError:
        problems.append("%s (not installed)" % name)
        continue
    if low and key(v) < key(low):
        problems.append("%s %s (needs %s or later)" % (name, v, low))
print(json.dumps(problems))
"""


class Stop(Exception):
    """A step failed. The message says what to do next."""


def say(msg=""):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "ascii"
        print(msg.encode(enc, "replace").decode(enc), flush=True)


def child_env():
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"              # read and write text files as UTF-8 on every platform
    env.setdefault("MPLBACKEND", "Agg")  # charts are written to files; no window is needed
    return env


def shown(cmd):
    parts = []
    for c in cmd:
        if os.path.isabs(c) and c.startswith(ROOT + os.sep):
            c = os.path.relpath(c, ROOT)
        parts.append('"%s"' % c if " " in c else c)
    return " ".join(parts)


def run(cmd, what, fatal=True):
    say("    > " + shown(cmd))
    rc = subprocess.call(cmd, cwd=ROOT, env=child_env())
    if rc != 0 and fatal:
        raise Stop("%s failed (exit code %d). See the lines above." % (what, rc))
    return rc


# ---------------------------------------------------------------- steps
def pull():
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        say("    This folder is not a git clone, so there is nothing to pull. Skipping this step.")
        return
    git = shutil.which("git")
    if not git:
        say("    git is not installed. Skipping this step.")
        return
    rc = subprocess.call([git, "pull", "--ff-only"], cwd=ROOT)
    if rc != 0:
        raise Stop("git pull did not finish.\n"
                   "    If files changed on this computer are in the way, keep them with 'git stash'\n"
                   "    or drop them with 'git checkout -- .', then run this script again.")


def venv_python():
    if os.name == "nt":
        return os.path.join(VENV, "Scripts", "python.exe")
    return os.path.join(VENV, "bin", "python")


def choose_python(a):
    if a.no_venv:
        say("    Using this Python (--no-venv): %s" % sys.executable)
        return sys.executable
    active = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    if active and os.path.realpath(sys.prefix) != os.path.realpath(VENV):
        say("    Using the virtual environment that is already active: %s" % sys.prefix)
        return sys.executable
    py = venv_python()
    if os.path.exists(py):
        say("    Using the private environment in .venv (made earlier).")
        return py
    say("    Making a private Python environment in .venv (this keeps your other Python projects untouched).")
    cmd = [sys.executable, "-m", "venv", VENV] + (["--system-site-packages"] if a.system_packages else [])
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0 or not os.path.exists(py):
        shutil.rmtree(VENV, ignore_errors=True)
        raise Stop("Could not make the private environment (.venv).\n"
                   "    On Debian or Ubuntu, install it with: sudo apt install python3-venv\n"
                   "    Or run this script again with --no-venv to use this Python as it is.")
    return py


def requirements():
    reqs = []
    with open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            name, _, low = line.partition(">=")
            reqs.append([name.strip(), low.strip() or None])
    return reqs


def package_problems(py, reqs):
    try:
        out = subprocess.run([py, "-c", CHECK_PACKAGES, json.dumps(reqs)], cwd=ROOT, env=child_env(),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        return json.loads(out.stdout.strip().splitlines()[-1]) if out.returncode == 0 else [r[0] for r in reqs]
    except (OSError, ValueError, IndexError):
        return [r[0] for r in reqs]


def ensure_packages(py, a):
    reqs = requirements()
    names = ", ".join(r[0] for r in reqs)
    problems = package_problems(py, reqs)
    if not problems:
        say("    Already installed: %s." % names)
        return
    say("    To install: %s" % "; ".join(problems))
    rc = run([py, "-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt"], "Installing the packages", fatal=False)
    if rc != 0:
        raise Stop("Installing the packages failed.\n"
                   "    Check the internet connection and run this script again.\n"
                   "    With --no-venv, pip may refuse to change this Python ('externally managed'): run again without --no-venv.")
    problems = package_problems(py, reqs)
    if problems:
        raise Stop("Still missing after the install: %s" % "; ".join(problems))


def check_page():
    node = shutil.which("node")
    if not node:
        say("    Node.js is not installed, so the page check is skipped (it is optional).")
        return
    try:
        p = subprocess.run([node, os.path.join("console", "test_render.js")], cwd=ROOT, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True, encoding="utf-8", errors="replace")
    except OSError:
        say("    Node.js could not run the page check; skipped.")
        return
    lines = [l for l in p.stdout.splitlines() if l.strip()]
    passed = sum(1 for l in lines if l.startswith("PASS "))
    failed = [l for l in lines if l.startswith("FAIL ")]
    say("    Page check: %d passed, %d failed." % (passed, len(failed)))
    for l in failed[:10]:
        say("      " + l[:200])


def check_fm2():
    sys.path.insert(0, os.path.join(ROOT, "console"))
    import console_lib  # standard library only
    v = console_lib.verify_fm2()
    if not v.get("present"):
        say("    No FM2 predictions file found.")
        return True
    say("    FM2 predictions frozen at %s" % v["frozen_at_utc"])
    say("    SHA-256 %s" % v["sha256"])
    say("    Matches predictions/SHA256SUMS.txt: %s" % ("yes" if v["sums_match"] else "NO - the predictions file was changed"))
    changed = [i["file"] for i in v["inputs"] if not i["unchanged"]]
    say("    Frozen inputs unchanged: %d of %d" % (len(v["inputs"]) - len(changed), len(v["inputs"])))
    for f in changed:
        say("      changed since the freeze: %s (new results differ from the frozen run; the predictions stay frozen)" % f)
    return bool(v["sums_match"])


def show_results():
    try:
        with open(os.path.join(ROOT, "dashboard_data", "summary.json"), encoding="utf-8") as fh:
            s = json.load(fh)
    except (OSError, ValueError):
        say("    No summary yet.")
        return
    say("    Experiments:")
    for e in s.get("experiments", []):
        say("      %s. %-44s %s" % (e.get("id"), str(e.get("title", ""))[:44], e.get("status", "")))
    say("    Six-step method:")
    for m in s.get("method_steps", []):
        say("      Step %s. %-28s %s" % (m.get("step"), str(m.get("requirement", ""))[:28], m.get("status", "")))


def git_changed_files():
    git = shutil.which("git")
    if not git or not os.path.isdir(os.path.join(ROOT, ".git")):
        return None
    try:
        out = subprocess.run([git, "status", "--porcelain"], cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, universal_newlines=True).stdout
    except OSError:
        return None
    return [l[3:] for l in out.splitlines() if l.strip()]


def gui_available():
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def serve(py, port, open_browser):
    url = "http://127.0.0.1:%d/" % port
    say("\nLive console: %s   (press Ctrl+C to stop)" % url)
    if open_browser and gui_available():
        threading.Timer(2.0, webbrowser.open, args=(url,)).start()
    try:
        rc = subprocess.call([py, os.path.join("console", "console_server.py"), "--no-build", "--port", str(port)],
                             cwd=ROOT, env=child_env())
    except KeyboardInterrupt:
        return 0
    if rc != 0:
        say("The console server stopped (exit code %d). If the port is in use, try --port %d." % (rc, port + 1))
    return rc


# ---------------------------------------------------------------- main
def parse_args(argv):
    ap = argparse.ArgumentParser(description="NextBurn setup: install, rerun the experiments and refresh index.html.",
                                 epilog="Run 'python3 setup_nextburn.py' with no options for the usual setup.")
    ap.add_argument("--serve", action="store_true", help="start the live console afterwards (change settings and rerun from the browser)")
    ap.add_argument("--pull", action="store_true", help="first get the latest version from GitHub (git pull --ff-only)")
    ap.add_argument("--full", action="store_true", help="also rerun the full Experiment 6 simulation (slow)")
    ap.add_argument("--no-run", action="store_true", help="install and check only; do not rerun the experiments")
    ap.add_argument("--no-venv", action="store_true", help="use this Python instead of a private .venv folder")
    ap.add_argument("--system-packages", action="store_true", help="let .venv use packages already installed on this computer")
    ap.add_argument("--no-open", action="store_true", help="do not open the dashboard in a browser")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="port for --serve (default %d)" % DEFAULT_PORT)
    return ap.parse_args(argv)


def main(argv=None):
    if sys.version_info < MIN_PY:
        say("NextBurn needs Python %d.%d or later; this is Python %d.%d." % (MIN_PY[0], MIN_PY[1], sys.version_info[0], sys.version_info[1]))
        say("Get it from https://www.python.org/downloads/ and run this script again.")
        return 1
    a = parse_args(argv)
    total = 6 + (1 if a.pull else 0)
    count = [0]

    def step(title):
        count[0] += 1
        say("\n[%d/%d] %s" % (count[0], total, title))

    say("NextBurn setup in %s" % ROOT)
    t0 = time.time()
    try:
        if a.pull:
            step("Getting the latest version from GitHub")
            pull()
        step("Choosing the Python environment")
        py = choose_python(a)
        step("Checking the Python packages (requirements.txt)")
        ensure_packages(py, a)
        step("Running the regression tests")
        run([py, os.path.join("tests", "run_tests.py")], "The regression tests")
        if a.no_run:
            step("Rebuilding the dashboard (index.html) from the current results")
            run([py, os.path.join("console", "build_console.py")], "Building index.html")
        else:
            step("Rerunning Experiments 2 to 7 and the six-step method, then rebuilding index.html" +
                 (" (with the full simulation)" if a.full else " (about two minutes)"))
            run([py, "run_all.py"] + ([] if a.full else ["--skip-sim"]), "Rerunning the experiments")
        step("Checking the page and the frozen FM2 predictions")
        check_page()
        fm2_ok = check_fm2()
        step("Results")
        show_results()
    except Stop as e:
        say("\nSTOPPED: %s" % e)
        return 1
    except KeyboardInterrupt:
        say("\nStopped.")
        return 130

    index = os.path.join(ROOT, "index.html")
    say("\nDone in %.1f minutes." % ((time.time() - t0) / 60))
    say("  Dashboard: %s" % index)
    changed = git_changed_files()
    if changed is not None:
        say("  Files that differ from your last commit: %d (see: git status, git diff --stat)." % len(changed))
    say("  To try a change: edit a file in config/ (or run with --serve to edit from the browser), then run this script again.")
    say("  To put the published results back: git checkout -- .")
    if not fm2_ok:
        say("\nWARNING: predictions/fm2_predictions.json no longer matches its published SHA-256.")
    if a.serve:
        serve(py, a.port, not a.no_open)
    elif not a.no_open and gui_available():
        try:
            webbrowser.open(Path(index).resolve().as_uri())
        except Exception:  # noqa: BLE001 - opening a browser is a convenience only
            pass
    return 0 if fm2_ok else 1


if __name__ == "__main__":
    sys.exit(main())
