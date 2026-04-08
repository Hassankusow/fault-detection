"""
dashboard.py  —  Streamlit dashboard
Equipment Health Monitor: anomaly detection, MTBF/MTTR, fault trends
"""

import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

DB = Path("data/equipment.db")

st.set_page_config(
    page_title="Equipment Health Monitor",
    page_icon="⚙️",
    layout="wide",
)

RISK_COLOR = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#22c55e"}


@st.cache_data(ttl=60)
def load(table: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB)
    df = pd.read_sql(f"SELECT * FROM {table}", conn)
    conn.close()
    return df


# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚙️ Equipment Health Monitor")
st.caption("Real-time fault detection · Rolling Z-score & IQR · MTBF/MTTR Analytics")

# ── Load data ─────────────────────────────────────────────────────────────────
anomalies  = load("anomaly_results")
metrics    = load("reliability_metrics")
telemetry  = load("parsed_telemetry")

anomalies["timestamp"] = pd.to_datetime(anomalies["timestamp"])
telemetry["timestamp"] = pd.to_datetime(telemetry["timestamp"])

# ── KPI row ───────────────────────────────────────────────────────────────────
total_eq   = metrics["equipment_id"].nunique()
high_risk  = (metrics["risk_level"] == "HIGH").sum()
avg_health = anomalies.groupby("equipment_id")["health_score"].last().mean()
total_faults = (telemetry["status"] == "FAULT").sum()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Equipment Units",   total_eq)
k2.metric("High Risk Units",   int(high_risk),  delta=f"{high_risk} need attention", delta_color="inverse")
k3.metric("Avg Health Score",  f"{avg_health:.1f}%")
k4.metric("Total Fault Events", f"{total_faults:,}")

st.divider()

# ── Layout ────────────────────────────────────────────────────────────────────
left, right = st.columns([1.4, 1])

# Health scores per equipment
with left:
    st.subheader("Health Score Over Time")
    eq_sel = st.multiselect(
        "Select equipment",
        options=sorted(anomalies["equipment_id"].unique()),
        default=sorted(anomalies["equipment_id"].unique())[:3],
    )
    if eq_sel:
        subset = anomalies[anomalies["equipment_id"].isin(eq_sel)]
        fig = px.line(
            subset, x="timestamp", y="health_score",
            color="equipment_id", line_shape="spline",
            labels={"health_score": "Health Score", "timestamp": ""},
            color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig.add_hline(y=70, line_dash="dash", line_color="orange", annotation_text="Warning threshold")
        fig.add_hline(y=50, line_dash="dash", line_color="red",    annotation_text="Critical threshold")
        fig.update_layout(height=350, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

# MTBF / MTTR table
with right:
    st.subheader("Reliability Metrics (MTBF / MTTR)")
    display = metrics[["equipment_id", "equipment_type", "mtbf_hours", "mttr_hours",
                        "fault_count", "downstream_systems_impacted", "risk_level"]].copy()
    display.columns = ["ID", "Type", "MTBF (h)", "MTTR (h)", "Faults", "Downstream", "Risk"]

    def color_risk(val):
        return f"color: {RISK_COLOR.get(val, 'white')}; font-weight: bold"

    st.dataframe(
        display.style.applymap(color_risk, subset=["Risk"]),
        use_container_width=True, height=350,
    )

st.divider()

# ── Fault breakdown ───────────────────────────────────────────────────────────
b1, b2 = st.columns(2)

with b1:
    st.subheader("Fault Frequency by Equipment")
    fault_df = (
        telemetry[telemetry["fault_code"] != "NONE"]
        .groupby(["equipment_id", "fault_code"])
        .size().reset_index(name="count")
    )
    fig2 = px.bar(
        fault_df, x="equipment_id", y="count", color="fault_code",
        barmode="stack",
        labels={"count": "Fault Events", "equipment_id": ""},
        color_discrete_sequence=px.colors.qualitative.Pastel,
    )
    fig2.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig2, use_container_width=True)

with b2:
    st.subheader("Downstream System Impact")
    ds_df = (
        telemetry[telemetry["downstream_system"] != "NONE"]
        .groupby("downstream_system")
        .size().reset_index(name="faults")
    )
    fig3 = px.pie(
        ds_df, names="downstream_system", values="faults",
        hole=0.45,
        color_discrete_sequence=px.colors.qualitative.Bold,
    )
    fig3.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig3, use_container_width=True)

st.divider()

# ── Anomaly table ─────────────────────────────────────────────────────────────
st.subheader("Recent Anomalies")
recent = (
    anomalies[anomalies["anomaly"]]
    .sort_values("timestamp", ascending=False)
    .head(50)[["timestamp","equipment_id","equipment_type",
               "temperature_c","vibration_mm_s","pressure_bar",
               "fault_code","downstream_system","health_score"]]
)
st.dataframe(recent, use_container_width=True)
