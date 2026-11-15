"""Experiment 5: gap ranking and a facility-constrained test planner (plus weight sensitivity)."""
import copy
import itertools
import math
import random

from . import coverage, ingest, physics, units


def ledger_asof(pts, cutoff_year=2025):
    """Test points with at least one source published before 1 January of cutoff_year."""
    return [tp for tp in pts if tp.get("first_year") is not None and tp["first_year"] < cutoff_year]


def risk_weight(cell, w):
    return (w["habitat_priority"][cell["habitat"]] * w["material_commonness"][cell["family"]]
            * (cell["o2_pct"] / 21.0) ** w.get("oxygen_exponent", 1.0) * w["direction_factor"][cell["direction"]])


def rank_gaps(table, w):
    gaps = []
    for c in table:
        gap = w["status_gap"][c["status"]]
        if gap <= 0:
            continue
        r = risk_weight(c, w)
        gaps.append(dict(c, risk=r, gap=gap, value=r * gap))
    return sorted(gaps, key=lambda g: -g["value"])


def _levels(fac):
    out = []
    for x in fac["gravity_levels"]:
        if x == "lunar_nominal":
            out.append(units.G_LUNAR)
        elif x == "luci_spin":
            out.append(units.g_from_spin(11, 1.22))
        else:
            out.append(float(x))
    return out


def _time_at(fac, g):
    t = fac.get("test_time_by_level_s", {})
    for k, v in t.items():
        if abs(float(k) - g) < 1e-6:
            return v
    return fac["test_time_s"]


def feasible(fac, cell, measurand, fcfg):
    """Whether a facility can run this cell's test and deliver the measurand; returns (ok, reasons, level, time)."""
    reasons = []
    if not fac.get("available", True):
        return False, ["already allocated"], None, None
    lv = [g for g in _levels(fac) if ingest.g_class(g) == cell["g_class"]]
    if not lv:
        return False, ["no %s gravity" % cell["g_class"]], None, None
    g = lv[0]
    t = _time_at(fac, g)
    a = fac["atmosphere"]
    if cell["o2_pct"] > a.get("o2_max_pct", 100) or cell["o2_pct"] < a.get("o2_min_pct", 0):
        reasons.append("oxygen %g%% outside %s" % (cell["o2_pct"], a["status"]))
    if not (a.get("p_min_kpa", 0) <= cell["p_kpa"] <= a.get("p_max_kpa", 1e9)):
        reasons.append("pressure %.1f kPa outside %s" % (cell["p_kpa"], a["status"]))
    thick = cell["family"] == "thick_plastic"
    if thick and not fac["thick_ok"]:
        reasons.append("thick samples need a long-duration facility")
    m = fcfg["measurands"][measurand]
    need = m.get("min_time_s_thick" if thick else "min_time_s_thin", 0)
    if measurand == "go_no_go" and thick and not fac["thick_ok"]:
        reasons.append("go/no-go on thick samples needs a long-duration facility")
    if t < need:
        reasons.append("%.1f s is shorter than the %.0f s a %s needs" % (t, need, measurand.replace("_", " ")))
    return (not reasons), reasons, g, t


def candidates(gaps, fcfg, w):
    out = []
    for gcell in gaps:
        for fac in fcfg["facilities"]:
            for meas in ("spread_rate", "go_no_go"):
                ok, why, g, t = feasible(fac, gcell, meas, fcfg)
                if not ok:
                    continue
                score = gcell["value"] * w["measurand_value"][meas] / (fac["cost_tier"] * w.get("cost_scale", {}).get(fac["id"], 1.0))
                out.append({"cell_id": gcell["cell_id"], "habitat": gcell["habitat"], "habitat_name": gcell["habitat_name"], "family": gcell["family"],
                            "direction": gcell["direction"], "status": gcell["status"], "o2_pct": gcell["o2_pct"], "p_psia": gcell["p_psia"],
                            "g_class": gcell["g_class"], "facility": fac["id"], "facility_name": fac["name"], "g_level": g, "test_time_s": t,
                            "measurand": meas, "cost_tier": fac["cost_tier"], "risk": gcell["risk"], "gap": gcell["gap"], "score": score})
    return out


def plan_tests(cands, top=5):
    """Pick tests one at a time; after each pick the cell it closes no longer counts, so two tests never close the same gap."""
    chosen, closed = [], set()
    pool = sorted(cands, key=lambda c: (-c["score"], -c["test_time_s"], c["cost_tier"], c["facility"]))
    for c in pool:
        if len(chosen) >= top:
            break
        if c["cell_id"] in closed:
            continue
        chosen.append(c)
        closed.add(c["cell_id"])
    return chosen


def infeasible_gaps(gaps, fcfg):
    out = []
    for gcell in gaps:
        any_ok = any(feasible(f, gcell, m, fcfg)[0] for f in fcfg["facilities"] for m in ("spread_rate", "go_no_go"))
        if not any_ok:
            why = sorted({r for f in fcfg["facilities"] for m in ("spread_rate", "go_no_go") for r in feasible(f, gcell, m, fcfg)[1]})
            out.append({"cell_id": gcell["cell_id"], "value": gcell["value"], "why": why[:4]})
    return out


def is_lunar(c):
    return c["g_class"] == "lunar"


def is_luci_like(c):
    return c["g_class"] == "lunar" and c["family"] in ("thin_fabric", "thick_plastic") and c["measurand"] == "spread_rate"


def perturb(w, rng, spread=0.5):
    w2 = copy.deepcopy(w)
    for key in ("habitat_priority", "material_commonness", "direction_factor", "measurand_value"):
        for k in w2[key]:
            w2[key][k] *= rng.uniform(1 - spread, 1 + spread)
    w2["status_gap"]["bounded"] *= rng.uniform(1 - spread, 1 + spread)
    w2["oxygen_exponent"] = w2.get("oxygen_exponent", 1.0) * rng.uniform(1 - spread, 1 + spread)
    w2["cost_scale"] = {}
    return w2


def kendall_tau(a, b):
    from scipy.stats import kendalltau
    return kendalltau(a, b).statistic


def weight_sensitivity(table, fcfg, w, draws=1000, spread=0.5, seed=2026, top=5):
    rng = random.Random(seed)
    base_c = candidates(rank_gaps(table, w), fcfg, w)
    key = lambda c: (c["cell_id"], c["facility"], c["measurand"])
    base_scores = {key(c): c["score"] for c in base_c}
    fac_ids = [f["id"] for f in fcfg["facilities"]]
    lunar = luci = 0
    taus, top_sets = [], {}
    for _ in range(draws):
        w2 = perturb(w, rng, spread)
        w2["cost_scale"] = {f: rng.uniform(1 - spread, 1 + spread) for f in fac_ids}
        c2 = candidates(rank_gaps(table, w2), fcfg, w2)
        p2 = plan_tests(c2, top)
        lunar += any(is_lunar(c) for c in p2)
        luci += any(is_luci_like(c) for c in p2)
        s2 = {key(c): c["score"] for c in c2}
        common = [k for k in base_scores if k in s2]
        taus.append(kendall_tau([base_scores[k] for k in common], [s2[k] for k in common]))
        for c in p2:
            top_sets[c["cell_id"]] = top_sets.get(c["cell_id"], 0) + 1
    taus.sort()
    return {"draws": draws, "spread": spread, "seed": seed, "lunar_in_top5_share": lunar / draws, "luci_like_in_top5_share": luci / draws,
            "kendall_tau_median": taus[len(taus) // 2], "kendall_tau_p10": taus[int(0.1 * len(taus))], "kendall_tau_min": taus[0],
            "cell_in_top5_share": {k: v / draws for k, v in sorted(top_sets.items(), key=lambda kv: -kv[1])}}


def null_lunar_probability(cands, top=5):
    """Chance that five cells drawn at random from the feasible gap cells include at least one lunar cell."""
    cells_ = {}
    for c in cands:
        cells_[c["cell_id"]] = is_lunar(c)
    n, l = len(cells_), sum(cells_.values())
    if n < top:
        return 1.0 if l else 0.0, n, l
    return 1 - math.comb(n - l, top) / math.comb(n, top), n, l


def null_strict_probability(cands, top=5, trials=20000, seed=2026):
    """Monte Carlo: five random gap cells, each with a random feasible facility and measurand; chance one is LUCI-like."""
    rng = random.Random(seed)
    by_cell = {}
    for c in cands:
        by_cell.setdefault(c["cell_id"], []).append(c)
    ids = sorted(by_cell)
    hits = 0
    for _ in range(trials):
        pick = rng.sample(ids, min(top, len(ids)))
        hits += any(is_luci_like(rng.choice(by_cell[i])) for i in pick)
    return hits / trials


def burn_distances(rates, facilities_times):
    return [{"rate_label": lab, "rate_cm_s": r, "distances_cm": {name: physics.burn_distance_cm(r, t) for name, t in facilities_times}} for lab, r in rates]
