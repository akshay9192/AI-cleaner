"""Run AI-cleaner directly from this source checkout.

This small wrapper and the installed ``ai-cleaner`` command use the same package implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = PROJECT_ROOT / "src" / "ai_cleaner"

if __name__ == "ai_cleaner":
    # A root script shares the package's name. Acting as a tiny package shim prevents it from
    # shadowing ``src/ai_cleaner`` when tools import from the repository root.
    __path__ = [str(PACKAGE_ROOT)]
    __version__ = "0.1.0"
else:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from ai_cleaner.cli import main

    raise SystemExit(main())
