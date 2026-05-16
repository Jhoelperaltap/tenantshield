"""Pytest configuration: add example directory to sys.path.

The FastAPI example is organized as a flat directory (NOT a Python
package) to avoid name conflicts with the external ``fastapi`` package.
This conftest adds the example directory to ``sys.path`` so tests can
import ``app`` and ``models`` modules.
"""

from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLE_DIR = Path(__file__).parent
if str(_EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLE_DIR))
