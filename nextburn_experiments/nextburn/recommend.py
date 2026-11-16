"""Step 5: rank candidate tests by how much each would reduce uncertainty at the operating points that matter most.

For each feasible candidate, the expected posterior variance of P(sustained) at every weighted operating point is computed
after one more burn at the candidate condition (both possible outcomes, weighted by the model's own prediction), using
importance reweighting of the posterior samples. The ranking score is the weighted variance reduction.
"""
import json
import os

import numpy as np

from . import boundary, envelope, ingest, units

O2_LEVELS = [21.0, 30.0, 34.0, 37.0]
P_LEVELS_PSIA = [8.2, 10.2, 14.7]
CLASS_G = {"micro": 0.0, "lunar": 0.16, "mars": 0.38, "earth": 1.0}


def _levels(fac):
    out = []
    for x in fac["gravity_levels"]:
        out.append(units.G_LUNAR if x == "lunar_nominal" else units.g_from_spin(11, 1.22) if x == "luci_spin" else float(x))
    return out


def candidates(fcfg):
    out = []
    for fac in fcfg["facilities"]:
        if not fac.get("available", True):
            continue
        a = fac["atmosphere"]
        for g in _levels(fac):
            gc = ingest.g_class(g)
            if gc not in CLASS_G:
                continue
            for o2 in O2_LEVELS:
                for psia in P_LEVELS_PSIA:
                    kpa = units.psia_to_kpa(psia)
                    if o2 > a.get("o2_max_pct", 100) or o2 < a.get("o2_min_pct", 0) or not (a.get("p_min_kpa", 0) <= kpa <= a.get("p_max_kpa", 1e9)):
                        continue
                    if fac["test_time_s"] < fcfg["measurands"]["go_no_go"]["min_time_s_thin"]:
                        continue
                    for d in (1, -1):
                        out.append({"facility": fac["id"], "facility_name": fac["name"], "cost_tier": fac["cost_tier"], "test_time_s": fac["test_time_s"],
                                    "g": g, "g_class": gc, "o2_pct": o2, "p_psia": psia, "p_kpa": kpa, "dir": d,
                                    "assumed_flow": "forced flow at or above 5 cm/s" if gc == "micro" else "buoyant flow only"})
    return out


def targets():
    t = []
    for op in envelope.ENV["operating_points"]:
        for d in (1, -1):
            t.append(dict(op, dir=d, p_kpa=units.psia_to_kpa(op["p_psia"])))
    return t


def rank(model, material, fcfg, top=10):
    T = targets()
    w = np.array([t["weight"] for t in T])
    Pt = model.prob(boundary.features([t["o2_pct"] for t in T], [t["p_kpa"] for t in T], [t["g"] for t in T], [t["dir"] for t in T]), material)
    V0 = Pt.var(axis=0)
    C = candidates(fcfg)
    Pc = model.prob(boundary.features([c["o2_pct"] for c in C], [c["p_kpa"] for c in C], [c["g"] for c in C], [c["dir"] for c in C]), material)
    p1 = Pc.mean(0)
    W1 = Pc / Pc.sum(0)
    W0 = (1 - Pc) / (1 - Pc).sum(0)
    v1 = W1.T @ (Pt ** 2) - (W1.T @ Pt) ** 2
    v0 = W0.T @ (Pt ** 2) - (W0.T @ Pt) ** 2
    ev = p1[:, None] * v1 + (1 - p1)[:, None] * v0
    evr = (V0[None, :] - ev) @ w
    total = float(V0 @ w)
    for k, c in enumerate(C):
        c.update(p_sustain_now=float(p1[k]), evr=float(evr[k]), evr_pct=float(100 * evr[k] / total), evr_per_cost=float(evr[k] / c["cost_tier"]))
    best = {}
    for c in sorted(C, key=lambda c: (-c["evr"], c["cost_tier"], -c["test_time_s"])):
        key = (c["g_class"], c["o2_pct"], c["p_psia"], c["dir"])
        if key not in best:
            best[key] = c
    ranked = sorted(best.values(), key=lambda c: -c["evr"])
    for i, c in enumerate(ranked):
        c["rank"] = i + 1
    by_target = []
    for i, t in enumerate(T):
        by_target.append({"id": t["id"], "name": t["name"], "dir": t["dir"], "weight": t["weight"], "variance_now": float(V0[i]),
                          "p_mean_now": float(Pt[:, i].mean())})
    return {"material": material, "total_weighted_variance_now": total, "candidates_evaluated": len(C), "distinct_conditions": len(ranked),
            "top": ranked[:top], "targets": by_target}


def greedy_plan(model, material, fcfg, k=10, max_samples=4000, seed=11):
    """Choose tests one at a time, each given the ones already chosen (all outcome combinations weighted by the model),
    like adding directed tests until the coverage holes that matter are closed. Returns the plan and the cumulative curve."""
    T = targets()
    w = np.array([t["weight"] for t in T])
    rng = np.random.default_rng(seed)
    idx = rng.choice(model.samples.shape[0], size=min(max_samples, model.samples.shape[0]), replace=False)
    B = model.samples[idx]
    mi = model.materials.index(material)

    def prob(X):
        eta = B[:, :boundary.NB] @ np.atleast_2d(X).T + B[:, boundary.NB + mi][:, None]
        return 1.0 / (1.0 + np.exp(-eta))

    best = {}
    for c in sorted(candidates(fcfg), key=lambda c: (c["cost_tier"], -c["test_time_s"])):
        best.setdefault((c["g_class"], c["o2_pct"], c["p_psia"], c["dir"]), c)
    C = list(best.values())
    Pc = prob(boundary.features([c["o2_pct"] for c in C], [c["p_kpa"] for c in C], [c["g"] for c in C], [c["dir"] for c in C]))
    Pt = prob(boundary.features([t["o2_pct"] for t in T], [t["p_kpa"] for t in T], [t["g"] for t in T], [t["dir"] for t in T]))
    S = B.shape[0]
    v0 = float(Pt.var(axis=0) @ w)
    W = np.ones((S, 1))
    plan, chosen = [], []
    for step in range(k):
        ev = np.zeros(len(C))
        for j in range(W.shape[1]):
            for A in (W[:, j:j + 1] * Pc, W[:, j:j + 1] * (1 - Pc)):
                tot = A.sum(0)
                N = A / np.where(tot > 0, tot, 1.0)
                M = N.T @ Pt
                var = (N.T @ (Pt ** 2) - M ** 2) @ w
                ev += (tot / S) * var
        ev[chosen] = np.inf
        c = int(np.argmin(ev))
        chosen.append(c)
        W = np.concatenate([W * Pc[:, c:c + 1], W * (1 - Pc[:, c:c + 1])], axis=1)
        item = dict(C[c], step=step + 1, p_sustain_now=float(Pc[:, c].mean()), expected_weighted_variance_after=float(ev[c]),
                    cumulative_reduction_pct=float(100 * (1 - ev[c] / v0)))
        item["added_reduction_pct"] = item["cumulative_reduction_pct"] - (plan[-1]["cumulative_reduction_pct"] if plan else 0.0)
        plan.append(item)
    return {"material": material, "weighted_variance_now": v0, "distinct_conditions": len(C), "samples_used": S, "plan": plan}
