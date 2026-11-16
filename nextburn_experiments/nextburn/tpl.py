"""Step 1: the test-point ledger.

One row per physical test with material, oxygen, pressure, gravity, flow and outcome, and a source for every row.
Conditions come from the evidence ledger (NTRS reports, plus PSI tables when present in data/extra_tests).
Outcomes come from config/test_outcomes.json; every outcome cites ledger rows or a source locator with a quote,
and each quote is checked against the cited row (or the source text, when a source folder is given).
"""
import copy
import csv
import json
import os
import re
import unicodedata

from . import checks, ingest, units

ADDITIONS = os.path.join(ingest.DATA, "ledger_additions_v3.json")
PSI_DIR = os.path.join(ingest.DATA, "psi")  # PSI experiment tables read from psi.nasa.gov (raw copies in data/psi_raw)
OUTCOMES = os.path.join(ingest.CONFIG, "test_outcomes.json")
DIR_SIGN = {"with_flow": 1, "against_flow": -1}


def _norm(t):
    t = unicodedata.normalize("NFKC", t or "")
    t = re.sub(r"[\u2010-\u2015\u2212]", "-", t).replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", t).strip().lower()


def load_rows():
    rows = ingest.load_ledger()
    add = json.load(open(ADDITIONS)) if os.path.exists(ADDITIONS) else []
    return rows + add, add


def source_urls():
    return {r["source_id"]: r["url"] for r in csv.DictReader(open(os.path.join(ingest.DATA, "sources.csv")))}


def _select(pts, sel):
    hits = [tp for tp in pts if sel["row"] in tp["row_ids"] and tp["family"] == sel["family"]
            and (sel.get("g") is None or (tp.get("g") is not None and abs(tp["g"] - sel["g"]) < 1e-6))]
    if len(hits) != 1:
        raise ValueError("outcome selector %s matched %d test points" % (sel, len(hits)))
    return hits[0]


def verify_evidence(evidence, rows_by_id, src_dir=None):
    out = []
    for e in evidence:
        if e.get("row_id"):
            r = rows_by_id.get(e["row_id"])
            if r is None:
                raise ValueError("outcome cites unknown row %s" % e["row_id"])
            quote = e.get("quote") or r.get("snippet") or ""
            hay = _norm((r.get("snippet") or "") + " " + (r.get("condition_notes") or ""))
            out.append({"row_id": r["row_id"], "source_id": r["source_id"], "locator": r.get("locator"), "quote": quote,
                        "quote_found": _norm(quote) in hay, "checked_against": "ledger row"})
        else:
            found, how = None, "not checked (source text not supplied)"
            if src_dir:
                p = os.path.join(src_dir, e["source_id"] + ".txt")
                if os.path.exists(p):
                    found, how = _norm(e["quote"]) in _norm(open(p, encoding="utf-8", errors="ignore").read()), "source text"
            out.append({"row_id": None, "source_id": e["source_id"], "locator": e["locator"], "quote": e["quote"],
                        "quote_found": found, "checked_against": how})
    return out


def _rng(tp, key):
    v, lo, hi = tp.get(key), tp.get(key.replace("_pct", "_lo_pct").replace("_kpa", "_lo_kpa").replace("_cm_s", "_lo_cm_s")), \
        tp.get(key.replace("_pct", "_hi_pct").replace("_kpa", "_hi_kpa").replace("_cm_s", "_hi_cm_s"))
    return v, lo, hi


def model_observation(tp, ob, cfg, bcfg):
    """Turn a test point plus its outcome into a model observation, or return (None, reason)."""
    m = ob.get("model", {})
    y = cfg["binary"].get(ob["outcome"])
    if y is None:
        return None, "outcome not usable (%s)" % ob["outcome"]
    if m.get("include") is False:
        return None, m.get("reason", "excluded")
    fam = tp["family"]
    if fam not in bcfg["flow_regime_min_cm_s"]:
        return None, "family not modelled"
    o2v, o2lo, o2hi = _rng(tp, "o2_pct")
    if m.get("o2_pct") is not None:
        o2 = float(m["o2_pct"])
    elif o2v is not None:
        o2 = float(o2v)
    elif o2lo is not None and o2hi is not None:
        o2 = [float(o2lo), float(o2hi)]
    else:
        return None, "oxygen not stated"
    pv, plo, phi = _rng(tp, "p_kpa")
    p_unknown = False
    if m.get("p_kpa") is not None:
        p = float(m["p_kpa"])
    elif m.get("p_kpa_range"):
        p = [float(x) for x in m["p_kpa_range"]]
    elif pv is not None and plo is not None and phi is not None and abs(plo - phi) < 1e-9:
        p = float(pv)
    elif plo is not None and phi is not None:
        p = [float(plo), float(phi)]
    elif pv is None and plo is None and phi is None:
        p, p_unknown = [float(x) for x in bcfg["unknown_pressure_range_kpa"]], True
    else:
        return None, "pressure only bounded on one side"
    if tp.get("g") is None:
        return None, "gravity not stated"
    g = float(tp["g"])
    if g < 0.01:
        flow = tp.get("flow_cm_s")
        if not m.get("flow_ok") and (flow is None or flow < bcfg["flow_regime_min_cm_s"][fam]):
            return None, "microgravity forced flow below %g cm/s or not stated" % bcfg["flow_regime_min_cm_s"][fam]
    return {"obs_id": ob["id"], "tp_id": tp["tp_id"], "label": tp["label"], "family": fam, "material": ob["material"],
            "o2": o2, "p_kpa": p, "p_unknown": p_unknown, "g": g, "dir": DIR_SIGN.get(tp.get("direction_class"), 0),
            "y": int(y), "outcome": ob["outcome"], "note": m.get("note", "")}, None


def build(src_dir=None):
    rows, add = load_rows()
    rows_by_id = {r["row_id"]: r for r in rows}
    norm, meta = ingest.normalize(rows)
    norm, merged = ingest.dedupe(norm)
    pts = ingest.test_points(norm)
    extra = ingest.load_extra_tests() + ingest.load_extra_tests(PSI_DIR)
    cfg = json.load(open(OUTCOMES))
    bcfg = json.load(open(os.path.join(ingest.CONFIG, "boundary_model.json")))
    urls = source_urls()
    nrow = {r["row_id"]: r for r in norm}
    ledger = {}
    for tp in pts:
        rec = copy.deepcopy(tp)
        rec.update(origin="added in v3" if any(rows_by_id[x].get("added_in") == "v3" for x in tp["row_ids"]) else "ledger v2",
                   outcome="not_reported", outcome_text="", outcome_evidence=[], outcome_id=None, derived_from=None, model_use="not used")
        ledger[tp["tp_id"]] = rec
    for tp in extra:
        rec = copy.deepcopy(tp)
        oc = (rec.get("outcome") or "unknown").strip() or "unknown"
        rec.update(origin="PSI table", outcome=oc if oc in cfg["binary"] else ("not_reported" if oc == "unknown" else oc),
                   outcome_text=rec.get("outcome_text") or "", outcome_evidence=[{"row_id": None, "source_id": rec.get("source_id"), "locator": rec.get("locator"),
                   "quote": rec.get("outcome_text") or "", "quote_found": None, "checked_against": "PSI table cell"}] if rec.get("outcome_text") else [], outcome_id=None, derived_from=None, model_use="not used",
                   direction_class=rec.get("direction_class") or "unknown")
        ledger[rec["tp_id"]] = rec
    observations, excluded, problems = [], [], []
    for ob in cfg["observations"]:
        ev = verify_evidence(ob["evidence"], rows_by_id, src_dir)
        problems += [dict(e, outcome_id=ob["id"]) for e in ev if e["quote_found"] is False]
        if "select" in ob:
            base = _select(pts, ob["select"])
            rec = ledger[base["tp_id"]]
            if rec["outcome_id"]:
                raise ValueError("%s and %s both set the outcome of %s" % (rec["outcome_id"], ob["id"], base["tp_id"]))
        else:
            base = _select(pts, ob["derive_from"])
            n = sum(1 for k in ledger if k.startswith(base["tp_id"] + "-"))
            rec = copy.deepcopy(ledger[base["tp_id"]])
            rec.update(ob.get("override", {}))
            rec.update(tp_id="%s-%s" % (base["tp_id"], "abcdefgh"[n]), derived_from=base["tp_id"], origin="derived from " + base["tp_id"])
            ledger[rec["tp_id"]] = rec
        rec.update(outcome=ob["outcome"], outcome_text=ob.get("outcome_text") or ob.get("note", ""), outcome_evidence=ev, outcome_id=ob["id"])
        mo, why = model_observation(rec, ob, cfg, bcfg)
        if mo:
            mo["tp_id"] = rec["tp_id"]
            observations.append(mo)
            rec["model_use"] = "boundary model (%s)" % ("pressure range assumed" if mo["p_unknown"] else "stated conditions")
        else:
            excluded.append({"outcome_id": ob["id"], "tp_id": rec["tp_id"], "reason": why})
            rec["model_use"] = "not used: " + why
    for x in ledger.values():  # PSI rows enter the model only when the table states pressure (none of the five tables does)
        if x["origin"] == "PSI table":
            if (x.get("source_id") or "") in ("PSI-98", "PSI-99", "PSI-100"):
                x["note"] = "May describe the same Saffire flight samples as the Saffire test points taken from NTRS reports; kept separate, and not counted twice in the model."
            if x.get("p_kpa") is None:
                x["model_use"] = "not used: the PSI table states no pressure"
                continue
        if x["origin"] == "PSI table" and x["outcome"] in cfg["binary"]:
            mo, why = model_observation(x, {"id": x["tp_id"], "outcome": x["outcome"], "material": x.get("material") or x["family"]}, cfg, bcfg)
            if mo:
                observations.append(mo)
                x["model_use"] = "boundary model"
            else:
                x["model_use"] = "not used: " + why
    for rec in ledger.values():
        rr = [nrow[r] for r in rec.get("row_ids", []) if r in nrow]
        rec["materials"] = sorted({r["material_text"] for r in rr if r.get("material_text")}) or [rec.get("material") or ""]
        rec["locators"] = sorted({"%s: %s" % (r["source_id"], r["locator"]) for r in rr}) or [rec.get("locator") or ""]
        rec["source_urls"] = sorted({urls.get(s, "") for s in rec.get("sources", [])} | ({rec.get("source_url")} if rec.get("source_url") else set()))
        rec["p_psia"] = units.kpa_to_psia(rec["p_kpa"]) if rec.get("p_kpa") is not None else None
    golden = json.load(open(os.path.join(ingest.CONFIG, "golden_rows.json")))
    chk, _, _ = checks.run_all(rows, golden)
    return {"rows": rows, "additions": add, "merged": merged, "ledger": sorted(ledger.values(), key=lambda r: r["tp_id"]),
            "observations": observations, "excluded": excluded, "quote_problems": problems, "checks": chk, "meta": meta}


COLUMNS = ["tp_id", "label", "materials", "family", "direction_class", "o2_pct", "o2_lo_pct", "o2_hi_pct", "p_kpa", "p_lo_kpa", "p_hi_kpa", "p_psia",
           "g", "g_class", "flow_cm_s", "outcome", "outcome_text", "outcome_evidence", "evidence_tier", "first_year", "sources", "locators",
           "source_urls", "row_ids", "origin", "model_use", "note"]


def write_csv(ledger, path):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(COLUMNS)
        for r in ledger:
            vals = []
            for c in COLUMNS:
                v = r.get(c)
                if c == "outcome_evidence":
                    v = " | ".join("%s%s: \"%s\"" % (e.get("row_id") or e.get("source_id"), (" (" + (e.get("locator") or "") + ")") if not e.get("row_id") else "", (e.get("quote") or "")[:160]) for e in v or [] if e.get("quote") or e.get("row_id"))
                elif isinstance(v, list):
                    v = "; ".join(str(x) for x in v)
                elif isinstance(v, float):
                    v = round(v, 4)
                vals.append("" if v is None else v)
            w.writerow(vals)
