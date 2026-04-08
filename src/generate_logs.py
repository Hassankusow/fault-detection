"""
generate_logs.py
Generates synthetic equipment telemetry logs simulating
infrastructure sensors (pumps, compressors, HVAC, generators).
"""

import random
import re
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

EQUIPMENT = [
    ("PUMP-01",       "pump"),
    ("PUMP-02",       "pump"),
    ("COMP-01",       "compressor"),
    ("COMP-02",       "compressor"),
    ("HVAC-01",       "hvac"),
    ("GEN-01",        "generator"),
    ("GEN-02",        "generator"),
]

FAULT_CODES = {
    "pump":       ["OVERHEAT", "VIBRATION_HIGH", "FLOW_LOW", "SEAL_LEAK"],
    "compressor": ["PRESSURE_DROP", "OVERHEAT", "OIL_LOW", "VIBRATION_HIGH"],
    "hvac":       ["FILTER_CLOG", "TEMP_DEVIATION", "FAN_FAULT", "REFRIGERANT_LOW"],
    "generator":  ["FUEL_LOW", "VOLTAGE_SPIKE", "OVERHEAT", "START_FAIL"],
}

DOWNSTREAM_SYSTEMS = ["WATER_TREATMENT", "POWER_GRID", "COOLING_LOOP", "VENTILATION"]

LOG_TEMPLATE = (
    "[{ts}] [{level}] EQUIP={equip} TYPE={etype} "
    "TEMP={temp:.1f}C VIBR={vibr:.2f}mm/s PRESSURE={pres:.1f}bar "
    "RUNTIME={runtime}h STATUS={status} FAULT={fault} DOWNSTREAM={ds}"
)

random.seed(42)
np.random.seed(42)


def _inject_anomaly(base_temp, base_vibr, base_pres, degrading: bool):
    if degrading:
        temp  = base_temp  + np.random.normal(18, 4)
        vibr  = base_vibr  + np.random.normal(3.5, 0.8)
        pres  = base_pres  - np.random.normal(1.2, 0.3)
    else:
        temp  = base_temp  + np.random.normal(0, 1.5)
        vibr  = base_vibr  + np.random.normal(0, 0.3)
        pres  = base_pres  + np.random.normal(0, 0.2)
    return round(temp, 1), round(max(vibr, 0), 2), round(max(pres, 0.1), 1)


def generate(days: int = 90, interval_min: int = 15) -> list[dict]:
    records = []
    start = datetime.now() - timedelta(days=days)
    steps = int(days * 24 * 60 / interval_min)

    equipment_state: dict[str, dict] = {}
    for eid, etype in EQUIPMENT:
        equipment_state[eid] = {
            "type": etype,
            "runtime": random.randint(100, 5000),
            "degrading": False,
            "degrade_countdown": 0,
            "last_fault_ts": None,
            "base_temp":  {"pump": 65, "compressor": 78, "hvac": 45, "generator": 80}[etype],
            "base_vibr":  {"pump": 1.2, "compressor": 2.1, "hvac": 0.8, "generator": 1.5}[etype],
            "base_pres":  {"pump": 4.5, "compressor": 7.2, "hvac": 1.1, "generator": 3.0}[etype],
        }

    for step in range(steps):
        ts = start + timedelta(minutes=step * interval_min)

        for eid, state in equipment_state.items():
            etype = state["type"]
            state["runtime"] += interval_min / 60

            # randomly start degradation period
            if not state["degrading"] and random.random() < 0.002:
                state["degrading"] = True
                state["degrade_countdown"] = random.randint(8, 48)

            if state["degrading"]:
                state["degrade_countdown"] -= 1
                if state["degrade_countdown"] <= 0:
                    state["degrading"] = False

            temp, vibr, pres = _inject_anomaly(
                state["base_temp"], state["base_vibr"], state["base_pres"],
                state["degrading"]
            )

            fault = "NONE"
            status = "OK"
            level = "INFO"
            if state["degrading"] and random.random() < 0.35:
                fault = random.choice(FAULT_CODES[etype])
                status = "FAULT"
                level = "ERROR"
                state["last_fault_ts"] = ts
            elif temp > state["base_temp"] + 10 or vibr > state["base_vibr"] + 1.5:
                status = "WARN"
                level = "WARN"

            downstream = random.choice(DOWNSTREAM_SYSTEMS) if status == "FAULT" else "NONE"

            records.append({
                "timestamp":        ts.strftime("%Y-%m-%dT%H:%M:%S"),
                "level":            level,
                "equipment_id":     eid,
                "equipment_type":   etype,
                "temperature_c":    temp,
                "vibration_mm_s":   vibr,
                "pressure_bar":     pres,
                "runtime_hours":    round(state["runtime"], 1),
                "status":           status,
                "fault_code":       fault,
                "downstream_system": downstream,
                "raw_log": LOG_TEMPLATE.format(
                    ts=ts.strftime("%Y-%m-%dT%H:%M:%S"),
                    level=level, equip=eid, etype=etype,
                    temp=temp, vibr=vibr, pres=pres,
                    runtime=round(state["runtime"], 1),
                    status=status, fault=fault, ds=downstream,
                ),
            })

    return records


def save(records: list[dict], out_dir: Path = Path("data")):
    out_dir.mkdir(exist_ok=True)
    df = pd.DataFrame(records)

    # raw log file
    log_path = out_dir / "equipment_logs.txt"
    with open(log_path, "w") as f:
        for r in records:
            f.write(r["raw_log"] + "\n")
    print(f"Wrote {len(records):,} log lines → {log_path}")

    # SQLite
    db_path = out_dir / "equipment.db"
    conn = sqlite3.connect(db_path)
    df.drop(columns=["raw_log"]).to_sql("telemetry", conn, if_exists="replace", index=False)
    conn.close()
    print(f"Wrote SQLite DB → {db_path}")
    return df


if __name__ == "__main__":
    records = generate(days=90)
    save(records)
