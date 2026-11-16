# Brief given to each independent checker (Experiment 1)

You are the independent checker for a ledger accuracy audit. Another person extracted test data from NASA documents into a ledger; you did not. Verify every field of every row in your batch against the cited source text, blind: do not open the ledger, the extraction scripts or other batches, and do not use outside knowledge.

For each row, find the cited location (page, table, slide or section), reconstruct any flattened table, and give one verdict per field for locator, platform, gravity, material, geometry, direction, flow, pressure, oxygen, measurement, value, unit and qualifier:

- OK: matches what the source says for this specific test (formatting differences only, such as ".9" for "0.9"). "not stated" is OK when the source does not state that attribute for this test.
- WRONG: the source states something different (give the correct value).
- NOT_IN_SOURCE: the ledger gives a value the source does not support for this row (inferred, or taken from another test or column).
- MISSED: the ledger says "not stated" but the source states it for this test (give the value).

Give one to three verbatim quotes per row (at most 300 characters each), including one that contains the row's value and one that supports every non-OK verdict. A script checks that each quote appears in the source text. Write one JSON object per row: row_id, a verdict for each of the 13 fields (with "correct" and a short "note" when not OK), and the quotes.
