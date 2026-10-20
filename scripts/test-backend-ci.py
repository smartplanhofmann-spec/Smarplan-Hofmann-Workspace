"""Run the real backend suite and make failures readable in GitHub annotations."""
from pathlib import Path
import sys
import unittest


def escape(value):
    return str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


if __name__ == "__main__":
    backend = Path(__file__).resolve().parent.parent / "backend"
    suite = unittest.defaultTestLoader.discover(str(backend))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    for test, traceback in result.errors + result.failures:
        print("::error title=" + escape(test.id()) + "::" + escape(traceback), flush=True)
    if not result.testsRun:
        print("::error::No backend tests were discovered", flush=True)
    sys.exit(0 if result.testsRun and result.wasSuccessful() else 1)
