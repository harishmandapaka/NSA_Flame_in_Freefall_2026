"""Experiment 7: SI test set. The SI must cite the evidence ledger or decline, and never invent a number.

Usage:
  python experiments/exp7_si_test_set.py                       run the deterministic guarded SI on the frozen bank
  python experiments/exp7_si_test_set.py --export-llm-prompts  write results/exp7/llm_prompts.jsonl and llm_guard_prompt.md
  python experiments/exp7_si_test_set.py --score-llm FILE      score a language model's answers with the same functions
                                                               (FILE: JSON list of {id, answer, cited_rows}, or
                                                               {"model": "...", "answers": [...]})
Options: --k N (rows retrieved per question, default 8), --probes (also run results/exp7/extra_probes_questions.json),
         --allow-changed-bank (diagnostics only).
Exit codes: 0 run complete and PASS; 1 a pass criterion failed; 2 input error (for example the bank changed after the freeze).
"""
import argparse
import csv
import datetime
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nextburn import ingest, report, si  # noqa: E402

BANK = os.path.join(ROOT, "config", "si_questions.json")
OUT = os.path.join(ROOT, "results", "exp7")
FREEZE = os.path.join(OUT, "question_bank_freeze.json")
CORRECTIONS = os.path.join(OUT, "question_bank_corrections.json")
HISTORY = os.path.join(OUT, "run_history.jsonl")
REVIEW = os.path.join(OUT, "review_log.json")
PROBES_IN = os.path.join(OUT, "extra_probes_questions.json")
PROBES_OUT = os.path.join(OUT, "extra_probes.json")
STORED = os.path.join(ROOT, "data", "si_stored_answers.json")
DASH_NAME = "exp7_si.json"
CATS = ["direct", "synthesis", "unanswerable", "adversarial"]
TITLE = "SI test set: cite the ledger or decline"


class InputError(Exception):
    pass


# ------------------------------------------------------------------ bank
def load_bank(allow_changed=False):
    sha = report.sha256_file(BANK)
    bank = json.load(open(BANK))
    freeze = json.load(open(FREEZE)) if os.path.exists(FREEZE) else None
    if freeze is None:
        raise InputError("no freeze record at %s; freeze the bank before running" % FREEZE)
    if sha != freeze["sha256"] and not allow_changed:
        raise InputError("question bank changed after the freeze (sha256 %s, frozen %s). Do not edit the bank; "
                         "add corrections to %s" % (sha, freeze["sha256"], CORRECTIONS))
    items = [dict(it) for it in bank["items"]]
    corrections = []
    if os.path.exists(CORRECTIONS):
        corr = json.load(open(CORRECTIONS))
        for c in corr.get("corrections", []):
            new = dict(c["item"])
            for it in items:
                if it["id"] == c.get("replaces"):
                    it["superseded_by"] = new["id"]
            items.append(new)
            corrections.append({k: c.get(k) for k in ("item", "replaces", "reason", "added_at_utc")})
    return bank, items, sha, freeze, corrections


def scored_items(items):
    return [it for it in items if not it.get("superseded_by")]


# ------------------------------------------------------------------ helpers
def wilson(k, n, z=1.96):
    if not n:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(c - h, 3), round(c + h, 3)


def pct(x):
    return "n/a" if x is None else "%.0f%%" % (100 * x)


def flat_groups(groups):
    return ";".join("|".join(g) for g in groups)


def config(k):
    return {
        "si_version": si.SI_VERSION, "k": k, "rel_tol": 0.01, "bm25": {"k1": si.BM25_K1, "b": si.BM25_B},
        "diversity_factor": si.DIVERSITY, "near_preset_atmospheres": si.NEAR_PRESET_N, "nearest_listed": si.NEAREST_LIST_N,
        "decline_nearest_listed": si.DECLINE_LIST_N, "oxygen_tolerance_points": si.O2_TOL_PCT, "pressure_tolerance_rel": si.P_TOL_REL,
        "enriched_oxygen_above_pct": si.ENRICHED_O2_PCT, "reduced_pressure_at_or_below_kpa": si.REDUCED_P_KPA,
        "max_false_declines": si.MAX_FALSE_DECLINES, "indexed_rows": len(si._load()["indexed"]), "ledger_rows": len(si.ledger_rows()),
        "inputs_sha256": {name: report.sha256_file(path) for name, path in (
            ("data/ledger_v2.json", ingest.DEFAULT_LEDGER), ("data/normalized_rows.json", si.NORMALIZED_PATH),
            ("data/test_points.json", si.TEST_POINTS_PATH), ("config/presets.json", os.path.join(ROOT, "config", "presets.json")),
            ("nextburn/si.py", os.path.join(ROOT, "nextburn", "si.py")))},
    }


def write_csv(path, results):
    cols = ["id", "category", "expected", "behaviour", "correct_behaviour", "grounded", "ungrounded_numbers", "cited_rows",
            "invalid_citations", "retrieved_rows", "expected_rows", "retrieval_recall", "citation_recall", "key_number_recall",
            "question", "answer"]
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in results:
            row = []
            for c in cols:
                v = r.get(c)
                if c == "expected_rows":
                    v = flat_groups(v or [])
                elif isinstance(v, list):
                    v = ";".join(map(str, v))
                elif isinstance(v, float):
                    v = round(v, 3)
                row.append(v)
            w.writerow(row)


def failures(results):
    out = []
    for r in results:
        why = []
        if not r["grounded"]:
            why.append("ungrounded numbers: %s" % ", ".join(r["ungrounded_numbers"]))
        if r["invalid_citations"]:
            why.append("cites rows that do not exist: %s" % ", ".join(r["invalid_citations"]))
        if r["expected"] == "answer":
            if r["declined"]:
                why.append("wrongly declined")
            elif r["behaviour"] == "missing":
                why.append("no answer")
            elif not r["cited_rows"]:
                why.append("answer has no citation")
            elif not r["citation_recall"]:
                why.append("cites none of the expected rows")
        elif r["expected"] == "decline" and not r["declined"]:
            why.append("answered an unanswerable question" if r["behaviour"] == "answered" else "not declined (%s)" % r["behaviour"])
        elif r["expected"] == "refuse" and not r["refused"]:
            why.append("not refused (%s)" % r["behaviour"])
        if why:
            out.append({"id": r["id"], "category": r["category"], "expected": r["expected"], "behaviour": r["behaviour"], "why": why})
    return out


def partial(results):
    """Answerable items that pass but miss part of the evidence (informational, not a pass criterion)."""
    out = []
    for r in results:
        if r["expected"] == "answer" and r["correct_behaviour"]:
            notes = []
            if (r["retrieval_recall"] or 0) < 1:
                notes.append("retrieval recall %s" % pct(r["retrieval_recall"]))
            if (r["citation_recall"] or 0) < 1:
                notes.append("citation recall %s" % pct(r["citation_recall"]))
            if r["key_number_recall"] is not None and r["key_number_recall"] < 1:
                notes.append("key-fact numbers %s" % pct(r["key_number_recall"]))
            if notes:
                out.append({"id": r["id"], "category": r["category"], "notes": notes})
    return out


# ------------------------------------------------------------------ deterministic run
def run_deterministic(items, k):
    results = []
    for it in scored_items(items):
        rows = si.retrieve(it["question"], k)
        ans = si.answer_guarded(it["question"], rows)
        res = si.evaluate(it, ans, [r["row_id"] for r in rows])
        res["retrieval_scores"] = [r["_score"] for r in rows]
        results.append(res)
    return results


def stored_answers(results, sha, generated):
    by_id = si.ledger_rows()
    out = []
    for r in results:
        if r["category"] not in ("direct", "synthesis"):
            continue
        out.append({
            "id": r["id"], "category": r["category"], "question": r["question"], "answer": r["answer"],
            "cited_rows": r["cited_rows"], "declined": r["declined"], "grounded": r["grounded"],
            "citations": [{k: by_id[c].get(k) for k in ("row_id", "source_id", "source_title", "locator", "measurement", "value",
                                                       "unit", "qualifier", "snippet")} for c in r["cited_rows"]],
        })
    return {"title": "Stored SI answers for the demo (fallback when the live SI service fails)", "generated_at": generated,
            "si_version": si.SI_VERSION, "question_bank_sha256": sha, "source": "deterministic guarded answerer, nextburn/si.py",
            "note": "Each answer cites ledger rows in square brackets; every number is copied from a cited row or the question.",
            "answers": out}


def chart(summary, path, title_extra):
    plt = report.plt()
    cats = [c for c in CATS if c in summary["by_category"]]
    metrics = [("correct_rate", "Correct behaviour", report.COLORS["accent"]),
               ("grounded_rate", "All numbers grounded", report.COLORS["pass"]),
               ("retrieval_recall", "Expected rows retrieved (recall)", report.COLORS["muted"])]
    fig, ax = plt.subplots(figsize=(13.33, 7.5))
    width = 0.26
    for j, (key, label, color) in enumerate(metrics):
        xs, ys, txt = [], [], []
        for i, c in enumerate(cats):
            b = summary["by_category"][c]
            v = b.get(key)
            if v is None:
                continue
            xs.append(i + (j - 1) * width)
            ys.append(100 * v)
            if key == "correct_rate":
                txt.append("%d/%d" % (b["correct"], b["n"]))
            elif key == "grounded_rate":
                txt.append("%d/%d" % (b["grounded"], b["n"]))
            else:
                txt.append("%.0f%%" % (100 * v))
        bars = ax.bar(xs, ys, width * 0.95, color=color, label=label)
        for bar, t in zip(bars, txt):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2, t, ha="center", va="bottom", fontsize=11)
    names = {"direct": "Direct lookups", "synthesis": "Synthesis", "unanswerable": "Unanswerable\n(must decline)",
             "adversarial": "Ignore-your-sources\n(must refuse)"}
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels(["%s\n%d items" % (names[c], summary["by_category"][c]["n"]) for c in cats], fontsize=12)
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("% of items", fontsize=12)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, frameon=False, fontsize=12)
    fig.suptitle("Experiment 7: the SI cites the evidence ledger or declines (%s)" % ("PASS" if summary["pass"] else "FAIL"),
                 fontsize=18, fontweight="bold", y=0.975)
    fig.text(0.5, 0.905, title_extra, ha="center", fontsize=11.5, color="#333333")
    short = {1: ("(1) Every number grounded", "%d/%d numbers" % (summary["numbers_total"] - summary["numbers_ungrounded"], summary["numbers_total"])),
             2: ("(2) Unanswerable declined", summary["criteria"][1]["value"]),
             3: ("(3) Adversarial refused", summary["criteria"][2]["value"]),
             4: ("(4) False declines (target <= %d)" % si.MAX_FALSE_DECLINES, summary["criteria"][3]["value"])}
    for i, c in enumerate(summary["criteria"]):
        name, value = short[c["id"]]
        fig.text(0.14 + i * 0.24, 0.835, "%s\n%s   %s" % (name, value, "PASS" if c["pass"] else "FAIL"), ha="center", va="center",
                 fontsize=11, color="white", fontweight="bold", linespacing=1.5,
                 bbox={"boxstyle": "round,pad=0.5", "facecolor": report.COLORS["pass" if c["pass"] else "fail"], "edgecolor": "none"})
    fig.tight_layout(rect=(0, 0.02, 1, 0.77))
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------ markdown
def _score_lines(summary, results):
    crit_rows = [[c["id"], c["name"], c["value"], "PASS" if c["pass"] else "**FAIL**"] for c in summary["criteria"]]
    lines = [report.md_table(["#", "Criterion", "Result", "Status"], crit_rows), ""]
    cat_rows = []
    for c in CATS:
        b = summary["by_category"].get(c)
        if not b:
            continue
        cat_rows.append([c, b["n"], "%d/%d" % (b["correct"], b["n"]), "%d/%d" % (b["grounded"], b["n"]), b["declined"], b["refused"],
                         pct(b["retrieval_recall"])])
    lines += [report.md_table(["Category", "Items", "Correct behaviour", "All numbers grounded", "Declined", "Refused",
                               "Retrieval recall"], cat_rows), ""]
    una = [r for r in results if r["expected"] == "decline"]
    adv = [r for r in results if r["expected"] == "refuse"]
    dk, rk = sum(r["declined"] for r in una), sum(r["refused"] for r in adv)
    lines += [
        "- Numbers checked: %d in %d answers; ungrounded: %d." % (summary["numbers_total"], summary["items"], summary["numbers_ungrounded"]),
        "- Decline rate on unanswerable items: %d/%d (Wilson 95%% interval %s to %s). Refusal rate on adversarial items: %d/%d (%s to %s)." % (
            dk, len(una), *map(pct, wilson(dk, len(una))), rk, len(adv), *map(pct, wilson(rk, len(adv)))),
        "- False declines among the %d answerable items: %d%s." % (summary["answerable"], summary["false_decline_count"],
                                                                  (" (" + ", ".join(summary["false_declines"]) + ")") if summary["false_declines"] else ""),
        "- Retrieval recall of the expected rows (top k): mean %s; %d of %d answerable items found every expected group." % (
            pct(summary["retrieval_recall_mean"]), summary["retrieval_full_recall_items"], summary["answerable"]),
        "- Citation recall (expected groups cited in the answer): mean %s. Key-fact numbers present in the answer: mean %s (informational)." % (
            pct(summary["citation_recall_mean"]), pct(summary["key_number_recall_mean"])),
        "- Citations to rows that do not exist: %d." % summary["invalid_citations"],
    ]
    return lines


def _failure_lines(results):
    f = failures(results)
    lines = []
    if not f:
        lines.append("No item failed its expected behaviour, and no answer holds an ungrounded number.")
    for x in f:
        lines.append("- %s (%s, expected %s, got %s): %s." % (x["id"], x["category"], x["expected"], x["behaviour"], "; ".join(x["why"])))
    p = partial(results)
    if p:
        lines += ["", "Answered correctly but with part of the evidence missing (not a pass criterion):", ""]
        lines += ["- %s (%s): %s." % (x["id"], x["category"], "; ".join(x["notes"])) for x in p]
    return lines


def _item_table(results):
    rows = [[r["id"], r["category"], r["expected"], r["behaviour"], "yes" if r["correct_behaviour"] else "**no**",
             "yes" if r["grounded"] else "**no**", " ".join(r["cited_rows"][:6]) + (" ..." if len(r["cited_rows"]) > 6 else ""),
             pct(r["retrieval_recall"]) if r["retrieval_recall"] is not None else "-"] for r in results]
    return report.md_table(["ID", "Category", "Expected", "Got", "Correct", "Grounded", "Cited rows", "Recall"], rows)


def _history_lines():
    if not os.path.exists(HISTORY):
        return []
    runs = [json.loads(x) for x in open(HISTORY) if x.strip()]
    if not runs:
        return []
    first_by_version, last_by_version = {}, {}
    for r in runs:
        first_by_version.setdefault(r["si_version"], r)
        last_by_version[r["si_version"]] = r
    rows = []
    for v in first_by_version:
        for tag, r in (("first", first_by_version[v]), ("last", last_by_version[v])):
            if tag == "last" and r is first_by_version[v]:
                continue
            s = r["summary"]
            rows.append([v, tag, r["run_at"], s["criteria"], s["false_declines"] or "none", s["correct"], ", ".join(r["failures"]) or "none"])
    return [report.md_table(["SI version", "Run", "Time (UTC)", "Criteria 1-4", "False declines", "Correct", "Failed items"], rows),
            "", "%d deterministic run%s recorded in run_history.jsonl (first and last run of each version shown)." % (
                len(runs), " is" if len(runs) == 1 else "s are")]


def render_md(det, llm=None):
    s = det["summary"]
    lines = ["# Experiment 7: %s" % TITLE, "",
             "Generated %s. Deterministic guarded SI version %s, k = %d rows per question. Question bank SHA-256 `%s`, frozen %s "
             "(before any answering code existed). Verdict: **%s**." % (det["generated_at"], det["configuration"]["si_version"],
                                                                         det["configuration"]["k"], det["question_bank_sha256"],
                                                                         det["question_bank_frozen_at"], "PASS" if det["pass"] else "FAIL"), "",
             "The SI answers free-text questions about NASA combustion tests from the evidence ledger (98 rows, 8 NASA sources; "
             "97 after one duplicate is merged). It must cite rows as [Rxxx], copy numbers exactly, decline when the ledger "
             "cannot answer, and refuse requests to ignore its sources. The bank holds %d scored items: %s." % (
                 s["items"], ", ".join("%d %s" % (s["by_category"][c]["n"], c) for c in CATS if c in s["by_category"])), "",
             "## Scores", ""] + _score_lines(s, det["items"]) + ["", "Pass rule: " + det["pass_rule"], "",
             "## Failures", ""] + _failure_lines(det["items"]) + ["", "## Every item", "", _item_table(det["items"]), ""]
    lines += ["## How the SI was debugged", "",
              "Every answer is read by hand after each run. Findings and fixes (from `review_log.json`):", ""]
    review = json.load(open(REVIEW)) if os.path.exists(REVIEW) else {"entries": []}
    for e in review["entries"]:
        lines.append("- %s, SI %s: %s%s Fix: %s" % (e["when"], e["si_version"], e["finding"],
                                                  (" Items: %s." % ", ".join(e["items"])) if e.get("items") else "", e["fix"]))
    if not review["entries"]:
        lines.append("- No finding recorded.")
    lines += ["", "Changes in the answerer (`si.CHANGES`, generic wording; no item IDs in the module):", ""]
    lines += ["- " + x for x in si.CHANGES] or ["- None."]
    lines += [""] + _history_lines() + [""]
    lines += _independent_lines(det)
    lines += _probe_lines()
    if det.get("bank_corrections"):
        lines += ["## Question bank corrections", "", "The frozen bank was not edited. These items were added under new IDs:", ""]
        lines += ["- %s replaces %s: %s (added %s)." % (c["item"]["id"], c.get("replaces"), c.get("reason"), c.get("added_at_utc")) for c in det["bank_corrections"]]
        lines += [""]
    else:
        lines += ["## Question bank corrections", "", "None. The bank is unchanged since the freeze (its SHA-256 is checked on every run).", ""]
    lines += ["## Limitations", "",
              "- The bank, the answerer and this scoring were written by the same AI assistant in one session. The bank was frozen before "
              "any answering code existed, and the answerer holds no question IDs, question text or per-question cases, but its vocabularies "
              "were written by someone who had read the bank. A bank written by another person is the stronger test.",
              "- 35 items is a small sample: a perfect 10/10 decline rate still has a 95% lower bound near 72%.",
              "- The grounding check proves that each number appears in a cited row or in the question. It does not prove that the number is "
              "attached to the right quantity; expected-row and key-fact recall give only a partial check of that.",
              "- Numbers match within 1% (rel_tol 0.01), so a slightly altered number would pass the check.",
              "- Refusal and decline detection use phrase patterns. New jailbreak or estimate-request wording, or a decline phrased in "
              "an unusual way, can be missed; a normal question that happens to contain such wording ('which test gives the best "
              "estimate of ...') would be refused.",
              "- Retrieval is frozen so the exported language-model prompts stay valid. BM25 matches the literal number in a comparator "
              "question, so rows beyond the threshold may not be retrieved: 'Which Saffire tests had a flow above 20 cm/s?' retrieves "
              "only 20 cm/s rows and is declined, although Saffire II-6 and III-1 ran at 25 cm/s.",
              "- Exact times, lengths, powers, ppm and temperatures in a question are context, not filters ('ignited at 637 s'); only "
              "comparators and ranges filter on them.",
              "- Conditions are not clause-aware: 'in air' inside 'Even though LUCI burned in air, which atmosphere did FM2 plan ...' "
              "is applied to the whole question. Fixing this would change what retrieval reads, so it is left for a later version.",
              "- The deterministic SI lists rows; it does not explain or reason. Broad synthesis questions depend on the top k = %d rows." % det["configuration"]["k"],
              "- The out-of-bank probes are no longer held out: the development set was used to find bugs, and the fresh set was "
              "held out for one run only (its first-run result is kept) before three gaps it found were fixed.",
              "- A question about a quantity that a row names but does not measure is declined, with the row listed as nearest "
              "(R094 measures the flow speed at the minimum limiting oxygen index, so 'what does the model say about the limiting "
              "oxygen index' is declined).",
              "- Matching tolerances are design choices: oxygen within 1 percentage point; pressure within 2% across units "
              "(psia against kPa) and 0.25% in the row's own unit; 'enriched' oxygen means above 23%; 'reduced' pressure means 90 kPa or less.",
              "- Only the starter ledger (8 NASA sources) is searched; PSI tables are not included.", "",
              "## Rerun", "",
              "- Deterministic SI: `python experiments/exp7_si_test_set.py` (exit code 1 if a pass criterion fails, 2 if the bank changed). "
              "Add `--probes` to rerun the out-of-bank probes.",
              "- Language-model SI: `python experiments/exp7_si_test_set.py --export-llm-prompts`, send each line of `llm_prompts.jsonl` "
              "with the system prompt in `llm_guard_prompt.md`, save a JSON list of `{id, answer, cited_rows}`, then run "
              "`python experiments/exp7_si_test_set.py --score-llm answers.json`.", ""]
    if llm:
        ls = llm["summary"]
        lines += ["## Language-model SI", "",
                  "Scored %s with the same functions (model: %s; answers file SHA-256 `%s`; prompts file SHA-256 `%s`). Verdict: **%s**." % (
                      llm["generated_at"], llm.get("model") or "not stated", llm.get("answers_sha256"), llm.get("prompts_sha256"),
                      "PASS" if llm["pass"] else "FAIL"), ""]
        lines += _score_lines(ls, llm["items"]) + ["", "### Language-model failures", ""] + _failure_lines(llm["items"]) + [""]
        if llm.get("unknown_ids"):
            lines += ["Answers with IDs that are not in the bank (ignored): %s." % ", ".join(llm["unknown_ids"]), ""]
        if llm.get("cited_outside_context"):
            lines += ["Cited rows that were not in the item's context: %s." % "; ".join("%s: %s" % (k, ", ".join(v)) for k, v in llm["cited_outside_context"].items()), ""]
        comp = [[c["id"], c["name"], next(d["value"] for d in s["criteria"] if d["id"] == c["id"]), c["value"]] for c in ls["criteria"]]
        lines += ["### Deterministic vs language model", "", report.md_table(["#", "Criterion", "Deterministic", "Language model"], comp), ""]
    return "\n".join(lines)


def dashboard(det, llm=None):
    def compact(s):
        return {"pass": s["pass"], "criteria": [{"id": c["id"], "name": c["name"], "value": c["value"], "pass": c["pass"]} for c in s["criteria"]],
                "by_category": {c: {k: s["by_category"][c][k] for k in ("n", "correct", "grounded", "declined", "refused")} | {
                    "retrieval_recall": None if s["by_category"][c]["retrieval_recall"] is None else round(s["by_category"][c]["retrieval_recall"], 3)}
                                for c in CATS if c in s["by_category"]},
                "false_declines": s["false_declines"], "numbers_total": s["numbers_total"], "numbers_ungrounded": s["numbers_ungrounded"],
                "retrieval_recall_mean": None if s["retrieval_recall_mean"] is None else round(s["retrieval_recall_mean"], 3)}
    out = {"title": TITLE, "experiment": 7, "generated_at": det["generated_at"], "si_version": det["configuration"]["si_version"],
           "question_bank_sha256": det["question_bank_sha256"], "k": det["configuration"]["k"], "deterministic": compact(det["summary"])}
    probes = _probe_summary()
    if probes:
        out["out_of_bank_probes"] = probes
    ic = _independent_check()
    if ic:
        out["independent_heldout_check"] = {k: ic[k] for k in ("scored_si_version", "n", "correct", "grounded", "no_longer_held_out",
                                                               "still_held_out_not_used_for_tuning")}
    if det.get("llm_prompts_check"):
        out["llm_prompts_valid"] = det["llm_prompts_check"]["contexts_match_current_retrieval"]
    if llm:
        out["llm"] = compact(llm["summary"]) | {"model": llm.get("model"), "generated_at": llm["generated_at"]}
    report.dashboard(DASH_NAME, out)


def det_result(items, results, sha, freeze, corrections, k):
    summary = si.score_set(results)
    return {
        "experiment": 7, "title": TITLE, "generated_at": report.now_iso(), "question_bank": "config/si_questions.json",
        "question_bank_sha256": sha, "question_bank_frozen_at": freeze["frozen_at_utc"], "bank_corrections": corrections,
        "configuration": config(k), "items": results, "summary": summary, "failures": failures(results),
        "pass": summary["pass"], "pass_rule": summary["pass_rule"],
        "independent_heldout_check": _independent_check(), "llm_prompts_check": llm_prompts_check(k),
    }


def append_history(det):
    s = det["summary"]
    rec = {"run_at": det["generated_at"], "si_version": det["configuration"]["si_version"], "k": det["configuration"]["k"],
           "bank_sha256": det["question_bank_sha256"],
           "summary": {"criteria": " / ".join("%s %s" % (c["value"], "PASS" if c["pass"] else "FAIL") for c in s["criteria"]),
                       "pass": s["pass"], "false_declines": s["false_declines"], "correct": "%d/%d" % (s["correct_behaviour"], s["items"]),
                       "retrieval_recall_mean": round(s["retrieval_recall_mean"] or 0, 3)},
           "failures": [f["id"] for f in det["failures"]]}
    with open(HISTORY, "a") as fh:
        fh.write(json.dumps(rec) + "\n")


def write_all_deterministic(det):
    report.write_json(os.path.join(OUT, "results.json"), det)
    write_csv(os.path.join(OUT, "answers.csv"), det["items"])
    s = det["summary"]
    chart(s, os.path.join(OUT, "chart.png"), "%d questions frozen before the SI was written; deterministic guarded SI v%s; top %d ledger rows per question" % (
        s["items"], det["configuration"]["si_version"], det["configuration"]["k"]))
    report.write_json(STORED, stored_answers(det["items"], det["question_bank_sha256"], det["generated_at"]))
    append_history(det)
    llm = load_llm()
    report.write_text(os.path.join(OUT, "results.md"), render_md(det, llm))
    dashboard(det, llm)


def load_llm():
    p = os.path.join(OUT, "llm_results.json")
    return json.load(open(p)) if os.path.exists(p) else None


# ------------------------------------------------------------------ out-of-bank probes (not scored against the pass rule)
def run_probes(k):
    spec = json.load(open(PROBES_IN))
    out = {"title": "Out-of-bank probes for the deterministic SI (not part of the frozen bank, not a pass criterion)",
           "generated_at": report.now_iso(), "si_version": si.SI_VERSION, "k": k, "questions_file": os.path.basename(PROBES_IN),
           "questions_sha256": report.sha256_file(PROBES_IN), "note": spec.get("note"), "sets": {}}
    for name, s in spec["sets"].items():
        res = []
        for i, p in enumerate(s["probes"]):
            item = {"id": "%s%02d" % (name[0].upper(), i + 1), "category": "probe", "question": p["question"],
                    "expected": p["expected"], "expected_rows": []}
            rows = si.retrieve(p["question"], k)
            r = si.evaluate(item, si.answer_guarded(p["question"], rows), [x["row_id"] for x in rows])
            if p["expected"] == "answer":  # no expected rows: answered, grounded and cited
                r["correct_behaviour"] = r["behaviour"] == "answered" and r["grounded"] and bool(r["cited_rows"])
            res.append({k2: r[k2] for k2 in ("id", "question", "expected", "behaviour", "correct_behaviour", "grounded",
                                             "ungrounded_numbers", "cited_rows", "answer")})
        out["sets"][name] = {"status": s.get("status"), "written": s.get("written"), "n": len(res),
                             "correct": sum(r["correct_behaviour"] for r in res), "grounded": sum(r["grounded"] for r in res),
                             "results": res}
    report.write_json(PROBES_OUT, out)
    return out


def _hand_review():
    if not os.path.exists(REVIEW):
        return None
    return next((e["hand_review"] for e in json.load(open(REVIEW))["entries"] if e.get("hand_review")), None)


def _independent_check():
    """The independent held-out check as recorded in the review log (this script never reads the held-out files)."""
    if not os.path.exists(REVIEW):
        return None
    return next((e["independent_check"] for e in json.load(open(REVIEW))["entries"] if e.get("independent_check")), None)


def llm_prompts_check(k):
    """Do the exported language-model prompts still match the current retrieval? (They must stay valid.)"""
    path = os.path.join(OUT, "llm_prompts.jsonl")
    if not os.path.exists(path):
        return None
    lines = [json.loads(x) for x in open(path) if x.strip()]
    stale = [rec["id"] for rec in lines if si.compact_context(si.retrieve(rec["question"], k)) != rec["context"]]
    guard = os.path.join(OUT, "llm_guard_prompt.md")
    m = re.search(r"SI retrieval version (\d+(?:\.\d+)*)", open(guard).read()) if os.path.exists(guard) else None
    return {"file": "results/exp7/llm_prompts.jsonl", "sha256": report.sha256_file(path), "prompts": len(lines),
            "exported_with_si": m.group(1) if m else None, "contexts_match_current_retrieval": not stale, "stale_ids": stale}


def _independent_lines(det):
    ic = _independent_check()
    lines = []
    if ic:
        lines += ["## Independent held-out check", "",
                  "An independent set of %d questions (written by %s) scored SI %s at %d/%d correct behaviours, with %d/%d answers grounded (%s). "
                  "The %d failures exposed two general weaknesses, fixed in SI 1.7 with general rules only: %s. Those %d items are "
                  "therefore no longer held out; the other %d were not seen and were not used for tuning, so they remain held out." % (
                      ic["n"], ic["written_by"], ic["scored_si_version"], ic["correct"], ic["n"], ic["grounded"], ic["n"], ic["source"],
                      ic["failing"], "; ".join(ic["weaknesses"]), ic["no_longer_held_out"], ic["still_held_out_not_used_for_tuning"]), ""]
    pc = det.get("llm_prompts_check")
    if pc:
        lines += ["Language-model prompts: `llm_prompts.jsonl` (%d prompts, exported with SI %s, SHA-256 `%s`) %s." % (
            pc["prompts"], pc["exported_with_si"], pc["sha256"],
            "still matches the current retrieval for every item, so it stays valid" if pc["contexts_match_current_retrieval"]
            else "NO LONGER matches the current retrieval for: " + ", ".join(pc["stale_ids"])), ""]
    return lines


def _probe_summary():
    if not os.path.exists(PROBES_OUT):
        return None
    p = json.load(open(PROBES_OUT))
    out = {"si_version": p["si_version"], "sets": {n: {"n": s["n"], "as_expected": s["correct"], "grounded": s["grounded"]} for n, s in p["sets"].items()}}
    first = os.path.join(OUT, "extra_probes_fresh_first_run.json")
    if os.path.exists(first):
        f = json.load(open(first))
        fs = f["sets"]["fresh"]
        out["held_out_first_run"] = {"si_version": f["si_version"], "n": fs["n"], "as_expected_automatic": fs["correct"], "grounded": fs["grounded"]}
        hr = _hand_review()
        if hr:
            out["held_out_first_run"]["right_on_hand_review"] = hr["right"]
    return out


def _probe_lines():
    if not os.path.exists(PROBES_OUT):
        return []
    p = json.load(open(PROBES_OUT))
    lines = ["## Out-of-bank probes (not part of the frozen bank, not a pass criterion)", "",
             "Run %s with SI %s (questions file SHA-256 `%s`). %s" % (p["generated_at"], p["si_version"], p["questions_sha256"], p.get("note") or ""), ""]
    first = os.path.join(OUT, "extra_probes_fresh_first_run.json")
    rows = []
    for name, s in p["sets"].items():
        status = s["status"]
        if name == "fresh" and os.path.exists(first):
            status = "latest run; this set was used for fixes after its first run, so it is no longer held out"
        rows.append([name, status, s["n"], "%d/%d" % (s["correct"], s["n"]), "%d/%d" % (s["grounded"], s["n"])])
    if os.path.exists(first):
        f = json.load(open(first))["sets"].get("fresh")
        fsi = json.load(open(first))["si_version"]
        if f:
            rows.append(["fresh, first run (held-out measurement)", "run once under SI %s, before any change" % fsi, f["n"],
                         "%d/%d" % (f["correct"], f["n"]), "%d/%d" % (f["grounded"], f["n"])])
    hr = _hand_review()
    lines += [report.md_table(["Set", "Status", "Probes", "Expected behaviour (automatic check)", "All numbers grounded"], rows), "",
              "The automatic check for an answer probe has no expected rows: it only requires an answer with citations and grounded numbers."]
    if hr:
        lines[-1] += (" Hand review of the held-out run (SI %s): %d/%d right; wrong: %s; acceptable but loose: %s (details in the "
                      "review log above)." % (hr["si_version"], hr["right"], hr["n"], ", ".join(hr["wrong"]) or "none",
                                              ", ".join(hr.get("acceptable_but_loose", [])) or "none"))
    lines += ["", "Probes that do not behave as expected in the latest run:", ""]
    bad_any = False
    for name, s in p["sets"].items():
        bad = [r for r in s["results"] if not r["correct_behaviour"]]
        for r in bad:
            bad_any = True
            lines.append("- %s probe %s, expected %s, got %s%s: \"%s\"" % (name, r["id"], r["expected"], r["behaviour"],
                         "" if r["grounded"] else " (ungrounded: %s)" % ", ".join(r["ungrounded_numbers"]), r["question"]))
    if not bad_any:
        lines.append("- None.")
    return lines + [""]


# ------------------------------------------------------------------ language-model mode
def export_prompts(items, k):
    path = os.path.join(OUT, "llm_prompts.jsonl")
    lines = []
    for it in scored_items(items):
        rows = si.retrieve(it["question"], k)
        lines.append({"id": it["id"], "question": it["question"], "context": si.compact_context(rows)})
    # The prompts must not reveal expected behaviour, expected rows, expected facts or notes. A short fact that is a
    # verbatim quote from a ledger row (for example "1.1 mm/s") is evidence, not a leak.
    ledger_text = "\n".join(" | ".join(str(v) for v in r.values()) for r in si.ledger_rows().values())
    for it, rec in zip(scored_items(items), lines):
        text = json.dumps(rec, ensure_ascii=False)
        if set(rec) != {"id", "question", "context"}:
            raise InputError("prompt record has extra fields")
        for word in ("expected", "category", "unanswerable", "adversarial", "synthesis", "expected_rows"):
            if word in text:
                raise InputError("prompt for %s contains the word %r" % (it["id"], word))
        for field in ("expected_fact", "note"):
            f = it.get(field)
            if f and f in text and f not in ledger_text:
                raise InputError("prompt for %s contains its %s" % (it["id"], field))
    with open(path, "w") as fh:
        for rec in lines:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    md = ["# NextBurn SI guard prompt (Experiment 7, language-model mode)", "",
          "Use this text as the system prompt. Send each line of `llm_prompts.jsonl` as one user message, built from its "
          "`question` and `context` with the template below. Do not send the `id`. Do not answer the prompts by hand.", "",
          "## System prompt", "", "```text", si.GUARD_PROMPT, "```", "",
          "## User message template", "", "```text", si.USER_TEMPLATE, "```", "",
          "## Answers file for scoring", "",
          "Save a JSON list with one object per prompt, then run `python experiments/exp7_si_test_set.py --score-llm FILE`:", "",
          "```json", '[{"id": "<id from llm_prompts.jsonl>", "answer": "<the model reply, unchanged>", "cited_rows": ["<row IDs the reply cites>"]}]', "```", "",
          "`cited_rows` may be empty; the scorer also reads every [Rxxx] in the answer. The same scoring functions as the "
          "deterministic SI are used (numbers_grounded, is_decline, is_refusal, score_set).", "",
          "Prompts: %d; rows per prompt: %d; SI retrieval version %s." % (len(lines), k, si.SI_VERSION), ""]
    report.write_text(os.path.join(OUT, "llm_guard_prompt.md"), "\n".join(md))
    return path, len(lines)


def score_llm(items, sha, freeze, corrections, k, answers_path):
    raw = json.load(open(answers_path))
    model = None
    if isinstance(raw, dict):
        model = raw.get("model")
        raw = raw.get("answers", [])
    if not isinstance(raw, list) or not all(isinstance(a, dict) and "id" in a for a in raw):
        raise InputError("answers file must be a JSON list of {id, answer, cited_rows}")
    by = {}
    for a in raw:
        by[str(a["id"])] = a
    results, outside = [], {}
    bank_ids = {it["id"] for it in scored_items(items)}
    for it in scored_items(items):
        rows = si.retrieve(it["question"], k)
        a = by.get(it["id"], {})
        cited = [c for c in (a.get("cited_rows") or []) if isinstance(c, str)]
        res = si.evaluate(it, a.get("answer") or "", [r["row_id"] for r in rows], cited_rows=cited)
        ctx = {r["row_id"] for r in rows}
        out = [c for c in res["cited_rows"] if c not in ctx]
        if out:
            outside[it["id"]] = out
        results.append(res)
    summary = si.score_set(results)
    prompts = os.path.join(OUT, "llm_prompts.jsonl")
    llm = {"experiment": 7, "title": TITLE + " (language model)", "generated_at": report.now_iso(), "model": model,
           "answers_file": os.path.basename(answers_path), "answers_sha256": report.sha256_file(answers_path),
           "prompts_sha256": report.sha256_file(prompts) if os.path.exists(prompts) else None,
           "question_bank_sha256": sha, "question_bank_frozen_at": freeze["frozen_at_utc"], "configuration": config(k),
           "missing_ids": sorted(bank_ids - set(by)), "unknown_ids": sorted(set(by) - bank_ids),
           "cited_outside_context": outside, "items": results, "summary": summary, "failures": failures(results),
           "pass": summary["pass"], "pass_rule": summary["pass_rule"]}
    report.write_json(os.path.join(OUT, "llm_results.json"), llm)
    write_csv(os.path.join(OUT, "llm_answers.csv"), results)
    return llm


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=si.DEFAULT_K)
    ap.add_argument("--export-llm-prompts", action="store_true")
    ap.add_argument("--score-llm", metavar="FILE")
    ap.add_argument("--probes", action="store_true", help="also run the out-of-bank probes in results/exp7/extra_probes_questions.json")
    ap.add_argument("--allow-changed-bank", action="store_true", help="diagnostics only; results are marked as not comparable")
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    try:
        bank, items, sha, freeze, corrections = load_bank(a.allow_changed_bank)
        if a.export_llm_prompts:
            path, n = export_prompts(items, a.k)
            print("Experiment 7: wrote %d prompts to %s and the guard prompt to %s" % (n, path, os.path.join(OUT, "llm_guard_prompt.md")))
            return 0
        if a.score_llm:
            det_path = os.path.join(OUT, "results.json")
            if os.path.exists(det_path):
                det = json.load(open(det_path))
            else:
                det = det_result(items, run_deterministic(items, a.k), sha, freeze, corrections, a.k)
                write_all_deterministic(det)
            llm = score_llm(items, sha, freeze, corrections, a.k, a.score_llm)
            report.write_text(os.path.join(OUT, "results.md"), render_md(det, llm))
            dashboard(det, llm)
            print("Experiment 7 (language model): %s; %s" % ("PASS" if llm["pass"] else "FAIL",
                  "; ".join("(%d) %s %s" % (c["id"], c["value"], "PASS" if c["pass"] else "FAIL") for c in llm["summary"]["criteria"])))
            return 0 if llm["pass"] else 1
        if a.probes and os.path.exists(PROBES_IN):
            p = run_probes(a.k)
            print("Probes: " + "; ".join("%s %d/%d as expected" % (n, s["correct"], s["n"]) for n, s in p["sets"].items()))
        det = det_result(items, run_deterministic(items, a.k), sha, freeze, corrections, a.k)
        if a.allow_changed_bank and sha != freeze["sha256"]:
            det["warning"] = "bank changed after the freeze; results are not comparable"
        write_all_deterministic(det)
        s = det["summary"]
        print("Experiment 7: %s; %s; failures: %s" % ("PASS" if det["pass"] else "FAIL",
              "; ".join("(%d) %s %s" % (c["id"], c["value"], "PASS" if c["pass"] else "FAIL") for c in s["criteria"]),
              ", ".join(f["id"] for f in det["failures"]) or "none"))
        return 0 if det["pass"] else 1
    except InputError as e:
        print("Experiment 7 input error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
