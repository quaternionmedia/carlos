"""Repo-root conftest.

Its only job is putting the repository root on `sys.path`, so a walkthrough
page collected by doctest can `import walkthrough.support` and `from src import
catalogue` the same way the tests do.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
