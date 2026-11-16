"""Shared code for the NextBurn Coverage Console: settings paths, validation, the data bundle and the page build.

Standard library only, so the console works anywhere the experiments run.
"""
import base64
import csv
import datetime
import hashlib
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSOLE = os.path.join(ROOT, "console")
SCHEMA_PATH = os.path.join(CONSOLE, "settings_schema.json")
TEMPLATE_PATH = os.path.join(CONSOLE, "console_template.html")
INDEX_PATH = os.path.join(ROOT, "index.html")
DATA_PATH = os.path.join(CONSOLE, "console_data.json")
IMAGES = {"exp2": "results/exp2/chart.png", "exp3": "results/exp3/chart.png", "exp4": "results/exp4/chart.png", "exp5": "results/exp5/chart.png",
          "exp6": "results/exp6/chart.png", "exp7": "results/exp7/chart.png", "coverage_thin_fabric": "results/method/coverage_thin_fabric.png",
          "coverage_thick_plastic": "results/method/coverage_thick_plastic.png", "coverage_other_textile": "results/method/coverage_other_textile.png",
          "boundary": "results/method/boundary_thin_fabric_SIBAL.png", "next_tests": "results/method/next_tests.png", "fm2": "results/method/fm2_predictions.png"}
SEG = re.compile(r"^([A-Za-z_][\w]*)(?:\[(?:(\w+)=([\w\-.]+)|(\d+))\])?$")


class SettingsError(ValueError):
    pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def rel(*parts):
    return os.path.join(ROOT, *parts)


def load_json(relpath, default=None):
    p = rel(relpath)
    if not os.path.exists(p):
        return default
    with open(p) as fh:
        return json.load(fh)


def load_csv(relpath):
    p = rel(relpath)
    if not os.path.exists(p):
        return []
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


# ------------------------------------------------------------ settings paths
def _step(node, seg, create=False):
    m = SEG.match(seg)
    if not m:
        raise SettingsError("bad path segment: %s" % seg)
    name, key, val, idx = m.groups()
    if not isinstance(node, dict) or name not in node:
        raise SettingsError("no setting named %s" % name)
    node = node[name]
    if key is not None:
        hits = [x for x in node if isinstance(x, dict) and str(x.get(key)) == val] if isinstance(node, list) else []
        if len(hits) != 1:
            raise SettingsError("%s[%s=%s] matched %d items" % (name, key, val, len(hits)))
        node = hits[0]
    elif idx is not None:
        if not isinstance(node, list) or int(idx) >= len(node):
            raise SettingsError("%s[%s] is out of range" % (name, idx))
        node = node[int(idx)]
    return node


def _split(path):
    parts, buf, depth = [], "", 0
    for ch in path:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "." and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return parts


def get_path(obj, path):
    node = obj
    for seg in _split(path):
        node = _step(node, seg)
    return node


def set_path(obj, path, value):
    parts = _split(path)
    node = obj
    for seg in parts[:-1]:
        node = _step(node, seg)
    m = SEG.match(parts[-1])
    if not m:
        raise SettingsError("bad path segment: %s" % parts[-1])
    name, key, val, idx = m.groups()
    if key is not None:
        raise SettingsError("a setting path must end on a value, not a list item")
    if not isinstance(node, dict) or name not in node:
        raise SettingsError("no setting named %s" % name)
    if idx is not None:
        lst = node[name]
        if not isinstance(lst, list) or int(idx) >= len(lst):
            raise SettingsError("%s[%s] is out of range" % (name, idx))
        old = lst[int(idx)]
        lst[int(idx)] = value
    else:
        old = node[name]
        node[name] = value
    return old


def schema():
    with open(SCHEMA_PATH) as fh:
        return json.load(fh)


def field_index(sch=None):
    sch = sch or schema()
    out = {}
    for g in sch["groups"]:
        for f in g["fields"]:
            out[(g["file"], f["path"])] = dict(f, group=g["id"], frozen_input=g.get("frozen_input", False), affects=g.get("affects", []))
    return out


def coerce(field, value):
    t = field.get("type", "number")
    try:
        if t == "bool":
            if isinstance(value, bool):
                v = value
            elif str(value).lower() in ("true", "1", "yes"):
                v = True
            elif str(value).lower() in ("false", "0", "no"):
                v = False
            else:
                raise ValueError
        elif t == "int":
            v = int(value)
            if float(value) != v:
                raise ValueError
        else:
            v = float(value)
            if v != v or v in (float("inf"), float("-inf")):
                raise ValueError
    except (TypeError, ValueError):
        raise SettingsError("%s: '%s' is not a valid %s" % (field["label"], value, t))
    if t != "bool":
        if "min" in field and v < field["min"]:
            raise SettingsError("%s: %s is below the minimum %s" % (field["label"], v, field["min"]))
        if "max" in field and v > field["max"]:
            raise SettingsError("%s: %s is above the maximum %s" % (field["label"], v, field["max"]))
    return v


def current_settings():
    sch = schema()
    files = {}
    for g in sch["groups"]:
        if g["file"] not in files:
            files[g["file"]] = load_json(g["file"], {})
    values = {}
    for g in sch["groups"]:
        for f in g["fields"]:
            try:
                values["%s|%s" % (g["file"], f["path"])] = get_path(files[g["file"]], f["path"])
            except SettingsError:
                values["%s|%s" % (g["file"], f["path"])] = None
    return {"schema": sch, "files": files, "values": values}


# ------------------------------------------------------------ FM2 integrity
def verify_fm2():
    p = load_json("predictions/fm2_predictions.json")
    if not p:
        return {"present": False}
    sums = {}
    sp = rel("predictions", "SHA256SUMS.txt")
    if os.path.exists(sp):
        for line in open(sp):
            if line.strip():
                h, f = line.split()
                sums[f] = h
    inputs = [{"file": f, "unchanged": os.path.exists(rel(f)) and sha256_file(rel(f)) == h} for f, h in p.get("inputs_sha256", {}).items()]
    actual = sha256_file(rel("predictions", "fm2_predictions.json"))
    return {"present": True, "frozen_at_utc": p.get("frozen_at_utc"), "sha256": actual, "sums_match": sums.get("fm2_predictions.json") == actual,
            "inputs": inputs, "all_inputs_unchanged": all(i["unchanged"] for i in inputs)}


# ------------------------------------------------------------ data bundle
def _subset(d, keys):
    return {k: d[k] for k in keys if isinstance(d, dict) and k in d}


def bundle(images=True):
    e1, e1s = load_json("data/exp1_reported_score.json", {}), load_json("data/exp1_strict_score.json", {})
    step4 = load_json("results/method/step4_boundary.json", {})
    fits = {}
    for fam, f in (step4.get("fits") or {}).items():
        fits[fam] = dict(_subset(f, ("family", "observations", "sustained", "not_sustained", "materials", "samples", "acceptance", "max_rhat", "coefficients")),
                         loo=_subset(f.get("loo", {}), ("brier_loo", "accuracy_loo", "brier_in_sample", "base_rate", "rows")))
    b = {
        "meta": {"generated_at": now(), "project": "NextBurn Coverage Console", "tagline": "From evidence gap to test plan: fire-safety coverage for Moon and Mars habitats"},
        "summary": load_json("dashboard_data/summary.json", {}),
        "checklist": load_json("dashboard_data/method_checklist.json", {}),
        "step1": load_json("results/method/step1_summary.json", {}),
        "envelope": load_json("config/envelope.json", {}),
        "coverage": {"bins": load_csv("results/method/step3_coverage_bins.csv"), "families": (load_json("results/method/step3_coverage.json", {}) or {}).get("families", {})},
        "grid": load_json("dashboard_data/method_boundary_grid.json", {}),
        "boundary": dict(_subset(step4, ("model", "decline_rule", "primary_family", "reference_material", "grid_decline_share", "grid_decline_share_by_panel", "operating_points", "settings_frozen_at_utc")), fits=fits),
        "observations": load_csv("results/method/step4_model_observations.csv"),
        "plan": load_json("results/method/step5_next_tests.json", {}),
        "fm2": load_json("predictions/fm2_predictions.json", {}),
        "verify": verify_fm2(),
        "ledger": load_csv("results/method/step1_test_point_ledger.csv"),
        "exp": {"exp1": {"reported": _subset(e1, ("result", "final", "raw", "numbers_only", "provenance")), "strict": _subset(e1s, ("result", "final"))},
                "exp2": load_json("dashboard_data/exp2_checks.json", {}), "exp3": load_json("dashboard_data/exp3_coverage.json", {}),
                "exp4": load_json("dashboard_data/exp4_luci.json", {}), "exp5": load_json("dashboard_data/exp5_plan.json", {}),
                "exp6": load_json("dashboard_data/exp6_sim.json", {}), "exp7": load_json("dashboard_data/exp7_si.json", {})},
        "results_files": {"exp%d" % i: "results/exp%d/results.md" % i for i in range(2, 8)},
        "run_log": load_json("dashboard_data/run_log.json", {}),
        "settings": current_settings(),
        "image_paths": IMAGES,
    }
    b["results_files"].update({"method": "results/method/results.md", "checklist": "CHECKLIST.md", "readme": "README.md", "fm2": "predictions/fm2_predictions.md"})
    b = scrub(b)
    imgs = {}
    if images:
        for k, p in IMAGES.items():
            if os.path.exists(rel(p)):
                with open(rel(p), "rb") as fh:
                    imgs[k] = "data:image/png;base64," + base64.b64encode(fh.read()).decode("ascii")
    return b, imgs


def _embed(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")


def write_index(images=True):
    b, imgs = bundle(images)
    with open(TEMPLATE_PATH, encoding="utf-8") as fh:
        page = fh.read()
    if "/*__NB_DATA__*/" not in page or "/*__NB_IMAGES__*/" not in page:
        raise RuntimeError("console template is missing its data placeholders")
    page = page.replace("/*__NB_DATA__*/", _embed(b)).replace("/*__NB_IMAGES__*/", _embed(imgs))
    with open(INDEX_PATH, "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(DATA_PATH, "w", encoding="utf-8") as fh:
        json.dump(b, fh, separators=(",", ":"), ensure_ascii=False)
    return {"index": os.path.relpath(INDEX_PATH, ROOT), "bytes": os.path.getsize(INDEX_PATH), "images": len(imgs), "ledger_rows": len(b["ledger"])}


# ------------------------------------------------------------ privacy: no local paths in anything we publish
def scrub(obj):
    """Replace this computer's folder names with '.' so the page never shows local paths."""
    roots = sorted({ROOT, os.path.realpath(ROOT), os.path.expanduser("~")}, key=len, reverse=True)
    if isinstance(obj, str):
        for r in roots:
            if r and r != "/" and r in obj:
                obj = obj.replace(r, ".")
        return obj
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    return obj


# ------------------------------------------------------------ applying setting changes (shared by the server and apply_settings.py)
HISTORY = os.path.join(CONSOLE, "history")
BACKUPS = os.path.join(HISTORY, "backups")
CHANGE_LOG = os.path.join(HISTORY, "change_log.jsonl")
RUN_LOG = os.path.join(HISTORY, "runs.jsonl")
_SAFE_NAME = re.compile(r"^[\w.\-]+$")


def _indent_of(text):
    m = re.search(r"\n( +)\S", text)
    return len(m.group(1)) if m else 2


def _write_like(path, obj, original_text):
    out = json.dumps(obj, indent=_indent_of(original_text), ensure_ascii=False)
    if original_text.endswith("\n"):
        out += "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(out)
    os.replace(tmp, path)


def cross_checks(file, obj):
    errs = []
    if file == "config/boundary_model.json":
        lo, hi = obj.get("unknown_pressure_range_kpa", [0, 1])
        if not lo < hi:
            errs.append("Pressure not stated: the low end must be below the high end")
    if file == "config/facilities.json":
        for f in obj.get("facilities", []):
            a = f.get("atmosphere", {})
            if "p_min_kpa" in a and "p_max_kpa" in a and a["p_min_kpa"] > a["p_max_kpa"]:
                errs.append("%s: lowest pressure is above highest pressure" % f.get("name", f.get("id")))
    if file == "config/coverage.json":
        for k in ("o2_tolerances_pts", "p_tolerances_frac"):
            if len(set(obj.get(k, []))) != len(obj.get(k, [])):
                errs.append("%s: the tolerances must differ from each other" % k)
    return errs


def _log(path, rec):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _backup(file, text):
    os.makedirs(BACKUPS, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    name = "%s_%s" % (stamp, file.replace("/", "__"))
    with open(os.path.join(BACKUPS, name), "w", encoding="utf-8") as fh:
        fh.write(text)
    return name


def apply_changes(file, changes, source="console"):
    """Validate and apply [{path, value}] to one settings file. Returns a record; raises SettingsError on any problem (nothing is written then)."""
    sch = schema()
    files = {g["file"] for g in sch["groups"]}
    if file not in files:
        raise SettingsError("%s is not an editable settings file" % file)
    if not isinstance(changes, list) or not changes:
        raise SettingsError("no changes given")
    if len(changes) > 200:
        raise SettingsError("too many changes in one request")
    fi = field_index(sch)
    path = rel(file)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    obj = json.loads(text)
    done, groups = [], set()
    for c in changes:
        if not isinstance(c, dict) or "path" not in c:
            raise SettingsError("each change needs a path and a value")
        f = fi.get((file, c["path"]))
        if not f:
            raise SettingsError("%s is not an editable setting in %s" % (c["path"], file))
        val = coerce(f, c.get("value", c.get("new")))
        old = set_path(obj, c["path"], val)
        if old != val:
            done.append({"path": c["path"], "label": f["label"], "old": old, "new": val})
        groups.add(f["group"])
    errs = cross_checks(file, obj)
    if errs:
        raise SettingsError("; ".join(errs))
    if not done:
        return {"file": file, "changed": [], "backup": None, "suggested_runs": [], "frozen_input": False}
    backup = _backup(file, text)
    _write_like(path, obj, text)
    affects, frozen = [], False
    for g in sch["groups"]:
        if g["id"] in groups:
            frozen = frozen or bool(g.get("frozen_input"))
            for a in g.get("affects", []):
                if a not in affects:
                    affects.append(a)
    rec = {"time_utc": now(), "file": file, "changes": done, "backup": backup, "source": source, "frozen_input": frozen, "suggested_runs": affects}
    _log(CHANGE_LOG, rec)
    return dict(rec, changed=done)


def restore_backup(name, source="console"):
    if not _SAFE_NAME.match(name or "") or not os.path.isfile(os.path.join(BACKUPS, name)):
        raise SettingsError("no such backup")
    file = None
    for rec in read_jsonl(CHANGE_LOG, 100000):
        if rec.get("backup") == name:
            file = rec["file"]
    if file is None or file not in {g["file"] for g in schema()["groups"]}:
        raise SettingsError("the backup is not linked to an editable settings file")
    with open(os.path.join(BACKUPS, name), encoding="utf-8") as fh:
        old_text = fh.read()
    json.loads(old_text)
    with open(rel(file), encoding="utf-8") as fh:
        cur_text = fh.read()
    pre = _backup(file, cur_text)
    tmp = rel(file) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(old_text)
    os.replace(tmp, rel(file))
    rec = {"time_utc": now(), "file": file, "changes": [{"path": "(whole file)", "old": "current", "new": "backup " + name}], "backup": pre, "source": source, "restored_from": name}
    _log(CHANGE_LOG, rec)
    return rec


def read_jsonl(path, last=50):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out[-last:]


def history():
    return {"changes": read_jsonl(CHANGE_LOG), "runs": read_jsonl(RUN_LOG),
            "backups": sorted(os.listdir(BACKUPS))[-50:] if os.path.isdir(BACKUPS) else []}
