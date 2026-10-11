"""Reproduce every dataset in output/ from scratch.

    python run_all.py            # uses cached raw downloads in data/raw/
    python run_all.py --refresh  # re-download all market data first
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
STEPS = ["fetch.py", "compute.py", "features_model.py", "build_outputs.py", "build_training_table.py", "train_model.py", "export_models.py",
         "market_features.py", "event_responses.py", "build_training_v2.py", "pattern_library.py", "summarize.py"]

if __name__ == "__main__":
    for step in STEPS:
        args = [sys.executable, str(HERE / "pipeline" / step)]
        if step == "fetch.py" and "--refresh" in sys.argv:
            args.append("--refresh")
        print(f"== {step}")
        subprocess.run(args, check=True, cwd=HERE)
