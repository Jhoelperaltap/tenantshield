"""Pytest configuration: add example directory to sys.path.

The CLI example is organized as a flat directory (NOT a Python
package). This conftest adds the example directory to ``sys.path``
so tests can import ``cli``, ``seed``, and ``models`` modules.
"""

from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLE_DIR = Path(__file__).parent
if str(_EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLE_DIR))
