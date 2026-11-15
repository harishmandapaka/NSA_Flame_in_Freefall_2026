"""Experiment 2: range, unit, uniqueness, provenance, consistency and reference checks.

Each check returns {"name", "status", "n_checked", "failures": [...], "what"}.
They run on every rebuild like a regression suite; any FAIL blocks deployment.
"""
import copy
import csv
import json
import os
import re

from . import ingest, units

LIMITS = {"o2_pct": (0.0, 100.0), "p_kpa": (0.0, 120.0), "flow_cm_s": (0.0, 100.0), "g": (0.0, 1.1)}
SPEED = set(units.SPEED_UNITS)
TIME = set(units.TIME_UNITS)
NOT_A_RATE = re.compile(r"^(ratio|dependence|gravity level|unique|number|how|time)\b")
CHECKS_VERSION = "1.2"
CHANGES_FROM_1_0 = [
    "A row is treated as a spread-rate measurement only when its measurand is a spread rate, not a count of spread rates or a gravity level (false alarms on R086 and R093 in run 1).",
    "An extinction row fails when it carries a speed that is not a flow speed; a flow speed at blowoff is legitimate (false alarm on R083 in run 1). Version 1.1 required the measurand name to say 'spread rate', which missed injected fault F10, so version 1.2 tests the unit instead.",
    "Two test points with identical conditions are duplicates only when at least one has no named test ID; Saffire I-1, II-5, II-6 and III-1 are distinct tests (false alarms in run 1).",
    "Air is 20.946% oxygen by volume (IUPAC); run 1 used 20.9% for rows and 21.0% for the plan's sea-level partial pressure, which flagged the plan's 3.08 psia wrongly.",
]


def is_rate(measurement):
    m = (measurement or "").strip().lower()
    return "spread rate" in m and not NOT_A_RATE.match(m)


def _result(name, what, n, failures):
    return {"name": name, "what": what, "status": "PASS" if not failures else "FAIL", "n_checked": n, "failures": failures}


def check_ranges(norm):
    fails, n = [], 0
    for r in norm:
        for label, keys in (("o2_pct", ("o2_pct", "o2_lo_pct", "o2_hi_pct")), ("p_kpa", ("p_kpa", "p_lo_kpa", "p_hi_kpa")),
                            ("flow_cm_s", ("flow_cm_s", "flow_lo_cm_s", "flow_hi_cm_s"))):
            lo, hi = LIMITS[label]
            for k in keys:
                v = r.get(k)
                if v is None:
                    continue
                n += 1
                if not (lo <= v <= hi):
                    fails.append({"row_id": r["row_id"], "field": k, "value": v, "limit": [lo, hi]})
        for g in r.get("g_levels") or []:
            n += 1
            if not (LIMITS["g"][0] <= g <= LIMITS["g"][1]):
                fails.append({"row_id": r["row_id"], "field": "gravity", "value": g, "limit": list(LIMITS["g"])})
        for k in ("thickness_mm_lo", "thickness_mm_hi"):
            if r.get(k) is not None:
                n += 1
                if r[k] <= 0:
                    fails.append({"row_id": r["row_id"], "field": k, "value": r[k], "limit": "above zero"})
    return _result("check_ranges", "Oxygen 0 to 100%, pressure 0 to 120 kPa, flow 0 to 100 cm/s, gravity 0 to 1.1 g, thickness above zero", n, fails)


def check_units(norm):
    fails, n = [], 0
    for u in ("kPa", "psia", "atm"):  # conversion round trips
        for v in (1.0, 8.2, 14.7, 54.1, 101.325):
            n += 1
            err = units.roundtrip_error(v, u)
            if err > 1e-3:
                fails.append({"row_id": None, "field": "conversion", "value": "%s %s" % (v, u), "error": err})
    for r in norm:
        n += 1
        if r.get("unit") not in units.ALLOWED_UNITS:
            fails.append({"row_id": r["row_id"], "field": "unit", "value": r.get("unit"), "limit": "allowed units"})
        m = (r.get("measurement") or "").lower()
        if r.get("value_num") is not None and is_rate(m):
            n += 1
            if r.get("unit") not in SPEED:
                fails.append({"row_id": r["row_id"], "field": "unit", "value": r.get("unit"), "limit": "speed unit for a spread rate"})
        if r.get("value_num") is not None and re.search(r"\bduration\b", m):
            n += 1
            if r.get("unit") not in TIME:
                fails.append({"row_id": r["row_id"], "field": "unit", "value": r.get("unit"), "limit": "time unit for a duration"})
        t = (r.get("p_text") or "").lower()  # a field stated in two units must agree within 0.1%
        mk, mp = re.search(r"(\d+(?:\.\d+)?)\s*kpa", t), re.search(r"(\d+(?:\.\d+)?)\s*psia", t)
        if mk and mp:
            n += 1
            a, b = float(mk.group(1)), units.psia_to_kpa(float(mp.group(1)))
            if abs(a - b) / a > 1e-3:
                fails.append({"row_id": r["row_id"], "field": "pressure", "value": r.get("p_text"), "error": abs(a - b) / a})
    return _result("check_units", "Allowed units only; kPa, psia and atm round-trip within 0.1%; a value stated in two units agrees within 0.1%; spread rates carry speed units and durations carry time units", n, fails)


def duplicate_rows(norm):
    seen, dups = {}, []
    for r in norm:
        if r.get("value_norm") is None:
            continue
        key = (r["series_id"], tuple(sorted(r["families"])), (r.get("measurement") or "").strip().lower(), r.get("unit_norm"))
        for prev in seen.get(key, []):
            a, b = prev["value_norm"], r["value_norm"]
            if abs(a - b) <= 0.005 * max(abs(a), abs(b), 1e-12):
                dups.append({"row_id": r["row_id"], "duplicate_of": prev["row_id"], "measurement": r.get("measurement"),
                             "value": "%s %s = %s %s" % (r.get("value_text"), r.get("unit"), prev.get("value_text"), prev.get("unit"))})
        seen.setdefault(key, []).append(r)
    return dups


def check_unique(norm, pts=None):
    fails = duplicate_rows(norm)
    n = len(norm)
    if pts:
        sig = {}
        for tp in pts:
            k = (tuple(sorted(tp["sources"])), tp["family"], tp["direction_class"], tp["g"], tp["p_kpa"], tp["o2_pct"], tp["flow_cm_s"])
            n += 1
            named = tp["label"].startswith(("Saffire", "LUCI", "FM2"))
            if k in sig and sig[k][0] != tp["label"] and not (named and sig[k][1]):
                fails.append({"tp_id": tp["tp_id"], "duplicate_of": sig[k][0], "measurement": "test point", "value": tp["label"]})
            sig.setdefault(k, (tp["label"], named))
    return _result("check_unique", "No duplicate measurements of the same test (after unit normalization) and no test recorded twice under two names", n, fails)


def check_provenance(raw_rows, sources_csv=os.path.join(ingest.DATA, "sources.csv")):
    known = {r["source_id"] for r in csv.DictReader(open(sources_csv))}
    fails = []
    for r in raw_rows:
        for k in ("source_id", "locator", "snippet"):
            if not (r.get(k) or "").strip():
                fails.append({"row_id": r.get("row_id"), "field": k, "value": r.get(k), "limit": "required"})
        if r.get("source_id") and r["source_id"] not in known:
            fails.append({"row_id": r.get("row_id"), "field": "source_id", "value": r["source_id"], "limit": "listed in sources.csv"})
    return _result("check_provenance", "Every row has a listed source, a locator (page, slide, table or section) and a supporting quote", len(raw_rows), fails)


def check_consistency(norm, pts, golden=None):
    fails, n = [], 0
    for r in norm:  # extinction or no-burn rows must not carry a spread rate
        txt = ("%s %s" % (r.get("measurement"), r.get("value_text"))).lower()
        if re.search(r"extinguish|extinction|no burn|blow-?off", txt):
            n += 1
            names_flow = re.search(r"flow|velocity", (r.get("measurement") or "").lower())
            if r.get("unit") in SPEED and (r.get("value_num") or 0) > 0 and not names_flow:
                fails.append({"row_id": r["row_id"], "field": "unit", "value": r.get("unit"), "limit": "no spread rate on an extinction row"})
    by_test = {}
    for r in norm:  # the same test reported in two sources must agree
        if r["role"] == "evidence" and r.get("test_id", "") and r["test_id"].startswith("Saffire"):
            by_test.setdefault(r["test_id"], []).append(r)
    for tid, rs in by_test.items():
        for k, tol in (("o2_pct", 0.1), ("p_kpa", 0.005)):
            vals = [(r["row_id"], r[k]) for r in rs if r.get(k) is not None]
            if len(vals) > 1:
                n += 1
                base = vals[0][1]
                bad = [v for v in vals if (abs(v[1] - base) > tol if k == "o2_pct" else abs(v[1] - base) / base > tol)]
                if bad:
                    fails.append({"row_id": ",".join(x[0] for x in bad), "field": k, "value": "%s disagrees within %s" % (tid, k), "limit": tol})
    rates = {(r["series_id"], (r.get("measurement") or "").lower(), tuple(r["families"])): r for r in norm if r.get("unit_norm") == "cm/s"}
    for r in norm:  # a stated lunar-to-1-g ratio must match the ratio of the stated rates (within 5%)
        m = (r.get("measurement") or "").lower()
        if r["role"] == "comparison" and m.startswith("ratio of lunar to 1-g") and r.get("value_num"):
            which = "flame base spread rate" if "base" in m else "flame tip spread rate"
            lunar = [x for (sid, mm, fam), x in rates.items() if sid.startswith("LUCI NS-29") and mm == which and fam == tuple(r["families"])]
            ground = [x for (sid, mm, fam), x in rates.items() if sid.startswith("LUCI 1-g") and mm == which and fam == tuple(r["families"])]
            if lunar and ground:
                n += 1
                calc = lunar[0]["value_norm"] / ground[0]["value_norm"]
                if abs(calc - r["value_num"]) / r["value_num"] > 0.05:
                    fails.append({"row_id": r["row_id"], "field": "value", "value": "stated %s vs %.3f from %s/%s" % (r["value_num"], calc, lunar[0]["row_id"], ground[0]["row_id"]), "limit": "5%"})
    if golden:  # oxygen partial pressure equals oxygen fraction times pressure (plan's derived figures)
        for item in golden.get("derived_ppo2_psia", []):
            n += 1
            calc = item["o2_pct"] / 100.0 * item["p_psia"]
            if abs(calc - item["stated_ppo2_psia"]) > 0.006:
                fails.append({"row_id": None, "field": "ppO2", "value": "%s: stated %s, calculated %.3f" % (item["label"], item["stated_ppo2_psia"], calc), "limit": "0.006 psia"})
    return _result("check_consistency", "Extinction rows carry no spread rate; a test reported twice agrees; stated ratios match their rates; oxygen partial pressure equals oxygen fraction times pressure", n, fails)


def check_golden(norm, pts, golden):
    fails, n = [], 0
    tps = {tp["label"]: tp for tp in pts}
    for g in golden["saffire"]:
        tp = tps.get("Saffire " + g["test"])
        n += 1
        if tp is None:
            fails.append({"tp_id": None, "field": "test", "value": g["test"], "limit": "reference test missing"})
            continue
        for k in ("p_kpa", "o2_pct", "flow_cm_s"):
            n += 1
            if tp.get(k) is None or abs(tp[k] - g[k]) > 1e-9:
                fails.append({"tp_id": tp["tp_id"], "field": k, "value": tp.get(k), "limit": g[k]})
        for k, gk in (("family", "material_family"), ("direction_class", "direction")):
            n += 1
            if tp.get(k) != g[gk]:
                fails.append({"tp_id": tp["tp_id"], "field": k, "value": tp.get(k), "limit": g[gk]})
    planned = [r for r in norm if r["role"] == "planned"]
    for g in golden["fm2_atmospheres"]:
        n += 1
        ok = [r for r in planned if g["material_family"] in r["families"] and r.get("o2_pct") is not None
              and abs(r["o2_pct"] - g["o2_pct"]) < 1e-9 and abs(units.kpa_to_psia(r["p_kpa"]) - g["p_psia"]) < 1e-6]
        if len(ok) != 2:
            fails.append({"row_id": None, "field": "FM2 atmosphere", "value": "%s%% at %s psia found %d times" % (g["o2_pct"], g["p_psia"], len(ok)), "limit": "2 planned burns"})
    spin = golden["luci_spin"]
    found = {r["measurement"]: r for r in norm if r["source_id"] == "luci_2025"}
    n += 2
    if (found.get("vehicle rotation rate") or {}).get("value_num") != spin["rpm"]:
        fails.append({"row_id": None, "field": "LUCI rpm", "value": (found.get("vehicle rotation rate") or {}).get("value_num"), "limit": spin["rpm"]})
    rad = [r for m, r in found.items() if m.startswith("effective radius")]
    if not rad or rad[0]["value_num"] != spin["radius_m"]:
        fails.append({"row_id": None, "field": "LUCI radius", "value": rad[0]["value_num"] if rad else None, "limit": spin["radius_m"]})
    return _result("check_golden", "Hand-verified reference rows (Saffire IV-1, VI-2, VI-3, VI-4; FM2 atmospheres; LUCI spin) match exactly", n, fails)


def golden_in_sources(golden, sources_dir):
    """Optional: confirm each reference number appears in the Saffire VI presentation text."""
    path = os.path.join(sources_dir, "saffire6_pres_2024.txt")
    if not os.path.exists(path):
        return {"status": "SKIPPED", "reason": "source text not available"}
    text = re.sub(r"[\u2010-\u2015\u2212]", "-", open(path, encoding="utf-8", errors="ignore").read())
    out = {}
    for test, nums in golden.get("source_quotes", {}).items():
        out[test] = {x: (x in text) for x in nums + [test]}
    ok = all(all(v.values()) for v in out.values())
    return {"status": "PASS" if ok else "FAIL", "found": out}


def luci_g_from_spin(rpm=11.0, r_m=1.22, tol=0.02):
    a = units.spin_accel_m_s2(rpm, r_m)
    lunar = units.G_LUNAR * units.G0
    dev = (a - lunar) / lunar
    return {"name": "luci_g_from_spin", "status": "PASS" if abs(dev) <= tol else "FAIL", "accel_m_s2": a,
            "g_ratio": a / units.G0, "lunar_m_s2": lunar, "deviation": dev, "tolerance": tol,
            "what": "LUCI's 11 rpm spin at 1.22 m must give lunar gravity within 2% (NASA fact-sheet value 1.62 m/s2)"}


def run_all(raw_rows, golden, sources_dir=None, dedupe=True):
    norm, meta = ingest.normalize(raw_rows)
    dropped = []
    if dedupe:
        norm, dropped = ingest.dedupe(norm)
    pts = ingest.test_points(norm)
    res = [check_ranges(norm), check_units(norm), check_unique(norm, pts), check_provenance(raw_rows),
           check_consistency(norm, pts, golden), check_golden(norm, pts, golden), luci_g_from_spin()]
    for r in res:
        r.setdefault("failures", [])
        r.setdefault("n_checked", 1)
    res.append({"name": "dedupe_log", "status": "INFO", "n_checked": len(dropped), "failures": [], "dropped": dropped,
                "what": "Rows merged by the documented duplicate rule before the checks ran"})
    return res, norm, pts


# ------------------------------------------------------------ fault injection
def _mut(rows, rid, **changes):
    out = copy.deepcopy(rows)
    for r in out:
        if r["row_id"] == rid:
            r.update(changes)
    return out


def faults(rows):
    dup = copy.deepcopy([r for r in rows if r["row_id"] == "R027"][0]); dup["row_id"] = "R999"
    ext_id = [r["row_id"] for r in rows if (r.get("measurement") or "").lower().startswith("extinguishment")][0]
    return [
        ("F01", "Oxygen typed as 140%", "check_ranges", "R029", _mut(rows, "R029", oxygen="140 mol %")),
        ("F02", "Pressure in hPa labelled kPa (1013)", "check_ranges", "R027", _mut(rows, "R027", pressure="1013 kPa")),
        ("F03", "Negative flow speed", "check_ranges", "R028", _mut(rows, "R028", flow="-5 cm/s")),
        ("F04", "Gravity in m/s2 instead of g", "check_ranges", "R001", _mut(rows, "R001", gravity="9.81 G")),
        ("F05", "Same row entered twice", "check_unique", "R999", rows + [dup]),
        ("F06", "Locator missing", "check_provenance", "R030", _mut(rows, "R030", locator="")),
        ("F07", "Unknown unit", "check_units", "R031", _mut(rows, "R031", unit="furlong/s")),
        ("F08", "Reference value drifted (VI-2 at 51.4 kPa)", "check_golden", "R029", _mut(rows, "R029", pressure="51.4 kPa")),
        ("F09", "Two stated units disagree (27.6 kPa vs 14.0 psia)", "check_units", "R093", _mut(rows, "R093", pressure="27.6 kPa (14.0 psia)")),
        ("F10", "Spread rate on an extinction row", "check_consistency", ext_id, _mut(rows, ext_id, value="1.2", unit="mm/s")),
        ("F11", "Spread rate recorded in seconds", "check_units", "R002", _mut(rows, "R002", unit="s")),
        ("F12", "Stated ratio inconsistent with its rates (0.93)", "check_consistency", "R006", _mut(rows, "R006", value="0.93")),
    ]


def fault_injection(rows, golden):
    out = []
    for fid, desc, expected, rid, mutated in faults(rows):
        res, _, _ = run_all(mutated, golden, dedupe=(expected != "check_unique"))
        failed = [r["name"] for r in res if r["status"] == "FAIL"]
        exp = [r for r in res if r["name"] == expected][0]
        hit = any((f.get("row_id") or "").find(rid) >= 0 or (f.get("tp_id") or "") for f in exp["failures"]) if exp["status"] == "FAIL" else False
        out.append({"fault": fid, "description": desc, "expected_check": expected, "row": rid,
                    "detected": exp["status"] == "FAIL", "located": bool(hit), "checks_failed": failed})
    return out
