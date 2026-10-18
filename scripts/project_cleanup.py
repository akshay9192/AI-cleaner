"""Repository entry point for AI-cleaner.

This wrapper uses the checkout's ``src`` tree. It is not a standalone copy of AI-cleaner.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ai_cleaner.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
