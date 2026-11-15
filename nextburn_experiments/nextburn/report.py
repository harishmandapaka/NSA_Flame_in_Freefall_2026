"""Shared helpers: result files, dashboard files, hashes and chart style."""
import datetime
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
DASH = os.path.join(ROOT, "dashboard_data")
COLORS = {"tested": "#2E7D32", "bounded": "#F9A825", "untested": "#C62828", "planned": "#6A1B9A",
          "pass": "#2E7D32", "fail": "#C62828", "info": "#546E7A", "accent": "#1F4E79", "muted": "#90A4AE"}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def exp_dir(n):
    d = os.path.join(RESULTS, "exp%d" % n)
    os.makedirs(d, exist_ok=True)
    return d


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, default=lambda o: round(o, 6) if isinstance(o, float) else str(o))
        fh.write("\n")


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def dashboard(name, obj):
    write_json(os.path.join(DASH, name), obj)


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as p
    p.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})
    return p
