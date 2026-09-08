# ==============================================================================
# File: conftest.py
# Description: Puts the repository root on the import path so that `src`
#   resolves the same way it does for `python -m src.harness.check_solution`.
# Usage: python -m pytest tests -q
# Tech Stack: Python 3.10+, pytest
# ==============================================================================

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
