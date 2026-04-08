"""
run.py — one-command pipeline
Generates data → parses logs → detects anomalies → computes metrics
"""
import subprocess
import sys
from pathlib import Path

steps = [
    ("Generating synthetic logs",  ["python3", "src/generate_logs.py"]),
    ("Parsing log files",          ["python3", "src/parse_logs.py"]),
    ("Running anomaly detection",  ["python3", "src/anomaly_detection.py"]),
    ("Computing MTBF/MTTR",        ["python3", "src/reliability_metrics.py"]),
]

for label, cmd in steps:
    print(f"\n{'─'*50}\n▶  {label}\n{'─'*50}")
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"✗ Failed at: {label}")
        sys.exit(1)

print("\n✓ Pipeline complete. Run the dashboard with:")
print("  streamlit run src/dashboard.py")
