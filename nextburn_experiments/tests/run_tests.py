"""Tiny test runner for machines without pytest. Exit code 1 when any test fails (use it as a deploy gate)."""
import glob
import importlib.util
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
failed = passed = 0
for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
    spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in sorted(n for n in dir(mod) if n.startswith("test_")):
        try:
            getattr(mod, name)()
            passed += 1
            print("PASS", name)
        except Exception:  # noqa: BLE001
            failed += 1
            print("FAIL", name)
            traceback.print_exc(limit=2)
print("%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
