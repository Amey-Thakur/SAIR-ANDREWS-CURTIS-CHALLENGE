# ==============================================================================
# File: __init__.py
# Description: The submission side. Nothing is imported here because
#   check_solution runs as `python -m`, and a package that pulls the module in
#   first has it loaded twice under two names.
# Usage: from src.harness.check_solution import check
# Tech Stack: Python 3.10+
# ==============================================================================

__all__ = ["check_solution"]
