# Checker instructions (NextBurn ledger audit)

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
