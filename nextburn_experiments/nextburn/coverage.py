"""Experiment 3: coverage of habitat cells by NASA test points, and its sensitivity to matching tolerances.

A cell is one habitat x one material family x one flame direction class.
Statuses follow the plan: tested, bounded (interpolation only; 'not proven safe' when gravity is a bounded axis) or untested.
Planned tests (FM2) never count as evidence; they are listed beside the cell.
"""
import math

from . import ingest, units

MICROFIRE_O2_BINS = [(0, 17), (17, 19), (19, 21.5), (21.5, 26), (26, 31), (31, 101)]


def cells(presets=ingest.PRESETS):
    out = []
    for h in presets["habitats"]:
        for fam in presets["material_families"]:
            for d in presets["direction_classes"]:
                out.append({"cell_id": "%s|%s|%s" % (h["id"], fam, d), "habitat": h["id"], "habitat_name": h["name"],
                            "o2_pct": h["o2_pct"], "p_kpa": units.psia_to_kpa(h["p_psia"]), "p_psia": h["p_psia"],
                            "g_class": h["g_class"], "family": fam, "direction": d})
    return out


def _rng(tp, k):
    v, lo, hi = tp.get(k), tp.get(k.replace("_pct", "_lo_pct").replace("_kpa", "_lo_kpa")), tp.get(k.replace("_pct", "_hi_pct").replace("_kpa", "_hi_kpa"))
    lo = lo if lo is not None else v
    hi = hi if hi is not None else v
    return lo, hi


def _overlap(lo, hi, a, b):
    return lo is not None and hi is not None and lo <= b and hi >= a


def match(tp, cell, tol_o2, tol_p_frac, same_g_class=True):
    if tp["family"] != cell["family"] or tp["direction_class"] != cell["direction"]:
        return False
    if same_g_class and tp["g_class"] != cell["g_class"]:
        return False
    olo, ohi = _rng(tp, "o2_pct")
    plo, phi = _rng(tp, "p_kpa")
    return (_overlap(olo, ohi, cell["o2_pct"] - tol_o2, cell["o2_pct"] + tol_o2)
            and _overlap(plo, phi, cell["p_kpa"] * (1 - tol_p_frac), cell["p_kpa"] * (1 + tol_p_frac)))


def bounded(cell, pts):
    """Per-axis bracketing by tests of the same family and direction with numeric oxygen, pressure and gravity."""
    pool = [tp for tp in pts if tp["family"] == cell["family"] and tp["direction_class"] == cell["direction"]
            and None not in _rng(tp, "o2_pct") and None not in _rng(tp, "p_kpa") and tp.get("g") is not None]
    target_g = {"micro": 0.0, "lunar": units.G_LUNAR, "mars": units.G_MARS}[cell["g_class"]]
    axes = {}
    for name, key, val in (("oxygen", "o2_pct", cell["o2_pct"]), ("pressure", "p_kpa", cell["p_kpa"])):
        below = [tp["tp_id"] for tp in pool if _rng(tp, key)[0] <= val]
        above = [tp["tp_id"] for tp in pool if _rng(tp, key)[1] >= val]
        axes[name] = {"below": below, "above": above, "bracketed": bool(below and above)}
    below = [tp["tp_id"] for tp in pool if tp["g"] <= target_g + 1e-9]
    above = [tp["tp_id"] for tp in pool if tp["g"] >= target_g - 1e-9]
    axes["gravity"] = {"below": below, "above": above, "bracketed": bool(below and above)}
    ok = all(a["bracketed"] for a in axes.values())
    exact_g = [tp for tp in pool if tp["g_class"] == cell["g_class"]]
    return ok, axes, (ok and not exact_g)


def unstated_near_misses(cell, pts):
    """Tests of the same family, direction and gravity class that cannot be matched because oxygen or pressure is not stated."""
    out = []
    for tp in pts:
        if tp["family"] != cell["family"] or tp["direction_class"] != cell["direction"] or tp["g_class"] != cell["g_class"]:
            continue
        o, p = _rng(tp, "o2_pct"), _rng(tp, "p_kpa")
        o_unk, p_unk = None in o, None in p
        if not (o_unk or p_unk):
            continue
        o_ok = o_unk or _overlap(o[0], o[1], cell["o2_pct"] - 4, cell["o2_pct"] + 4)
        p_ok = p_unk or _overlap(p[0], p[1], cell["p_kpa"] * 0.8, cell["p_kpa"] * 1.2)
        if o_ok and p_ok:
            out.append(tp["tp_id"])
    return out


def coverage_status(cell, pts, tol_o2, tol_p_frac, planned=(), same_g_class=True):
    hits = [tp["tp_id"] for tp in pts if match(tp, cell, tol_o2, tol_p_frac, same_g_class)]
    plan = [tp["tp_id"] for tp in planned if match(tp, cell, tol_o2, tol_p_frac)]
    if hits:
        return {"status": "tested", "matches": hits, "planned": plan, "not_proven_safe": False}
    ok, axes, grav_only = bounded(cell, pts)
    if ok:
        return {"status": "bounded", "matches": [], "planned": plan, "not_proven_safe": grav_only,
                "bracket_counts": {k: [len(v["below"]), len(v["above"])] for k, v in axes.items()}}
    return {"status": "untested", "matches": [], "planned": plan, "not_proven_safe": True,
            "missing_bracket": [k for k, v in axes.items() if not v["bracketed"]]}


def coverage_table(cell_list, pts, tol_o2, tol_p_frac, planned=(), same_g_class=True):
    return [dict(c, **coverage_status(c, pts, tol_o2, tol_p_frac, planned, same_g_class), unstated=unstated_near_misses(c, pts)) for c in cell_list]


def shares(table):
    n = len(table)
    return {s: sum(1 for c in table if c["status"] == s) / n for s in ("tested", "bounded", "untested")}


def sensitivity(cell_list, pts, o2_tols=(1, 2, 4), p_tols=(0.10, 0.20), planned=(), same_g_class=True):
    runs = []
    for to in o2_tols:
        for tp_ in p_tols:
            tab = coverage_table(cell_list, pts, to, tp_, planned, same_g_class)
            runs.append({"tol_o2_pts": to, "tol_p_frac": tp_, "same_g_class": same_g_class, "table": tab, "shares": shares(tab),
                         "counts": {s: sum(1 for c in tab if c["status"] == s) for s in ("tested", "bounded", "untested")}})
    return runs


def distance(tp, cell, s_o2=2.0, s_p=0.10):
    """Normalized distance in tolerance units over oxygen and log-pressure (closest point of any stated range)."""
    olo, ohi = _rng(tp, "o2_pct")
    plo, phi = _rng(tp, "p_kpa")
    if None in (olo, ohi, plo, phi) or plo <= 0:
        return None
    o = min(max(cell["o2_pct"], olo), ohi)
    p = min(max(cell["p_kpa"], plo), phi)
    return math.sqrt(((o - cell["o2_pct"]) / s_o2) ** 2 + (math.log(p / cell["p_kpa"]) / math.log(1 + s_p)) ** 2)


def distance_status(cell, pts, threshold=1.0):
    near = [(distance(tp, cell), tp) for tp in pts if tp["family"] == cell["family"] and tp["direction_class"] == cell["direction"]
            and tp["g_class"] == cell["g_class"] and distance(tp, cell) is not None]
    best = min(near, key=lambda x: x[0]) if near else (None, None)
    return {"status": "tested" if best[0] is not None and best[0] <= threshold else "not_tested", "best_distance": best[0],
            "best_tp": best[1]["tp_id"] if best[1] else None}


def microfire_status(cell, pts):
    """Competitor-grid check: same gravity row and the same MicroFire oxygen bin, same material family."""
    b = [x for x in MICROFIRE_O2_BINS if x[0] <= cell["o2_pct"] < x[1]][0]
    hits = [tp["tp_id"] for tp in pts if tp["family"] == cell["family"] and tp["g_class"] == cell["g_class"]
            and _overlap(*_rng(tp, "o2_pct"), b[0], b[1] - 1e-9)]
    return {"bin": "%s-%s%%" % b if b[1] < 100 else ">= %s%%" % b[0], "status": "known" if hits else "unknown", "matches": hits}


def nearest_evidence(cell, pts, k=3, ignore_gravity=True):
    rows = []
    for tp in pts:
        if tp["family"] != cell["family"]:
            continue
        if not ignore_gravity and tp["g_class"] != cell["g_class"]:
            continue
        d = distance(tp, cell)
        if d is None:
            continue
        diffs = []
        if tp["g_class"] != cell["g_class"]:
            diffs.append("gravity %s, not %s" % (tp["g_class"], cell["g_class"]))
        if tp["direction_class"] != cell["direction"]:
            diffs.append("direction %s" % tp["direction_class"])
        if tp.get("flow_cm_s"):
            diffs.append("forced flow %g cm/s" % tp["flow_cm_s"])
        rows.append({"tp_id": tp["tp_id"], "label": tp["label"], "distance": d, "o2_pct": tp.get("o2_pct"), "p_kpa": tp.get("p_kpa"),
                     "p_psia": units.kpa_to_psia(tp["p_kpa"]) if tp.get("p_kpa") else None, "g_class": tp["g_class"],
                     "differences": diffs, "row_ids": tp["row_ids"]})
    return sorted(rows, key=lambda r: r["distance"])[:k]
