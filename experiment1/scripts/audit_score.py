"""Experiment 1 (ledger accuracy): score an independent field-by-field audit of a sampled set of ledger rows.
Usage: python3 audit_score.py  [reads ledger_v1.json, audit/sample_ids.json, audit/verdicts_batch*.json, audit/adjudication.json (optional)]"""
import json, glob, math, re, unicodedata, csv, os
from collections import Counter, defaultdict
AUD = ["locator","platform","gravity","material","geometry","direction","flow","pressure","oxygen","measurement","value","unit","qualifier"]
def norm(s):
    s = unicodedata.normalize("NFKC", str(s)).replace("\u2010","-").replace("\u2011","-").replace("\u2013","-").replace("\u2019","'").replace("\u201c",'"').replace("\u201d",'"')
    return re.sub(r"\s+", " ", s).strip()
def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),)*2
    p = k/n; d = 1 + z*z/n; c = p + z*z/(2*n); h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)); return ((c-h)/d, (c+h)/d)
def num_forms(v):
    v = str(v).strip(); out = {v}
    try:
        x = float(v.replace(",", ""))
        out |= {v.replace(",", ""), f"{x:,.0f}" if x == int(x) else v}
        if v.startswith("0."): out.add(v[1:])
        if v.startswith("-0."): out.add("-" + v[2:])
    except ValueError: pass
    return {o for o in out if o}
ledger = {r["row_id"]: r for r in json.load(open("ledger_v1.json"))}
sample = json.load(open("audit/sample_ids.json"))
verd = {}
for f in sorted(glob.glob("audit/verdicts_batch*.json")):
    for row in json.load(open(f)): verd[row["row_id"]] = row
adj = json.load(open("audit/adjudication.json")) if os.path.exists("audit/adjudication.json") else {}
src_cache = {}
def src(sid):
    if sid not in src_cache: src_cache[sid] = norm(open(f"sources/{sid}.txt", encoding="utf-8").read())
    return src_cache[sid]
problems, quote_fail, value_unquoted = [], [], []
cells = []   # (row_id, source_id, field, raw_verdict, final_verdict)
for rid in sample:
    if rid not in verd: problems.append(f"{rid}: no verdict"); continue
    v, r = verd[rid], ledger[rid]
    for q in v.get("quotes", []):
        if norm(q) not in src(r["source_id"]): quote_fail.append((rid, q[:90]))
    qs = " ".join(norm(q) for q in v.get("quotes", []))
    if r["value"] and not any(f in qs for f in num_forms(r["value"])) and r["qualifier"] != "categorical":
        value_unquoted.append(rid)
    for fld in AUD:
        raw = (v["verdicts"].get(fld) or {}).get("v")
        if raw not in ("OK","WRONG","NOT_IN_SOURCE","MISSED"): problems.append(f"{rid}.{fld}: bad verdict {raw}"); continue
        final = raw
        a = adj.get(f"{rid}.{fld}")
        if a: final = "OK" if a["decision"] == "overturned" else raw
        cells.append((rid, r["source_id"], fld, raw, final))
def metrics(key):
    n = len(cells); ok = sum(1 for c in cells if c[key] == "OK")
    rows = defaultdict(list)
    for c in cells: rows[c[0]].append(c[key] == "OK")
    rok = sum(all(x) for x in rows.values())
    return {"fields_checked": n, "fields_ok": ok, "field_accuracy": ok/n, "field_ci95": wilson(ok, n),
            "rows_checked": len(rows), "rows_all_ok": rok, "row_accuracy": rok/len(rows), "row_ci95": wilson(rok, len(rows)),
            "by_field": {f: f"{sum(1 for c in cells if c[2]==f and c[key]=='OK')}/{sum(1 for c in cells if c[2]==f)}" for f in AUD},
            "by_source": {s: f"{sum(1 for c in cells if c[1]==s and c[key]=='OK')}/{sum(1 for c in cells if c[1]==s)}" for s in sorted({c[1] for c in cells})},
            "error_types": dict(Counter(c[key] for c in cells if c[key] != "OK"))}
out = {"raw": metrics(3), "after_adjudication": metrics(4),
       "provenance": {"ledger_rows": len(ledger), "rows_with_source_and_locator": sum(1 for r in ledger.values() if r["source_id"] and r["locator"]),
                      "sample_rows_with_source_and_locator": sum(1 for rid in sample if ledger[rid]["source_id"] and ledger[rid]["locator"])},
       "checker_quotes_not_found": quote_fail, "rows_value_not_in_checker_quotes": value_unquoted, "problems": problems}
json.dump(out, open("audit/score.json", "w"), indent=1)
with open("audit/audit_sheet.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["row_id","source_id","field","ledger_value","checker_verdict","checker_correct_value","checker_note","adjudication","final_verdict"])
    for rid, sid, fld, raw, final in cells:
        vv = verd[rid]["verdicts"][fld]; a = adj.get(f"{rid}.{fld}", {})
        w.writerow([rid, sid, fld, ledger[rid][fld], raw, vv.get("correct",""), vv.get("note",""), a.get("decision",""), final])
print(json.dumps({k: (v if k not in ("raw","after_adjudication") else {kk: vv for kk, vv in v.items() if kk not in ("by_field","by_source")}) for k, v in out.items()}, indent=1, default=str)[:3000])
