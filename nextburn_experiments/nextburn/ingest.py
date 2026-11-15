"""Load the evidence ledger and turn its text fields into numbers.

Every parsed number keeps a pointer to its ledger row, so each value on the
dashboard still traces to a source and a locator. Nothing here invents a
value: a field the source does not state stays empty.
"""
import csv
import glob
import json
import math
import os
import re

from . import units

ROOT = units.ROOT
DATA = os.path.join(ROOT, "data")
CONFIG = os.path.join(ROOT, "config")
DEFAULT_LEDGER = os.path.join(DATA, "ledger_v2.json")
NUM = r"(?<![\d.])-?\d+(?:\.\d+)?"


def load_json(name):
    return json.load(open(os.path.join(CONFIG, name)))


PRESETS = load_json("presets.json")
SOURCES_META = load_json("sources_meta.json")


def load_ledger(path=DEFAULT_LEDGER):
    rows = json.load(open(path))
    return rows if isinstance(rows, list) else rows["rows"]


def _nums(text):
    return [float(x) for x in re.findall(NUM, text or "")]


def _stated(text):
    t = (text or "").strip().lower()
    return bool(t) and t not in {"not stated", "n/a", "-", "none"}


# ---------------------------------------------------------------- pressure
def parse_pressure(text):
    """Return value_kpa, lo_kpa, hi_kpa and kind for a pressure field."""
    out = {"value_kpa": None, "lo_kpa": None, "hi_kpa": None, "kind": "not_stated", "text": text}
    if not _stated(text):
        return out
    t = text.lower()
    if "normal pressure" in t or t.strip() in {"1 atm", "ambient"}:
        out.update(value_kpa=units.KPA_PER_ATM, lo_kpa=units.KPA_PER_ATM, hi_kpa=units.KPA_PER_ATM, kind="nominal")
        return out
    unit = "kpa" if "kpa" in t else "psia" if "psi" in t else "atm" if "atm" in t else None
    nums = _nums(t)
    if unit is None or not nums:
        out["kind"] = "unparsed"
        return out
    vals = [units.to_kpa(x, unit) for x in nums]
    if unit == "kpa" and "psi" in t:  # e.g. "27.6 kPa (4.0 psia)": use the first (kPa) value
        vals = vals[:1]
    if "above" in t or "more than" in t:
        out.update(lo_kpa=vals[0], kind="lower_bound")
    elif "below" in t or "less than" in t:
        out.update(hi_kpa=vals[0], kind="upper_bound")
    elif len(vals) >= 2 and re.search(NUM + r"\s*(?:-|to|–)\s*" + NUM, t):
        out.update(lo_kpa=min(vals[:2]), hi_kpa=max(vals[:2]), value_kpa=sum(vals[:2]) / 2, kind="range")
    else:
        out.update(value_kpa=vals[0], lo_kpa=vals[0], hi_kpa=vals[0], kind="exact")
    return out


# ---------------------------------------------------------------- oxygen
def parse_oxygen(text):
    out = {"value_pct": None, "lo_pct": None, "hi_pct": None, "kind": "not_stated", "text": text}
    if not _stated(text):
        return out
    t = text.lower()
    if t.strip() in {"varied", "various"}:
        out["kind"] = "varied"
        return out
    nums = _nums(t)
    if not nums:
        if "air" in t:
            a = units.AIR_O2_PCT
            out.update(value_pct=a, lo_pct=a, hi_pct=a, kind="air")
        else:
            out["kind"] = "unparsed"
        return out
    if "falling to" in t or "decreas" in t:
        out.update(value_pct=nums[0], lo_pct=min(nums), hi_pct=max(nums), kind="falling")
    elif "and below" in t or "or less" in t:
        out.update(hi_pct=nums[0], kind="upper_bound")
    elif len(nums) >= 2 and re.search(NUM + r"\s*%?\s*(?:-|to|–)\s*" + NUM, t):
        out.update(value_pct=(nums[0] + nums[1]) / 2, lo_pct=min(nums[:2]), hi_pct=max(nums[:2]), kind="range")
    else:
        out.update(value_pct=nums[0], lo_pct=nums[0], hi_pct=nums[0], kind="approx" if "~" in t else "exact")
    return out


# ---------------------------------------------------------------- flow
def parse_flow(text):
    out = {"value_cm_s": None, "lo_cm_s": None, "hi_cm_s": None, "kind": "not_stated", "text": text}
    if not _stated(text):
        return out
    t = text.lower()
    nums = _nums(t)
    if not nums:
        out["kind"] = "varied" if ("varied" in t or "reduced" in t) else "unparsed"
        return out
    unit = "mm/s" if "mm/s" in t else "cm/s"
    vals = [units.speed_to_cm_s(x, unit) for x in nums if not re.search(re.escape(str(x)) + r"\s*s\b", t)]
    vals = [units.speed_to_cm_s(float(x), unit) for x in re.findall(NUM + r"(?=\s*(?:to\s*" + NUM + r"\s*)?(?:cm|mm)/s)", t)] or vals
    if "up to" in t:
        out.update(lo_cm_s=0.0, hi_cm_s=vals[0], kind="range")
    elif re.search(NUM + r"\s*(?:to|-|–)\s*" + NUM + r"\s*(?:cm|mm)/s", t):
        a, b = [units.speed_to_cm_s(float(x), unit) for x in re.search("(" + NUM + r")\s*(?:to|-|–)\s*(" + NUM + r")\s*(?:cm|mm)/s", t).groups()]
        out.update(lo_cm_s=min(a, b), hi_cm_s=max(a, b), value_cm_s=(a + b) / 2, kind="range")
    elif "reduced to" in t:
        lo = 0.0 if "fan off" in t else min(vals)
        out.update(value_cm_s=vals[0], lo_cm_s=lo, hi_cm_s=max(vals), kind="schedule")
    else:
        out.update(value_cm_s=vals[0], lo_cm_s=vals[0], hi_cm_s=vals[0], kind="exact")
    return out


# ---------------------------------------------------------------- gravity
def luci_spin_g(rows):
    """LUCI spin gravity computed from the ledger's own rotation-rate and radius rows."""
    rpm = radius = None
    for r in rows:
        m = r.get("measurement", "").lower()
        if r.get("source_id") == "luci_2025" and m == "vehicle rotation rate":
            rpm = float(r["value"])
        if r.get("source_id") == "luci_2025" and m.startswith("effective radius"):
            radius = float(r["value"])
    if rpm is None or radius is None:
        return units.G_LUNAR, None
    return units.g_from_spin(rpm, radius), {"rpm": rpm, "radius_m": radius}


def parse_gravity(text, g_spin):
    t = (text or "").lower()
    if "computed" in t:
        return {"levels": [0.0], "kind": "model"}
    if " vs " in t:
        lv = []
        if "micro" in t:
            lv.append(0.0)
        if "lunar" in t:
            lv.append(g_spin)
        if "1 g" in t:
            lv.append(1.0)
        return {"levels": lv, "kind": "comparison"}
    if "micro" in t or "zero" in t:
        return {"levels": [0.0], "kind": "single"}
    if "lunar" in t:
        if "spin" in t:
            return {"levels": [g_spin], "kind": "single"}
        return {"levels": [units.G_LUNAR], "kind": "single"}
    nums = _nums(t)
    if len(nums) > 1:
        return {"levels": nums, "kind": "multi"}
    if nums:
        return {"levels": nums, "kind": "single"}
    return {"levels": [], "kind": "unparsed"}


def g_class(g):
    for name, (lo, hi) in PRESETS["gravity_classes"].items():
        if lo <= g < hi or (name == "earth" and abs(g - hi) < 1e-9):
            return name
    return "other"


# ---------------------------------------------------------------- material and direction
def families_of(text):
    t = (text or "").lower()
    fam = [k for k, v in PRESETS["material_families"].items() if any(w in t for w in v["keywords"])]
    return fam


def direction_class(text):
    t = (text or "").lower()
    if "stagnation" in t:
        return "other"
    for k, v in PRESETS["direction_classes"].items():
        if any(w in t for w in v["keywords"]):
            return k
    return "unknown"


def parse_thickness_mm(geometry):
    t = (geometry or "").lower()
    m = re.search("(" + NUM + r")\s*(?:to\s*(" + NUM + r")\s*)?mm thick", t)
    if m:
        a = float(m.group(1)); b = float(m.group(2)) if m.group(2) else a
        return min(a, b), max(a, b)
    return None


def parse_value(text):
    t = (text or "").strip()
    if re.fullmatch(NUM, t):
        return float(t), None, None
    m = re.fullmatch("(" + NUM + r")\s*(?:-|to|–)\s*(" + NUM + ")", t)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        return None, min(a, b), max(a, b)
    return None, None, None


def normalize_value(v, unit):
    if v is None:
        return None, None
    if unit in units.SPEED_UNITS:
        return units.speed_to_cm_s(v, unit), "cm/s"
    if unit in units.LENGTH_UNITS:
        return units.length_to_cm(v, unit), "cm"
    if unit in units.TIME_UNITS:
        return units.time_to_s(v, unit), "s"
    return v, unit


SAFFIRE_ID = re.compile(r"\b(I{1,3}|IV|V|VI)-(\d)\b")


def test_id_of(r, fams, dcls):
    plat = r.get("platform", "")
    m = SAFFIRE_ID.search(plat)
    if m:
        return "Saffire %s-%s" % m.groups()
    src = r["source_id"]
    fam = "+".join(fams) or "unknown"
    if src == "luci_2025":
        if "ground" in plat.lower() or r.get("gravity", "").lower().startswith("1 g"):
            return "LUCI 1-g ground"
        return "LUCI NS-29 lunar spin"
    if src == "fm2_poster_2024":
        if "planned" in plat.lower():
            return "FM2 planned / %s" % dcls
        if "centrifuge" in plat.lower():
            return "FM2 team lunar-g simulation"
        return "FM2 team 1-g ground"
    return None


def role_of(r, gk):
    tier = (r.get("evidence_tier") or "").lower()
    if "planned" in tier:
        return "planned"
    if "model" in tier or gk == "model":
        return "model"
    if "comparison" in tier or gk == "comparison":
        return "comparison"
    return "evidence"


def normalize(rows):
    g_spin, spin = luci_spin_g(rows)
    out = []
    for r in rows:
        p = parse_pressure(r.get("pressure"))
        o = parse_oxygen(r.get("oxygen"))
        f = parse_flow(r.get("flow"))
        g = parse_gravity(r.get("gravity"), g_spin)
        fams = families_of(r.get("material"))
        dcls = direction_class(r.get("direction"))
        v, vlo, vhi = parse_value(r.get("value"))
        vn, un = normalize_value(v, r.get("unit"))
        th = parse_thickness_mm(r.get("geometry"))
        tid = test_id_of(r, fams, dcls)
        role = role_of(r, g["kind"])
        series = tid or "|".join([r["source_id"], r.get("platform", ""), "+".join(fams) or "unknown", dcls,
                                  str(p["value_kpa"] or p["lo_kpa"] or p["hi_kpa"]), str(o["value_pct"] or o["hi_pct"]),
                                  str(f["value_cm_s"] or f["hi_cm_s"]), ",".join("%.3f" % x for x in g["levels"])])
        meta = SOURCES_META.get(r["source_id"], {})
        out.append({
            "row_id": r["row_id"], "source_id": r["source_id"], "source_year": meta.get("year"),
            "locator": r.get("locator"), "evidence_tier": r.get("evidence_tier"), "role": role,
            "platform": r.get("platform"), "test_id": tid, "series_id": series,
            "g_levels": g["levels"], "g_kind": g["kind"], "g_classes": [g_class(x) for x in g["levels"]],
            "p_kpa": p["value_kpa"], "p_lo_kpa": p["lo_kpa"], "p_hi_kpa": p["hi_kpa"], "p_kind": p["kind"], "p_text": r.get("pressure"),
            "o2_pct": o["value_pct"], "o2_lo_pct": o["lo_pct"], "o2_hi_pct": o["hi_pct"], "o2_kind": o["kind"], "o2_text": r.get("oxygen"),
            "flow_cm_s": f["value_cm_s"], "flow_lo_cm_s": f["lo_cm_s"], "flow_hi_cm_s": f["hi_cm_s"], "flow_kind": f["kind"], "flow_text": r.get("flow"),
            "direction_text": r.get("direction"), "direction_class": dcls,
            "material_text": r.get("material"), "families": fams,
            "geometry_text": r.get("geometry"), "thickness_mm_lo": th[0] if th else None, "thickness_mm_hi": th[1] if th else None,
            "measurement": r.get("measurement"), "value_text": r.get("value"), "value_num": v, "value_lo": vlo, "value_hi": vhi,
            "unit": r.get("unit"), "value_norm": vn, "unit_norm": un, "qualifier": r.get("qualifier"),
            "snippet": r.get("snippet"), "source_title": r.get("source_title"),
        })
    return out, {"g_spin": g_spin, "spin": spin, "g_lunar": units.G_LUNAR, "g_mars": units.G_MARS}


DEDUPE_RULE = ("Two rows are one measurement when they describe the same test and material family, name the same measurand "
               "and agree within 0.5% after unit normalization. The lower row ID is kept; the other row's locator is kept as corroboration.")


def dedupe(norm):
    """Merge duplicate measurement rows (documented rule); returns kept rows and a log of merged rows."""
    from .checks import duplicate_rows  # local import keeps the dependency one-way at import time
    dups = duplicate_rows(norm)
    drop = {d["row_id"]: d["duplicate_of"] for d in dups}
    kept = []
    for r in norm:
        if r["row_id"] in drop:
            continue
        r = dict(r)
        r["corroborated_by"] = [x for x, keep in drop.items() if keep == r["row_id"]]
        kept.append(r)
    return kept, [{"row_id": k, "merged_into": v, "rule": DEDUPE_RULE} for k, v in drop.items()]


def _merge(a, b, key_v, key_lo, key_hi):
    """Fill missing condition values from another row of the same test."""
    for k in (key_v, key_lo, key_hi):
        if a.get(k) is None and b.get(k) is not None:
            a[k] = b[k]


def test_points(norm, include_roles=("evidence",)):
    """One record per physical test, per material family and per gravity level."""
    groups = {}
    for r in norm:
        if r["role"] not in include_roles:
            continue
        fams = r["families"] or ["unknown"]
        levels = r["g_levels"] or [None]
        for fam in fams:
            for g in levels:
                key = (r["series_id"] if r["test_id"] else r["series_id"], fam, None if g is None else round(g, 4))
                tp = groups.get(key)
                if tp is None:
                    tp = groups[key] = {
                        "tp_id": None, "test_id": r["test_id"] or r["series_id"].split("|")[0] + ":" + r["row_id"],
                        "label": r["test_id"] or "%s %s" % (r["source_id"], r["platform"]),
                        "family": fam, "direction_class": r["direction_class"],
                        "g": g, "g_class": g_class(g) if g is not None else "unknown",
                        "p_kpa": r["p_kpa"], "p_lo_kpa": r["p_lo_kpa"], "p_hi_kpa": r["p_hi_kpa"],
                        "o2_pct": r["o2_pct"], "o2_lo_pct": r["o2_lo_pct"], "o2_hi_pct": r["o2_hi_pct"],
                        "flow_cm_s": r["flow_cm_s"], "flow_lo_cm_s": r["flow_lo_cm_s"], "flow_hi_cm_s": r["flow_hi_cm_s"],
                        "evidence_tier": r["evidence_tier"], "sources": [], "row_ids": [], "years": [], "measurands": [],
                    }
                else:
                    for trip in (("p_kpa", "p_lo_kpa", "p_hi_kpa"), ("o2_pct", "o2_lo_pct", "o2_hi_pct"), ("flow_cm_s", "flow_lo_cm_s", "flow_hi_cm_s")):
                        _merge(tp, r, *trip)
                    if tp["direction_class"] == "unknown" and r["direction_class"] != "unknown":
                        tp["direction_class"] = r["direction_class"]
                if r["source_id"] not in tp["sources"]:
                    tp["sources"].append(r["source_id"])
                tp["row_ids"].append(r["row_id"])
                if r["source_year"] not in tp["years"]:
                    tp["years"].append(r["source_year"])
                tp["measurands"].append(r["measurement"])
    pts = list(groups.values())
    for i, tp in enumerate(sorted(pts, key=lambda x: (x["label"], x["family"], x["g"] if x["g"] is not None else -1))):
        tp["tp_id"] = "TP%03d" % (i + 1)
        tp["first_year"] = min(y for y in tp["years"] if y is not None) if any(tp["years"]) else None
    return sorted(pts, key=lambda x: x["tp_id"])


def load_extra_tests(folder=os.path.join(DATA, "extra_tests")):
    """Optional extra test points (for example PSI table exports) in the test-point schema."""
    pts = []
    for path in sorted(glob.glob(os.path.join(folder, "*.csv"))):
        for row in csv.DictReader(open(path)):
            tp = {k: (float(v) if k in {"g", "p_kpa", "o2_pct", "flow_cm_s"} and v not in ("", None) else (v or None)) for k, v in row.items()}
            for a, b in (("p_lo_kpa", "p_kpa"), ("p_hi_kpa", "p_kpa"), ("o2_lo_pct", "o2_pct"), ("o2_hi_pct", "o2_pct"), ("flow_lo_cm_s", "flow_cm_s"), ("flow_hi_cm_s", "flow_cm_s")):
                tp[a] = tp.get(a) if tp.get(a) not in (None, "") else tp.get(b)
            tp["g_class"] = g_class(tp["g"]) if tp.get("g") is not None else "unknown"
            tp["sources"] = [tp.get("source_id") or os.path.basename(path)]
            tp["row_ids"] = [tp.get("row_id") or ""]
            tp["first_year"] = int(tp["first_year"]) if tp.get("first_year") else None
            pts.append(tp)
    return pts


def write_tables(norm, pts, meta, folder=DATA):
    json.dump(norm, open(os.path.join(folder, "normalized_rows.json"), "w"), indent=1)
    json.dump({"meta": meta, "test_points": pts}, open(os.path.join(folder, "test_points.json"), "w"), indent=1)
    cols = ["tp_id", "label", "family", "direction_class", "g", "g_class", "p_kpa", "p_lo_kpa", "p_hi_kpa", "o2_pct", "o2_lo_pct",
            "o2_hi_pct", "flow_cm_s", "flow_lo_cm_s", "flow_hi_cm_s", "evidence_tier", "first_year", "sources", "row_ids"]
    with open(os.path.join(folder, "test_points.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for tp in pts:
            w.writerow([";".join(map(str, tp[c])) if isinstance(tp.get(c), list) else tp.get(c) for c in cols])


def build(ledger_path=DEFAULT_LEDGER, write=True):
    rows = load_ledger(ledger_path)
    norm, meta = normalize(rows)
    norm, merged = dedupe(norm)
    meta["merged_rows"] = merged
    pts = test_points(norm) + load_extra_tests()
    if write:
        write_tables(norm, pts, meta)
    return rows, norm, pts, meta
