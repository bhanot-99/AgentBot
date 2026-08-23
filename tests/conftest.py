import os
import sys
from pathlib import Path

# Tests import "app.*" as an absolute package; make the repo root importable regardless of
# whether pytest is invoked as "pytest" or "python -m pytest" (their sys.path defaults differ).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# app.config fails fast if GEMINI_API_KEY is unset (rules.md P0 exit gate) — importing
# app.main to build a TestClient triggers that check even in Tier 1 tests. A syntactically
# present dummy value satisfies startup validation; FakeLLMClient (tests/fakes.py) guarantees
# no real network call is ever made, which is what rules.md T1 actually protects against.
os.environ.setdefault("GEMINI_API_KEY", "test-dummy-not-a-real-key")
