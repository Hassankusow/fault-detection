"""
anomaly_detection.py
Flags equipment degradation using:
  - Rolling Z-score  (detects gradual drift)
  - IQR method       (detects sharp outliers)
"""

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

WINDOW      = 20    # rolling window (observations)
Z_THRESHOLD = 2.5   # flag if |z| > this
IQR_MULT    = 1.5   # standard IQR fence


def load_telemetry(db_path: Path) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM parsed_telemetry ORDER BY equipment_id, timestamp", conn)
    conn.close()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def rolling_zscore(series: pd.Series, window: int = WINDOW) -> pd.Series:
    roll = series.rolling(window, min_periods=3)
    return (series - roll.mean()) / roll.std().replace(0, np.nan)


def iqr_flag(series: pd.Series, mult: float = IQR_MULT) -> pd.Series:
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    return (series < q1 - mult * iqr) | (series > q3 + mult * iqr)


def detect(df: pd.DataFrame) -> pd.DataFrame:
    results = []
    for eid, grp in df.groupby("equipment_id"):
        grp = grp.sort_values("timestamp").copy()

        for col in ["temperature_c", "vibration_mm_s", "pressure_bar"]:
            grp[f"zscore_{col}"]   = rolling_zscore(grp[col])
            grp[f"iqr_flag_{col}"] = iqr_flag(grp[col])

        grp["anomaly_zscore"] = (
            (grp["zscore_temperature_c"].abs()  > Z_THRESHOLD) |
            (grp["zscore_vibration_mm_s"].abs() > Z_THRESHOLD) |
            (grp["zscore_pressure_bar"].abs()   > Z_THRESHOLD)
        )
        grp["anomaly_iqr"] = (
            grp["iqr_flag_temperature_c"] |
            grp["iqr_flag_vibration_mm_s"] |
            grp["iqr_flag_pressure_bar"]
        )
        grp["anomaly"] = grp["anomaly_zscore"] | grp["anomaly_iqr"]

        # health score: 100 = perfect, degrades with anomalies
        window_anomaly = grp["anomaly"].rolling(WINDOW, min_periods=1).mean()
        grp["health_score"] = ((1 - window_anomaly) * 100).round(1)

        results.append(grp)

    return pd.concat(results).reset_index(drop=True)


def save_anomalies(df: pd.DataFrame, db_path: Path):
    cols = [
        "timestamp", "equipment_id", "equipment_type",
        "temperature_c", "vibration_mm_s", "pressure_bar",
        "status", "fault_code", "downstream_system",
        "anomaly_zscore", "anomaly_iqr", "anomaly", "health_score",
    ]
    conn = sqlite3.connect(db_path)
    df[cols].to_sql("anomaly_results", conn, if_exists="replace", index=False)
    conn.close()

    total    = len(df)
    flagged  = df["anomaly"].sum()
    print(f"Anomaly detection complete: {flagged:,} / {total:,} flagged ({flagged/total*100:.1f}%)")


if __name__ == "__main__":
    db_path = Path("data/equipment.db")
    df      = load_telemetry(db_path)
    df      = detect(df)
    save_anomalies(df, db_path)
