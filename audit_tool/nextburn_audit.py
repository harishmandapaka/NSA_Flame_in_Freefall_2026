#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nextburn_audit.py - NextBurn evidence-ledger audit.

One file. Python 3.8 or later. Standard library only. No installation is necessary.

LEVEL 1 (automatic). The script examines every ledger row in every run:
  L1-PROV   The row has a source and a locator.
  L1-SRC    A source text file is available for the source of the row.
  L1-QUOTE  The quote (snippet) of the row is in the source text.
  L1-BLANK  No audited field is blank ("not stated" is a value, but blank is not).
  L1-VALUE  The numbers of the value are in the quote.
  L1-UNIT   A numeric value has a unit ("-" means no unit).
  L1-HINT   A field says "not stated", but other rows of the same source give
            that condition, and the source has matching words near the quote.
  L1-TERM   A named term (vehicle, facility, material) is not in the source text.

LEVEL 2 (sample). Independent checkers examine 13 fields of each sampled row.
  Verdict codes: OK, WRONG, NOT_IN_SOURCE, MISSED. Each row needs quotes. The
  script finds each quote in the source text. A reviewer can give a decision
  for each finding: upheld, overturned or added.

RECORDS. Each command that makes data writes a record to
  <records>/audit_log.jsonl. A record contains the SHA-256 hash of each file
  that the command wrote and the hash of the record before it (a hash chain).
  The script does not write over a record file. "verify" finds changed files,
  missing files and a broken chain.

COMMANDS
  run     Start a run: Level 1, sample, checker packets. With --verdicts or
          --checker-cmd, the run also calculates the score.
  score   Calculate the score of a run from verdicts and review decisions.
  list    Show the runs.
  show    Show one run.
  verify  Examine the records for changes.
  serve   Start a local HTTP API (JSON) for a front end.

EXIT CODES
  0  The command is complete. Read "result" for the audit result.
  1  You used --strict and the audit result is NOT SATISFACTORY,
     or "verify" found changes in the records.
  2  An input is not correct. The message tells you what to do.
  3  An unexpected error occurred.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import getpass
import hashlib
import io
import json
import math
import os
import random
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

TOOL = "nextburn-audit"
VERSION = "1.0.0"
GENESIS = "0" * 64
DEFAULT_RECORDS = os.environ.get("NEXTBURN_AUDIT_RECORDS", "audit_records")

AUDITED_FIELDS = ["locator", "platform", "gravity", "material", "geometry", "direction",
                  "flow", "pressure", "oxygen", "measurement", "value", "unit", "qualifier"]
NUMBER_FIELDS = ["measurement", "value", "unit", "qualifier"]
VERDICT_CODES = ("OK", "WRONG", "NOT_IN_SOURCE", "MISSED")
DECISIONS = ("upheld", "overturned", "added")
REQUIRED_COLUMNS = ["row_id", "source_id", "snippet"] + AUDITED_FIELDS
DEFAULTS = {"n": 50, "seed": 2026, "checkers": 3, "field_limit": 0.98, "provenance_limit": 1.0,
            "bootstrap": 10000, "hint_window": 3000, "hint_context": 0}
Z95 = 1.96

# Words that show a condition in the source text. They are used for the L1-HINT check.
HINT_PATTERNS = {
    "oxygen": r"\boxygen\b|\bO2\b|\bin air\b|\bambient air\b|\bair at\b|mole fraction|%\s*O2",
    "pressure": r"\bkPa\b|\bpsia?\b|\batm\b|\btorr\b|\bmmHg\b|\bpressure\b",
    "flow": r"cm/s|\bflow\b|\bvelocity\b|\bfan\b|\bquiescent\b",
    "geometry": (r"\bwide\b|\bwidth\b|\blong\b|\blength\b|\bthick(?:ness)?\b|\bdiameter\b|\bDIA\b|\brod\b"
                 r"|\bsheet\b|\bslab\b|\bcylind\w*|\d+(?:\.\d+)?\s*(?:mm|cm)\s*(?:x|by)\s*\d+"),
    "direction": r"\bupward\b|\bdownward\b|\bconcurrent\b|\bco-?current\b|\bopposed\b|\bopposing\b|\bcounter-?flow\b",
    "gravity": r"microgravity|\bmicro-?g\b|\blunar\b|\bmartian\b|\bmars\b|partial gravity|reduced gravity|normal gravity|\b1-?g\b",
    "platform": r"\bISS\b|space station|cygnus|new shepard|drop tower|parabolic|aircraft|sounding rocket|\bZARM\b|glovebox|capsule",
    "material": r"PMMA|acrylic|cotton|fiberglass|fibreglass|SIBAL|nomex|ultem|polyethylene|kapton|silicone|fabric",
}
HINT_RES = {k: re.compile(v, re.IGNORECASE) for k, v in HINT_PATTERNS.items()}
TERM_RE = re.compile(r"\b[A-Z][A-Za-z]{2,}\b|\b[A-Z]{2,}[A-Za-z0-9-]*\b")
TERM_STOPWORDS = {
    "the", "not", "and", "with", "for", "from", "this", "that", "test", "tests", "flight", "flights",
    "sample", "samples", "lunar", "mars", "martian", "earth", "normal", "fuel", "model", "simulated",
    "vehicle", "named", "paper", "orbit", "orbiting", "spacecraft", "cargo", "station", "ground",
    "drop", "tower", "aircraft", "capsule", "fabric", "rod", "sheet", "thin", "solid", "composite",
}

CHECKER_BRIEF = """# Checker instructions (NextBurn ledger audit)

You are an independent checker. You did not make the ledger rows.
Do not open the ledger, the extraction scripts or the other packets.
Do not use information from outside the cited source.

For each row in your packet:

1. Open the source text file of the row.
2. Find the cited location (page, table, slide or section).
3. Compare each of the 13 fields with the source.
4. Give one verdict for each field.

The 13 fields are locator, platform, gravity, material, geometry, direction, flow,
pressure, oxygen, measurement, value, unit and qualifier.

Verdict codes:

- OK: The value agrees with the source for this test. A format difference is OK (".9" and "0.9").
- WRONG: The source gives a different value. Write the correct value.
- NOT_IN_SOURCE: The source does not support the value for this test. The value comes from a different test, a different column or a different document.
- MISSED: The ledger says "not stated", but the source gives the value for this test. Write the value.

Rules:

- Before you write OK for "not stated", search all of the source. Search the other slides, the figure captions, the tables and the summary.
- If the ledger names a vehicle, a facility or a material, make sure that the cited source connects that name to this test.
- Give one to three quotes for each row. A quote is a copy of the source text, 300 characters or less.
- One quote must contain the value of the row. One quote must support each verdict that is not OK.
- The script finds each quote in the source text. A quote that the script cannot find is a defect.

Write your verdicts in one of these two formats:

- JSON: a list with one object for each row, for example
  {"row_id": "R001", "verdicts": {"locator": {"v": "OK"}, "oxygen": {"v": "MISSED", "correct": "21%", "note": "slide 4"}, ...}, "quotes": ["...", "..."]}
- CSV: fill in the columns verdict, correct_value, quote and note of checker_N.csv. The file has one line for each field.
"""


class AuditError(Exception):
    """An input problem. The message tells the operator what to do."""

    def __init__(self, message, details=None):
        super().__init__(message)
        self.message = message
        self.details = list(details or [])


# ----------------------------------------------------------------------------- helpers
def now_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_operator():
    name = os.environ.get("NEXTBURN_OPERATOR")
    if name:
        return name
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - any failure means "unknown"
        return "unknown"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _new_file(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise AuditError(f"The file exists. The script does not write over a record file: {path}")
    return path


def write_json(path, obj):
    with open(_new_file(path), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def write_text(path, text):
    with open(_new_file(path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_bytes(path, data):
    with open(_new_file(path), "wb") as fh:
        fh.write(data)


def write_csv(path, header, rows):
    with open(_new_file(path), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def read_json(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def pct(x, digits=1):
    return "n/a" if x is None else f"{100 * x:.{digits}f}%"


_TRANSLATE = {0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-", 0x2212: "-",
              0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x00AD: ""}
ALNUM = frozenset("0123456789abcdefghijklmnopqrstuvwxyz")


def norm(s):
    """Unicode NFKC, one form for dashes and quote marks, one space for each run of white space."""
    s = unicodedata.normalize("NFKC", str(s)).translate(_TRANSLATE)
    return re.sub(r"\s+", " ", s).strip()


def alnum(s):
    return "".join(ch for ch in norm(s).lower() if ch in ALNUM)


def is_not_stated(value):
    return str(value).strip().lower().startswith("not stated")


def num_forms(v):
    """Text forms of one number that a quote can contain ("0.92" also as ".92")."""
    v = str(v).strip()
    out = {v}
    try:
        x = float(v.replace(",", ""))
        out |= {v.replace(",", ""), f"{x:,.0f}" if x == int(x) else v}
        if v.startswith("0."):
            out.add(v[1:])
        if v.startswith("-0."):
            out.add("-" + v[2:])
    except (ValueError, OverflowError):
        pass
    return {o for o in out if o}


def wilson(k, n, z=Z95):
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [max(0.0, (c - h) / d), min(1.0, (c + h) / d)]


def row_bootstrap(row_ok, row_n, resamples, seed, limit):
    """Row-cluster bootstrap of field accuracy. Rows are drawn with replacement."""
    m = len(row_ok)
    if m == 0 or resamples <= 0:
        return {"resamples": 0, "ci95": [None, None], "share_at_or_above_limit": None}
    rng = random.Random(seed)
    accs = []
    for _ in range(resamples):
        ok = n = 0
        for _ in range(m):
            i = rng.randrange(m)
            ok += row_ok[i]
            n += row_n[i]
        accs.append(ok / n)
    accs.sort()
    lo = accs[int(0.025 * resamples)]
    hi = accs[min(resamples - 1, int(0.975 * resamples))]
    share = sum(1 for a in accs if a >= limit - 1e-12) / resamples
    return {"resamples": resamples, "seed": seed, "ci95": [lo, hi], "share_at_or_above_limit": share}


# ----------------------------------------------------------------------------- inputs
def load_ledger(path):
    p = Path(path)
    if not p.is_file():
        raise AuditError(f"The ledger file is not found: {path}")
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AuditError("The ledger file is not UTF-8 text. Save it as UTF-8 and try again.")
    fmt = "json" if p.suffix.lower() == ".json" else "csv"
    if fmt == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AuditError(f"The JSON ledger is not valid JSON: {exc}")
        if isinstance(data, dict) and isinstance(data.get("rows"), list):
            data = data["rows"]
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            raise AuditError("A JSON ledger must be a list of row objects.")
        columns = set()
        for r in data:
            columns |= {str(k) for k in r}
        rows = [{str(k): ("" if v is None else str(v)).strip() for k, v in r.items()} for r in data]
    else:
        reader = csv.DictReader(io.StringIO(text))
        columns = {(c or "").strip() for c in (reader.fieldnames or [])}
        rows = [{(k or "").strip(): (v or "").strip() for k, v in r.items() if k is not None} for r in reader]
    if not rows:
        raise AuditError("The ledger has no rows.")
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise AuditError("The ledger does not have all the necessary columns.",
                         [f"Missing column: {c}" for c in missing])
    for r in rows:
        for c in REQUIRED_COLUMNS + ["source_title"]:
            r.setdefault(c, "")
    ids = [r["row_id"] for r in rows]
    blank = sum(1 for i in ids if not i)
    dups = sorted(k for k, c in Counter(ids).items() if c > 1 and k)
    if blank or dups:
        raise AuditError("Each row must have a unique row_id.",
                         ([f"{blank} rows have no row_id"] if blank else []) + [f"Duplicate row_id: {d}" for d in dups])
    return rows, raw, fmt


class SourceText:
    """The text of one source document, prepared for quote search."""

    def __init__(self, sid, path):
        raw = Path(path).read_bytes()
        self.sid = sid
        self.path = str(path)
        self.sha256 = sha256_bytes(raw)
        self.n = norm(raw.decode("utf-8", errors="replace"))
        self.low = self.n.lower()
        self.amap = [i for i, ch in enumerate(self.low) if ch in ALNUM]
        self.a = "".join(self.low[i] for i in self.amap)

    def find(self, quote):
        """Return (match level, position). Levels: exact, case, alnum, not_found, empty."""
        q = norm(quote)
        if not q:
            return "empty", -1
        i = self.n.find(q)
        if i >= 0:
            return "exact", i
        i = self.low.find(q.lower())
        if i >= 0:
            return "case", i
        qa = alnum(q)
        if len(qa) >= 12:
            j = self.a.find(qa)
            if j >= 0:
                return "alnum", self.amap[j]
        return "not_found", -1

    def context(self, pos, width=70):
        a, b = max(0, pos - width), min(len(self.n), pos + width)
        return ("..." if a else "") + self.n[a:b] + ("..." if b < len(self.n) else "")


def load_sources(sources_dir, source_ids):
    d = Path(sources_dir)
    if not d.is_dir():
        raise AuditError(f"The source folder is not found: {sources_dir}")
    found, missing = {}, []
    for sid in sorted(source_ids):
        p = d / f"{sid}.txt"
        if p.is_file():
            found[sid] = SourceText(sid, p)
        else:
            missing.append(sid)
    return found, missing


def _code(v):
    return re.sub(r"[\s\-]+", "_", str(v or "").strip().upper())


def load_verdicts(paths):
    """Read checker verdicts. A path can be a file or a folder of .json and .csv files."""
    files = []
    for p in paths:
        P = Path(p)
        if P.is_dir():
            files += sorted(x for x in P.iterdir() if x.is_file() and x.suffix.lower() in (".json", ".csv"))
        elif P.is_file():
            files.append(P)
        else:
            raise AuditError(f"The verdict file or folder is not found: {p}")
    out, problems, used, skipped = {}, [], [], []
    for f in files:
        if f.suffix.lower() == ".json":
            try:
                data = read_json(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                problems.append(f"{f.name}: not valid JSON ({exc})")
                continue
            if isinstance(data, dict) and isinstance(data.get("rows"), list):
                data = data["rows"]
            if not (isinstance(data, list) and data and all(isinstance(r, dict) and "verdicts" in r for r in data)):
                skipped.append(f.name)
                continue
            used.append(f)
            for row in data:
                rid = str(row.get("row_id", "")).strip()
                if not rid:
                    problems.append(f"{f.name}: a row has no row_id")
                    continue
                if rid in out:
                    problems.append(f"{f.name}: row {rid} has verdicts in more than one place")
                    continue
                vd = {}
                for fld, val in (row.get("verdicts") or {}).items():
                    if not isinstance(val, dict):
                        val = {"v": val}
                    vd[fld] = {"v": _code(val.get("v", val.get("verdict"))),
                               "correct": str(val.get("correct", "") or ""), "note": str(val.get("note", "") or "")}
                out[rid] = {"verdicts": vd, "quotes": [str(q) for q in (row.get("quotes") or []) if str(q).strip()],
                            "file": f.name}
        else:
            text = f.read_bytes().decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            cols = {(c or "").strip() for c in (reader.fieldnames or [])}
            if not {"row_id", "field", "verdict"} <= cols:
                skipped.append(f.name)
                continue
            used.append(f)
            seen_rows = set()
            for rec in reader:
                rec = {(k or "").strip(): (v or "").strip() for k, v in rec.items() if k is not None}
                rid, fld = rec.get("row_id", ""), rec.get("field", "")
                if not rid or not fld:
                    continue
                if rid in out and rid not in seen_rows:
                    problems.append(f"{f.name}: row {rid} has verdicts in more than one place")
                    continue
                seen_rows.add(rid)
                entry = out.setdefault(rid, {"verdicts": {}, "quotes": [], "file": f.name})
                if fld in entry["verdicts"]:
                    problems.append(f"{f.name}: {rid}.{fld} has more than one verdict")
                    continue
                entry["verdicts"][fld] = {"v": _code(rec.get("verdict")), "correct": rec.get("correct_value", ""),
                                          "note": rec.get("note", "")}
                if rec.get("quote"):
                    entry["quotes"].append(rec["quote"])
    if not used:
        raise AuditError("No verdict file was found. Give JSON or CSV verdict files.", skipped)
    return out, problems, used, skipped


def load_adjudication(path):
    """Read review decisions: {"R003.oxygen": {"decision": "upheld", "cause": "...", "reason": "..."}} or a CSV."""
    if not path:
        return {}, None
    P = Path(path)
    if not P.is_file():
        raise AuditError(f"The review file is not found: {path}")
    items = []
    if P.suffix.lower() == ".json":
        data = read_json(P)
        if isinstance(data, dict):
            for key, val in data.items():
                if "." not in key or not isinstance(val, dict):
                    raise AuditError(f"Review entry '{key}' is not valid. Use 'ROW.field' keys with an object value.")
                rid, fld = key.split(".", 1)
                items.append(dict(val, row_id=rid, field=fld))
        elif isinstance(data, list):
            items = [dict(x) for x in data]
        else:
            raise AuditError("The review file must be an object or a list.")
    else:
        reader = csv.DictReader(io.StringIO(P.read_bytes().decode("utf-8-sig", errors="replace")))
        items = [{(k or "").strip(): (v or "").strip() for k, v in r.items() if k is not None} for r in reader]
    out, errors = {}, []
    for it in items:
        rid, fld = str(it.get("row_id", "")).strip(), str(it.get("field", "")).strip()
        dec = str(it.get("decision", "")).strip().lower()
        key = f"{rid}.{fld}"
        if fld not in AUDITED_FIELDS:
            errors.append(f"{key}: '{fld}' is not an audited field")
        if dec not in DECISIONS:
            errors.append(f"{key}: decision must be upheld, overturned or added")
        verdict = _code(it.get("verdict", ""))
        if dec == "added" and verdict not in VERDICT_CODES[1:]:
            errors.append(f"{key}: an 'added' finding needs a verdict: WRONG, NOT_IN_SOURCE or MISSED")
        if key in out:
            errors.append(f"{key}: more than one review decision")
        out[key] = {"decision": dec, "verdict": verdict, "cause": str(it.get("cause", "") or ""),
                    "reason": str(it.get("reason", "") or "")}
    if errors:
        raise AuditError("The review file has errors.", errors)
    return out, P


# ----------------------------------------------------------------------------- level 1
def named_terms(value):
    if is_not_stated(value):
        return []
    out = []
    for m in TERM_RE.finditer(value):
        t = m.group(0)
        if t.lower() not in TERM_STOPWORDS and t not in out:
            out.append(t)
    return out


def level1(rows, sources, hint_window, hint_context=0):
    """Automatic checks on every row. Returns (issues, summary)."""
    issues = []
    given = Counter((r["source_id"], f) for r in rows for f in HINT_RES if r.get(f) and not is_not_stated(r[f]))
    prov = quote_found = 0
    levels = Counter()
    for r in rows:
        rid, sid = r["row_id"], r["source_id"]
        src = sources.get(sid)

        def add(check, level, field, message, context=""):
            issues.append({"row_id": rid, "source_id": sid, "check": check, "level": level,
                           "field": field, "message": message, "context": context})

        if sid and r["locator"]:
            prov += 1
        else:
            add("L1-PROV", "FAIL", "locator" if sid else "source_id", "The row has no source or no locator.")
        qpos = -1
        if src is None:
            levels["no_source_text"] += 1
            add("L1-SRC", "FAIL", "source_id", f"No source text for '{sid}'. Put {sid}.txt in the source folder.")
        else:
            qlevel, qpos = src.find(r["snippet"])
            levels[qlevel] += 1
            if qpos >= 0:
                quote_found += 1
            else:
                add("L1-QUOTE", "FAIL", "snippet", "The quote is not in the source text.")
        for f in AUDITED_FIELDS:
            if not r[f]:
                add("L1-BLANK", "FAIL", f, "The field is blank. Write the value or 'not stated'.")
        if r["qualifier"].lower() != "categorical":
            nums = re.findall(r"-?\d+(?:\.\d+)?", r["value"].replace(",", ""))
            sn = norm(r["snippet"])
            lost = []
            for x in nums:
                forms = num_forms(x)
                if x.startswith("-") and re.search(r"\b(negative|minus)\b", sn, re.IGNORECASE):
                    forms |= num_forms(x[1:])
                if not any(f in sn for f in forms):
                    lost.append(x)
            if lost:
                add("L1-VALUE", "WARN", "value", "The quote does not contain the number " + ", ".join(lost) + ".")
            if nums and (not r["unit"] or is_not_stated(r["unit"])):
                add("L1-UNIT", "WARN", "unit", "The value has no unit. Write the unit, or '-' for no unit.")
        if src is None:
            continue
        for f, rx in HINT_RES.items():
            if qpos < 0 or not is_not_stated(r.get(f, "")) or not given[(sid, f)]:
                continue
            near = [m for m in rx.finditer(src.n) if abs(m.start() - qpos) <= hint_window]
            if not near:
                continue
            m0 = min(near, key=lambda m: abs(m.start() - qpos))
            h = m0.start()
            where = (src.context(h, hint_context) if hint_context > 0
                     else f"match '{m0.group(0)}' at character {h} of the source text")
            add("L1-HINT", "HINT", f, f"The field is 'not stated', but {given[(sid, f)]} other rows of this source "
                                      f"give this condition, and the source has a match {abs(h - qpos)} characters "
                                      f"from the quote. Search the source for this condition.", where)
        for f in ("platform", "material"):
            for t in named_terms(r[f]):
                rx = re.compile(r"(?<![a-z0-9])" + re.escape(t.lower()) + r"(?![a-z0-9])")
                if not rx.search(src.low):
                    add("L1-TERM", "WARN", f, f"The term '{t}' is not in the source text.")
    n = len(rows)
    count = Counter(i["level"] for i in issues)
    summary = {
        "rows": n,
        "rows_with_source_and_locator": prov,
        "rows_with_quote_in_source": quote_found,
        "provenance_rate": prov / n,
        "quote_rate": quote_found / n,
        "quote_match_levels": dict(sorted(levels.items())),
        "fail": count.get("FAIL", 0), "warn": count.get("WARN", 0), "hint": count.get("HINT", 0),
        "by_check": dict(sorted(Counter(f'{i["check"]} {i["level"]}' for i in issues).items())),
        "hints_by_field": dict(sorted(Counter(i["field"] for i in issues if i["level"] == "HINT").items())),
    }
    return issues, summary


# ----------------------------------------------------------------------------- sample and packets
def draw_sample(rows, n, seed, exclude):
    """Stratified sample: proportional allocation by source (largest remainder), fixed seed."""
    eligible = [r for r in rows if r["row_id"] not in exclude]
    if not eligible:
        raise AuditError("No rows are available for a sample. All rows are in earlier audited samples.")
    by = defaultdict(list)
    for r in eligible:
        by[r["source_id"]].append(r)
    total = len(eligible)
    if n >= total:
        return sorted(r["row_id"] for r in eligible), {s: len(v) for s, v in sorted(by.items())}, "all eligible rows"
    quota = {s: n * len(v) / total for s, v in by.items()}
    alloc = {s: int(math.floor(q)) for s, q in quota.items()}
    for s in sorted(quota, key=lambda s: (-(quota[s] - alloc[s]), s))[: n - sum(alloc.values())]:
        alloc[s] += 1
    rng = random.Random(seed)
    sample = []
    for s in sorted(by):
        sample += rng.sample(sorted(by[s], key=lambda r: r["row_id"]), alloc[s])
    ids = sorted(r["row_id"] for r in sample)
    return ids, dict(sorted(alloc.items())), "stratified by source, proportional allocation, largest remainder"


def audited_rows(records):
    """Row ids in the samples of earlier runs that have a score."""
    ids = set()
    for sp in (Path(records) / "runs").glob("*/sample.json"):
        if any(sp.parent.glob("scoring/*/score.json")):
            try:
                ids.update(read_json(sp)["row_ids"])
            except (OSError, KeyError, ValueError):
                pass
    return ids


def write_packets(run_dir, by_id, sample_ids, k):
    blind = [dict({"row_id": rid, "source_id": by_id[rid]["source_id"],
                   "source_file": f"{by_id[rid]['source_id']}.txt",
                   "source_title": by_id[rid].get("source_title", "")},
                  **{f: by_id[rid][f] for f in AUDITED_FIELDS}) for rid in sample_ids]
    k = max(1, min(k, len(blind)))
    paths = []
    for i in range(k):
        batch = blind[i::k]
        pj = run_dir / "packets" / f"checker_{i + 1}.json"
        write_json(pj, batch)
        rows = [[b["row_id"], b["source_id"], b["source_title"], f, b[f], "", "", "", ""] for b in batch for f in AUDITED_FIELDS]
        pc = run_dir / "packets" / f"checker_{i + 1}.csv"
        write_csv(pc, ["row_id", "source_id", "source_title", "field", "ledger_value", "verdict", "correct_value",
                       "quote", "note"], rows)
        paths += [pj, pc]
    pi = run_dir / "packets" / "instructions.md"
    write_text(pi, CHECKER_BRIEF)
    return paths + [pi], k


# ----------------------------------------------------------------------------- records
_PROC_LOCK = threading.Lock()


class _LogLock:
    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        _PROC_LOCK.acquire()
        self.fh = open(self.path, "a+")
        try:
            import fcntl
            fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX)
        except ImportError:  # Windows: the lock in this process is the only lock
            pass
        return self

    def __exit__(self, *exc):
        try:
            import fcntl
            fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
        except ImportError:
            pass
        self.fh.close()
        _PROC_LOCK.release()


def _read_log(records):
    log = Path(records) / "audit_log.jsonl"
    if not log.exists():
        return []
    with open(log, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _rel(records, path):
    return Path(path).resolve().relative_to(Path(records).resolve()).as_posix()


def append_record(records, event, run_id, operator, summary, files):
    records = Path(records)
    records.mkdir(parents=True, exist_ok=True)
    log = records / "audit_log.jsonl"
    with _LogLock(records / ".audit_log.lock"):
        prior = _read_log(records)
        last = prior[-1] if prior else None
        rec = {"seq": (last["seq"] + 1) if last else 1, "time_utc": now_utc(), "tool": TOOL, "version": VERSION,
               "event": event, "run_id": run_id, "operator": operator, "summary": summary,
               "files": {_rel(records, f): sha256_file(f) for f in files},
               "prev_hash": last["hash"] if last else GENESIS}
        rec["hash"] = sha256_bytes(canonical(rec).encode("utf-8"))
        with open(log, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical(rec) + "\n")
    return rec


def verify_records(records=DEFAULT_RECORDS):
    records = Path(records)
    recs = _read_log(records)
    problems, prev, started = [], GENESIS, set()
    for i, rec in enumerate(recs, 1):
        body = dict(rec)
        h = body.pop("hash", None)
        if sha256_bytes(canonical(body).encode("utf-8")) != h:
            problems.append(f"Record {i}: the record hash is not correct. The record changed.")
        if rec.get("prev_hash") != prev:
            problems.append(f"Record {i}: the chain is broken. A record before it changed or is missing.")
        if rec.get("seq") != i:
            problems.append(f"Record {i}: the sequence number is {rec.get('seq')}, not {i}.")
        prev = h
        if rec.get("event") == "run_started":
            started.add(rec.get("run_id"))
        for rel, digest in (rec.get("files") or {}).items():
            p = records / rel
            if not p.is_file():
                problems.append(f"Record {i}: a file is missing: {rel}")
            elif sha256_file(p) != digest:
                problems.append(f"Record {i}: a file changed: {rel}")
    for d in sorted((records / "runs").glob("*")) if (records / "runs").is_dir() else []:
        if d.is_dir() and d.name not in started:
            problems.append(f"Run folder {d.name} has no start record.")
    return {"ok": not problems, "result": "NO CHANGES FOUND" if not problems else "CHANGES FOUND",
            "records": len(recs), "last_hash": prev, "problems": problems}


# ----------------------------------------------------------------------------- run
def _check_settings(n, checkers, field_limit, provenance_limit, bootstrap, hint_window):
    errs = []
    if n < 1:
        errs.append("--n must be 1 or more")
    if checkers < 1:
        errs.append("--checkers must be 1 or more")
    if not 0 < field_limit <= 1:
        errs.append("--field-limit must be more than 0 and not more than 1")
    if not 0 < provenance_limit <= 1:
        errs.append("--provenance-limit must be more than 0 and not more than 1")
    if bootstrap < 0:
        errs.append("--bootstrap must be 0 or more")
    if hint_window < 1:
        errs.append("--hint-window must be 1 or more")
    if errs:
        raise AuditError("A setting is not correct.", errs)


def _new_run_id(records):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    while True:
        rid = f"AUD-{stamp}-{secrets.token_hex(2)}"
        if not (Path(records) / "runs" / rid).exists():
            return rid


def run_checker_cmd(cmd, records, run_id, run_dir, packets, sources_dir, timeout, operator):
    out_dir = run_dir / "checker_output"
    out_dir.mkdir(parents=True, exist_ok=False)
    produced = []
    posix = os.name != "nt"
    for i, pk in enumerate(packets, 1):
        out = out_dir / f"checker_{i}.json"
        subst = {"{packet}": str(pk), "{out}": str(out), "{sources}": str(Path(sources_dir).resolve()),
                 "{instructions}": str(run_dir / "packets" / "instructions.md"), "{run_dir}": str(run_dir),
                 "{checker}": str(i)}
        args = []
        for a in shlex.split(cmd, posix=posix):
            for k, v in subst.items():
                a = a.replace(k, v)
            args.append(a)
        try:
            cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            raise AuditError(f"The checker program is not found: {args[0] if args else cmd}")
        except subprocess.TimeoutExpired:
            raise AuditError(f"The checker program did not stop in {timeout} seconds (packet {i}).")
        log = out_dir / f"checker_{i}.log"
        write_text(log, f"$ {' '.join(args)}\n--- exit code {cp.returncode}\n--- stdout\n{cp.stdout}\n--- stderr\n{cp.stderr}\n")
        produced.append(log)
        if cp.returncode != 0:
            raise AuditError(f"The checker program stopped with exit code {cp.returncode} (packet {i}).",
                             [cp.stderr[-2000:]])
        if not out.is_file():
            raise AuditError(f"The checker program did not write {out.name}.")
        produced.append(out)
    append_record(records, "checker_done", run_id, operator, {"command": cmd, "packets": len(packets)}, produced)
    return out_dir


def do_run(ledger, sources, records=DEFAULT_RECORDS, n=DEFAULTS["n"], seed=DEFAULTS["seed"],
           checkers=DEFAULTS["checkers"], exclude_audited=False, sample_ids=None, verdicts=None,
           adjudication=None, checker_cmd=None, checker_timeout=3600, operator=None, note="", label="",
           field_limit=DEFAULTS["field_limit"], provenance_limit=DEFAULTS["provenance_limit"],
           bootstrap=DEFAULTS["bootstrap"], hint_window=DEFAULTS["hint_window"],
           hint_context=DEFAULTS["hint_context"]):
    """Start an audit run. Returns a JSON-ready dict. Writes a record."""
    n, seed, checkers = int(n), int(seed), int(checkers)
    bootstrap, hint_window, hint_context = int(bootstrap), int(hint_window), max(0, int(hint_context))
    field_limit, provenance_limit = float(field_limit), float(provenance_limit)
    _check_settings(n, checkers, field_limit, provenance_limit, bootstrap, hint_window)
    operator = operator or default_operator()
    records = Path(records)
    (records / "runs").mkdir(parents=True, exist_ok=True)

    rows, raw, fmt = load_ledger(ledger)
    by_id = {r["row_id"]: r for r in rows}
    srcs, missing_src = load_sources(sources, {r["source_id"] for r in rows if r["source_id"]})
    issues, l1 = level1(rows, srcs, hint_window, hint_context)
    l1["result"] = ("SATISFACTORY" if l1["fail"] == 0 and l1["provenance_rate"] >= provenance_limit
                    and l1["quote_rate"] >= provenance_limit else "NOT SATISFACTORY")

    excluded = set()
    if sample_ids:
        if isinstance(sample_ids, (str, Path)):
            sp = Path(sample_ids)
            if not sp.is_file():
                raise AuditError(f"The sample list is not found: {sample_ids}")
            txt = sp.read_text(encoding="utf-8-sig")
            ids = json.loads(txt) if sp.suffix.lower() == ".json" else txt.split()
            if isinstance(ids, dict):
                ids = ids.get("row_ids", [])
        else:
            ids = list(sample_ids)
        unknown = [i for i in ids if i not in by_id]
        if unknown:
            raise AuditError("The sample list has row ids that are not in the ledger.", unknown)
        sample = sorted(set(ids))
        alloc = dict(sorted(Counter(by_id[i]["source_id"] for i in sample).items()))
        method = "given list"
    else:
        excluded = audited_rows(records) if exclude_audited else set()
        sample, alloc, method = draw_sample(rows, n, seed, excluded)

    # Examine the verdict and review files before the run starts, so that a bad file does not leave a run.
    if adjudication:
        load_adjudication(adjudication)
    if verdicts and not checker_cmd:
        if isinstance(verdicts, (str, Path)):
            verdicts = [verdicts]
        pre, vproblems, _, _ = load_verdicts(verdicts)
        gaps = []
        for rid in sample:
            if rid not in pre:
                gaps.append(f"{rid}: no verdicts")
                continue
            for fld in AUDITED_FIELDS:
                code = (pre[rid]["verdicts"].get(fld) or {}).get("v", "")
                if code not in VERDICT_CODES:
                    gaps.append(f"{rid}.{fld}: the verdict is missing or not valid ('{code}')")
        if vproblems or gaps:
            raise AuditError("The verdicts are not complete or not valid. The script did not start the run.",
                             vproblems + gaps)

    run_id = _new_run_id(records)
    run_dir = records / "runs" / run_id
    run_dir.mkdir(parents=True)
    files = []
    led = run_dir / "inputs" / f"ledger.{fmt}"
    write_bytes(led, raw)
    files.append(led)
    sample_doc = {"row_ids": sample, "allocation": alloc, "method": method, "seed": seed, "n_requested": n,
                  "n_drawn": len(sample), "excluded_rows": sorted(excluded)}
    write_json(run_dir / "sample.json", sample_doc)
    files.append(run_dir / "sample.json")
    write_csv(run_dir / "level1.csv", ["row_id", "source_id", "check", "level", "field", "message", "context"],
              [[i["row_id"], i["source_id"], i["check"], i["level"], i["field"], i["message"], i["context"]]
               for i in issues])
    files.append(run_dir / "level1.csv")
    packet_files, k = write_packets(run_dir, by_id, sample, checkers)
    files += packet_files
    manifest = {
        "run_id": run_id, "created_utc": now_utc(), "tool": TOOL, "version": VERSION,
        "operator": operator, "label": label, "note": note,
        "ledger": {"given_path": str(ledger), "file": _rel(records, led), "format": fmt,
                   "sha256": sha256_bytes(raw), "rows": len(rows)},
        "sources": {"given_dir": str(sources), "missing": missing_src,
                    "files": {sid: {"sha256": s.sha256, "characters": len(s.n)} for sid, s in sorted(srcs.items())}},
        "settings": {"n": n, "seed": seed, "checkers": k, "field_limit": field_limit,
                     "provenance_limit": provenance_limit, "bootstrap": bootstrap, "hint_window": hint_window,
                     "hint_context": hint_context,
                     "exclude_audited": bool(exclude_audited), "audited_fields": AUDITED_FIELDS,
                     "number_fields": NUMBER_FIELDS},
        "sample": {k2: v for k2, v in sample_doc.items() if k2 != "excluded_rows"},
        "level1": l1,
    }
    write_json(run_dir / "manifest.json", manifest)
    files.insert(0, run_dir / "manifest.json")
    rec = append_record(records, "run_started", run_id, operator,
                        {"label": label, "ledger_sha256": manifest["ledger"]["sha256"], "rows": len(rows),
                         "sample": len(sample), "level1": l1["result"], "level1_fail": l1["fail"],
                         "level1_warn": l1["warn"], "level1_hint": l1["hint"]}, files)
    result = {"ok": True, "run_id": run_id, "status": "waiting_for_verdicts", "run_dir": str(run_dir),
              "level1": l1, "sample": {"n": len(sample), "method": method, "seed": seed, "allocation": alloc,
                                       "excluded_rows": len(excluded)},
              "packets": [_rel(records, p) for p in packet_files], "record": {"seq": rec["seq"], "hash": rec["hash"]}}
    if checker_cmd:
        jpk = [p for p in packet_files if p.suffix == ".json"]
        vdir = run_checker_cmd(checker_cmd, records, run_id, run_dir, jpk, sources, checker_timeout, operator)
        verdicts = [vdir]
    if verdicts:
        sc = do_score(run_id, verdicts, adjudication, records=records, operator=operator, note=note, sources=sources)
        result["status"] = sc["status"]
        result["score"] = sc
    return result


# ----------------------------------------------------------------------------- score
def _metrics(cells, key):
    n = len(cells)
    ok = sum(1 for c in cells if c[key] == "OK")
    per_row = defaultdict(list)
    for c in cells:
        per_row[c["row_id"]].append(c[key] == "OK")
    rows_ok = sum(1 for v in per_row.values() if all(v))

    def tally(sel):
        return {"ok": sum(1 for c in sel if c[key] == "OK"), "n": len(sel)}

    return {"fields_checked": n, "fields_ok": ok, "field_accuracy": ok / n if n else None,
            "field_ci95": wilson(ok, n), "rows_checked": len(per_row), "rows_all_ok": rows_ok,
            "row_accuracy": rows_ok / len(per_row) if per_row else None, "row_ci95": wilson(rows_ok, len(per_row)),
            "by_field": {f: tally([c for c in cells if c["field"] == f]) for f in AUDITED_FIELDS},
            "by_source": {s: tally([c for c in cells if c["source_id"] == s])
                          for s in sorted({c["source_id"] for c in cells})},
            "error_types": dict(sorted(Counter(c[key] for c in cells if c[key] != "OK").items()))}


def _render_report(sc, man):
    f, r, nb = sc["final"], sc["raw"], sc["numbers_only"]
    lim = sc["limits"]["field_limit"]
    lines = [f"# Audit report: run {sc['run_id']}, scoring {sc['scoring']}", "",
             f"Date (UTC): {sc['time_utc']}. Operator: {sc['operator']}. Label: {man.get('label') or '-'}.", "",
             f"Ledger: {man['ledger']['rows']} rows. SHA-256 of the ledger: {man['ledger']['sha256']}.", "",
             f"## Result: {sc['result']}", "",
             f"The limit for field accuracy is {pct(lim)} or more. "
             f"The field accuracy after review is {pct(f['field_accuracy'])}.", ""]
    if sc["review"]["pending"]:
        lines += [f"{sc['review']['pending']} findings have no review decision. "
                  "The score counts these findings as errors.", ""]
    lines += ["| Measure | Result | 95% interval |", "|---|---|---|",
              f"| Fields correct, after review | {f['fields_ok']} of {f['fields_checked']} = {pct(f['field_accuracy'])} "
              f"| {pct(f['field_ci95'][0])} to {pct(f['field_ci95'][1])} (Wilson) |",
              f"| Fields correct, row bootstrap | | {pct(sc['bootstrap']['ci95'][0])} to {pct(sc['bootstrap']['ci95'][1])} |",
              f"| Fields correct, checker verdicts only | {r['fields_ok']} of {r['fields_checked']} = "
              f"{pct(r['field_accuracy'])} | {pct(r['field_ci95'][0])} to {pct(r['field_ci95'][1])} |",
              f"| Numbers correct ({', '.join(NUMBER_FIELDS)}) | {nb['ok']} of {nb['checks']} = {pct(nb['accuracy'])} "
              f"| {pct(nb['ci95'][0])} to {pct(nb['ci95'][1])} |",
              f"| Rows with all fields correct | {f['rows_all_ok']} of {f['rows_checked']} = {pct(f['row_accuracy'])} "
              f"| {pct(f['row_ci95'][0])} to {pct(f['row_ci95'][1])} |",
              f"| Rows with a source and a locator (all rows) | {sc['provenance']['rows_with_source_and_locator']} of "
              f"{sc['provenance']['rows']} | |",
              f"| Quotes of the ledger found in the source (all rows) | {sc['provenance']['rows_with_quote_in_source']} of "
              f"{sc['provenance']['rows']} | |", "",
              f"Errors permitted at this sample size: {sc['gate']['errors_permitted']}. "
              f"Errors after review: {sc['gate']['errors_after_review']}.", "",
              f"Share of bootstrap resamples at or above the limit: {pct(sc['bootstrap']['share_at_or_above_limit'])}.", "",
              "## Accuracy by field", "", "| Field | Correct | Rate |", "|---|---|---|"]
    for k, v in f["by_field"].items():
        lines.append(f"| {k} | {v['ok']}/{v['n']} | {pct(v['ok'] / v['n'] if v['n'] else None)} |")
    lines += ["", "## Accuracy by source", "", "| Source | Correct | Rate |", "|---|---|---|"]
    for k, v in f["by_source"].items():
        lines.append(f"| {k} | {v['ok']}/{v['n']} | {pct(v['ok'] / v['n'] if v['n'] else None)} |")
    lines += ["", "## Findings", "", "| Row | Field | Checker verdict | Review | Final | Cause |", "|---|---|---|---|---|---|"]
    for c in sc["findings"]:
        lines.append(f"| {c['row_id']} | {c['field']} | {c['raw']} | {c['decision'] or 'pending'} | {c['final']} | "
                     f"{(c['cause'] or '').replace('|', '/')} |")
    q = sc["quotes"]
    lines += ["", "## Quote checks", "",
              f"Checker quotes: {q['checked']}. Quotes not found in the source: {len(q['not_found'])}.", ""]
    if sc["warnings"]:
        lines += ["## Warnings", ""] + [f"- {w}" for w in sc["warnings"]] + [""]
    return "\n".join(lines) + "\n"


def do_score(run_id, verdicts, adjudication=None, records=DEFAULT_RECORDS, operator=None, note="", sources=None):
    """Calculate the score of a run. Returns a JSON-ready dict. Writes a record."""
    operator = operator or default_operator()
    records = Path(records)
    run_dir = records / "runs" / str(run_id)
    if not (run_dir / "manifest.json").is_file():
        raise AuditError(f"The run is not found: {run_id}")
    man = read_json(run_dir / "manifest.json")
    sample = read_json(run_dir / "sample.json")["row_ids"]
    st = man["settings"]
    rows, _, _ = load_ledger(records / man["ledger"]["file"])
    by_id = {r["row_id"]: r for r in rows}
    src_dir = sources or man["sources"]["given_dir"]
    srcs, _ = load_sources(src_dir, {by_id[i]["source_id"] for i in sample})
    warnings = []
    for sid, s in srcs.items():
        old = man["sources"]["files"].get(sid, {}).get("sha256")
        if old and old != s.sha256:
            warnings.append(f"The source text {sid} changed after the run started.")
    if verdicts is None:
        raise AuditError("Give the verdicts (--verdicts).")
    if isinstance(verdicts, (str, Path)):
        verdicts = [verdicts]
    vd, vproblems, vfiles, skipped = load_verdicts(verdicts)
    adj, adj_path = load_adjudication(adjudication)
    if skipped:
        warnings.append("These files are not verdict files and the script did not use them: " + ", ".join(skipped))

    problems = list(vproblems)
    cells = []
    sset = set(sample)
    for rid in sample:
        if rid not in vd:
            problems.append(f"{rid}: no verdicts")
            continue
        v = vd[rid]
        for fld in AUDITED_FIELDS:
            raw = (v["verdicts"].get(fld) or {}).get("v", "")
            if raw not in VERDICT_CODES:
                problems.append(f"{rid}.{fld}: the verdict is missing or not valid ('{raw}')")
                continue
            a = adj.get(f"{rid}.{fld}")
            final, decision = raw, ""
            if a:
                decision = a["decision"]
                if decision == "overturned":
                    final = "OK"
                elif decision == "added":
                    final = a["verdict"]
                    if raw != "OK":
                        warnings.append(f"{rid}.{fld}: 'added' on a field that already has a finding.")
                elif raw == "OK":
                    warnings.append(f"{rid}.{fld}: 'upheld' on an OK verdict has no effect.")
            vv = v["verdicts"][fld]
            cells.append({"row_id": rid, "source_id": by_id[rid]["source_id"], "field": fld,
                          "ledger_value": by_id[rid][fld], "raw": raw, "final": final, "decision": decision,
                          "correct": vv.get("correct", ""), "note": vv.get("note", ""), "file": v.get("file", ""),
                          "cause": (a or {}).get("cause", ""), "reason": (a or {}).get("reason", "")})
    if problems:
        raise AuditError("The verdicts are not complete or not valid. The script did not calculate a score.", problems)
    extra = sorted(set(vd) - sset)
    if extra:
        warnings.append("Verdicts for rows that are not in the sample (not used): " + ", ".join(extra))
    unused = sorted(k for k in adj if k.split(".", 1)[0] not in sset)
    if unused:
        warnings.append("Review decisions for rows that are not in the sample (not used): " + ", ".join(unused))

    # Quote checks
    q_checked, q_missing, q_levels = 0, [], Counter()
    no_quote, value_unquoted = [], []
    for rid in sample:
        r, v = by_id[rid], vd[rid]
        src = srcs.get(r["source_id"])
        for q in v["quotes"]:
            q_checked += 1
            level = src.find(q)[0] if src else "no_source_text"
            q_levels[level] += 1
            if level in ("not_found", "no_source_text"):
                q_missing.append({"row_id": rid, "quote": q[:200]})
        if any(v["verdicts"][f]["v"] != "OK" for f in AUDITED_FIELDS) and not v["quotes"]:
            no_quote.append(rid)
        qs = " ".join(norm(q) for q in v["quotes"])
        if r["value"] and r["qualifier"] != "categorical" and not any(x in qs for x in num_forms(r["value"])):
            value_unquoted.append(rid)
    if q_missing:
        warnings.append(f"{len(q_missing)} checker quotes are not in the source text. Examine these verdicts again.")
    if no_quote:
        warnings.append("Rows with a finding but no quote: " + ", ".join(no_quote))

    raw_m, fin_m = _metrics(cells, "raw"), _metrics(cells, "final")
    num_cells = [c for c in cells if c["field"] in NUMBER_FIELDS]
    num_ok = sum(1 for c in num_cells if c["final"] == "OK")
    order = []
    for c in cells:
        if c["row_id"] not in order:
            order.append(c["row_id"])
    row_ok = [sum(1 for c in cells if c["row_id"] == rid and c["final"] == "OK") for rid in order]
    row_n = [sum(1 for c in cells if c["row_id"] == rid) for rid in order]
    boot = row_bootstrap(row_ok, row_n, st["bootstrap"], st["seed"], st["field_limit"])
    findings = [c for c in cells if c["raw"] != "OK" or c["final"] != "OK"]
    pending = sum(1 for c in findings if c["raw"] != "OK" and not c["decision"])
    nfields = fin_m["fields_checked"]
    need_ok = math.ceil(round(st["field_limit"] * nfields, 9))
    l1 = man["level1"]
    field_pass = fin_m["field_accuracy"] is not None and fin_m["fields_ok"] >= need_ok
    prov_pass = (l1["provenance_rate"] >= st["provenance_limit"] and l1["quote_rate"] >= st["provenance_limit"])
    result = "SATISFACTORY" if field_pass and prov_pass else "NOT SATISFACTORY"
    root = Counter(c["cause"] or "no cause given" for c in cells
                   if c["final"] != "OK" and c["decision"] in ("upheld", "added"))

    sdir_root = run_dir / "scoring"
    nums = [int(p.name) for p in sdir_root.glob("[0-9][0-9][0-9]")] if sdir_root.is_dir() else []
    scoring = f"{(max(nums) + 1) if nums else 1:03d}"
    sdir = sdir_root / scoring
    files = []
    for i, f in enumerate(vfiles, 1):
        dst = sdir / "inputs" / "verdicts" / f"{i:02d}_{f.name}"
        write_bytes(dst, f.read_bytes())
        files.append(dst)
    if adj_path:
        dst = sdir / "inputs" / f"review{adj_path.suffix.lower()}"
        write_bytes(dst, adj_path.read_bytes())
        files.append(dst)

    sc = {
        "ok": True, "run_id": run_id, "scoring": scoring, "time_utc": now_utc(), "operator": operator, "note": note,
        "result": result, "status": "review_pending" if pending else "scored",
        "limits": {"field_limit": st["field_limit"], "provenance_limit": st["provenance_limit"]},
        "gate": {"field_accuracy_passed": field_pass, "provenance_passed": prov_pass, "fields_needed_ok": need_ok,
                 "errors_permitted": nfields - need_ok, "errors_after_review": nfields - fin_m["fields_ok"]},
        "raw": raw_m, "final": fin_m,
        "numbers_only": {"fields": NUMBER_FIELDS, "checks": len(num_cells), "ok": num_ok,
                         "accuracy": num_ok / len(num_cells) if num_cells else None,
                         "ci95": wilson(num_ok, len(num_cells))},
        "bootstrap": boot,
        "provenance": {"rows": l1["rows"], "rows_with_source_and_locator": l1["rows_with_source_and_locator"],
                       "rows_with_quote_in_source": l1["rows_with_quote_in_source"]},
        "review": {"findings": sum(1 for c in cells if c["raw"] != "OK"),
                   "upheld": sum(1 for c in cells if c["decision"] == "upheld" and c["raw"] != "OK"),
                   "overturned": sum(1 for c in cells if c["decision"] == "overturned" and c["raw"] != "OK"),
                   "added": sum(1 for c in cells if c["decision"] == "added"), "pending": pending,
                   "root_causes": dict(root.most_common())},
        "quotes": {"checked": q_checked, "not_found": q_missing, "match_levels": dict(sorted(q_levels.items())),
                   "rows_with_finding_but_no_quote": no_quote, "rows_value_not_in_quotes": value_unquoted},
        "findings": [{k: c[k] for k in ("row_id", "source_id", "field", "ledger_value", "raw", "decision", "final",
                                         "correct", "cause", "reason")} for c in findings],
        "warnings": warnings,
        "inputs": {"verdict_files": [_rel(records, p) for p in files if "verdicts" in p.parts],
                   "review_file": _rel(records, files[-1]) if adj_path else None},
    }
    write_json(sdir / "score.json", sc)
    write_csv(sdir / "audit_sheet.csv",
              ["row_id", "source_id", "field", "ledger_value", "checker_verdict", "checker_correct_value",
               "checker_note", "checker_file", "review_decision", "final_verdict", "review_cause", "review_reason"],
              [[c["row_id"], c["source_id"], c["field"], c["ledger_value"], c["raw"], c["correct"], c["note"],
                c["file"], c["decision"], c["final"], c["cause"], c["reason"]] for c in cells])
    write_csv(sdir / "findings.csv",
              ["row_id", "source_id", "field", "ledger_value", "checker_verdict", "checker_correct_value",
               "review_decision", "final_verdict", "review_cause", "review_reason"],
              [[c["row_id"], c["source_id"], c["field"], c["ledger_value"], c["raw"], c["correct"], c["decision"],
                c["final"], c["cause"], c["reason"]] for c in findings])
    write_text(sdir / "report.md", _render_report(sc, man))
    files += [sdir / "score.json", sdir / "audit_sheet.csv", sdir / "findings.csv", sdir / "report.md"]
    rec = append_record(records, "scored", run_id, operator,
                        {"scoring": scoring, "result": result, "fields_ok": fin_m["fields_ok"],
                         "fields_checked": nfields, "field_accuracy": fin_m["field_accuracy"],
                         "review_pending": pending, "quotes_not_found": len(q_missing)}, files)
    sc["record"] = {"seq": rec["seq"], "hash": rec["hash"]}
    sc["files"] = [_rel(records, p) for p in files]
    return sc


# ----------------------------------------------------------------------------- list / show
def list_runs(records=DEFAULT_RECORDS):
    records = Path(records)
    runs = []
    for mp in sorted((records / "runs").glob("*/manifest.json")):
        man = read_json(mp)
        scores = sorted(mp.parent.glob("scoring/*/score.json"))
        latest = read_json(scores[-1]) if scores else None
        runs.append({
            "run_id": man["run_id"], "created_utc": man["created_utc"], "operator": man["operator"],
            "label": man.get("label", ""), "ledger_sha256": man["ledger"]["sha256"], "rows": man["ledger"]["rows"],
            "sample": man["sample"]["n_drawn"], "level1": man["level1"]["result"],
            "status": (latest["status"] if latest else "waiting_for_verdicts"), "scorings": len(scores),
            "latest": None if not latest else {
                "scoring": latest["scoring"], "result": latest["result"],
                "fields_ok": latest["final"]["fields_ok"], "fields_checked": latest["final"]["fields_checked"],
                "field_accuracy": latest["final"]["field_accuracy"], "field_ci95": latest["final"]["field_ci95"]},
        })
    runs.sort(key=lambda x: x["created_utc"])
    return {"ok": True, "records": str(records), "runs": runs}


def show_run(run_id, records=DEFAULT_RECORDS, details=False):
    run_dir = Path(records) / "runs" / str(run_id)
    if not (run_dir / "manifest.json").is_file():
        raise AuditError(f"The run is not found: {run_id}")
    out = {"ok": True, "manifest": read_json(run_dir / "manifest.json"), "scorings": []}
    for sp in sorted(run_dir.glob("scoring/*/score.json")):
        sc = read_json(sp)
        out["scorings"].append({"scoring": sc["scoring"], "time_utc": sc["time_utc"], "result": sc["result"],
                                "status": sc["status"], "fields_ok": sc["final"]["fields_ok"],
                                "fields_checked": sc["final"]["fields_checked"]})
        out["latest_score"] = sc
    if details:
        with open(run_dir / "level1.csv", encoding="utf-8") as fh:
            out["level1_issues"] = list(csv.DictReader(fh))
    return out


# ----------------------------------------------------------------------------- HTTP API
def serve(records=DEFAULT_RECORDS, host="127.0.0.1", port=8765, token=None, cors_origin=""):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlparse

    records = Path(records)
    uploads = records / "uploads"

    def save_upload(kind, content, suffix):
        name = f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}-{kind}{suffix}"
        p = uploads / name
        if isinstance(content, (dict, list)):
            write_json(p, content)
        else:
            write_text(p, str(content))
        return str(p)

    class Handler(BaseHTTPRequestHandler):
        server_version = f"{TOOL}/{VERSION}"

        def _headers(self, code, ctype="application/json; charset=utf-8", length=0):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            if cors_origin:
                self.send_header("Access-Control-Allow-Origin", cors_origin)
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Audit-Token")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()

        def _send(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False, indent=1, default=str).encode("utf-8")
            self._headers(code, length=len(body))
            self.wfile.write(body)

        def _authorized(self):
            if token and self.headers.get("X-Audit-Token") != token:
                self._send(401, {"ok": False, "error": "The token is missing or not correct."})
                return False
            return True

        def _guard(self, fn):
            try:
                self._send(200, fn())
            except AuditError as exc:
                self._send(400, {"ok": False, "error": exc.message, "details": exc.details})
            except Exception as exc:  # noqa: BLE001
                self._send(500, {"ok": False, "error": f"Unexpected error: {exc}"})

        def do_OPTIONS(self):
            self._headers(204)

        def do_GET(self):
            if not self._authorized():
                return
            u = urlparse(self.path)
            path, qs = u.path.rstrip("/"), parse_qs(u.query)
            m = re.fullmatch(r"/api/runs/([A-Za-z0-9_.-]+)", path)
            mf = re.fullmatch(r"/api/runs/([A-Za-z0-9_.-]+)/file", path)
            if path == "/api/health":
                self._send(200, {"ok": True, "tool": TOOL, "version": VERSION, "records": str(records)})
            elif path == "/api/runs":
                self._guard(lambda: list_runs(records))
            elif path == "/api/verify":
                self._guard(lambda: verify_records(records))
            elif mf:
                run_dir = (records / "runs" / mf.group(1)).resolve()
                target = (run_dir / qs.get("path", [""])[0]).resolve()
                if run_dir not in target.parents or not target.is_file():
                    self._send(404, {"ok": False, "error": "The file is not found in this run."})
                    return
                data = target.read_bytes()
                ctype = {".json": "application/json", ".csv": "text/csv", ".md": "text/markdown"}.get(
                    target.suffix.lower(), "application/octet-stream") + "; charset=utf-8"
                self._headers(200, ctype, len(data))
                self.wfile.write(data)
            elif m:
                self._guard(lambda: show_run(m.group(1), records, details=qs.get("details", ["0"])[0] == "1"))
            else:
                self._send(404, {"ok": False, "error": "Unknown path."})

        def do_POST(self):
            if not self._authorized():
                return
            path = urlparse(self.path).path.rstrip("/")
            length = int(self.headers.get("Content-Length") or 0)
            if length > 50 * 1024 * 1024:
                self._send(413, {"ok": False, "error": "The request is too large (50 MB maximum)."})
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                if not isinstance(body, dict):
                    raise ValueError("the body must be a JSON object")
            except (ValueError, UnicodeDecodeError) as exc:
                self._send(400, {"ok": False, "error": f"The request body is not valid JSON: {exc}"})
                return
            ms = re.fullmatch(r"/api/runs/([A-Za-z0-9_.-]+)/score", path)

            def prepare():
                b = dict(body)
                if "ledger_text" in b:
                    b["ledger"] = save_upload("ledger", b.pop("ledger_text"), "." + b.pop("ledger_format", "csv"))
                if "verdicts_inline" in b:
                    b["verdicts"] = [save_upload("verdicts", b.pop("verdicts_inline"), ".json")]
                if "review_inline" in b:
                    b["adjudication"] = save_upload("review", b.pop("review_inline"), ".json")
                if "review" in b:
                    b["adjudication"] = b.pop("review")
                if isinstance(b.get("verdicts"), str):
                    b["verdicts"] = [b["verdicts"]]
                return b

            if path == "/api/runs":
                allowed = {"ledger", "sources", "n", "seed", "checkers", "exclude_audited", "sample_ids", "verdicts",
                           "adjudication", "checker_cmd", "checker_timeout", "operator", "note", "label",
                           "field_limit", "provenance_limit", "bootstrap", "hint_window", "hint_context"}

                def go():
                    b = prepare()
                    bad = sorted(set(b) - allowed)
                    if bad:
                        raise AuditError("Unknown fields in the request.", bad)
                    if "ledger" not in b or "sources" not in b:
                        raise AuditError("Give 'ledger' (or 'ledger_text') and 'sources'.")
                    return do_run(records=records, **b)
                self._guard(go)
            elif ms:
                def go_score():
                    b = prepare()
                    return do_score(ms.group(1), b.get("verdicts"), b.get("adjudication"), records=records,
                                    operator=b.get("operator"), note=b.get("note", ""), sources=b.get("sources"))
                self._guard(go_score)
            else:
                self._send(404, {"ok": False, "error": "Unknown path."})

    httpd = ThreadingHTTPServer((host, int(port)), Handler)
    print(f"{TOOL} {VERSION}: the API is at http://{host}:{port}/api (records: {records}). Push Ctrl+C to stop.",
          flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


# ----------------------------------------------------------------------------- command line
def _print_summary(res):
    if "level1" in res and "run_id" in res and "manifest" not in res:
        l1 = res["level1"]
        print(f"Run {res['run_id']}: {res['status']}.")
        print(f"  Level 1: {l1['result']}. Rows with a source and a locator: {l1['rows_with_source_and_locator']} of "
              f"{l1['rows']}. Quotes found in the source: {l1['rows_with_quote_in_source']} of {l1['rows']}. "
              f"FAIL {l1['fail']}, WARN {l1['warn']}, HINT {l1['hint']}.")
        s = res["sample"]
        print(f"  Sample: {s['n']} rows ({s['method']}, seed {s['seed']}). Excluded rows: {s['excluded_rows']}.")
        print(f"  Packets: {', '.join(p for p in res['packets'] if p.endswith('.json'))}")
        if "score" in res:
            _print_summary(res["score"])
        return
    if "final" in res:
        f = res["final"]
        print(f"Run {res['run_id']}, scoring {res['scoring']}: {res['result']}.")
        print(f"  Fields correct after review: {f['fields_ok']} of {f['fields_checked']} = {pct(f['field_accuracy'])} "
              f"(95% interval {pct(f['field_ci95'][0])} to {pct(f['field_ci95'][1])}). "
              f"Limit: {pct(res['limits']['field_limit'])}.")
        r = res["raw"]
        print(f"  Checker verdicts only: {r['fields_ok']} of {r['fields_checked']} = {pct(r['field_accuracy'])}. "
              f"Findings: {res['review']['findings']}. Upheld {res['review']['upheld']}, overturned "
              f"{res['review']['overturned']}, added {res['review']['added']}, pending {res['review']['pending']}.")
        nb = res["numbers_only"]
        print(f"  Numbers correct: {nb['ok']} of {nb['checks']}. Rows with all fields correct: {f['rows_all_ok']} of "
              f"{f['rows_checked']}. Quotes not found: {len(res['quotes']['not_found'])}.")
        print(f"  Report: {res['files'][-1]}")
        for w in res["warnings"]:
            print(f"  WARNING: {w}")
        return
    if "runs" in res:
        if not res["runs"]:
            print("No runs.")
        for r in res["runs"]:
            lt = r["latest"]
            score = (f"{lt['result']} {lt['fields_ok']}/{lt['fields_checked']} = {pct(lt['field_accuracy'])}"
                     if lt else "no score")
            print(f"{r['run_id']}  {r['created_utc']}  {r['label'] or '-'}  rows {r['rows']}  sample {r['sample']}  "
                  f"L1 {r['level1']}  {r['status']}  {score}")
        return
    if "problems" in res and "records" in res:
        print(f"Records: {res['records']}. Result: {res['result']}.")
        for p in res["problems"]:
            print(f"  {p}")
        return
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--records", default=DEFAULT_RECORDS,
                        help="Record folder (default: %(default)s, or the NEXTBURN_AUDIT_RECORDS variable).")
    common.add_argument("--json", action="store_true", help="Print one JSON object.")
    ap = argparse.ArgumentParser(prog="nextburn_audit.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"{TOOL} {VERSION}")
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True

    r = sub.add_parser("run", parents=[common], help="Start a run (Level 1, sample, packets; optional score).")
    r.add_argument("--ledger", required=True, help="Ledger file (.csv or .json).")
    r.add_argument("--sources", required=True, help="Folder with one <source_id>.txt file for each source.")
    r.add_argument("--n", type=int, default=DEFAULTS["n"], help="Rows in the sample (default: %(default)s).")
    r.add_argument("--seed", type=int, default=DEFAULTS["seed"], help="Random seed (default: %(default)s).")
    r.add_argument("--checkers", type=int, default=DEFAULTS["checkers"], help="Checker packets (default: %(default)s).")
    r.add_argument("--exclude-audited", action="store_true", help="Do not select rows from earlier scored samples.")
    r.add_argument("--sample-ids", help="Use this list of row ids (.json list or text) as the sample.")
    r.add_argument("--verdicts", nargs="+", help="Verdict files or folders. If you give them, the run also scores.")
    r.add_argument("--adjudication", "--review", dest="adjudication", help="Review decisions (.json or .csv).")
    r.add_argument("--checker-cmd", help="Program for each packet. Use {packet} {out} {sources} {instructions}.")
    r.add_argument("--checker-timeout", type=int, default=3600, help="Seconds for each packet (default: %(default)s).")
    r.add_argument("--field-limit", type=float, default=DEFAULTS["field_limit"],
                   help="Minimum field accuracy (default: %(default)s).")
    r.add_argument("--provenance-limit", type=float, default=DEFAULTS["provenance_limit"],
                   help="Minimum share of rows with source, locator and quote (default: %(default)s).")
    r.add_argument("--bootstrap", type=int, default=DEFAULTS["bootstrap"], help="Bootstrap resamples (default: %(default)s).")
    r.add_argument("--hint-window", type=int, default=DEFAULTS["hint_window"],
                   help="Characters around the quote for the L1-HINT check (default: %(default)s).")
    r.add_argument("--hint-context", type=int, default=DEFAULTS["hint_context"],
                   help="Characters of source text to show around each hint. 0 shows only the match "
                        "and its position (default: %(default)s).")
    r.add_argument("--operator", help="Name of the person who runs the audit.")
    r.add_argument("--label", default="", help="Short name for the run.")
    r.add_argument("--note", default="", help="Note for the record.")
    r.add_argument("--strict", action="store_true", help="Exit code 1 if the result is NOT SATISFACTORY.")

    s = sub.add_parser("score", parents=[common], help="Calculate the score of a run.")
    s.add_argument("--run", required=True, help="Run id.")
    s.add_argument("--verdicts", nargs="+", required=True, help="Verdict files or folders.")
    s.add_argument("--adjudication", "--review", dest="adjudication", help="Review decisions (.json or .csv).")
    s.add_argument("--sources", help="Source folder, if it is not the folder of the run.")
    s.add_argument("--operator", help="Name of the person who calculates the score.")
    s.add_argument("--note", default="", help="Note for the record.")
    s.add_argument("--strict", action="store_true", help="Exit code 1 if the result is NOT SATISFACTORY.")

    sub.add_parser("list", parents=[common], help="Show the runs.")
    sh = sub.add_parser("show", parents=[common], help="Show one run.")
    sh.add_argument("--run", required=True, help="Run id.")
    sh.add_argument("--details", action="store_true", help="Include the Level 1 issues.")
    sub.add_parser("verify", parents=[common], help="Examine the records for changes.")
    sv = sub.add_parser("serve", parents=[common], help="Start a local HTTP API for a front end.")
    sv.add_argument("--host", default="127.0.0.1", help="Host (default: %(default)s).")
    sv.add_argument("--port", type=int, default=8765, help="Port (default: %(default)s).")
    sv.add_argument("--token", default=os.environ.get("NEXTBURN_AUDIT_TOKEN"),
                    help="If set, each request must send this value in the X-Audit-Token header.")
    sv.add_argument("--cors-origin", default="", help="Origin of the front end, for example http://localhost:3000.")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "run":
            res = do_run(args.ledger, args.sources, records=args.records, n=args.n, seed=args.seed,
                         checkers=args.checkers, exclude_audited=args.exclude_audited, sample_ids=args.sample_ids,
                         verdicts=args.verdicts, adjudication=args.adjudication, checker_cmd=args.checker_cmd,
                         checker_timeout=args.checker_timeout, operator=args.operator, note=args.note,
                         label=args.label, field_limit=args.field_limit, provenance_limit=args.provenance_limit,
                         bootstrap=args.bootstrap, hint_window=args.hint_window, hint_context=args.hint_context)
        elif args.cmd == "score":
            res = do_score(args.run, args.verdicts, args.adjudication, records=args.records, operator=args.operator,
                           note=args.note, sources=args.sources)
        elif args.cmd == "list":
            res = list_runs(args.records)
        elif args.cmd == "show":
            res = show_run(args.run, args.records, details=args.details)
        elif args.cmd == "verify":
            res = verify_records(args.records)
        else:
            serve(args.records, args.host, args.port, args.token, args.cors_origin)
            return 0
    except AuditError as exc:
        err = {"ok": False, "error": exc.message, "details": exc.details}
        if getattr(args, "json", False):
            print(json.dumps(err, indent=1, ensure_ascii=False))
        else:
            print(f"ERROR: {exc.message}", file=sys.stderr)
            for d in exc.details[:50]:
                print(f"  - {d}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        err = {"ok": False, "error": f"Unexpected error: {type(exc).__name__}: {exc}"}
        print(json.dumps(err, indent=1) if getattr(args, "json", False) else f"ERROR: {err['error']}",
              file=sys.stdout if getattr(args, "json", False) else sys.stderr)
        return 3
    if args.json:
        print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    else:
        _print_summary(res)
    if args.cmd == "verify" and not res["ok"]:
        return 1
    result = res.get("result") or (res.get("score") or {}).get("result")
    if getattr(args, "strict", False) and result == "NOT SATISFACTORY":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
