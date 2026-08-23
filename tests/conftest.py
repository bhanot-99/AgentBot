import sys
from pathlib import Path

# Tests import "app.*" as an absolute package; make the repo root importable regardless of
# whether pytest is invoked as "pytest" or "python -m pytest" (their sys.path defaults differ).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
