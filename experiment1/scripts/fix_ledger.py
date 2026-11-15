import json, csv, re, unicodedata
def norm(s):
    s = unicodedata.normalize("NFKC", s).replace("\u2010","-").replace("\u2011","-").replace("\u2013","-").replace("\u2019","'")
    return re.sub(r"\s+", " ", s).strip()
rows = json.load(open("ledger_v1.json")); sample = set(json.load(open("audit/sample_ids.json")))
adj = json.load(open("audit/adjudication.json"))
found = {k.split(".")[0] + "." + k.split(".")[1] for k, a in adj.items() if a["decision"] == "upheld"}
changes = []
def setf(r, field, new, reason, quote, src_loc):
    old = r[field]
    if old == new: return
    r[field] = new
    r.setdefault("condition_notes", [])
    r["condition_notes"].append(f"{field}: {src_loc}")
    key = f"{r['row_id']}.{field}"
    how = "audit finding (sampled row)" if key in found else ("same root cause, row not sampled" if r["row_id"] not in sample else "same root cause, field passed audit")
    changes.append({"row_id": r["row_id"], "field": field, "old": old, "new": new, "reason": reason, "found_by": how, "quote": quote})
for r in rows:
    s, p, m = r["source_id"], r["platform"], r["material"]
    if s == "luci_2025":
        sib1 = ("~20% (roughly constant)", "O2% varies slightly but is roughly constant at 20%.", "slide '1-G Results: SIBAL Flame Length and Flame Width vs. O2% for LUCI SIBAL'")
        pm1 = ("21% at start, falling to 14.5%", "O2% rises quickly in the beginning, then decreases ~linearly from 21% to 14.5%.", "slide 'Results: PMMA Flame Spread vs. O2% for LUCI PMMA' (1-G)")
        if p.startswith("ground") and m.startswith("SIBAL"):
            setf(r, "oxygen", sib1[0], "1-g test oxygen is stated on another slide of the same source", sib1[1], sib1[2])
        if p.startswith("ground") and m.startswith("PMMA"):
            setf(r, "oxygen", pm1[0], "1-g test oxygen is stated on another slide of the same source", pm1[1], pm1[2])
        if p.startswith("New Shepard NS-29 vs") and m.startswith("SIBAL"):
            setf(r, "oxygen", "air (lunar burn); ~20% (1-g burn)", "both burns' oxygen is stated in the same source", "Two samples are burned simultaneously in air at normal pressure", "summary bullets and 1-G SIBAL oxygen slide")
        if p.startswith("New Shepard NS-29 vs") and m.startswith("PMMA"):
            setf(r, "oxygen", "air (lunar burn); 21% falling to 14.5% (1-g burn)", "both burns' oxygen is stated in the same source", pm1[1], "summary bullets and 1-G PMMA oxygen slide")
        if r["locator"].startswith("Summary bullets"):
            setf(r, "geometry", "fabric sheet; 4 mm diameter rod", "sample geometry is stated in the same summary bullets", "Cotton-fiberglass composite fabric sheet and a 4-mm diameter rod of acrylic plastic", "same summary bullets")
    if s == "saffire45_paper_2021" and any(t in p for t in ("Saffire I-1", "Saffire II-5", "Saffire II-6", "Saffire III-1")):
        test = p.split("Saffire ")[-1]
        setf(r, "platform", f"orbiting spacecraft, Saffire {test} (vehicle not named in this source)", "this paper names Cygnus only for Saffire IV and V", "Steady spread rate summary for the cotton-fiberglass fabric burning in microgravity", "Figure 10 caption")
    if s == "saffire45_paper_2021" and ("Saffire V-3" in p or "Saffire V-4" in p):
        setf(r, "flow", "20 cm/s, reduced to 5 cm/s and held 300 s, then fan off", "flow step before fan-off was omitted", "the air flow for Saffire V samples 3 and 4 was reduced from the starting condition of 20 cm/s to 5 cm/s and held at 5 cm/s for 300 seconds", "text before Figure 4 caption")
    if s == "bass2_poster_2014" and r["measurement"] == "test points obtained" and r["geometry"].startswith("1-cm and 2-cm wide; 0.1"):
        setf(r, "direction", "opposed", "flow direction is stated in the same panel", "Comparison of flame extinction at low opposing flow velocity", "Bhattacharjee panel caption")
    if s == "sacksteder_2003" and r["evidence_tier"].startswith("Model"):
        setf(r, "material", "cotton/fiberglass composite fuel (simulated)", "model fuel is named in the source", "A cotton fiberglass composite fuel was simulated.", "text discussing Figure 3")
        setf(r, "geometry", "5 cm wide x 15 cm long, in a vertical flow tunnel with a 10 cm x 10 cm cross section", "geometry is given in the Figure 3 caption", "Fuel samples are 5 cm wide by 15 cm long burning in a vertical flow tunnel with a 10cm by 10cm cross sect", "Figure 3 caption")
        setf(r, "direction", "downward", "model is of downward spreading", "A derivative three-dimensional model of downward spreading has been developed", "same section")
    if s == "feier_2001" and r["platform"] == "NASA KC-135 aircraft":
        setf(r, "geometry", "1, 2 and 4 cm wide samples", "sample widths are stated in the same source", "Fuel samples 1-cm, 2-cm, and 4-cm wide were burned in air", "abstract and Experiments section")
        if r["measurement"].startswith("time within 15%"):
            setf(r, "locator", "Experimental Results, 'Acceleration Environment' subsection (Figure 2 discussion)", "value sits in the Acceleration Environment subsection", "Experimental Results Acceleration Environment Figure 2 shows the measured vertical accelerations", "section heading")
    if s == "fm2_poster_2024" and r["platform"].startswith("lunar-gravity centrifuge"):
        r["evidence_tier"] = "Simulated lunar gravity (centrifuge drop and aircraft)"
# verify every new quote is verbatim in its source
src = {}
bad = [c for c in changes if norm(c["quote"]) not in src.setdefault(next(r["source_id"] for r in rows if r["row_id"] == c["row_id"]),
       norm(open(f"sources/{next(r['source_id'] for r in rows if r['row_id'] == c['row_id'])}.txt", encoding="utf-8").read()))]
print("changes:", len(changes), "| quotes not found:", len(bad))
for b in bad: print("  BAD", b["row_id"], b["quote"][:80])
from collections import Counter
print(Counter(c["found_by"] for c in changes))
for r in rows: r["condition_notes"] = "; ".join(r.get("condition_notes", []))
FIELDS = ["row_id","source_id","source_title","locator","platform","gravity","material","geometry","direction","flow","pressure","oxygen","measurement","value","unit","qualifier","evidence_tier","snippet","condition_notes"]
with open("ledger_v2.csv","w",newline="",encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); [w.writerow({k: r.get(k,"") for k in FIELDS}) for r in rows]
json.dump(rows, open("ledger_v2.json","w"), indent=1, ensure_ascii=False)
with open("audit/fixes.csv","w",newline="",encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["row_id","field","old","new","reason","found_by","quote"]); w.writeheader(); [w.writerow(c) for c in changes]
