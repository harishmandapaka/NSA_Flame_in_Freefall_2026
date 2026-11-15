# NextBurn audit script: user guide (ASD-STE100 style)

File: nextburn_audit.py, version 1.0.0. One file. Python 3.8 or later. You do not need other packages.

## 1. What the script does

The script does an audit of the NextBurn evidence ledger. One command starts the audit. Each command saves a record. The script does not write over a record.

The audit has two levels:

| Level | Rows | Who examines | What it examines |
|---|---|---|---|
| Level 1 | All rows, in each run | The script | Source and locator, quote in the source text, blank fields, numbers in the quote, units, named terms, hints for "not stated" fields |
| Level 2 | A sample of rows | Independent checkers (persons or an AI program) | 13 fields of each sampled row, with quotes. Then the script calculates the score. |

The Level 1 checks give these codes:

| Code | Level | Description |
|---|---|---|
| L1-PROV | FAIL | The row has no source or no locator. |
| L1-SRC | FAIL | No source text file is available for the source of the row. |
| L1-QUOTE | FAIL | The quote of the row is not in the source text. |
| L1-BLANK | FAIL | An audited field is blank. Write the value or "not stated". |
| L1-VALUE | WARN | The quote does not contain the number of the value. |
| L1-UNIT | WARN | A number has no unit. Write the unit, or "-" for no unit. |
| L1-TERM | WARN | A named term (vehicle, facility or material) is not in the source text. |
| L1-HINT | HINT | A field says "not stated", but other rows of the same source give this condition, and the source has a word for this condition near the quote. |

## 2. What you need

- Python 3.8 or later.
- The ledger file (.csv or .json). It must have the columns row_id, source_id, snippet and the 13 audited fields.
- A folder with one text file for each source. The name of each file is the source_id with the extension .txt.

The 13 audited fields are locator, platform, gravity, material, geometry, direction, flow, pressure, oxygen, measurement, value, unit and qualifier.

## 3. Make the source text files

This folder does not contain the source texts, because some of the documents have a copyright. Make the files on your computer:

1. Open sources.csv in the experiment1 folder.
2. Download each document from its link.
3. Convert each PDF document to text. For example, use pdftotext.
4. Put the text files in the folder "sources", next to the script.
5. Make sure that each file name agrees with the source_id column of the ledger.

```
pdftotext -layout luci.pdf sources/luci_2025.txt
```

NOTE: A different conversion program can change line breaks and hyphens. The script ignores these differences when it searches for a quote. If a source text changes after a run starts, the score report shows a warning.

## 4. Start an audit run

Run this command in the audit_tool folder:

```
python nextburn_audit.py run --ledger ../experiment1/ledger_v2.csv --sources sources --exclude-audited --label "Ledger v2: fresh rows"
```

The script does these steps:

1. It reads the ledger and the source texts.
2. It does the Level 1 checks on all rows.
3. It selects the sample from each source in proportion to the size of the source. It uses a fixed seed.
4. It writes one packet for each checker and a file with the checker instructions.
5. It saves the run and writes a record.

If Level 1 shows a FAIL, correct the ledger. Then start a new run.

| Option | Default | Description |
|---|---|---|
| --n | 50 | Number of rows in the sample. If the ledger has fewer free rows, the sample contains all of them. |
| --seed | 2026 | Seed of the random generator. The same seed and ledger give the same sample. |
| --checkers | 3 | Number of checker packets |
| --exclude-audited | off | Do not select rows from samples that have a score |
| --sample-ids | none | Use this list of row ids as the sample |
| --field-limit | 0.98 | Minimum field accuracy |
| --provenance-limit | 1.0 | Minimum share of rows with a source, a locator and a quote in the source |
| --bootstrap | 10000 | Number of bootstrap resamples for the interval of the rows |
| --hint-window | 3000 | Characters around the quote for the L1-HINT check |
| --hint-context | 0 | Characters of source text to show with each hint. 0 shows only the match and its position. |
| --verdicts, --review | none | Give these to start the run and calculate the score in one command |
| --checker-cmd | none | Program that gives the verdicts (see section 8) |
| --label, --note, --operator | | Text for the record |
| --records | audit_records | Record folder |
| --json | off | Print one JSON object |
| --strict | off | Exit code 1 if the result is NOT SATISFACTORY |

## 5. Get the checker verdicts

1. Open the folder audit_records/runs/RUN_ID/packets.
2. Give each packet to a different checker.
3. Give each checker the file instructions.md and the source text files.
4. Tell each checker to write a JSON or CSV verdict file.
5. Put all verdict files in one folder.

A JSON verdict file is a list with one object for each row:

```json
[{"row_id": "R002",
  "verdicts": {"locator": {"v": "OK"}, "oxygen": {"v": "MISSED", "correct": "21%", "note": "slide 4"}},
  "quotes": ["text copied from the source"]}]
```

The object must have a verdict for each of the 13 fields. A CSV verdict file has one line for each field, with the columns row_id, field, verdict, correct_value, quote and note. The packet file checker_N.csv has this format. The checker fills in the empty columns.

## 6. Calculate the score

```
python nextburn_audit.py score --run RUN_ID --verdicts verdicts/
```

The script examines the verdicts:

- Each sampled row must have a verdict for each of the 13 fields. If a verdict is not there, the script stops and shows a list.
- The script searches for each checker quote in the source text. A quote that the script cannot find is a warning.

Then the script writes these files in a new numbered folder (001, 002 and more) in the folder "scoring":

| File | Content |
|---|---|
| score.json | All results: field accuracy with the Wilson interval, the bootstrap interval of the rows, the numbers, the rows, the result for each field and each source, and the findings |
| report.md | The report for persons |
| audit_sheet.csv | One line for each field verdict |
| findings.csv | One line for each finding |
| inputs/ | Copies of the verdict files and the review file |

## 7. Review the findings

A finding is a verdict that is not OK. A reviewer examines each finding against the source text. Write the decisions in a review file:

```json
{
 "R003.oxygen": {"decision": "upheld", "cause": "condition on another slide", "reason": "1-g slide gives O2 near 20%"},
 "R081.geometry": {"decision": "overturned", "reason": "1/4 inch applies to one rod only"},
 "R005.oxygen": {"decision": "added", "verdict": "MISSED", "reason": "same defect as R006"}
}
```

| Decision | Effect on the score |
|---|---|
| upheld | The finding is an error. |
| overturned | The finding is not an error. The field is OK. |
| added | The reviewer found an error that the checker did not find. Give the verdict. |

Then calculate the score again with the review file:

```
python nextburn_audit.py score --run RUN_ID --verdicts verdicts/ --review review.json
```

If a finding has no decision, the score counts the finding as an error. The script saves each new score in a new numbered folder. It does not write over an old score.

## 8. Use an AI checker program

You can connect a checker program. For example, the program can send each packet to an AI model. Use the option --checker-cmd:

```
python nextburn_audit.py run --ledger ../experiment1/ledger_v2.csv --sources sources --exclude-audited --checker-cmd "python my_checker.py {packet} {out} {sources}"
```

The script runs the program one time for each packet. The program must do these steps:

1. Read the packet file {packet}. It is a JSON list of rows.
2. Read the source texts in the folder {sources}.
3. Write the verdicts to the file {out} in the JSON verdict format.
4. Stop with exit code 0.

You can also use {instructions} (the path of instructions.md) and {checker} (the packet number). After the last packet, the script calculates the score.

NOTE: If an AI program gives the verdicts, write this in your submission. The Space Apps rules tell teams to show where they used AI.

## 9. Audit records

| File | Content |
|---|---|
| audit_records/audit_log.jsonl | One line for each event: run_started, checker_done and scored. Each line has the time, the operator, the SHA-256 hash of each file and the hash of the line before it. |
| runs/RUN_ID/manifest.json | The settings, the ledger hash, the source hashes and the Level 1 summary |
| runs/RUN_ID/inputs/ | A copy of the ledger that the run used |
| runs/RUN_ID/sample.json | The sampled row ids and the number of rows from each source |
| runs/RUN_ID/level1.csv | Each Level 1 FAIL, WARN and HINT |
| runs/RUN_ID/packets/ | The checker packets (JSON and CSV) and instructions.md |
| runs/RUN_ID/scoring/NNN/ | The files of each score calculation |

To examine the records, run this command:

```
python nextburn_audit.py verify
```

The command calculates each hash again. If a file or a record changed, the command shows the change and stops with exit code 1.

Keep the audit_records folder in a shared OneDrive folder. Then the team has one record history. Do not edit or delete the files in this folder. Use only one computer at a time to write to the folder. The file lock of the script works only on one computer.

## 10. Connect a front end

Start the local API:

```
python nextburn_audit.py serve --port 8765 --token YOUR_SECRET --cors-origin http://localhost:3000
```

| Method | Path | Input | Result |
|---|---|---|---|
| GET | /api/health | | Tool name and version |
| GET | /api/runs | | All runs, each with its last score |
| GET | /api/runs/RUN_ID | ?details=1 adds the Level 1 issues | The run and its scores |
| GET | /api/runs/RUN_ID/file | ?path=scoring/001/report.md | One file of the run |
| GET | /api/verify | | The result of the "verify" command |
| POST | /api/runs | {"ledger": path, "sources": path, ...} or {"ledger_text": CSV text, "ledger_format": "csv", ...} | Starts a run. If the body has verdicts, the run also gets a score. |
| POST | /api/runs/RUN_ID/score | {"verdicts": folder} or {"verdicts_inline": list}, and "review" or "review_inline" | Calculates the score |

Each request must send the token in the header X-Audit-Token. The body of POST /api/runs can contain the same names as the run options, with "_" in place of "-" (for example "exclude_audited": true).

```js
const api = "http://127.0.0.1:8765/api";
const headers = {"Content-Type": "application/json", "X-Audit-Token": "YOUR_SECRET"};
const run = await fetch(`${api}/runs`, {method: "POST", headers,
  body: JSON.stringify({ledger: "../experiment1/ledger_v2.csv", sources: "sources",
                        exclude_audited: true, label: "Ledger v2: fresh rows"})}).then(r => r.json());
console.log(run.run_id, run.level1.result, run.packets);
```

A Python program can also import the script:

```python
import nextburn_audit as na
run = na.do_run("../experiment1/ledger_v2.csv", "sources", exclude_audited=True, label="v2")
score = na.do_score(run["run_id"], ["verdicts/"], "review.json")
print(score["result"], score["final"]["field_accuracy"])
```

NOTE: The API has no user accounts. Keep it on your computer (host 127.0.0.1). If you open it to a network, always set a token.

## 11. Exit codes

| Code | Description |
|---|---|
| 0 | The command is complete. Read "result" for the audit result. |
| 1 | You used --strict and the result is NOT SATISFACTORY, or the "verify" command found a change. |
| 2 | An input is not correct. The message tells you what to do. |
| 3 | An unexpected error occurred. |

## 12. Test of this version

We ran the script on the files of Experiment 1. The script gave the same results as Experiment 1 in 32 of 32 comparisons. The comparisons included the sample, the packets, the counts, the intervals, the bootstrap and the 650 lines of the audit sheet. We also tested these items:

- The CSV verdict format and the CSV review format
- The checker program option
- The decision "added"
- Bad inputs (a ledger without a necessary column, a bad decision, verdicts that are not complete)
- The record check after a change to a file and after a change to a record
- The local API with a token

## 13. Records in this folder

| Run | Label | Status | Result |
|---|---|---|---|
| AUD-20261115-055827-3cc2 | Experiment 1 replay | Scored two times | Score 001: 632 of 650 = 97.2% (as reported). Score 002: 631 of 650 = 97.1% (strict count with R005). Both NOT SATISFACTORY. |
| AUD-20261115-055829-c64f | Ledger v2: fresh rows | Waits for verdicts | 48 rows that Experiment 1 did not select, in 3 packets |
