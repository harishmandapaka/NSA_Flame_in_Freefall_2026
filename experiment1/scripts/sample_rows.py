import json, random, math
from collections import defaultdict
rows = json.load(open("ledger_v1.json"))
N, SEED = 50, 2026
by = defaultdict(list)
for r in rows: by[r["source_id"]].append(r)
total = len(rows)
quota = {s: N * len(v) / total for s, v in by.items()}
alloc = {s: int(math.floor(q)) for s, q in quota.items()}
for s in sorted(quota, key=lambda s: (-(quota[s] - alloc[s]), s))[: N - sum(alloc.values())]:
    alloc[s] += 1
rng = random.Random(SEED)
sample = []
for s in sorted(by):
    sample += rng.sample(sorted(by[s], key=lambda r: r["row_id"]), alloc[s])
sample.sort(key=lambda r: r["row_id"])
AUD = ["locator","platform","gravity","material","geometry","direction","flow","pressure","oxygen","measurement","value","unit","qualifier"]
blind = [{"row_id": r["row_id"], "source_file": f"/mnt/workspace/working/exp1/sources/{r['source_id']}.txt",
          "source_title": r["source_title"], **{k: r[k] for k in AUD}} for r in sample]
batches = [blind[0::3], blind[1::3], blind[2::3]]
for i, b in enumerate(batches, 1):
    json.dump(b, open(f"audit/sheet_batch{i}.json", "w"), indent=1, ensure_ascii=False)
json.dump([r["row_id"] for r in sample], open("audit/sample_ids.json", "w"))
print("allocation:", dict(sorted(alloc.items())), "| sampled:", len(sample), "| batches:", [len(b) for b in batches])
print("fields audited per row:", len(AUD), "| total field checks:", len(AUD) * len(sample))
