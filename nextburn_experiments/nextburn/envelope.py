"""Steps 2 and 3: the operating envelope and a binned coverage report (tested, nearby or none)."""
import json
import math
import os

from . import ingest, units

ENV = json.load(open(os.path.join(ingest.CONFIG, "envelope.json")))
O2E, PE = ENV["bins"]["o2_edges"], ENV["bins"]["p_psia_edges"]


def bin_index(edges, v):
    for i in range(len(edges) - 1):
        if edges[i] <= v < edges[i + 1]:
            return i
    return None


def overlapping(edges, lo, hi):
    return [i for i in range(len(edges) - 1) if lo < edges[i + 1] and hi >= edges[i]]


def placement(tp):
    o2, plo, phi = tp.get("o2_pct"), tp.get("p_lo_kpa"), tp.get("p_hi_kpa")
    if o2 is None and tp.get("o2_lo_pct") is not None and tp.get("o2_hi_pct") is not None:
        o2 = (tp["o2_lo_pct"] + tp["o2_hi_pct"]) / 2
    p = tp.get("p_kpa")
    if p is None and plo is not None and phi is not None:
        p = (plo + phi) / 2
    if o2 is None or p is None or tp.get("g") is None:
        return None
    return o2, units.kpa_to_psia(p)


def region_bins():
    r = ENV["region"]
    oi = [i for i in range(len(O2E) - 1) if O2E[i] >= r["o2_pct"][0] - 1e-9 and O2E[i + 1] <= r["o2_pct"][1] + 1e-9]
    pi = [j for j in range(len(PE) - 1) if PE[j] >= r["p_psia"][0] - 1e-9 and PE[j + 1] <= r["p_psia"][1] + 1e-9]
    return oi, pi


def coverage(ledger, family):
    tests = [t for t in ledger if t["family"] == family and t.get("outcome") != "planned"]
    panels, unplaced = {}, []
    for t in tests:
        if placement(t) is None:
            unplaced.append({"tp_id": t["tp_id"], "label": t["label"], "g_class": t.get("g_class"), "why": "oxygen or pressure not stated, or bounded on one side"})
    for pan in ENV["panels"]:
        gc = pan["g_class"]
        grid = {(i, j): {"o2_bin": [O2E[i], O2E[i + 1]], "p_psia_bin": [PE[j], PE[j + 1]], "tests": [], "outcomes": {}, "range_overlap": []}
                for i in range(len(O2E) - 1) for j in range(len(PE) - 1)}
        for t in tests:
            if t.get("g_class") != gc:
                continue
            pl = placement(t)
            if pl is None:
                continue
            i, j = bin_index(O2E, pl[0]), bin_index(PE, pl[1])
            if i is None or j is None:
                unplaced.append({"tp_id": t["tp_id"], "label": t["label"], "g_class": gc, "why": "outside the bin grid"})
                continue
            grid[(i, j)]["tests"].append(t["tp_id"])
            grid[(i, j)]["outcomes"][t["outcome"]] = grid[(i, j)]["outcomes"].get(t["outcome"], 0) + 1
            olo = t.get("o2_lo_pct") if t.get("o2_lo_pct") is not None else pl[0]
            ohi = t.get("o2_hi_pct") if t.get("o2_hi_pct") is not None else pl[0]
            plo = units.kpa_to_psia(t["p_lo_kpa"]) if t.get("p_lo_kpa") is not None else pl[1]
            phi = units.kpa_to_psia(t["p_hi_kpa"]) if t.get("p_hi_kpa") is not None else pl[1]
            for a in overlapping(O2E, olo, ohi):
                for b in overlapping(PE, plo, phi):
                    if (a, b) != (i, j):
                        grid[(a, b)]["range_overlap"].append(t["tp_id"])
        for (i, j), c in grid.items():
            if c["tests"]:
                c["status"] = "tested"
            else:
                adj = [grid[(a, b)]["tests"] for a in (i - 1, i, i + 1) for b in (j - 1, j, j + 1) if (a, b) in grid and (a, b) != (i, j)]
                c["status"] = "nearby" if any(adj) or c["range_overlap"] else "none"
                c["nearby_tests"] = sorted({x for lst in adj for x in lst} | set(c["range_overlap"]))
        panels[gc] = grid
    oi, pi = region_bins()
    summary = {}
    for gc in ENV["region"]["g_classes"]:
        cells = [panels[gc][(i, j)]["status"] for i in oi for j in pi]
        summary[gc] = {s: cells.count(s) for s in ("tested", "nearby", "none")}
        summary[gc]["bins"] = len(cells)
    tot = {s: sum(summary[g][s] for g in summary) for s in ("tested", "nearby", "none")}
    tot["bins"] = sum(summary[g]["bins"] for g in summary)
    ops = []
    for op in ENV["operating_points"]:
        i, j = bin_index(O2E, op["o2_pct"]), bin_index(PE, op["p_psia"])
        cell = panels[op["g_class"]][(i, j)]
        ops.append({"id": op["id"], "name": op["name"], "status": cell["status"], "tests_in_bin": cell["tests"],
                    "nearby_tests": cell.get("nearby_tests", []), "nearest_any_gravity": nearest(op, tests)})
    return {"family": family, "panels": panels, "summary_by_gravity": summary, "summary_total": tot, "operating_points": ops, "unplaced": unplaced}


def nearest(op, tests, k=3):
    out = []
    for t in tests:
        pl = placement(t)
        if pl is None:
            continue
        d = math.sqrt(((pl[0] - op["o2_pct"]) / 3.0) ** 2 + (math.log(pl[1] / op["p_psia"]) / math.log(1.3)) ** 2)
        out.append({"tp_id": t["tp_id"], "label": t["label"], "o2_pct": round(pl[0], 2), "p_psia": round(pl[1], 2), "g_class": t.get("g_class"),
                    "outcome": t.get("outcome"), "distance_ignoring_gravity": round(d, 2), "same_gravity": t.get("g_class") == op["g_class"]})
    return sorted(out, key=lambda x: x["distance_ignoring_gravity"])[:k]


def bins_rows(cov):
    out = []
    for gc, grid in cov["panels"].items():
        for (i, j), c in sorted(grid.items()):
            out.append([cov["family"], gc, "%g-%g" % tuple(c["o2_bin"]), "%g-%g" % tuple(c["p_psia_bin"]), c["status"], len(c["tests"]),
                        ";".join(c["tests"]), ";".join("%s:%d" % kv for kv in sorted(c["outcomes"].items())), ";".join(c.get("nearby_tests", []))])
    return out
