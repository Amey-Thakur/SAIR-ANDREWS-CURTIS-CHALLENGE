# ==============================================================================
# File: __init__.py
# Description: The Andrews-Curtis moves and the objects they act on. This is the
#   only part of the repository whose correctness a submitted move sequence
#   depends on.
# Usage: from src.ac import Presentation, verify
# Tech Stack: Python 3.10+
# ==============================================================================

from .moves import (Conjugate, Destabilize, IllegalMove, Invert, Multiply,
                    Stabilize, apply, neighbours)
from .presentation import AK, EMPTY, Presentation, presentation, trivial
from .verify import Result, verify

__all__ = ["AK", "Conjugate", "Destabilize", "EMPTY", "IllegalMove", "Invert",
           "Multiply", "Presentation", "Result", "Stabilize", "apply",
           "neighbours", "presentation", "trivial", "verify"]
