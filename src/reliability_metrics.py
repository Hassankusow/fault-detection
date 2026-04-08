"""
reliability_metrics.py
Runs SQL-based MTBF/MTTR analysis and saves results.
"""

import sqlite3
import pandas as pd
from pathlib import Path


def compute_metrics(db_path: Path) -> pd.DataFrame:
    sql = Path("sql/mtbf_mttr.sql").read_text()
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(sql, conn)
    conn.close()

    # flag high-risk equipment (MTBF < 50h or MTTR > 2h)
    df["risk_level"] = "LOW"
    df.loc[(df["mtbf_hours"] < 100) | (df["mttr_hours"] > 1.5), "risk_level"] = "MEDIUM"
    df.loc[(df["mtbf_hours"] < 50)  | (df["mttr_hours"] > 3.0), "risk_level"] = "HIGH"

    conn = sqlite3.connect(db_path)
    df.to_sql("reliability_metrics", conn, if_exists="replace", index=False)
    conn.close()

    print(df.to_string(index=False))
    return df


if __name__ == "__main__":
    compute_metrics(Path("data/equipment.db"))
