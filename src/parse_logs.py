"""
parse_logs.py
Parses raw equipment log files using regex and loads structured
records into SQLite for downstream SQL analysis.
"""

import re
import sqlite3
from pathlib import Path
from datetime import datetime

LOG_PATTERN = re.compile(
    r"\[(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\]"
    r"\s+\[(?P<level>\w+)\]"
    r"\s+EQUIP=(?P<equipment_id>\S+)"
    r"\s+TYPE=(?P<equipment_type>\S+)"
    r"\s+TEMP=(?P<temperature_c>[\d.]+)C"
    r"\s+VIBR=(?P<vibration_mm_s>[\d.]+)mm/s"
    r"\s+PRESSURE=(?P<pressure_bar>[\d.]+)bar"
    r"\s+RUNTIME=(?P<runtime_hours>[\d.]+)h"
    r"\s+STATUS=(?P<status>\w+)"
    r"\s+FAULT=(?P<fault_code>\S+)"
    r"\s+DOWNSTREAM=(?P<downstream_system>\S+)"
)


def parse_log_file(path: Path) -> list[dict]:
    records = []
    unmatched = 0
    with open(path) as f:
        for line in f:
            m = LOG_PATTERN.match(line.strip())
            if m:
                r = m.groupdict()
                r["temperature_c"]  = float(r["temperature_c"])
                r["vibration_mm_s"] = float(r["vibration_mm_s"])
                r["pressure_bar"]   = float(r["pressure_bar"])
                r["runtime_hours"]  = float(r["runtime_hours"])
                records.append(r)
            else:
                unmatched += 1

    print(f"Parsed {len(records):,} records | {unmatched} unmatched lines")
    return records


def load_to_db(records: list[dict], db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS parsed_telemetry")
    conn.execute("""
        CREATE TABLE parsed_telemetry (
            timestamp        TEXT,
            level            TEXT,
            equipment_id     TEXT,
            equipment_type   TEXT,
            temperature_c    REAL,
            vibration_mm_s   REAL,
            pressure_bar     REAL,
            runtime_hours    REAL,
            status           TEXT,
            fault_code       TEXT,
            downstream_system TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO parsed_telemetry VALUES "
        "(:timestamp,:level,:equipment_id,:equipment_type,"
        ":temperature_c,:vibration_mm_s,:pressure_bar,:runtime_hours,"
        ":status,:fault_code,:downstream_system)",
        records,
    )
    conn.commit()
    conn.close()
    print(f"Loaded {len(records):,} rows into parsed_telemetry")


if __name__ == "__main__":
    log_path = Path("data/equipment_logs.txt")
    db_path  = Path("data/equipment.db")
    records  = parse_log_file(log_path)
    load_to_db(records, db_path)
