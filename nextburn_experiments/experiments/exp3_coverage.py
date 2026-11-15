"""Experiment 3: coverage sensitivity. Usage: python experiments/exp3_coverage.py"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nextburn import coverage, ingest, report, units  # noqa: E402

O2_TOLS, P_TOLS, DEFAULT = (1, 2, 4), (0.10, 0.20), (2, 0.10)


def main():
    out = report.exp_dir(3)
    rows, norm, pts, meta = ingest.build()
    planned = ingest.test_points(norm, include_roles=("planned",))
    cl = coverage.cells()
    runs = coverage.sensitivity(cl, pts, O2_TOLS, P_TOLS, planned)
    nog = coverage.sensitivity(cl, pts, O2_TOLS, P_TOLS, planned, same_g_class=False)
    flips = {}
    for r in nog:
        for c in r["table"]:
            if c["status"] == "tested" and c["g_class"] != "micro":
                flips.setdefault(c["cell_id"], []).append({"tol_o2_pts": r["tol_o2_pts"], "tol_p_frac": r["tol_p_frac"], "matches": c["matches"]})
    by_cell = {c["cell_id"]: [] for c in cl}
    for r in runs:
        for c in r["table"]:
            by_cell[c["cell_id"]].append(c["status"])
    default = [r for r in runs if (r["tol_o2_pts"], r["tol_p_frac"]) == DEFAULT][0]["table"]
    dist = {c["cell_id"]: coverage.distance_status(c, pts) for c in cl}
    mf = {c["cell_id"]: coverage.microfire_status(c, pts) for c in cl}
    near = {h["id"]: {fam: coverage.nearest_evidence([c for c in cl if c["habitat"] == h["id"] and c["family"] == fam][0], pts)
                      for fam in ingest.PRESETS["material_families"]} for h in ingest.PRESETS["habitats"]}
    moon = [c for c in cl if c["habitat"] == "moon_base"]
    moon_tested = [sum(1 for c in r["table"] if c["habitat"] == "moon_base" and c["status"] == "tested") for r in runs]
    holds = all(x == 0 for x in moon_tested) and all(dist[c["cell_id"]]["status"] != "tested" for c in moon) and all(mf[c["cell_id"]]["status"] == "unknown" for c in moon)
    tested_range = [min(r["counts"]["tested"] for r in runs), max(r["counts"]["tested"] for r in runs)]
    bounded_range = [min(r["counts"]["bounded"] for r in runs), max(r["counts"]["bounded"] for r in runs)]
    untested_range = [min(r["counts"]["untested"] for r in runs), max(r["counts"]["untested"] for r in runs)]
    per_hab = {}
    for h in ingest.PRESETS["habitats"]:
        vals = [sum(1 for c in r["table"] if c["habitat"] == h["id"] and c["status"] == "tested") for r in runs]
        per_hab[h["id"]] = {"name": h["name"], "cells": 6, "tested_min": min(vals), "tested_max": max(vals),
                            "share_tested_range": [min(vals) / 6, max(vals) / 6]}
    vi2 = [tp for tp in pts if tp["label"] == "Saffire VI-2"][0]
    result = {
        "experiment": 3, "title": "Coverage sensitivity", "generated_at": report.now_iso(),
        "ledger_sha256": report.sha256_file(ingest.DEFAULT_LEDGER), "presets_sha256": report.sha256_file(os.path.join(ROOT, "config", "presets.json")),
        "cells": len(cl), "test_points": len(pts), "planned_points": len(planned),
        "runs": [{"tol_o2_pts": r["tol_o2_pts"], "tol_p_frac": r["tol_p_frac"], "counts": r["counts"], "shares": r["shares"]} for r in runs],
        "ranges": {"tested": tested_range, "bounded": bounded_range, "untested": untested_range},
        "per_habitat": per_hab,
        "headline": {"claim": "The Moon-base atmosphere (34% oxygen at 8.2 psia) has no direct test in lunar gravity",
                     "holds_in_all_runs": holds, "moon_base_tested_cells_per_run": moon_tested,
                     "cross_checks": {"normalized_distance": all(dist[c["cell_id"]]["status"] != "tested" for c in moon),
                                      "microfire_bins": all(mf[c["cell_id"]]["status"] == "unknown" for c in moon)}},
        "nearest_evidence_moon_base": near["moon_base"],
        "gravity_ignored_check": {"what": "Same six runs with the gravity axis ignored, to show which cells only lack a gravity match",
                                  "runs": [{"tol_o2_pts": r["tol_o2_pts"], "tol_p_frac": r["tol_p_frac"], "counts": r["counts"]} for r in nog],
                                  "cells_that_become_tested": flips,
                                  "reading": "Cells listed here have an orbit test at nearly the same atmosphere; their gap is gravity, not atmosphere."},
        "ledger_gaps": {c["cell_id"]: c["unstated"] for c in runs[0]["table"] if c["status"] != "tested" and c["unstated"]},
        "saffire_vi2_note": {"p_kpa": vi2["p_kpa"], "p_psia": units.kpa_to_psia(vi2["p_kpa"]), "o2_pct": vi2["o2_pct"], "gravity": vi2["g_class"],
                             "statement": "Nearest flight evidence, not a test of the Moon-base case: it burned in microgravity with forced flow"},
        "cells_detail": [dict(c, statuses_by_run=by_cell[c["cell_id"]], distance_check=dist[c["cell_id"]], microfire=mf[c["cell_id"]]) for c in default],
        "default_tolerance": {"tol_o2_pts": DEFAULT[0], "tol_p_frac": DEFAULT[1]},
        "pass": holds, "pass_rule": "The Moon-base headline holds in all six tolerance runs and in both cross-checks; coverage is reported as a range",
        "limits": ["Flow is not matched because habitat presets do not set a flow; ignoring flow makes matching more lenient, so 'untested' is conservative.",
                   "BASS-II rows from the poster lack pressure, so they cannot match any cell; the PSI-25 table would add them.",
                   "Rows whose direction is not stated (Saffire I to III, LUCI 1-g) cannot match a direction class."],
    }
    report.write_json(os.path.join(out, "results.json"), result)
    with open(os.path.join(out, "coverage_cells.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cell_id", "habitat", "family", "direction", "status_default", "statuses_by_run", "matches", "planned", "not_proven_safe", "microfire_bin", "microfire_status", "best_distance"])
        for c in result["cells_detail"]:
            w.writerow([c["cell_id"], c["habitat"], c["family"], c["direction"], c["status"], ";".join(c["statuses_by_run"]), ";".join(c["matches"]),
                        ";".join(c["planned"]), c["not_proven_safe"], c["microfire"]["bin"], c["microfire"]["status"],
                        "" if c["distance_check"]["best_distance"] is None else round(c["distance_check"]["best_distance"], 3)])
    report.dashboard("exp3_coverage.json", {"title": result["title"], "headline": result["headline"], "ranges": result["ranges"], "per_habitat": per_hab,
                                            "runs": result["runs"], "cells": [{k: c[k] for k in ("cell_id", "habitat", "habitat_name", "family", "direction", "status", "statuses_by_run", "matches", "planned", "not_proven_safe")} for c in result["cells_detail"]],
                                            "nearest_evidence_moon_base": near["moon_base"],
        "gravity_ignored_check": {"what": "Same six runs with the gravity axis ignored, to show which cells only lack a gravity match",
                                  "runs": [{"tol_o2_pts": r["tol_o2_pts"], "tol_p_frac": r["tol_p_frac"], "counts": r["counts"]} for r in nog],
                                  "cells_that_become_tested": flips,
                                  "reading": "Cells listed here have an orbit test at nearly the same atmosphere; their gap is gravity, not atmosphere."},
        "ledger_gaps": {c["cell_id"]: c["unstated"] for c in runs[0]["table"] if c["status"] != "tested" and c["unstated"]}, "generated_at": result["generated_at"]})
    # heatmap
    plt = report.plt()
    import numpy as np
    habs = ingest.PRESETS["habitats"]
    cols = [(f, d) for f in ingest.PRESETS["material_families"] for d in ingest.PRESETS["direction_classes"]]
    code = {"tested": 2, "bounded": 1, "untested": 0}
    M = np.zeros((len(habs), len(cols)))
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    from matplotlib.colors import ListedColormap
    for i, h in enumerate(habs):
        for j, (f, d) in enumerate(cols):
            c = [x for x in result["cells_detail"] if x["habitat"] == h["id"] and x["family"] == f and x["direction"] == d][0]
            M[i, j] = code[c["status"]]
            nt = sum(1 for s in c["statuses_by_run"] if s == "tested")
            label = {"tested": "tested", "bounded": "bounded", "untested": "untested"}[c["status"]]
            ax.text(j, i, "%s\n%d/6 runs tested%s" % (label, nt, "\nFM2 planned" if c["planned"] else ""), ha="center", va="center", fontsize=7, color="white")
    ax.imshow(M, cmap=ListedColormap([report.COLORS["untested"], report.COLORS["bounded"], report.COLORS["tested"]]), vmin=0, vmax=2, aspect="auto")
    ax.set_yticks(range(len(habs)), ["%s\n%g%% O2, %g psia" % (h["name"], h["o2_pct"], h["p_psia"]) for h in habs], fontsize=8)
    lab = {"thin_fabric": "Thin fabric", "thick_plastic": "PMMA", "other_textile": "Other textile", "with_flow": "up/concurrent", "against_flow": "down/opposed"}
    ax.set_xticks(range(len(cols)), ["%s\n%s" % (lab[f], lab[d]) for f, d in cols], fontsize=8)
    ax.set_title("Experiment 3: coverage at oxygen +/-%d points, pressure +/-%d%% (status in 6 tolerance runs)" % (DEFAULT[0], DEFAULT[1] * 100), fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(out, "chart.png")); plt.close(fig)
    rows_md = [["oxygen +/-%d pts, pressure +/-%d%%" % (r["tol_o2_pts"], r["tol_p_frac"] * 100), r["counts"]["tested"], r["counts"]["bounded"], r["counts"]["untested"]] for r in runs]
    hab_md = [[v["name"], "%d to %d of 6" % (v["tested_min"], v["tested_max"])] for v in per_hab.values()]
    near_md = [[fam, n["label"], "%.1f%%" % n["o2_pct"] if n["o2_pct"] else "", "%.2f psia" % n["p_psia"] if n["p_psia"] else "", n["g_class"], "%.1f" % n["distance"], "; ".join(n["differences"])]
               for fam, lst in near["moon_base"].items() for n in lst[:1]]
    md = ["# Experiment 3: Coverage sensitivity", "", "Generated %s. %d cells (5 habitats x 3 material families x 2 flame directions), %d NASA test points, %d planned FM2 points (never counted as evidence)." % (result["generated_at"], len(cl), len(pts), len(planned)), "",
          "**Headline:** %s. Holds in all six runs: **%s**. Normalized-distance cross-check: %s. MicroFire oxygen-bin cross-check: %s." % (result["headline"]["claim"], holds, result["headline"]["cross_checks"]["normalized_distance"], result["headline"]["cross_checks"]["microfire_bins"]), "",
          "Coverage across the six runs: tested %d to %d cells, bounded %d to %d, untested %d to %d (of %d)." % (tested_range[0], tested_range[1], bounded_range[0], bounded_range[1], untested_range[0], untested_range[1], len(cl)), "",
          report.md_table(["Tolerance", "Tested", "Bounded", "Untested"], rows_md), "", report.md_table(["Habitat", "Cells tested across runs"], hab_md), "",
          "## Nearest evidence to the Moon-base atmosphere (ignoring gravity)", "", report.md_table(["Family", "Test", "Oxygen", "Pressure", "Gravity", "Distance", "Differences"], near_md), "",
          "## Gravity is the missing axis", "", "With gravity ignored, these partial-gravity cells would count as tested: %s." % ("; ".join("%s (at %s)" % (k, ", ".join("oxygen +/-%d, pressure +/-%d%%" % (x["tol_o2_pts"], x["tol_p_frac"] * 100) for x in v)) for k, v in flips.items()) or "none"), "",
          "Cells left untested because a cited source does not state oxygen or pressure (ledger gaps, not NASA gaps): %s." % ("; ".join("%s: %s" % (k, ", ".join(v)) for k, v in result["ledger_gaps"].items()) or "none"), "",
          "Saffire VI-2 burned at %.2f psia and %.1f%% oxygen in microgravity with forced flow: nearby evidence, never a test of the Moon-base case." % (units.kpa_to_psia(vi2["p_kpa"]), vi2["o2_pct"]), "",
          "## Limits", ""] + ["- " + x for x in result["limits"]] + ["", "Rerun: `python experiments/exp3_coverage.py`.", ""]
    report.write_text(os.path.join(out, "results.md"), "\n".join(md))
    print("Experiment 3: headline holds=%s; tested %s, bounded %s, untested %s" % (holds, tested_range, bounded_range, untested_range))
    for v in per_hab.values():
        print("  ", v["name"], v["tested_min"], v["tested_max"])
    for fam, lst in near["moon_base"].items():
        print("  nearest", fam, [(n["label"], round(n["distance"], 1), n["differences"]) for n in lst[:2]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
