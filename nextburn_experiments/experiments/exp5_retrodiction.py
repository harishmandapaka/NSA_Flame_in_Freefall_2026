"""Experiment 5: planner retrodiction with weights frozen in advance. Usage: python experiments/exp5_retrodiction.py [--draws 1000]"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nextburn import coverage, ingest, planner, report, units  # noqa: E402

SHORT = {"iss_cabin": "Station cabin (21%, 14.7 psia)", "moon_base": "Moon base (34%, 8.2 psia)", "moon_upper": "Moon base upper bound (30%, 10.2 psia)",
         "spacesuit": "Spacesuit (100%, 4.3 psia)", "mars_hab": "Mars habitat (34%, 8.2 psia)"}
LAB = {"thin_fabric": "thin fabric", "thick_plastic": "PMMA", "other_textile": "other textile", "with_flow": "upward/concurrent",
       "against_flow": "downward/opposed", "spread_rate": "spread-rate measurement", "go_no_go": "go/no-go limit test"}


def rationale(c):
    return ("%s (%g%% oxygen, %g psia, %s gravity), %s, %s: %s in the evidence so far. %s gives %s g for about %g s, enough for a %s. "
            "Risk weight %.2f, gap weight %.1f, cost tier %d." % (c["habitat_name"], c["o2_pct"], c["p_psia"], c["g_class"], LAB[c["family"]], LAB[c["direction"]],
                                                               c["status"], c["facility_name"], "%.3f" % c["g_level"], c["test_time_s"], LAB[c["measurand"]],
                                                               c["risk"], c["gap"], c["cost_tier"]))


def slim(c):
    keep = ("cell_id", "habitat", "habitat_name", "family", "direction", "status", "o2_pct", "p_psia", "g_class", "facility", "facility_name",
            "g_level", "test_time_s", "measurand", "cost_tier", "risk", "gap", "score")
    return dict({k: c[k] for k in keep}, lunar=planner.is_lunar(c), luci_like=planner.is_luci_like(c), rationale=rationale(c))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=1000)
    a = ap.parse_args(argv)
    out = report.exp_dir(5)
    wpath, fpath = os.path.join(ROOT, "config", "weights.json"), os.path.join(ROOT, "config", "facilities.json")
    w, fcfg = json.load(open(wpath)), json.load(open(fpath))
    rows, norm, pts, meta = ingest.build()
    planned = ingest.test_points(norm, include_roles=("planned",))
    cl = coverage.cells()
    pre = planner.ledger_asof(pts, 2025)
    t_pre = coverage.coverage_table(cl, pre, 2, 0.10, planned)
    t_now = coverage.coverage_table(cl, pts, 2, 0.10, planned)
    g_pre, g_now = planner.rank_gaps(t_pre, w), planner.rank_gaps(t_now, w)
    c_pre, c_now = planner.candidates(g_pre, fcfg, w), planner.candidates(g_now, fcfg, w)
    p_pre, p_now = planner.plan_tests(c_pre, 5), planner.plan_tests(c_now, 5)
    sens = planner.weight_sensitivity(t_pre, fcfg, w, draws=a.draws, spread=0.5, seed=2026)
    null_p, n_cells, n_lunar = planner.null_lunar_probability(c_pre)
    null_strict = planner.null_strict_probability(c_pre)
    rates = [("Acrylic rod tip, %s" % "0.15 cm/s [R007]", 0.15), ("Fabric tip, 1.1 mm/s [R002]", 0.11), ("Fabric base, 0.92 mm/s [R001]", 0.092)]
    times = [("2.2 s drop", 2.2), ("5.18 s drop", 5.18), ("NASA parabola, about 20 s", 20.0), ("Novespace 0.16 g, up to 25 s", 25.0), ("New Shepard spin, about 120 s", 120.0)]
    burn = planner.burn_distances(rates, times)
    lunar_pass = any(planner.is_lunar(c) for c in p_pre)
    luci_pass = any(planner.is_luci_like(c) for c in p_pre)
    result = {
        "experiment": 5, "title": "Planner retrodiction", "generated_at": report.now_iso(),
        "weights_sha256": report.sha256_file(wpath), "weights_frozen_at_utc": w["frozen_at_utc"], "facilities_sha256": report.sha256_file(fpath),
        "cutoff": "evidence published before 1 January 2025", "test_points_before_cutoff": len(pre), "test_points_all": len(pts),
        "excluded_after_cutoff": sorted({tp["label"] for tp in pts if tp not in pre}),
        "coverage_before_cutoff": {s: sum(1 for c in t_pre if c["status"] == s) for s in ("tested", "bounded", "untested")},
        "plan_before_cutoff": [slim(c) for c in p_pre],
        "pass": lunar_pass, "pass_rule": "A lunar-gravity solid-fuel test appears in the top five with weights frozen in advance",
        "strict_check": {"luci_like_in_top5": luci_pass, "definition": "lunar gravity, thin fabric or PMMA, spread-rate measurement (what LUCI measured)"},
        "null_baseline": {"probability_random_five_include_lunar": null_p, "probability_random_five_include_luci_like": null_strict, "feasible_gap_cells": n_cells, "lunar_cells": n_lunar,
                          "reading": "If this is near 1, the basic pass criterion is weak; read the strict check and the sensitivity instead"},
        "weight_sensitivity": sens, "optional_target_80pct": sens["lunar_in_top5_share"] >= 0.8,
        "infeasible_gaps_before_cutoff": planner.infeasible_gaps(g_pre, fcfg),
        "plan_today": [slim(c) for c in p_now], "infeasible_gaps_today": planner.infeasible_gaps(g_now, fcfg),
        "burn_distance_cm": burn, "burn_distance_note": "LUCI rates were published in 2025, so this table explains facility limits after the fact; the retrodiction itself uses the facility catalogue's minimum test times, not LUCI's rates.",
        "honesty_note": "Weights were frozen before this run, but by a team that already knew LUCI flew; the null baseline and the 1,000-draw sensitivity show how much the result depends on that choice.",
    }
    report.write_json(os.path.join(out, "results.json"), result)
    report.dashboard("exp5_plan.json", {"title": result["title"], "pass": lunar_pass, "strict_luci_like": luci_pass, "plan_before_2025": result["plan_before_cutoff"],
                                        "plan_today": result["plan_today"], "sensitivity": {k: sens[k] for k in ("draws", "lunar_in_top5_share", "luci_like_in_top5_share", "kendall_tau_median", "kendall_tau_p10")},
                                        "null_baseline": result["null_baseline"], "infeasible_gaps_today": result["infeasible_gaps_today"], "burn_distance_cm": burn,
                                        "generated_at": result["generated_at"]})
    plt = report.plt()
    fig, ax = plt.subplots(1, 2, figsize=(12.5, 4.4), gridspec_kw={"width_ratios": [1.6, 1.1]})
    labels = ["%d. %s, %s, %s\n%s (%s)" % (i + 1, SHORT[c["habitat"]], LAB[c["family"]], LAB[c["direction"]].split("/")[0], c["facility_name"].split("(")[0].strip(), LAB[c["measurand"]].split(" ")[0]) for i, c in enumerate(p_pre)]
    ax[0].barh(labels, [c["score"] for c in p_pre], color=[report.COLORS["accent"] if planner.is_lunar(c) else report.COLORS["muted"] for c in p_pre])
    ax[0].invert_yaxis(); ax[0].set_xlabel("score = risk x gap x measurand value / cost tier"); ax[0].tick_params(axis="y", labelsize=7)
    ax[0].set_title("Top five tests using evidence before 2025 (dark = lunar gravity)", fontsize=9)
    vals = [sens["lunar_in_top5_share"], null_p, sens["luci_like_in_top5_share"], null_strict, sens["kendall_tau_median"]]
    ax[1].bar(["any lunar\ntest in\ntop 5", "random\npicks", "LUCI-like\ntest in\ntop 5", "random\npicks ", "Kendall\ntau\n(median)"], vals,
              color=[report.COLORS["pass"], report.COLORS["muted"], report.COLORS["pass"], report.COLORS["muted"], report.COLORS["info"]])
    for i, v in enumerate(vals):
        ax[1].text(i, v + 0.02, "%.2f" % v, ha="center", fontsize=8)
    ax[1].set_ylim(0, 1.15); ax[1].set_title("%d weight draws, each weight x0.5 to x1.5" % sens["draws"], fontsize=9); ax[1].tick_params(axis="x", labelsize=8)
    fig.suptitle("Experiment 5: the planner, run on pre-2025 evidence, recommends a lunar-gravity test", fontweight="bold", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(out, "chart.png")); plt.close(fig)
    plan_md = [[i + 1, c["habitat_name"], LAB[c["family"]], LAB[c["direction"]], c["facility_name"], LAB[c["measurand"]], "%.3f" % c["score"]] for i, c in enumerate(p_pre)]
    today_md = [[i + 1, c["habitat_name"], LAB[c["family"]], LAB[c["direction"]], c["facility_name"], LAB[c["measurand"]], "%.3f" % c["score"]] for i, c in enumerate(p_now)]
    burn_md = [[b["rate_label"]] + ["%.2f cm" % b["distances_cm"][n] for n, _ in times] for b in burn]
    md = ["# Experiment 5: Planner retrodiction", "", "Generated %s. Weights frozen %s (sha256 %s...). %s" % (result["generated_at"], w["frozen_at_utc"], result["weights_sha256"][:12], result["honesty_note"]), "",
          "Evidence before 1 January 2025: %d of %d test points (excluded: %s)." % (len(pre), len(pts), ", ".join(result["excluded_after_cutoff"])), "",
          "**Result:** lunar-gravity test in the top five: **%s**. Strict check (lunar gravity, thin fabric or PMMA, spread rate, as LUCI measured): **%s**." % (lunar_pass, luci_pass), "",
          report.md_table(["#", "Habitat", "Material", "Direction", "Facility", "Measurement", "Score"], plan_md), "",
          "**Sensitivity (%d draws, every weight and cost scaled by 0.5 to 1.5):** a lunar test stays in the top five in %.1f%% of draws (optional target 80%%: %s); a LUCI-like test in %.1f%%. Kendall's tau against the frozen ranking: median %.2f, 10th percentile %.2f." % (
              sens["draws"], 100 * sens["lunar_in_top5_share"], result["optional_target_80pct"], 100 * sens["luci_like_in_top5_share"], sens["kendall_tau_median"], sens["kendall_tau_p10"]), "",
          "**Null baseline:** five gap cells picked at random from the %d feasible ones (%d lunar) include a lunar cell with probability %.2f, and a LUCI-like test with probability %.2f. %s." % (n_cells, n_lunar, null_p, null_strict, result["null_baseline"]["reading"]), "",
          "Gaps no catalogued facility can close (before 2025): %s." % ("; ".join("%s (%s)" % (g["cell_id"], ", ".join(g["why"][:2])) for g in result["infeasible_gaps_before_cutoff"]) or "none"), "",
          "## Today's top five (all evidence, including LUCI)", "", report.md_table(["#", "Habitat", "Material", "Direction", "Facility", "Measurement", "Score"], today_md), "",
          "## Burn distance at LUCI's lunar spread rates", "", report.md_table(["Rate"] + [n for n, _ in times], burn_md), "", result["burn_distance_note"], "",
          "Rerun: `python experiments/exp5_retrodiction.py`.", ""]
    report.write_text(os.path.join(out, "results.md"), "\n".join(md))
    print("Experiment 5: lunar in top5=%s strict=%s; sens lunar=%.3f luci=%.3f tau med=%.3f p10=%.3f; null=%.3f strict-null=%.3f (%d cells, %d lunar)" % (lunar_pass, luci_pass, sens["lunar_in_top5_share"], sens["luci_like_in_top5_share"], sens["kendall_tau_median"], sens["kendall_tau_p10"], null_p, null_strict, n_cells, n_lunar))
    for i, c in enumerate(p_pre):
        print("  pre", i + 1, c["cell_id"], c["facility"], c["measurand"], round(c["score"], 3))
    for i, c in enumerate(p_now):
        print("  now", i + 1, c["cell_id"], c["facility"], c["measurand"], round(c["score"], 3))
    print("  excluded:", result["excluded_after_cutoff"], "coverage pre:", result["coverage_before_cutoff"])
    print("  infeasible:", [g["cell_id"] for g in result["infeasible_gaps_before_cutoff"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
