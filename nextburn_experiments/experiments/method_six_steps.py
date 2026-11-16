"""The six-step method: ledger, envelope, binned coverage, boundary model with decline, test ranking, FM2 predictions.

Usage: python experiments/method_six_steps.py [--sources DIR] [--no-predictions]
Writes results/method/, predictions/ (frozen FM2 predictions with SHA-256) and dashboard_data/method_*.json.
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nextburn import boundary, envelope, ingest, recommend, report, tpl, units  # noqa: E402

OUT = os.path.join(ROOT, "results", "method")
PRED = os.path.join(ROOT, "predictions")
FAM_LABEL = {"thin_fabric": "Thin fabrics and papers", "thick_plastic": "PMMA (acrylic)", "other_textile": "Other textiles"}
DLAB = {1: "upward or concurrent", -1: "downward or opposed", 0: "not stated"}
FM2_G = units.G_LUNAR


def py(o):
    if isinstance(o, dict):
        return {str(k): py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [py(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# ---------------------------------------------------------------- charts
def chart_coverage(cov, path):
    plt = report.plt()
    from matplotlib.colors import ListedColormap
    E = envelope.ENV
    o2e, pe = E["bins"]["o2_edges"], E["bins"]["p_psia_edges"]
    code = {"none": 0, "nearby": 1, "tested": 2}
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.6), sharey=True)
    for ax, pan in zip(axes, E["panels"]):
        grid = cov["panels"][pan["g_class"]]
        M = np.zeros((len(pe) - 1, len(o2e) - 1))
        for (i, j), c in grid.items():
            M[j, i] = code[c["status"]]
            if c["tests"]:
                s = c["outcomes"].get("sustained", 0)
                x = sum(v for k, v in c["outcomes"].items() if k in ("extinguished", "quench", "blowoff", "no_ignition"))
                ax.text((o2e[i] + o2e[i + 1]) / 2, (pe[j] + pe[j + 1]) / 2, "%d\n%dB %dX" % (len(c["tests"]), s, x),
                        ha="center", va="center", fontsize=6.5, color="white")
        ax.pcolormesh(o2e, pe, M, cmap=ListedColormap(["#E0E0E0", "#F9A825", "#2E7D32"]), vmin=0, vmax=2, edgecolors="white", linewidth=0.6)
        r = E["region"]
        if pan["g_class"] in r["g_classes"]:
            ax.add_patch(plt.Rectangle((r["o2_pct"][0], r["p_psia"][0]), r["o2_pct"][1] - r["o2_pct"][0], r["p_psia"][1] - r["p_psia"][0], fill=False, lw=1.6, ls="--", ec="#1F4E79"))
        for op in E["operating_points"]:
            if op["g_class"] == pan["g_class"]:
                ax.plot(op["o2_pct"], op["p_psia"], marker="*", ms=14, mec="black", mfc="#C62828")
                lab = "ISS air" if op["id"].startswith("iss") else "%g%%" % op["o2_pct"]
                ax.annotate(lab, (op["o2_pct"], op["p_psia"]), xytext=(-6, 9) if op["o2_pct"] < 36 else (2, -14), textcoords="offset points", fontsize=7, fontweight="bold")
        nun = sum(1 for u in cov["unplaced"] if u.get("g_class") == pan["g_class"])
        if nun:
            ax.text(0.02, 0.02, "%d test%s not placed (pressure or oxygen\nnot stated, or one-sided)" % (nun, "s" if nun > 1 else ""), transform=ax.transAxes, fontsize=7, color="#424242")
        s = cov["summary_by_gravity"].get(pan["g_class"])
        ax.set_title("%s%s" % (pan["label"], ("\nenvelope: %d tested, %d nearby, %d none of %d bins" % (s["tested"], s["nearby"], s["none"], s["bins"])) if s else ""), fontsize=9)
        ax.set_xlabel("oxygen (% by volume)")
    axes[0].set_ylabel("pressure (psia)")
    fig.suptitle("Step 3 coverage, %s: green = tested (count; B = burned, X = did not), amber = nearby only, grey = none; dashed box = envelope; stars = operating points" % FAM_LABEL[cov["family"]],
                 fontsize=10, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def boundary_grid(model, material):
    o2 = np.arange(14.0, 40.01, 1.0)
    ps = np.arange(1.0, 16.01, 0.5)
    O, Pp = np.meshgrid(o2, ps)
    panels = []
    for d in (1, -1):
        for pan in envelope.ENV["panels"]:
            g = pan["g"]
            res = model.answer(O.ravel(), units.psia_to_kpa(Pp.ravel()), np.full(O.size, g), np.full(O.size, d), material)
            mean = np.array([r["p_mean"] for r in res]).reshape(O.shape)
            width = np.array([r["p_hi90"] - r["p_lo90"] for r in res]).reshape(O.shape)
            declined = np.array([r["decision"] == "declined" for r in res]).reshape(O.shape)
            panels.append({"g_class": pan["g_class"], "label": pan["label"], "g": g, "dir": d, "mean": mean, "width": width, "declined": declined})
    return o2, ps, panels


def chart_boundary(model, material, grid, path):
    plt = report.plt()
    o2, ps, panels = grid
    fig, axes = plt.subplots(2, 4, figsize=(18, 8.6), sharex=True, sharey=True)
    im = None
    for ax, pan in zip(axes.ravel(), panels):
        im = ax.pcolormesh(o2, ps, pan["mean"], cmap="coolwarm", vmin=0, vmax=1, shading="nearest")
        from matplotlib.colors import ListedColormap
        masked = np.ma.masked_where(~pan["declined"], np.ones_like(pan["mean"]))
        ax.pcolormesh(o2, ps, masked, cmap=ListedColormap(["#CFCFCF"]), vmin=0, vmax=1, alpha=0.9, shading="nearest")
        live = np.ma.masked_where(pan["declined"], pan["mean"])
        if (~pan["declined"]).sum() > 3 and live.min() < 0.5 < live.max():
            ax.contour(o2, ps, live, levels=[0.5], colors="black", linewidths=1.6)
        for ob in model.obs:
            if envelope.ingest.g_class(ob["g"]) != pan["g_class"] or (ob["dir"] not in (0, pan["dir"])):
                continue
            ox = np.mean(ob["o2"]) if isinstance(ob["o2"], list) else ob["o2"]
            if isinstance(ob["p_kpa"], list):
                lo, hi = units.kpa_to_psia(ob["p_kpa"][0]), units.kpa_to_psia(ob["p_kpa"][1])
                ax.errorbar(ox, (lo + hi) / 2, yerr=[[(hi - lo) / 2], [(hi - lo) / 2]], fmt="none", ecolor="black", elinewidth=0.8, capsize=2)
                py_ = (lo + hi) / 2
            else:
                py_ = units.kpa_to_psia(ob["p_kpa"])
            ax.plot(ox, py_, marker="o" if ob["y"] == 1 else "X", ms=7, mfc="white" if ob["y"] == 1 else "black", mec="black")
        for op in envelope.ENV["operating_points"]:
            if op["g_class"] == pan["g_class"]:
                ax.plot(op["o2_pct"], op["p_psia"], marker="*", ms=13, mec="black", mfc="yellow")
        ax.set_title("%s, %s" % (pan["label"].split(" (reference")[0], DLAB[pan["dir"]]), fontsize=9)
    for ax in axes[1]:
        ax.set_xlabel("oxygen (% by volume)")
    for ax in axes[:, 0]:
        ax.set_ylabel("pressure (psia)")
    cb = fig.colorbar(im, ax=axes, shrink=0.85, pad=0.01)
    cb.set_label("P(sustained flame), posterior mean")
    fig.suptitle("Step 4 flammability boundary for %s (%s): grey = model declines (no nearby test, or 90%% interval wider than %.1f); black line = P = 0.5;\n"
                 "circles = burned, crosses = did not burn, bars = pressure range or not stated; stars = operating points" % (material, FAM_LABEL[model.family], model.cfg["decline"]["ci90_max_width"]),
                 fontsize=10, fontweight="bold")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def chart_next_tests(gp, path):
    plt = report.plt()
    top = [dict(c, rank=c["step"], evr_pct=c["cumulative_reduction_pct"]) for c in gp["plan"]]
    col = {"micro": "#546E7A", "lunar": "#1F4E79", "mars": "#C62828", "earth": "#90A4AE"}
    fig, ax = plt.subplots(figsize=(11, 0.55 * len(top) + 1.6))
    labels = ["%d. %s, %g%% O2, %g psia, %s\n%s (cost tier %d)" % (c["rank"], {"micro": "microgravity", "lunar": "Moon gravity", "mars": "Mars gravity", "earth": "1 g"}[c["g_class"]],
              c["o2_pct"], c["p_psia"], DLAB[c["dir"]], c["facility_name"].split("(")[0].strip(), c["cost_tier"]) for c in top]
    ax.barh(labels, [c["evr_pct"] for c in top], color=[col[c["g_class"]] for c in top])
    for i, c in enumerate(top):
        ax.text(c["evr_pct"], i, "  %.1f%%" % c["evr_pct"], va="center", fontsize=8)
    ax.invert_yaxis()
    ax.tick_params(axis="y", labelsize=7.5)
    ax.set_xlabel("expected reduction in weighted uncertainty at the operating points after this test and the ones above it (%)")
    ax.set_title("Step 5: next tests, each chosen given the ones above (%s)\ndark blue = Moon, red = Mars, slate = microgravity, light grey = 1 g" % gp["material"], fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def chart_fm2(preds, path):
    plt = report.plt()
    fig, ax = plt.subplots(figsize=(10, 3.6))
    for i, p in enumerate(preds):
        m = p["model"]
        c = {"sustains": "#C62828", "does not sustain": "#1F4E79", "declined": "#9E9E9E"}[m["decision"]]
        ax.plot([m["p_lo90"], m["p_hi90"]], [i, i], color=c, lw=6, alpha=0.6, solid_capstyle="butt")
        ax.plot(m["p_mean"], i, "o", color="black")
        ax.text(1.02, i, m["decision"], va="center", fontsize=9, color=c, fontweight="bold")
    ax.set_yticks(range(len(preds)), ["Burn %d: %s, %s\n%g%% O2 at %g psia, Moon" % (p["burn"], p["fuel"], p["direction"], p["o2_pct"], p["p_psia"]) for p in preds], fontsize=8)
    ax.axvline(0.5, color="grey", ls="--", lw=0.8)
    ax.set_xlim(0, 1.25)
    ax.invert_yaxis()
    ax.set_xlabel("predicted probability that the flame sustains (dot = mean, bar = 90% interval)")
    ax.set_title("Step 6: FM2 predictions, frozen before FM2 flies", fontsize=10)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------- steps
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", default=os.environ.get("NEXTBURN_SOURCES", ""))
    ap.add_argument("--no-predictions", action="store_true", help="do not rewrite the frozen FM2 predictions")
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    now = report.now_iso()

    # Step 1
    built = tpl.build(a.sources or None)
    led = built["ledger"]
    tpl.write_csv(led, os.path.join(OUT, "step1_test_point_ledger.csv"))
    gate = [c for c in built["checks"] if c["status"] == "FAIL"]
    fam_counts = {}
    for r in led:
        fam_counts.setdefault(r["family"], {}).setdefault(r["outcome"], 0)
        fam_counts[r["family"]][r["outcome"]] += 1
    s1 = {"step": 1, "title": "Test-point ledger", "generated_at": now, "test_points": len(led),
          "by_origin": {o: sum(1 for r in led if r["origin"].startswith(o)) for o in ("ledger v2", "added in v3", "derived", "PSI table")},
          "by_family_outcome": fam_counts, "with_outcome": sum(1 for r in led if r["outcome"] != "not_reported"),
          "with_source": sum(1 for r in led if r.get("sources") or r.get("source_id")), "sources": sorted({s for r in led for s in (r.get("sources") or [r.get("source_id")])}),
          "ledger_rows": len(built["rows"]), "rows_added_v3": [r["row_id"] for r in built["additions"]], "merged_rows": built["merged"],
          "outcome_quotes_checked": sum(1 for r in led for e in r["outcome_evidence"] if e.get("quote_found") is not None),
          "outcome_quotes_not_found": built["quote_problems"],
          "checks_gate": "PASS" if not gate else "FAIL", "checks_failed": [c["name"] for c in gate],
          "psi_tables": "included" if any(r["origin"] == "PSI table" for r in led) else "not included: PSI tables could not be downloaded in this session",
          "model_observations": len(built["observations"]), "excluded_from_model": built["excluded"]}
    report.write_json(os.path.join(OUT, "step1_summary.json"), py(s1))

    # Step 2
    env = envelope.ENV
    report.write_json(os.path.join(OUT, "step2_envelope.json"), {"step": 2, "title": "Operating envelope", "generated_at": now,
                      "envelope_sha256": sha(os.path.join(ROOT, "config", "envelope.json")), **env})

    # Step 3
    covs = {f: envelope.coverage(led, f) for f in ("thin_fabric", "thick_plastic", "other_textile")}
    with open(os.path.join(OUT, "step3_coverage_bins.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["family", "gravity", "o2_bin_pct", "p_bin_psia", "status", "n_tests", "tests", "outcomes", "nearby_tests"])
        for f, c in covs.items():
            w.writerows(envelope.bins_rows(c))
    for f, c in covs.items():
        chart_coverage(c, os.path.join(OUT, "coverage_%s.png" % f))
    s3 = {"step": 3, "title": "Binned coverage", "generated_at": now, "rules": env["rules"],
          "families": {f: {"summary_by_gravity": c["summary_by_gravity"], "summary_total": c["summary_total"], "operating_points": c["operating_points"],
                           "unplaced": c["unplaced"]} for f, c in covs.items()}}
    report.write_json(os.path.join(OUT, "step3_coverage.json"), py(s3))

    # Step 4
    bcfg = boundary.CFG
    obs = built["observations"]
    models, strict = {}, {}
    for fam in ("thin_fabric", "thick_plastic"):
        fo = [o for o in obs if o["family"] == fam]
        models[fam] = boundary.BoundaryModel(fam, fo).fit()
        so = [o for o in fo if not o["p_unknown"]]
        strict[fam] = boundary.BoundaryModel(fam, so).fit() if len({o["y"] for o in so}) > 0 and len(so) >= 3 else None
    prim = bcfg["primary_family"]
    ref = bcfg["reference_material"][prim]
    m = models[prim]
    grid = boundary_grid(m, ref)
    chart_boundary(m, ref, grid, os.path.join(OUT, "boundary_%s_%s.png" % (prim, ref)))
    op_rows = []
    for op in env["operating_points"]:
        for d in (1, -1):
            for mat in (ref, "new"):
                r = m.answer([op["o2_pct"]], [units.psia_to_kpa(op["p_psia"])], [op["g"]], [d], mat)[0]
                op_rows.append(dict(op_id=op["id"], name=op["name"], direction=DLAB[d], material=(mat if mat != "new" else "a new material in the family"), **r))
    with open(os.path.join(OUT, "step4_model_observations.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["obs_id", "tp_id", "family", "material", "label", "o2_pct", "p_kpa", "pressure_assumed_range", "g", "direction", "outcome", "y"])
        for o in obs:
            w.writerow([o["obs_id"], o["tp_id"], o["family"], o["material"], o["label"], o["o2"], o["p_kpa"], o["p_unknown"], round(o["g"], 4), DLAB[o["dir"]], o["outcome"], o["y"]])
    o2g, psg, pans = grid
    tot = sum(p["declined"].size for p in pans)
    s4 = {"step": 4, "title": "Flammability boundary with uncertainty and a decline rule", "generated_at": now,
          "settings_sha256": sha(os.path.join(ROOT, "config", "boundary_model.json")), "settings_frozen_at_utc": bcfg["frozen_at_utc"],
          "model": bcfg["model"], "decline_rule": bcfg["decline_rule"], "primary_family": prim, "reference_material": ref,
          "fits": {f: dict(mo.summary(), loo=mo.loo()) for f, mo in models.items()},
          "strict_fits_without_assumed_pressure": {f: (mo.summary() if mo else None) for f, mo in strict.items()},
          "grid_decline_share": float(sum(p["declined"].sum() for p in pans) / tot),
          "grid_decline_share_by_panel": [{"g_class": p["g_class"], "dir": DLAB[p["dir"]], "declined_share": float(p["declined"].mean())} for p in pans],
          "operating_points": op_rows}
    report.write_json(os.path.join(OUT, "step4_boundary.json"), py(s4))
    report.dashboard("method_boundary_grid.json", py({"family": prim, "material": ref, "o2_pct": o2g.tolist(), "p_psia": psg.tolist(),
                     "panels": [{"g_class": p["g_class"], "label": p["label"], "direction": DLAB[p["dir"]], "p_mean": np.round(p["mean"], 3).tolist(),
                                 "ci90_width": np.round(p["width"], 3).tolist(), "declined": p["declined"].astype(int).tolist()} for p in pans]}))

    # Step 5
    fcfg = json.load(open(os.path.join(ROOT, "config", "facilities.json")))
    rk = recommend.rank(m, ref, fcfg, top=10)
    gp = recommend.greedy_plan(m, ref, fcfg, k=10)
    with open(os.path.join(OUT, "step5_next_tests.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "facility", "gravity_class", "g", "o2_pct", "p_psia", "direction", "assumed_flow", "p_sustain_now", "uncertainty_reduction_pct", "cost_tier", "reduction_per_cost_tier"])
        for c in rk["top"]:
            w.writerow([c["rank"], c["facility_name"], c["g_class"], round(c["g"], 4), c["o2_pct"], c["p_psia"], DLAB[c["dir"]], c["assumed_flow"], round(c["p_sustain_now"], 3),
                        round(c["evr_pct"], 2), c["cost_tier"], round(100 * c["evr_per_cost"] / rk["total_weighted_variance_now"], 2)])
    with open(os.path.join(OUT, "step5_test_plan.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["step", "facility", "gravity_class", "g", "o2_pct", "p_psia", "direction", "assumed_flow", "p_sustain_now", "added_reduction_pct", "cumulative_reduction_pct", "cost_tier"])
        for c in gp["plan"]:
            w.writerow([c["step"], c["facility_name"], c["g_class"], round(c["g"], 4), c["o2_pct"], c["p_psia"], DLAB[c["dir"]], c["assumed_flow"], round(c["p_sustain_now"], 3),
                        round(c["added_reduction_pct"], 2), round(c["cumulative_reduction_pct"], 2), c["cost_tier"]])
    chart_next_tests(gp, os.path.join(OUT, "next_tests.png"))
    report.write_json(os.path.join(OUT, "step5_next_tests.json"), py({"step": 5, "title": "Next tests ranked by uncertainty reduction", "generated_at": now,
                      "plan": gp, "single_test_ranking": rk, "method": recommend.__doc__.strip() + " " + recommend.greedy_plan.__doc__.strip()}))

    # Step 6
    burns = [dict(burn=1, fuel="SIBAL fabric", family="thin_fabric", material="SIBAL", direction="upward", d=1, o2_pct=21.0, p_psia=14.7),
             dict(burn=2, fuel="SIBAL fabric", family="thin_fabric", material="SIBAL", direction="downward", d=-1, o2_pct=21.0, p_psia=14.7),
             dict(burn=3, fuel="4 mm acrylic (PMMA) rod", family="thick_plastic", material="PMMA rod", direction="upward", d=1, o2_pct=34.0, p_psia=8.2),
             dict(burn=4, fuel="4 mm acrylic (PMMA) rod", family="thick_plastic", material="PMMA rod", direction="downward", d=-1, o2_pct=34.0, p_psia=8.2)]
    preds = []
    for b in burns:
        mm, sm = models[b["family"]], strict[b["family"]]
        args = ([b["o2_pct"]], [units.psia_to_kpa(b["p_psia"])], [FM2_G], [b["d"]], b["material"])
        r = mm.answer(*args)[0]
        rs = sm.answer(*args)[0] if sm and b["material"] in sm.materials else None
        preds.append(dict({k: v for k, v in b.items() if k != "d"}, g=FM2_G, model={k: r[k] for k in ("p_mean", "p_lo90", "p_hi90", "decision", "reasons", "support_distance", "nearest_label", "nearest_outcome")},
                          strict_model=({k: rs[k] for k in ("p_mean", "p_lo90", "p_hi90", "decision")} if rs else None)))
    preds[1]["analog"] = {"source": "LUCI lunar-gravity spin burn of SIBAL in air at normal pressure (rows R001, R002)", "flame_base_spread_mm_s": 0.92, "flame_tip_spread_mm_s": 1.1,
                          "tolerance": "plus or minus 50% (team judgement for sample and hardware differences; not a statistical interval)",
                          "falsified_if": "the flame-base spread rate is outside 0.46 to 1.38 mm/s, or the flame-tip spread rate is outside 0.55 to 1.65 mm/s"}
    rule = {"sustained_definition": "the flame spreads away from the igniter and is still burning 10 s after the igniter turns off",
            "scoring": "Each answered burn is falsified if the observed outcome is the opposite of its decision. All four probabilities, including declined ones, are scored with the Brier score; each outcome is also checked against its 90% interval."}
    if not a.no_predictions:
        os.makedirs(PRED, exist_ok=True)
        code_files = ["nextburn/boundary.py", "nextburn/tpl.py", "config/boundary_model.json", "config/test_outcomes.json", "data/ledger_v2.json", "data/ledger_additions_v3.json"]
        doc = {"title": "NextBurn predictions for the four FM2 burns (Flammability of Materials on the Moon)", "frozen_at_utc": now,
               "status": "Published before FM2 results exist. FM2 is manifested for a CLPS lunar delivery (NTRS 20240015307); no FM2 results had been reported on the freeze date.",
               "fm2_conditions_source": "NTRS 20240015307 (FM2 poster): two SIBAL fabrics burned in air (21% oxygen at 14.7 psia) and two acrylic rods in 34% oxygen at 8.2 psia, one of each upward and downward",
               "gravity_used_g": FM2_G, "inputs_sha256": {f: sha(os.path.join(ROOT, f)) for f in code_files}, "decision_rule": bcfg["decline_rule"], "scoring_rule": rule, "predictions": preds}
        pj = os.path.join(PRED, "fm2_predictions.json")
        report.write_json(pj, py(doc))
        md = ["# NextBurn predictions for FM2 (frozen %s)" % now, "", doc["status"], "",
              "| Burn | Fuel | Direction | Atmosphere | P(sustains), 90% interval | Model answer | Nearest evidence |", "|---|---|---|---|---|---|---|"]
        for p in preds:
            mo = p["model"]
            md.append("| %d | %s | %s | %g%% O2, %g psia | %.2f (%.2f to %.2f) | %s | %s (%s) |" % (p["burn"], p["fuel"], p["direction"], p["o2_pct"], p["p_psia"], mo["p_mean"], mo["p_lo90"], mo["p_hi90"],
                      mo["decision"], mo["nearest_label"], mo["nearest_outcome"]))
        md += ["", "Burn 2 analog: LUCI measured 0.92 mm/s at the flame base and 1.1 mm/s at the tip for the same fabric in air at lunar gravity. Prediction: within plus or minus 50% of those values (team judgement).", "",
               "Sustained means: %s. %s" % (rule["sustained_definition"], rule["scoring"]), "",
               "SHA-256 of fm2_predictions.json is in SHA256SUMS.txt. Post that hash on the project page so the prediction can be checked later.", ""]
        report.write_text(os.path.join(PRED, "fm2_predictions.md"), "\n".join(md))
        with open(os.path.join(PRED, "SHA256SUMS.txt"), "w") as fh:
            for f in ("fm2_predictions.json", "fm2_predictions.md"):
                fh.write("%s  %s\n" % (sha(os.path.join(PRED, f)), f))
        chart_fm2(preds, os.path.join(OUT, "fm2_predictions.png"))
    s6 = {"step": 6, "title": "FM2 predictions", "predictions": preds, "frozen_file": "predictions/fm2_predictions.json",
          "sha256": open(os.path.join(PRED, "SHA256SUMS.txt")).read().split()[0] if os.path.exists(os.path.join(PRED, "SHA256SUMS.txt")) else None}
    report.write_json(os.path.join(OUT, "step6_fm2.json"), py(s6))
    report.dashboard("method_steps.json", py({"generated_at": now, "step1": s1, "step3": s3, "step4": {k: s4[k] for k in ("model", "decline_rule", "grid_decline_share", "operating_points")},
                                              "step5": {"plan": gp["plan"], "single_test_ranking": rk["top"], "material": ref}, "step6": s6}))
    return {"s1": s1, "s3": s3, "s4": s4, "rk": rk, "gp": gp, "preds": preds, "models": models}


if __name__ == "__main__":
    r = main()
    s1, s3, s4, rk, preds = r["s1"], r["s3"], r["s4"], r["rk"], r["preds"]
    for c in r["gp"]["plan"]:
        print("PLAN", c["step"], c["facility"], c["g_class"], c["o2_pct"], c["p_psia"], c["dir"], "p %.2f" % c["p_sustain_now"], "cum %.1f%% (+%.1f)" % (c["cumulative_reduction_pct"], c["added_reduction_pct"]))
    print("STEP1 points %d, with outcome %d, by origin %s, gate %s, quote problems %d, model obs %d" % (s1["test_points"], s1["with_outcome"], s1["by_origin"], s1["checks_gate"], len(s1["outcome_quotes_not_found"]), s1["model_observations"]))
    for f, v in s3["families"].items():
        print("STEP3", f, v["summary_by_gravity"], [(o["id"], o["status"]) for o in v["operating_points"]])
    for f, fit in s4["fits"].items():
        print("STEP4", f, "obs", fit["observations"], "neg", fit["not_sustained"], "rhat %.3f" % fit["max_rhat"], "acc", fit["acceptance"], "LOO brier %.3f acc %.2f base %.2f (base-rate Brier %.3f)" % (fit["loo"]["brier_loo"], fit["loo"]["accuracy_loo"], fit["loo"]["base_rate"], fit["loo"]["base_rate"] * (1 - fit["loo"]["base_rate"])))
        print("   wrong LOO:", [(x["obs_id"], x["y"], round(x["p_leave_one_out"], 2), round(x["p_in_sample"], 2)) for x in fit["loo"]["rows"] if not x["correct_loo"]])
    print("STEP4 decline share %.2f" % s4["grid_decline_share"])
    for o in s4["operating_points"]:
        print("   ", o["op_id"], o["direction"][:8], o["material"][:10], "%.2f [%.2f,%.2f] d=%.2f %s" % (o["p_mean"], o["p_lo90"], o["p_hi90"], o["support_distance"], o["decision"]))
    for c in rk["top"]:
        print("STEP5", c["rank"], c["facility"], c["g_class"], c["o2_pct"], c["p_psia"], c["dir"], "evr %.2f%%" % c["evr_pct"], "p %.2f" % c["p_sustain_now"], "cost", c["cost_tier"])
    for p in preds:
        print("STEP6", p["burn"], p["fuel"][:12], p["direction"], "%.2f [%.2f, %.2f]" % (p["model"]["p_mean"], p["model"]["p_lo90"], p["model"]["p_hi90"]), p["model"]["decision"], p["strict_model"])
