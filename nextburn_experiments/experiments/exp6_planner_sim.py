#!/usr/bin/env python3
"""Experiment 6: planner efficiency (SIMULATION).

Compares four ways of choosing tests (fixed 6x6 matrix, Halton space-filling, random,
uncertainty-driven lower confidence bound) by how many tests each needs before its
estimate of the minimum extinction oxygen stays within 0.5 O2 points of the truth.
Every boundary is simulated and anchored only on the published SoFIE-GEL ranges; no
NASA data are used.  All strategies share the same estimator, so only test selection
differs.

Run from the package root:
    python experiments/exp6_planner_sim.py              # full run  -> results/exp6/
    python experiments/exp6_planner_sim.py --quick      # ~10 boundaries -> results/exp6/quick/
    python experiments/exp6_planner_sim.py --boundaries 300 --small-boundaries 150
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

try:
    from nextburn import sim  # noqa: E402
except Exception:  # the package __init__ is shared with other modules; fall back to the file
    import importlib.util

    _spec = importlib.util.spec_from_file_location("nextburn_sim", ROOT / "nextburn" / "sim.py")
    sim = importlib.util.module_from_spec(_spec)
    sys.modules["nextburn_sim"] = sim
    _spec.loader.exec_module(sim)

SEED = 2026
BOUNDARY_SEED_BASE = 600_000
BOOTSTRAP_SEED = (SEED, 77)
N_BOOTSTRAP = 2000
DEFAULT_MAIN = 200
DEFAULT_SMALL = 200
QUICK_N = 10
VARIANT_ORDER = ("two_variable", "go_no_go", "one_variable")
VARIANT_CODES = {"two_variable": 2, "one_variable": 1, "go_no_go": 3}
STRATEGY_CODES = {"fixed_matrix": 1, "space_filling": 2, "random": 3, "uncertainty_driven": 4}
MAIN_FIXED = ("flow_major", "inset")
SENSITIVITY = {
    "two_variable": [("pressure_high_first", "inset"), ("pressure_low_first", "inset"), ("shuffled", "inset"),
                     ("flow_major", "endpoints"), ("pressure_high_first", "endpoints")],
    "go_no_go": [("flow_major", "endpoints")],
}
ABOUT_HALF = (0.40, 0.60)

TITLE = "Experiment 6: Planner efficiency (SIMULATION)"
PART_NAMES = {"two_variable": "two-variable", "one_variable": "one-variable", "go_no_go": "go/no-go",
              "fixed_matrix_sensitivity": "fixed-matrix sensitivity"}
VARIANT_TITLES = {
    "two_variable": "Two-variable boundary (log-flow x pressure), main variant",
    "go_no_go": "Go/no-go tests (drop-tower style: flow x oxygen, burn / no-burn only)",
    "one_variable": "One-variable control (flow only, 1.1 atm slice)",
}
VARIANT_SHORT = {
    "two_variable": "Two variables\n(flow x pressure)",
    "go_no_go": "Go/no-go\n(burn / no-burn)",
    "one_variable": "One variable\n(control)",
}
COLORS = {
    "fixed_matrix": "#8c8c8c",
    "space_filling": "#6baed6",
    "random": "#c6dbef",
    "uncertainty_driven": "#d94801",
}


def config_text(variant, order, levels):
    second = {"two_variable": "pressure", "go_no_go": "oxygen"}.get(variant, "pressure")
    orders = {
        "flow_major": f"plan order (flows low to high, every {second} level at each flow)",
        "pressure_high_first": "highest-pressure row first (flows low to high in each row)",
        "pressure_low_first": "lowest-pressure row first (flows low to high in each row)",
        "shuffled": f"one fixed shuffled order (seed {sim.FIXED_SHUFFLE_SEED})",
    }
    lv = {"inset": "levels at 5-95% of each range", "endpoints": "levels span the full ranges, ends included"}
    return f"{orders[order]}; {lv[levels]}"


CLAIM_PHRASES = {
    ("pressure_high_first", "inset"): "a matrix run from its highest-pressure row first, nearest the simulated "
                                      "minimum",
    ("pressure_high_first", "endpoints"): "a matrix that includes 1.1 atm, where the simulated minimum always lies, "
                                          "and runs that row first",
    ("flow_major", "endpoints"): "a matrix whose levels include 1.1 atm, where the simulated minimum always lies,",
    ("shuffled", "inset"): "a matrix run in a shuffled order",
    ("pressure_low_first", "inset"): "a matrix run from its lowest-pressure row first",
}
SHORT_PHRASES = {
    ("pressure_high_first", "inset"): "the same matrix run from its highest-pressure row first",
    ("pressure_high_first", "endpoints"): "a 6x6 matrix that includes 1.1 atm and runs that row first",
    ("flow_major", "endpoints"): "a 6x6 matrix whose levels include 1.1 atm",
    ("shuffled", "inset"): "the same matrix run in a shuffled order",
    ("pressure_low_first", "inset"): "the same matrix run from its lowest-pressure row first",
}
CHART_PHRASES = {
    ("pressure_high_first", "inset"): "Same matrix, run from\nthe highest-pressure\nrow first",
    ("pressure_high_first", "endpoints"): "6x6 matrix including\n1.1 atm, run from that\nrow first",
    ("flow_major", "endpoints"): "6x6 matrix with levels\nincluding 1.1 atm",
    ("shuffled", "inset"): "Same matrix,\nshuffled order",
    ("pressure_low_first", "inset"): "Same matrix, run from\nthe lowest-pressure\nrow first",
}
RUN_SIZING = ("Counts were sized from a 10-boundary pilot of every variant plus the sensitivity runs. It took 52.5 s "
              "wall time on the shared single core (21.5 s CPU), which projects about 18 min for 200 boundaries per "
              "variant, under the 40-minute limit.")


# --------------------------------------------------------------------------- helpers
def jnum(v, nd=3):
    """JSON-safe number: inf / nan -> None, floats rounded."""
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    v = float(v)
    if not math.isfinite(v):
        return None
    return round(v, nd)


def fmt_num(v):
    return f"{v:.0f}" if float(v).is_integer() else f"{v:.1f}"


def fmt_tests(v):
    if v is None or not math.isfinite(v):
        return "not reached (>40)"
    return fmt_num(v)


def fmt_p80_text(v):
    if v is None or not math.isfinite(v):
        return "80th percentile beyond the 40-test budget"
    return f"80th percentile {fmt_num(v)}"


def fmt_pct(v):
    """Whole percent, but never round a partial success up to 100% or down to 0%."""
    s = f"{100.0 * v:.0f}%"
    if (s == "100%" and v < 1.0) or (s == "0%" and v > 0.0):
        s = f"{100.0 * v:.1f}%"
    return s


def log(msg):
    print(msg, flush=True)


# --------------------------------------------------------------------------- running
def run_variant(name, n_boundaries, strategies, fixed=MAIN_FIXED, tag=""):
    spec = sim.make_variant(name, fixed[0], sim.BUDGET, fixed[1])
    rows = []
    t0 = time.perf_counter()
    every = max(1, n_boundaries // 10)
    for i in range(n_boundaries):
        bseed = BOUNDARY_SEED_BASE + i
        f, tmin = sim.make_boundary(bseed, spec.boundary_dims)
        draws = np.random.default_rng([SEED, VARIANT_CODES[name], i]).standard_normal(sim.BUDGET)
        for s in strategies:
            res = sim.run_strategy(s, (f, tmin), sim.BUDGET, sim.NOISE_SD, variant=spec,
                                   seed=[SEED, VARIANT_CODES[name], i, STRATEGY_CODES[s]],
                                   noise_draws=draws)
            rows.append({
                "variant": name,
                "boundary_index": i,
                "boundary_seed": bseed,
                "strategy": s,
                "fixed_order": res["fixed_order"],
                "fixed_levels": res["fixed_levels"],
                "tests_to_converge": res["tests_to_converge"],
                "true_min": tmin,
                "final_estimate": res["final_estimate"],
                "flow_at_min_cm_s": float(sim.flow_cm_s(f.params["u0"])),
            })
        if (i + 1) % every == 0 or i + 1 == n_boundaries:
            el = time.perf_counter() - t0
            eta = el / (i + 1) * (n_boundaries - i - 1)
            log(f"  [{name}{tag}] {i + 1}/{n_boundaries} boundaries, {el:6.1f} s elapsed, ~{eta:5.0f} s left")
    return rows, time.perf_counter() - t0


def ttc_by(rows, strategy):
    return [r["tests_to_converge"] for r in sorted(rows, key=lambda r: r["boundary_index"])
            if r["strategy"] == strategy]


def strategy_table(rows, variant, strategies):
    table = []
    for s in strategies:
        sm = sim.summarize(ttc_by(rows, s))
        table.append({
            "name": s,
            "label": sim.strategy_label(s, variant),
            "n_runs": sm["n_runs"],
            "n_success": sm["n_success"],
            "success_rate": jnum(sm["success_rate"], 4),
            "median_tests": jnum(sm["median_tests"], 2),
            "p80_tests": jnum(sm["p80_tests"], 2),
            "mean_tests": jnum(sm["mean_tests"], 2),
            "_raw": sm,
        })
    return table


def public(entry):
    return {k: v for k, v in entry.items() if not k.startswith("_")}


def paired(rows_a, rows_b, a="uncertainty_driven", b="fixed_matrix"):
    xa, xb = np.array(ttc_by(rows_a, a)), np.array(ttc_by(rows_b, b))
    return {"vs": b, "n": int(xa.size), "fewer_tests": int(np.sum(xa < xb)),
            "same": int(np.sum(xa == xb)), "more_tests": int(np.sum(xa > xb))}


def bootstrap_median_ratio(a, b, n_boot=N_BOOTSTRAP, seed=BOOTSTRAP_SEED):
    """95% paired-bootstrap interval for median(a) / median(b) over boundaries."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(list(seed))
    idx = rng.integers(0, a.size, size=(n_boot, a.size))
    ratios = []
    for row in idx:
        ma, mb = sim.quantile(a[row], 0.5), sim.quantile(b[row], 0.5)
        if math.isfinite(mb):
            ratios.append(ma / mb)
        elif math.isfinite(ma):
            ratios.append(0.0)
    if not ratios:
        return None, None
    return sim.quantile(ratios, 0.025), sim.quantile(ratios, 0.975)


def get(table, name):
    return next(t for t in table if t["name"] == name)


# --------------------------------------------------------------------------- verdicts
def build_verdict(tables, fixed_cfgs, n_main):
    """Headline, claim, caveats and pass from the two-variable results.

    fixed_cfgs: {(order, levels): summary} for every fixed-matrix design run on the
    two-variable boundaries (the plan's design plus the sensitivity designs).
    """
    two = tables["two_variable"]
    u, f = get(two, "uncertainty_driven")["_raw"], get(two, "fixed_matrix")["_raw"]
    mu, mf = u["median_tests"], f["median_tests"]
    su, sf = u["success_rate"], f["success_rate"]
    passed = bool(mu < mf and su >= sf)
    ratio = (mu / mf) if (math.isfinite(mu) and math.isfinite(mf) and mf > 0) else math.nan
    nums = (f"median {fmt_tests(mu)} vs {fmt_tests(mf)} tests, success {fmt_pct(su)} vs {fmt_pct(sf)}, "
            f"{n_main} simulated two-variable boundaries")
    meds = {cfg: sm["median_tests"] for cfg, sm in fixed_cfgs.items()}
    ratios = {cfg: (mu / m if math.isfinite(m) and m > 0 else 0.0) for cfg, m in meds.items()}
    in_half = lambda r: ABOUT_HALF[0] <= r <= ABOUT_HALF[1]  # noqa: E731
    all_half = all(in_half(r) for r in ratios.values())
    beats_all = all(mu < m for m in meds.values())
    alts = {cfg: m for cfg, m in meds.items() if cfg != MAIN_FIXED}
    best = min(alts, key=lambda c: (alts[c], c)) if alts else None
    qualify = bool(alts) and not all_half
    which = "a fixed matrix run in the plan's order" if qualify else "a fixed matrix"

    if passed and in_half(ratio):
        claim = f"Choosing each test by uncertainty needed about half the tests of {which}, in simulation ({nums})"
    elif passed and ratio < ABOUT_HALF[0]:
        claim = (f"Choosing each test by uncertainty needed fewer than half the tests of {which}, in simulation "
                 f"(about {100 * ratio:.0f}% of them; {nums})")
    elif passed:
        claim = (f"Choosing each test by uncertainty needed fewer tests than {which}, in simulation, but not half "
                 f"(about {100 * ratio:.0f}% of them; {nums})")
    else:
        claim = f"In simulation, choosing each test by uncertainty did not beat a fixed matrix ({nums})"
    if passed and best is not None and not beats_all:
        sb = fixed_cfgs[best]
        cmp = "fewer at the median" if meds[best] < mu else "as few at the median"
        claim += f"; {CLAIM_PHRASES[best]} needed {cmp} ({fmt_tests(meds[best])})"
        worse = []
        if sb["success_rate"] < su:
            worse.append(f"succeeded less often ({fmt_pct(sb['success_rate'])})")
        if sb["p80_tests"] > u["p80_tests"]:
            worse.append(f"had a longer tail (80th percentile {fmt_tests(sb['p80_tests'])} vs "
                         f"{fmt_tests(u['p80_tests'])})")
        if worse:
            claim += " but " + " and ".join(worse)
    claim += "."

    caveats = []
    if alts:
        sb = fixed_cfgs[best]
        if not beats_all:
            caveats.append(
                f"The saving depends on how the fixed matrix is laid out. MOC rises as pressure falls, so the "
                f"simulated minimum always lies at 1.1 atm. {SHORT_PHRASES[best][0].upper()}{SHORT_PHRASES[best][1:]} "
                f"needed a median of {fmt_tests(meds[best])} tests ({fmt_p80_text(sb['p80_tests'])}, success "
                f"{fmt_pct(sb['success_rate'])}). The uncertainty-driven planner, given no hint about where the "
                f"hazard lies, needed a median of {fmt_tests(mu)} ({fmt_p80_text(u['p80_tests'])}, success "
                f"{fmt_pct(su)}). The planner's advantage is that it does not need that prior knowledge, not that "
                f"it beats every matrix at the median. See the fixed-matrix layout table.")
        elif not all_half:
            lo, hi = min(ratios.values()), max(ratios.values())
            caveats.append(
                f"The size of the saving depends on how the fixed matrix is laid out: the uncertainty-driven median "
                f"was {100 * lo:.0f}%-{100 * hi:.0f}% of the fixed matrix's across the {len(meds)} layouts tested. "
                f"See the fixed-matrix layout table.")
        else:
            caveats.append(f"The result held for all {len(meds)} fixed-matrix layouts tested.")
    headline = (f"In simulation ({n_main} random two-variable boundaries), choosing each test by uncertainty found "
                f"the minimum extinction oxygen within 0.5 points in a median of {fmt_tests(mu)} tests "
                f"({fmt_p80_text(u['p80_tests'])}) versus {fmt_tests(mf)} ({fmt_p80_text(f['p80_tests'])}) for the "
                f"plan's fixed 6x6 test matrix, with {fmt_pct(su)} vs {fmt_pct(sf)} success.")
    return {"pass": passed, "ratio": ratio, "claim": claim, "headline": headline, "caveats": caveats,
            "best_alternative": best, "fixed_medians": meds}


# --------------------------------------------------------------------------- outputs
def make_chart(path, tables, counts, verdict, fixed_cfgs):
    order = [v for v in VARIANT_ORDER if v in tables]
    strategies = list(sim.STRATEGIES)
    budget = sim.BUDGET
    fig, ax = plt.subplots(figsize=(12, 6.8), dpi=150)
    width = 0.2
    white_box = dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.9)
    for gi, v in enumerate(order):
        for si, s in enumerate(strategies):
            t = get(tables[v], s)["_raw"]
            x = gi + (si - 1.5) * width
            med, p80, succ = t["median_tests"], t["p80_tests"], t["success_rate"]
            reached = math.isfinite(med)
            ax.bar(x, med if reached else budget, width * 0.92, color=COLORS[s], edgecolor="black",
                   linewidth=0.6, hatch=None if reached else "//", zorder=2,
                   label=sim.STRATEGY_LABELS[s] if gi == 0 else None)
            if reached:
                top = p80 if math.isfinite(p80) else budget
                ax.plot([x, x], [med, top], color="black", lw=1.2, zorder=3)
                ax.plot([x - 0.04, x + 0.04], [top, top], color="black", lw=1.2, zorder=3)
                if not math.isfinite(p80):
                    ax.annotate("", xy=(x, budget + 2.4), xytext=(x, budget),
                                arrowprops=dict(arrowstyle="->", lw=1.1), zorder=3)
                ax.text(x, max(med / 2, 1.6), fmt_tests(med), ha="center", va="center", fontsize=9.5,
                        fontweight="bold", zorder=4,
                        color="white" if s in ("fixed_matrix", "uncertainty_driven") else "black")
            else:
                ax.text(x, budget / 2, "not\nreached", ha="center", va="center", fontsize=8, zorder=4,
                        bbox=white_box)
            ax.text(x, -1.7, fmt_pct(succ), ha="center", va="top", fontsize=8.5, color="#333333")
    best = verdict.get("best_alternative")
    left = -0.55
    if best is not None and "two_variable" in order and math.isfinite(fixed_cfgs[best]["median_tests"]):
        left = -0.98
        m = fixed_cfgs[best]["median_tests"]
        x = order.index("two_variable") - 1.5 * width
        ax.plot([x - 0.092, x + 0.092], [m, m], color="black", lw=1.6, ls=(0, (2, 1.5)), zorder=5)
        ax.plot([x], [m], marker="D", color="black", ms=5, zorder=6)
        ax.annotate(f"Sensitivity check -\n{CHART_PHRASES[best]}:\nmedian {fmt_tests(m)}, success "
                    f"{fmt_pct(fixed_cfgs[best]['success_rate'])}", xy=(x - 0.092, m),
                    xytext=(left + 0.03, m + 9), fontsize=8, ha="left", va="bottom",
                    arrowprops=dict(arrowstyle="-", lw=0.8, color="black"), zorder=6, bbox=white_box)
    ax.axhline(budget, color="#555555", ls="--", lw=1, zorder=1)
    ax.text(len(order) - 0.47, budget + 0.5, f"budget = {budget} tests", ha="right", va="bottom", fontsize=8.5,
            color="#555555")
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([f"{VARIANT_SHORT[v]}\n{counts[v]} boundaries" for v in order], fontsize=10)
    ax.tick_params(axis="x", pad=19, length=0)
    ax.set_ylim(-0.5, budget + 9)
    ax.set_xlim(left, len(order) - 0.45)
    ax.set_yticks(range(0, budget + 1, 5))
    ax.set_ylabel("Tests until the estimate stays within 0.5 O$_2$ points", fontsize=10.5)
    ax.text(left + 0.03, -1.7, "success:", ha="left", va="top", fontsize=8.5, color="#333333")
    ax.set_title("Simulation: tests needed to find the minimum extinction oxygen\n"
                 "Experiment 6 planner efficiency - simulated boundaries on SoFIE-GEL ranges, not NASA data",
                 fontsize=12.5)
    ax.legend(loc="upper center", fontsize=9, frameon=False, ncol=4, bbox_to_anchor=(0.5, 1.0),
              handlelength=1.4, columnspacing=1.4)
    ax.grid(axis="y", color="#e5e5e5", zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.text(0.01, 0.006, "SIMULATION. Bars: median; whiskers: 80th percentile; arrow: 80th percentile beyond the "
             "budget; hatched: median not reached. Runs that never converged count as failures.",
             fontsize=8, color="#444444")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def md_table(table):
    lines = ["| Strategy | Success | Median tests | 80th percentile | Mean tests (converged runs) |",
             "|---|---|---|---|---|"]
    for t in table:
        r = t["_raw"]
        mean = "-" if not math.isfinite(r["mean_tests"]) else f"{r['mean_tests']:.1f}"
        lines.append(f"| {t['label']} | {fmt_pct(r['success_rate'])} ({r['n_success']}/{r['n_runs']}) | "
                     f"{fmt_tests(r['median_tests'])} | {fmt_tests(r['p80_tests'])} | {mean} |")
    return "\n".join(lines)


def write_csv(path, rows):
    cols = ["label", "variant", "boundary_index", "boundary_seed", "strategy", "fixed_order", "fixed_levels",
            "tests_to_converge", "converged", "true_min_o2_pct", "final_estimate_o2_pct",
            "final_error_o2_pts", "flow_at_min_cm_s", "pressure_at_min_atm"]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            ttc = r["tests_to_converge"]
            w.writerow([sim.LABEL, r["variant"], r["boundary_index"], r["boundary_seed"], r["strategy"],
                        r["fixed_order"], r["fixed_levels"], "" if not math.isfinite(ttc) else int(ttc),
                        int(math.isfinite(ttc)), f"{r['true_min']:.4f}", f"{r['final_estimate']:.4f}",
                        f"{r['final_estimate'] - r['true_min']:.4f}", f"{r['flow_at_min_cm_s']:.3f}",
                        f"{sim.PRESSURE_RANGE_ATM[1]:.2f}"])


def variant_sentence(v, table, counts):
    u = get(table, "uncertainty_driven")["_raw"]
    f = get(table, "fixed_matrix")["_raw"]
    h = get(table, "space_filling")["_raw"]
    r = get(table, "random")["_raw"]
    name = {"two_variable": "Two variables", "go_no_go": "Go/no-go", "one_variable": "One-variable control"}[v]
    return (f"{name} ({counts[v]} boundaries): uncertainty-driven median {fmt_tests(u['median_tests'])} tests, "
            f"success {fmt_pct(u['success_rate'])}; fixed {fmt_tests(f['median_tests'])}, "
            f"{fmt_pct(f['success_rate'])}; space-filling {fmt_tests(h['median_tests'])}, "
            f"{fmt_pct(h['success_rate'])}; random {fmt_tests(r['median_tests'])}, {fmt_pct(r['success_rate'])}.")


def sensitivity_md(v, rows_by_cfg, u_raw):
    lines = ["| Fixed-matrix design | Success | Median tests | 80th percentile |", "|---|---|---|---|"]
    for cfg, sm in rows_by_cfg.items():
        tag = " **(main)**" if cfg == MAIN_FIXED else ""
        lines.append(f"| {config_text(v, *cfg)}{tag} | {fmt_pct(sm['success_rate'])} | "
                     f"{fmt_tests(sm['median_tests'])} | {fmt_tests(sm['p80_tests'])} |")
    lines.append(f"| *Uncertainty-driven planner, for reference* | {fmt_pct(u_raw['success_rate'])} | "
                 f"{fmt_tests(u_raw['median_tests'])} | {fmt_tests(u_raw['p80_tests'])} |")
    return "\n".join(lines)


def write_markdown(path, res, tables, sens_cfgs, verdict, counts, quick, out_rel):
    s = res["settings"]
    two = res["variants"]["two_variable"]
    lines = [f"# {TITLE}", "",
             "> **SIMULATION.** Every extinction boundary here is simulated. The boundaries are anchored only on the "
             "published SoFIE-GEL operating ranges: forced flow 0.2-80 cm/s, oxygen 13-34% and pressure 0.15-1.1 atm. "
             "They are not NASA data and are not measurements of any material.", ""]
    if quick:
        lines += ["> **Quick smoke run** with only a few boundaries. Do not quote these numbers; the full results are in "
                  "`results/exp6/`.", ""]
    lines += [f"**Headline.** {verdict['headline']}", "",
              f"**Claim (the only one allowed).** {verdict['claim']}", "",
              f"**Pass: {'yes' if verdict['pass'] else 'no'}.** The test passes when the uncertainty-driven planner "
              "needs fewer tests than the plan's fixed matrix at the median in the two-variable variant, with a success "
              "rate at least as high.", ""]
    for c in verdict["caveats"]:
        lines += [f"**Caveat.** {c}", ""]
    lines += ["## What was compared", "",
              "The question is how many tests (burns) each test-selection strategy needs before its estimate of the "
              "most hazardous condition, the minimum extinction oxygen, settles within 0.5 O2 points of the true value. "
              "A run *converges* at the first test count after which the estimate stays within 0.5 points for the "
              "rest of the 40-test budget. Runs that never settle count as failures (infinite), so they push up the "
              "median and 80th percentile.", "",
              "- **Fixed matrix:** a 6x6 grid run in a fixed order, as in the plan's prototype. In the two-variable variant "
              "it is 6 flows by 6 pressures: flows low to high, with all pressures at each flow, at levels set at 5-95% of each range. "
              "Tests 37-40 repeat the first cells. The one-variable control uses 6 flows swept low to high, repeated. The go/no-go "
              "variant uses 6 flows by 6 oxygen levels.",
              "- **Space-filling:** the Halton sequence (bases 2 and 3).",
              "- **Random:** uniform draws over the test range.",
              "- **Uncertainty-driven:** the first few Halton points (5, or 4 in the one-variable control). After that, each test "
              "goes where the model's lower confidence bound (mean - 2 s.d.) on the extinction oxygen is lowest.", "",
              "Within a variant every strategy uses the same estimator, so only test selection differs. For limit tests "
              "the estimate is the minimum of a Gaussian-process posterior mean over a dense grid. For go/no-go tests it is "
              "the posterior mean of the minimum from a Bayesian grid model for burn / no-burn outcomes.", "",
              "## Results", ""]
    for v in VARIANT_ORDER:
        if v not in tables:
            continue
        p = res["variants"][v]["paired_vs_fixed"]
        lines += [f"### {VARIANT_TITLES[v]}: {counts[v]} boundaries", "", md_table(tables[v]), "",
                  f"Paired by boundary, the uncertainty-driven planner needed fewer tests than the fixed design on "
                  f"{p['fewer_tests']} of {p['n']} boundaries, the same number on {p['same']} and more on {p['more_tests']}.", ""]
        if v == "two_variable":
            ci = two.get("median_ratio_vs_fixed_95ci") or [None, None]
            if ci[0] is not None and verdict["ratio"] == verdict["ratio"]:
                lines += [f"Ratio of medians (uncertainty-driven / fixed matrix): {verdict['ratio']:.2f}, with a 95% "
                          f"paired bootstrap interval of {ci[0]:.2f}-{ci[1]:.2f} ({N_BOOTSTRAP} resamples of boundaries).", ""]
    if sens_cfgs:
        lines += ["### Fixed-matrix layout (sensitivity check)", "",
                  "A fixed matrix's run order and levels are arbitrary choices, and here they matter. MOC rises as pressure "
                  "falls, so the simulated minimum always lies at the highest pressure, 1.1 atm. The plan's matrix levels "
                  "stop at 1.05 atm. The same boundaries and noise were rerun with other layouts.", ""]
        for v in ("two_variable", "go_no_go"):
            if v in sens_cfgs:
                u_raw = get(tables[v], "uncertainty_driven")["_raw"]
                lines += [f"**{VARIANT_TITLES[v].split(' (')[0]}**", "", sensitivity_md(v, sens_cfgs[v], u_raw), ""]
    lines += ["### One line per variant", ""]
    lines += [f"- {variant_sentence(v, tables[v], counts)}" for v in VARIANT_ORDER if v in tables]
    lines += ["", "![Chart](chart.png)", "", "## Method", "",
              "**Simulated boundary.** For each seed, the MOC (the minimum oxygen that sustains burning) is an asymmetric U "
              "in log-flow. The quench side, at low flow, is steep, with curvature 20-60 per unit of normalized log-flow squared. "
              "The blowoff side, at high flow, is gentler (8-30). At 1.1 atm the minimum sits at a flow of 1.2-13 cm/s. Its value, "
              "the minimum extinction oxygen, is drawn uniformly in [13.0, 14.0)%. In the two-variable variant, MOC rises as "
              "pressure falls, by +3 to +8 points at the optimum flow at 0.15 atm. Two interaction terms couple flow and "
              "pressure. The flow at the minimum shifts with pressure, and the U narrows by a factor of 1.5-2.5 at "
              "0.15 atm. The shift is capped so that MOC rises as pressure falls at every flow, which keeps the boundaries nested. "
              "Values are clipped to 13-34%. The one-variable and go/no-go boundaries are the 1.1 atm slices of the same random "
              "boundaries.", "",
              "**Tests.** A limit test returns the MOC at the chosen condition plus Gaussian noise (s.d. 0.5 points). A "
              "go/no-go test at a chosen flow and oxygen returns burn when the oxygen exceeds the boundary plus Gaussian "
              "noise (s.d. 0.5 points), and no-burn otherwise. On a given boundary, every strategy sees the same noise "
              "sequence (common random numbers).", "",
              "**Estimators (shared by all strategies).** The limit-test variants use Gaussian-process regression. It has "
              "a Matern-5/2 kernel with one length scale per input, a constant mean, standardized outputs and the known "
              "noise s.d. of 0.5. The signal variance and length scales are refitted by maximum marginal likelihood at the "
              "first fit and every 5th test, and held fixed in between for speed. The estimate after each test is the "
              "minimum of the posterior mean over a dense grid: 41x41 for two variables, 201 points for one. The first estimate "
              f"comes after test {s['variants']['two_variable']['first_estimate_after_test']} for two variables and after test "
              f"{s['variants']['one_variable']['first_estimate_after_test']} for one. The go/no-go variant uses a Bayesian grid "
              "posterior over the parameters of an asymmetric U-shaped boundary: the minimum oxygen, the flow at the minimum and "
              "two curvatures. It has a probit likelihood and known noise. Its prior is uniform over a minimum oxygen of 11-22%, "
              "the whole flow range and curvatures of 5-120. The estimate is the posterior mean of the minimum extinction "
              "oxygen, from test 5 on.", "",
              "## Settings", "",
              f"- Label: {sim.LABEL}. Budget {sim.BUDGET} tests per run; tolerance {sim.TOL} O2 points; noise s.d. "
              f"{sim.NOISE_SD} points; lower-confidence-bound kappa = {sim.KAPPA}.",
              f"- Boundaries: {counts.get('two_variable', 0)} two-variable, {counts.get('go_no_go', 0)} go/no-go and "
              f"{counts.get('one_variable', 0)} one-variable. Boundary i uses seed {BOUNDARY_SEED_BASE} + i in every variant. "
              f"Runs: {s['counts']['runs_main']} main and {s['counts']['runs_fixed_matrix_sensitivity']} sensitivity.",
              f"- Seeds: noise draws use numpy default_rng([{SEED}, variant code, i]). The random strategy uses "
              f"default_rng([{SEED}, variant code, i, strategy code]). The shuffled matrix order uses seed "
              f"{sim.FIXED_SHUFFLE_SEED}, and the bootstrap uses seed {list(BOOTSTRAP_SEED)}.",
              "- Fixed-matrix levels (main) are set at 5%, 23%, 41%, 59%, 77% and 95% of each normalized axis: flows "
              f"{', '.join(f'{v:.2f}' for v in sim.flow_cm_s(sim.MATRIX_LEVELS))} cm/s; pressures "
              f"{', '.join(f'{v:.3f}' for v in sim.pressure_atm(sim.MATRIX_LEVELS))} atm; oxygen "
              f"{', '.join(f'{v:.2f}' for v in sim.o2_pct(sim.MATRIX_LEVELS))}%.",
              f"- Runtime: {res['runtime_s']:.0f} s on one shared CPU core ("
              + ", ".join(f"{PART_NAMES.get(k, k)} {v:.0f} s" for k, v in s["runtime_by_part_s"].items()) + ").",
              f"- Run sizing: {RUN_SIZING}",
              "- `results.json` records every setting under `settings`.", "",
              "## Limitations", "",
              "- **Simulated boundaries, not NASA data.** The boundaries are anchored only on the published SoFIE-GEL ranges. "
              "The U shape, curvatures, pressure rise, interaction terms and noise level are assumptions, not fits to "
              "measurements.",
              "- MOC rises as pressure falls, so the simulated minimum always lies at the highest pressure. A fixed matrix's "
              "layout therefore matters (see the sensitivity check). A team that already knows where the hazard lies can "
              "order a matrix to find it early. The planner was given no such hint.",
              "- The go/no-go model has the same functional form as the simulated boundary. That is a best case for "
              "model-based estimation, although all four strategies share it. Real boundaries will not match any model exactly.",
              "- The tests are idealized: one limit test returns one noisy MOC value. There is no cost for changing "
              "conditions, no failed or aborted tests and no facility constraint such as drop-tower test time.",
              "- Gaussian-process hyperparameters are refitted only every 5th test, as stated above. The lower-confidence-bound "
              "setting (kappa = 2) and the start designs were fixed in advance, not tuned.",
              "- These numbers describe this simulation only. They can support planning decisions, not safety limits.", "",
              "## How to rerun", "",
              "From the package root (`nextburn_experiments/`):", "",
              "```",
              "python experiments/exp6_planner_sim.py            # full run: results/exp6/ and dashboard_data/exp6_sim.json",
              "python experiments/exp6_planner_sim.py --quick    # ~10-boundary smoke run: results/exp6/quick/ only",
              "python experiments/exp6_planner_sim.py --boundaries 300 --small-boundaries 150",
              "```", "",
              "Seeds are fixed, so a rerun with the same counts reproduces these numbers. `--no-sensitivity` skips the "
              "fixed-matrix layout check.", "",
              "## Files", "",
              f"- `{out_rel}/results.json`: settings, strategy tables, headline, claim and pass.",
              f"- `{out_rel}/runs.csv`: one row per boundary, variant and strategy. `tests_to_converge` is blank when "
              "the run never converged.",
              f"- `{out_rel}/runs_fixed_matrix_sensitivity.csv`: fixed-matrix runs with the other layouts.",
              f"- `{out_rel}/chart.png`: the slide chart.",
              "- `dashboard_data/exp6_sim.json`: a compact copy for the dashboard (full runs only).", ""]
    Path(path).write_text("\n".join(lines))


# --------------------------------------------------------------------------- main
def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--boundaries", type=int, default=None,
                   help=f"boundaries for the two-variable variant (default {DEFAULT_MAIN}; {QUICK_N} with --quick)")
    p.add_argument("--small-boundaries", type=int, default=None,
                   help=f"boundaries for the one-variable and go/no-go variants "
                        f"(default min(--boundaries, {DEFAULT_SMALL}))")
    p.add_argument("--quick", action="store_true",
                   help="fast smoke run (~10 boundaries) written to results/exp6/quick/")
    p.add_argument("--out", default=None, help="output directory (default results/exp6 or results/exp6/quick)")
    p.add_argument("--no-sensitivity", action="store_true", help="skip the fixed-matrix layout check")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    t_start = time.perf_counter()
    n_main = args.boundaries if args.boundaries is not None else (QUICK_N if args.quick else DEFAULT_MAIN)
    n_small = args.small_boundaries if args.small_boundaries is not None else min(n_main, DEFAULT_SMALL)
    if n_main < 1 or n_small < 1:
        raise SystemExit("boundary counts must be positive")
    out_dir = Path(args.out) if args.out else ROOT / "results" / "exp6" / ("quick" if args.quick else "")
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        out_rel = out_dir.relative_to(ROOT).as_posix()
    except ValueError:
        out_rel = out_dir.as_posix()
    counts = {"two_variable": n_main, "go_no_go": n_small, "one_variable": n_small}
    log(TITLE)
    log(f"boundaries: two-variable {n_main}, go/no-go {n_small}, one-variable {n_small}; output {out_rel}")

    strategies = list(sim.STRATEGIES)
    rows_by_variant, tables, timing = {}, {}, {}
    for v in ("two_variable", "one_variable", "go_no_go"):
        rows, secs = run_variant(v, counts[v], strategies)
        rows_by_variant[v] = rows
        tables[v] = strategy_table(rows, v, strategies)
        timing[v] = secs
        for t in tables[v]:
            r = t["_raw"]
            log(f"    {t['name']:<20} success {fmt_pct(r['success_rate']):>4}  median {fmt_tests(r['median_tests']):>5}"
                f"  p80 {fmt_tests(r['p80_tests']):>5}")

    sens_rows, sens_cfgs = [], {}
    if not args.no_sensitivity:
        t0 = time.perf_counter()
        for v, cfgs in SENSITIVITY.items():
            main_fixed = get(tables[v], "fixed_matrix")["_raw"]
            sens_cfgs[v] = {MAIN_FIXED: main_fixed}
            for cfg in cfgs:
                rows, _ = run_variant(v, counts[v], ["fixed_matrix"], fixed=cfg, tag=f", fixed {cfg[0]}/{cfg[1]}")
                sens_rows += rows
                sens_cfgs[v][cfg] = sim.summarize(ttc_by(rows, "fixed_matrix"))
                r = sens_cfgs[v][cfg]
                log(f"    fixed_matrix {cfg[0]}/{cfg[1]}: success {fmt_pct(r['success_rate'])} median "
                    f"{fmt_tests(r['median_tests'])} p80 {fmt_tests(r['p80_tests'])}")
        timing["fixed_matrix_sensitivity"] = time.perf_counter() - t0

    fixed_two = sens_cfgs.get("two_variable", {MAIN_FIXED: get(tables["two_variable"], "fixed_matrix")["_raw"]})
    verdict = build_verdict(tables, fixed_two, n_main)
    two_rows = rows_by_variant["two_variable"]
    ci = bootstrap_median_ratio(ttc_by(two_rows, "uncertainty_driven"), ttc_by(two_rows, "fixed_matrix"))

    variants = {}
    for v in ("two_variable", "one_variable", "go_no_go"):
        spec = sim.make_variant(v)
        entry = {
            "title": VARIANT_TITLES[v],
            "n_boundaries": counts[v],
            "measurement": "noisy MOC value (limit test)" if spec.measurement == "limit" else "burn / no-burn",
            "test_variables": {"two_variable": ["log flow", "pressure"], "one_variable": ["log flow"],
                               "go_no_go": ["log flow", "oxygen"]}[v],
            "fixed_design": sim.FIXED_LABELS[v],
            "fixed_order": spec.fixed_order,
            "fixed_levels": spec.fixed_levels,
            "first_estimate_after_test": spec.n_first,
            "strategies": [public(t) for t in tables[v]],
            "paired_vs_fixed": paired(rows_by_variant[v], rows_by_variant[v]),
        }
        if v == "two_variable":
            entry["median_ratio_vs_fixed"] = jnum(verdict["ratio"], 3)
            entry["median_ratio_vs_fixed_95ci"] = [jnum(ci[0], 3), jnum(ci[1], 3)]
        if v in sens_cfgs:
            entry["fixed_matrix_sensitivity"] = [
                {"order": cfg[0], "levels": cfg[1], "main": cfg == MAIN_FIXED,
                 "description": config_text(v, *cfg), "n_runs": sm["n_runs"], "n_success": sm["n_success"],
                 "success_rate": jnum(sm["success_rate"], 4), "median_tests": jnum(sm["median_tests"], 2),
                 "p80_tests": jnum(sm["p80_tests"], 2), "mean_tests": jnum(sm["mean_tests"], 2)}
                for cfg, sm in sens_cfgs[v].items()]
        variants[v] = entry

    settings = {
        "label": sim.LABEL,
        "quick_run": bool(args.quick),
        "budget_tests": sim.BUDGET,
        "tolerance_o2_pts": sim.TOL,
        "noise_sd_o2_pts": sim.NOISE_SD,
        "lcb_kappa": sim.KAPPA,
        "counts": {"two_variable_boundaries": n_main, "one_variable_boundaries": n_small,
                   "go_no_go_boundaries": n_small, "strategies": len(strategies),
                   "runs_main": sum(len(r) for r in rows_by_variant.values()),
                   "runs_fixed_matrix_sensitivity": len(sens_rows)},
        "seeds": {"master": SEED, "boundary_seed": f"{BOUNDARY_SEED_BASE} + boundary index (same in every variant)",
                  "noise_draws": f"numpy default_rng([{SEED}, variant_code, boundary_index]).standard_normal({sim.BUDGET})",
                  "random_strategy": f"numpy default_rng([{SEED}, variant_code, boundary_index, strategy_code])",
                  "variant_codes": VARIANT_CODES, "strategy_codes": STRATEGY_CODES,
                  "fixed_matrix_shuffle": sim.FIXED_SHUFFLE_SEED, "bootstrap": list(BOOTSTRAP_SEED),
                  "bootstrap_resamples": N_BOOTSTRAP},
        "anchors_published_ranges": {"flow_cm_s": list(sim.FLOW_RANGE_CM_S), "o2_pct": list(sim.O2_RANGE_PCT),
                                     "pressure_atm": list(sim.PRESSURE_RANGE_ATM),
                                     "source": "NASA SoFIE-GEL operating ranges as quoted in the team plan"},
        "boundary_model": {
            "form": "MOC = clip(xmin + rise*((1-curv)*lo + curv*lo^2) + a_side*(1+steep*lo)*(u - u0 - shift*lo)^2, "
                    "13, 34); u = normalized log10 flow, lo = 1 - normalized pressure (0 at 1.1 atm, 1 at 0.15 atm)",
            "xmin_min_extinction_o2_pct": list(sim.MIN_EXTINCTION_O2_RANGE),
            "u0_flow_at_min_normalized": [0.30, 0.70],
            "u0_flow_at_min_cm_s": [round(float(sim.flow_cm_s(0.30)), 2), round(float(sim.flow_cm_s(0.70)), 2)],
            "a_quench_low_flow_side": [20.0, 60.0], "a_blowoff_high_flow_side": [8.0, 30.0],
            "rise_o2_pts_at_0p15_atm": [3.0, 8.0], "curv": [0.0, 0.5], "steep": [0.5, 1.5],
            "shift": "random sign x U(0.3, 1.0) x the largest shift that keeps MOC rising as pressure falls at "
                     "every flow",
            "minimum_location": "u = u0 at 1.1 atm (the highest pressure)",
            "one_variable_and_go_no_go": "1.1 atm slice of the same boundary (flow only)",
        },
        "fixed_matrix": {"levels_normalized": {k: [round(float(x), 3) for x in lv]
                                               for k, lv in sim.MATRIX_LEVEL_SETS.items()},
                         "main_levels": "inset (5-95% of each range, as in the plan prototype)",
                         "flow_levels_cm_s": [round(float(x), 3) for x in sim.flow_cm_s(sim.MATRIX_LEVELS)],
                         "pressure_levels_atm": [round(float(x), 4) for x in sim.pressure_atm(sim.MATRIX_LEVELS)],
                         "o2_levels_pct": [round(float(x), 2) for x in sim.o2_pct(sim.MATRIX_LEVELS)],
                         "main_order": sim.FIXED_ORDER_LABELS[MAIN_FIXED[0]],
                         "after_36_tests": "the matrix repeats from its first cell (tests 37-40)",
                         "one_variable": "6 flows swept low to high, repeated",
                         "sensitivity_designs": {v: [f"{o}/{lv}" for o, lv in c] for v, c in SENSITIVITY.items()}},
        "space_filling": "unscrambled Halton sequence, bases 2 (flow) and 3 (pressure or oxygen), origin skipped",
        "random": "independent uniform draws over the normalized test range",
        "uncertainty_driven": "first n Halton points (n = first_estimate_after_test), then the grid point minimizing "
                              "posterior mean - kappa * posterior s.d. of MOC (go/no-go: the flow minimizing that "
                              "bound, tested at the posterior-mean boundary oxygen)",
        "estimator_limit_tests": {
            "model": "Gaussian-process regression, Matern-5/2 ARD kernel, constant mean, outputs standardized, "
                     "known noise s.d. 0.5 O2 points",
            "hyperparameters": "signal variance and length scales by maximum marginal likelihood (L-BFGS-B, warm "
                               "start + default start), refitted at the first fit and every 5th test, fixed in "
                               "between",
            "bounds": {"signal_variance_standardized": [0.05, 20.0], "length_scale_normalized": [0.05, 2.0]},
            "estimate": "minimum of the posterior mean over a dense grid (41x41 two-variable, 201 points "
                        "one-variable)",
        },
        "estimator_go_no_go": {
            "model": "Bayesian grid posterior over (xmin, u0, aL, aR) of an asymmetric U boundary clipped at 34%, "
                     "probit likelihood with known noise s.d. 0.5 (likelihood read from a 0.002-point lookup table)",
            "prior_grid": {"xmin_pct": "11.0 to 22.0 in steps of 0.1", "u0": "33 points over [0, 1]",
                           "aL_aR": "7 log-spaced values over [5, 120] each"},
            "estimate": "posterior mean of xmin (minimum extinction oxygen)",
        },
        "convergence": "first test count after which the estimate stays within tolerance for the rest of the "
                       "budget; never converging = failure (infinite); median and 80th percentile use linear "
                       "interpolation with failures as infinite (null = not reached); mean_tests is over converged "
                       "runs only",
        "claim_rule": f"'about half' only if the two-variable pass holds and the median ratio is within "
                      f"{ABOUT_HALF[0]:.2f}-{ABOUT_HALF[1]:.2f}; qualified by the fixed-matrix layout check",
        "runtime_by_part_s": {k: round(v, 1) for k, v in timing.items()},
        "run_sizing": RUN_SIZING,
        "variants": {v: {"first_estimate_after_test": variants[v]["first_estimate_after_test"],
                         "n_boundaries": counts[v]} for v in variants},
    }
    res = {
        "experiment": 6,
        "title": TITLE,
        "label": sim.LABEL,
        "settings": settings,
        "variants": variants,
        "headline": verdict["headline"],
        "claim": verdict["claim"],
        "caveats": verdict["caveats"],
        "pass": verdict["pass"],
        "runtime_s": None,
        "generated_at": None,
    }

    write_csv(out_dir / "runs.csv", [r for v in ("two_variable", "one_variable", "go_no_go")
                                     for r in rows_by_variant[v]])
    if sens_rows:
        write_csv(out_dir / "runs_fixed_matrix_sensitivity.csv", sens_rows)
    make_chart(out_dir / "chart.png", tables, counts, verdict, fixed_two)

    runtime = time.perf_counter() - t_start
    res["runtime_s"] = round(runtime, 1)
    res["generated_at"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    write_markdown(out_dir / "results.md", res, tables, sens_cfgs, verdict, counts, args.quick, out_rel)
    (out_dir / "results.json").write_text(json.dumps(res, indent=2) + "\n")

    dash = {
        "experiment": 6,
        "label": sim.LABEL,
        "title": res["title"],
        "headline": res["headline"],
        "claim": res["claim"],
        "pass": res["pass"],
        "caveats": res["caveats"],
        "budget_tests": sim.BUDGET,
        "tolerance_o2_pts": sim.TOL,
        "variants": {v: {"n_boundaries": counts[v],
                         "strategies": [{k: t[k] for k in ("name", "label", "success_rate", "median_tests",
                                                           "p80_tests")} for t in variants[v]["strategies"]]}
                     for v in VARIANT_ORDER},
        "fixed_matrix_sensitivity_two_variable": [
            {k: e[k] for k in ("order", "levels", "main", "success_rate", "median_tests", "p80_tests")}
            for e in variants["two_variable"].get("fixed_matrix_sensitivity", [])],
        "note": "SIMULATION: simulated boundaries anchored on SoFIE-GEL ranges, not NASA data. "
                "null median/p80 = not reached within the 40-test budget.",
        "source": f"{out_rel}/results.json",
        "generated_at": res["generated_at"],
    }
    if args.quick or args.out:
        (out_dir / "dashboard_exp6_sim.json").write_text(json.dumps(dash, indent=2) + "\n")
    else:
        dash_dir = ROOT / "dashboard_data"
        dash_dir.mkdir(exist_ok=True)
        (dash_dir / "exp6_sim.json").write_text(json.dumps(dash, indent=2) + "\n")

    log("")
    log(f"HEADLINE: {verdict['headline']}")
    log(f"CLAIM:    {verdict['claim']}")
    for c in verdict["caveats"]:
        log(f"CAVEAT:   {c}")
    log(f"PASS:     {verdict['pass']}")
    log(f"runtime {runtime:.1f} s; outputs in {out_rel}")
    return res


if __name__ == "__main__":
    main()
