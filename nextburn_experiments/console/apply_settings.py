"""Apply a settings change request made in the NextBurn Coverage Console (static mode or a GitHub issue).

Usage:
  python console/apply_settings.py change.json      a file saved with "Download change request"
  python console/apply_settings.py issue_body.md    the text of a "Settings change" GitHub issue (the JSON block is read)

Every value is checked against console/settings_schema.json; nothing is written if any value is refused.
The old file is backed up in console/history/backups and the change is logged in console/history/change_log.jsonl.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import console_lib  # noqa: E402


def read_request(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    req = json.loads(m.group(1) if m else text)
    if req.get("nextburn_settings_change") != 1 or "file" not in req or "changes" not in req:
        raise console_lib.SettingsError("this is not a NextBurn settings change request")
    return req


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    try:
        req = read_request(argv[0])
        rec = console_lib.apply_changes(req["file"], [{"path": c["path"], "value": c["new"]} for c in req["changes"]], source="apply_settings.py")
    except (console_lib.SettingsError, ValueError, KeyError, OSError) as e:
        print("Not applied: %s" % e)
        return 1
    if not rec["changed"]:
        print("Nothing to change: %s already has these values." % req["file"])
        return 0
    for c in rec["changed"]:
        print("%s: %s -> %s" % (c["path"], c["old"], c["new"]))
    print("Backup: console/history/backups/%s" % rec["backup"])
    if rec.get("frozen_input"):
        print("Note: this file is an input of the frozen FM2 predictions. The predictions stay frozen; the integrity check will show the input as changed.")
    print("Rerun: %s (see console/settings_schema.json run_targets, or python run_all.py --skip-sim)" % ", ".join(rec["suggested_runs"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
