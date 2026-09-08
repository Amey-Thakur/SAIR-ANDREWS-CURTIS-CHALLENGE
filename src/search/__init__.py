# ==============================================================================
# File: __init__.py
# Description: Search over move sequences. Kept apart from the moves so that a
#   bad heuristic can only fail to find a path, never invent one.
# Usage: from src.search.best_first import best_first
# Tech Stack: Python 3.10+
# ==============================================================================

__all__ = ["best_first"]
