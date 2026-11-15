"""Experiment 4: LUCI holdout and gravity-rule comparison. Usage: python experiments/exp4_luci_rules.py"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nextburn import ingest, physics, report, units  # noqa: E402


def find(norm, test_prefix, family, measurement):
    rows = [r for r in norm if (r.get("test_id") or "").startswith(test_prefix) and family in r["families"]
            and (r.get("measurement") or "").lower() == measurement and r.get("value_norm") is not None]
    return rows[0] if rows else None


def main():
    out = report.exp_dir(4)
    rules_path = os.path.join(ROOT, "config", "rules.json")
    cfg = json.load(open(rules_path))
    rows, norm, pts, meta = ingest.build()
    g_spin = meta["g_spin"]
    obs, stated = [], []
    for label, fam, meas, ratio_meas in (("Fabric flame tip", "thin_fabric", "flame tip spread rate", "ratio of lunar to 1-g flame tip spread rate"),
                                         ("Acrylic rod flame tip", "thick_plastic", "flame tip spread rate", "ratio of lunar to 1-g flame tip spread rate"),
                                         ("Fabric flame base", "thin_fabric", "flame base spread rate", "ratio of lunar to 1-g flame base spread rate")):
        lun, gnd = find(norm, "LUCI NS-29", fam, meas), find(norm, "LUCI 1-g", fam, meas)
        st = [r for r in norm if r["role"] == "comparison" and fam in r["families"] and (r.get("measurement") or "").lower() == ratio_meas]
        ratio = lun["value_norm"] / gnd["value_norm"]
        obs.append({"label": label, "family": fam, "g_ratio": g_spin, "ratio": ratio, "lunar": "%s %s [%s]" % (lun["value_text"], lun["unit"], lun["row_id"]),
                    "earth": "%s %s [%s]" % (gnd["value_text"], gnd["unit"], gnd["row_id"]), "row_ids": [lun["row_id"], gnd["row_id"]],
                    "implied_n": physics.implied_exponent(ratio, g_spin)})
        if st:
            stated.append({"label": label, "ratio": st[0]["value_num"], "row_id": st[0]["row_id"], "implied_n": physics.implied_exponent(st[0]["value_num"], g_spin)})
    scored = physics.score_rules(cfg["rules"], obs, cfg["hit_threshold_pct"])
    scored_plan_g = physics.score_rules(cfg["rules"], [dict(o, g_ratio=0.1657) for o in obs], cfg["hit_threshold_pct"])
    sack = [r for r in norm if r["source_id"] == "sacksteder_2003" and "dependence of upward spread rate" in (r.get("measurement") or "")]
    peak = [r for r in norm if r["source_id"] == "sacksteder_2003" and "peaks" in (r.get("measurement") or "")]
    second = {"source": "Sacksteder and colleagues, NASA KC-135 aircraft, thin cellulose at 27.6 kPa in air",
              "upward": {"row_id": sack[0]["row_id"] if sack else None, "finding": sack[0]["value_text"] if sack else None, "implied_n": 1.0 if sack and sack[0]["value_text"] == "linear" else None},
              "downward": {"row_id": peak[0]["row_id"] if peak else None, "finding": "downward spread peaks near %s %s" % (peak[0]["value_text"], peak[0]["unit"]) if peak else None},
              "reading": "Upward spread over thin paper at reduced pressure scaled linearly with gravity (n = 1), which neither the square-root nor the cube-root rule predicts. Downward spread peaked between the gravity levels, so no single power law with a positive exponent describes it.",
              "feier": "Feier and colleagues report spread rates only in figures; the cited text has no spread-rate numbers. Digitizing the figures (WebPlotDigitizer) is a next step and is not done here."}
    n_all = [o["implied_n"] for o in obs] + [s["implied_n"] for s in stated]
    n_low, n_high = min(n_all), (second["upward"]["implied_n"] or max(n_all))
    band_moon = physics.ratio_band(units.G_LUNAR, n_low, n_high)
    band_mars = physics.ratio_band(units.G_MARS, n_low, n_high)
    hits = {r["id"]: sum(1 for s in scored if s["rules"][r["id"]]["hit"]) for r in cfg["rules"]}
    bi = [{"setting": name, "o2_pct": o2, "p_psia": p, "g": g, "buoyancy_index": physics.buoyancy_index(g, units.psia_to_kpa(p))}
          for name, o2, p, g in (("Earth, sea level", 20.946, 14.7, 1.0), ("Earth laboratory at exploration pressure", 34, 8.2, 1.0),
                                 ("Mars habitat", 34, 8.2, units.G_MARS), ("Moon base, upper pressure bound", 30, 10.2, units.G_LUNAR),
                                 ("Moon base, exploration atmosphere", 34, 8.2, units.G_LUNAR), ("Spacesuit on the Moon", 100, 4.3, units.G_LUNAR))]
    result = {
        "experiment": 4, "title": "LUCI holdout and gravity-rule comparison", "generated_at": report.now_iso(),
        "rules_file_sha256": report.sha256_file(rules_path), "rules_frozen_at_utc": cfg["frozen_at_utc"], "honesty_note": cfg["honesty_note"],
        "g_ratio_luci_spin": g_spin, "g_ratio_plan": 0.1657, "hit_threshold_pct": cfg["hit_threshold_pct"],
        "observations": scored, "stated_ratios": stated, "sensitivity_plan_g_0_1657": [{"label": s["label"], **{k: v["error_pct"] for k, v in s["rules"].items()}} for s in scored_plan_g],
        "hits_per_rule": hits, "second_check": second,
        "implied_exponents": {"rate_derived": [o["implied_n"] for o in obs], "stated_ratios": [s["implied_n"] for s in stated], "n_low": n_low, "n_high": n_high},
        "uncertainty_band": {"moon": {"g_ratio": units.G_LUNAR, "ratio_low": band_moon[0], "ratio_high": band_moon[1], "fold": band_moon[1] / band_moon[0]},
                             "mars": {"g_ratio": units.G_MARS, "ratio_low": band_mars[0], "ratio_high": band_mars[1], "fold": band_mars[1] / band_mars[0]},
                             "use": "Spread-rate ratio band shown for any cell with no direct test; never shown as tested"},
        "buoyancy_index": bi,
        "pass": True, "pass_rule": "Report every hit and miss as it falls, and publish the band of implied exponents for untested cells",
    }
    report.write_json(os.path.join(out, "results.json"), result)
    report.dashboard("exp4_luci.json", {"title": result["title"], "observations": [{"label": s["label"], "measured": s["ratio"], "implied_n": s["implied_n"],
                                                                                   "rules": {k: {"predicted": v["predicted"], "error_pct": v["error_pct"], "hit": v["hit"]} for k, v in s["rules"].items()},
                                                                                   "row_ids": s["row_ids"]} for s in scored],
                                        "hits_per_rule": hits, "uncertainty_band": result["uncertainty_band"], "second_check": second["reading"], "buoyancy_index": bi, "generated_at": result["generated_at"]})
    plt = report.plt()
    import numpy as np
    g = np.logspace(-1.05, 0, 200)
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.fill_between(g, g ** n_high, g ** n_low, color=report.COLORS["muted"], alpha=0.35, label="band n = %.2f to %.2f" % (n_low, n_high))
    for r, st in zip(cfg["rules"], ("-", "--", ":")):
        ax.plot(g, g ** r["n"], st, color=report.COLORS["accent"], label=r["label"])
    for o, m in zip(scored, ("o", "s", "^")):
        ax.plot(o["g_ratio"], o["ratio"], m, color=report.COLORS["fail"] if "base" in o["label"] else report.COLORS["pass"], ms=8, label="LUCI %s: %.3f" % (o["label"].lower(), o["ratio"]))
    for x, t in ((units.G_LUNAR, "Moon"), (units.G_MARS, "Mars")):
        ax.axvline(x, color="grey", lw=0.8, ls="--"); ax.text(x * 1.02, 0.92, t, fontsize=8)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("gravity (fraction of Earth)"); ax.set_ylabel("spread-rate ratio to 1 g")
    ax.set_title("Experiment 4: no single gravity rule fits LUCI (tips fit n = 1/2, base does not)", fontsize=10)
    ax.legend(fontsize=7, loc="lower right"); fig.tight_layout(); fig.savefig(os.path.join(out, "chart.png")); plt.close(fig)
    rows_md = [[s["label"], s["lunar"], s["earth"], "%.3f" % s["ratio"], "%.2f" % s["implied_n"]] + ["%+.1f%%%s" % (s["rules"][r["id"]]["error_pct"], " hit" if s["rules"][r["id"]]["hit"] else "") for r in cfg["rules"]] for s in scored]
    md = ["# Experiment 4: LUCI holdout and gravity-rule comparison", "",
          "Generated %s. Rules file frozen %s (sha256 %s...). %s" % (result["generated_at"], cfg["frozen_at_utc"], result["rules_file_sha256"][:12], cfg["honesty_note"]), "",
          "LUCI gravity from the ledger's own spin rows: %.4f g. Hit = within %g%%." % (g_spin, cfg["hit_threshold_pct"]), "",
          report.md_table(["LUCI ratio", "Lunar", "1 g", "Measured", "Implied n"] + [r["label"] for r in cfg["rules"]], rows_md), "",
          "Stated ratios in the LUCI presentation: %s." % ", ".join("%s %s [%s] (n = %.2f)" % (s["label"].lower(), s["ratio"], s["row_id"], s["implied_n"]) for s in stated), "",
          "**Second check.** %s %s" % (second["reading"], second["feier"]), "",
          "**Uncertainty band for untested cells:** exponents %.2f to %.2f give a lunar-to-Earth ratio of %.2f to %.2f (%.1f-fold) at the Moon and %.2f to %.2f (%.1f-fold) at Mars." % (
              n_low, n_high, band_moon[0], band_moon[1], band_moon[1] / band_moon[0], band_mars[0], band_mars[1], band_mars[1] / band_mars[0]), "",
          "## Buoyancy index (gravity x (pressure / 14.7 psia)^2)", "", report.md_table(["Setting", "Oxygen", "Pressure", "Gravity", "Index"], [[b["setting"], "%g%%" % b["o2_pct"], "%g psia" % b["p_psia"], "%.3f g" % b["g"], "%.2f" % b["buoyancy_index"]] for b in bi]), "",
          "Rerun: `python experiments/exp4_luci_rules.py`.", ""]
    report.write_text(os.path.join(out, "results.md"), "\n".join(md))
    print("Experiment 4:", [(s["label"], round(s["ratio"], 3), round(s["implied_n"], 3), {k: round(v["error_pct"], 1) for k, v in s["rules"].items()}) for s in scored])
    print("stated:", [(s["label"], s["ratio"], round(s["implied_n"], 3)) for s in stated], "band moon", [round(x, 3) for x in band_moon], "mars", [round(x, 3) for x in band_mars], "hits", hits)
    print("plan g sensitivity:", result["sensitivity_plan_g_0_1657"])
    print("buoyancy:", [(b["setting"], round(b["buoyancy_index"], 3)) for b in bi])
    return 0


if __name__ == "__main__":
    sys.exit(main())
