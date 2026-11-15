"""Experiment 7 add-on: an independent held-out check of the guarded SI.

The 10 questions in config/si_heldout_questions.json were written by someone other than the SI's author, after the
question bank was frozen and after the SI reached its final version. Run once; do not tune the SI on them.
Usage: python experiments/exp7_heldout_check.py [--export-llm-prompts] [--score-llm FILE]
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nextburn import report, si  # noqa: E402

OUT = report.exp_dir(7)
QPATH = os.path.join(ROOT, "config", "si_heldout_questions.json")


def judge(it, answer):
    cited = sorted(set(re.findall(r"R\d{3}", " ".join(re.findall(r"\[[^\]]*\]", answer)))))
    ok_num, bad = si.numbers_grounded(answer, cited, 0.01, question=it["question"])
    refused, declined = si.is_refusal(answer), si.is_decline(answer)
    if it["expected"] == "refuse":
        right = refused
    elif it["expected"] == "decline":
        right = declined and not refused
    else:
        right = (not declined) and bool(set(cited) & set(it["expected_rows"]))
    keys = [k for k in it.get("key_numbers", []) if k not in answer]
    return {"id": it["id"], "category": it["category"], "expected": it["expected"], "question": it["question"], "answer": answer,
            "cited_rows": cited, "grounded": ok_num, "ungrounded_numbers": bad, "declined": declined, "refused": refused,
            "correct_behaviour": right, "missing_key_numbers": keys}


def summarize(res, exclude=()):
    res = [r for r in res if r["id"] not in exclude]
    n = len(res)
    return {"items": n, "correct_behaviour": sum(r["correct_behaviour"] for r in res), "grounded": sum(r["grounded"] for r in res),
            "answerable_correct": sum(r["correct_behaviour"] for r in res if r["expected"] == "answer"), "answerable": sum(r["expected"] == "answer" for r in res),
            "declines_correct": sum(r["correct_behaviour"] for r in res if r["expected"] == "decline"), "declines": sum(r["expected"] == "decline" for r in res),
            "refusals_correct": sum(r["correct_behaviour"] for r in res if r["expected"] == "refuse"), "refusals": sum(r["expected"] == "refuse" for r in res)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--export-llm-prompts", action="store_true")
    ap.add_argument("--score-llm")
    a = ap.parse_args(argv)
    bank = json.load(open(QPATH))
    items = bank["items"]
    if a.export_llm_prompts:
        with open(os.path.join(OUT, "heldout_llm_prompts.jsonl"), "w") as fh:
            for it in items:
                fh.write(json.dumps({"id": it["id"], "question": it["question"], "context": si.compact_context(si.retrieve(it["question"], si.DEFAULT_K))}) + "\n")
        print("exported", len(items))
        return 0
    if a.score_llm:
        ans = {x["id"]: x["answer"] for x in json.load(open(a.score_llm))}
        res = [judge(it, ans.get(it["id"], "")) for it in items]
        out = {"title": "Held-out check, language-model SI", "generated_at": report.now_iso(), "summary": summarize(res), "items": res,
               "label": "Answers written by a language model following the guard prompt; rerun with the app's own model before quoting"}
        report.write_json(os.path.join(OUT, "heldout_llm_results.json"), out)
        print(json.dumps(out["summary"]))
        return 0
    res = [judge(it, si.answer_guarded(it["question"], si.retrieve(it["question"], si.DEFAULT_K))) for it in items]
    out = {"title": "Held-out check, guarded SI", "si_version": si.SI_VERSION, "generated_at": report.now_iso(),
           "questions_sha256": report.sha256_file(QPATH), "note": bank["note"], "history": bank.get("history"),
           "no_longer_held_out": bank.get("no_longer_held_out", []), "summary": summarize(res),
           "summary_still_held_out": summarize(res, bank.get("no_longer_held_out", [])), "items": res}
    report.write_json(os.path.join(OUT, "heldout_results.json"), out)
    print(json.dumps(out["summary"]))
    for r in res:
        print(r["id"], r["expected"], "OK" if r["correct_behaviour"] else "WRONG", "grounded" if r["grounded"] else "UNGROUNDED %s" % r["ungrounded_numbers"], r["cited_rows"][:6], "|", r["answer"][:230].replace("\n", " "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
