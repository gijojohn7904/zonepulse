# zonepulse_app.py

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="ZonePulse – DE Supply Efficiency Monitor", layout="wide")

st.markdown("""
# 🚦 ZonePulse – DE Supply Efficiency Monitor | Powered by Claude Sonnet 4
Track delivery executive efficiency, prevent idle-time churn, and balance supply vs demand in real-time across Instamart and SwiggyFood.
""")

uploaded_file = st.file_uploader("📥 Upload your DE CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Classify DE vertical
    df["Vertical"] = df["DE_SHIFT"].apply(lambda x: "Instamart" if any(k in str(x).upper() for k in ["IM", "DDE"]) else "SwiggyFood")

    # Vertical filter
    vertical = st.selectbox("Choose vertical", ["SwiggyFood", "Instamart"])
    df = df[df["Vertical"] == vertical]

    # City filter
    cities = df["City"].dropna().unique()
    selected_city = st.selectbox("Choose City", sorted(cities))
    df = df[df["City"] == selected_city]

    # Total login and order summary
    df["Total Login Mins"] = df[[f"LH_{str(i).zfill(2)}" for i in range(24)]].sum(axis=1)
    df["Total Orders"] = df[[f"FD_{str(i).zfill(2)}" for i in range(24)]].sum(axis=1)

    # Hourly zone-level metrics
    hourly_data = []
    for hr in range(24):
        fd_col = f"FD_{str(hr).zfill(2)}"
        lh_col = f"LH_{str(hr).zfill(2)}"

        grouped = df.groupby("Zone")[[fd_col, lh_col]].mean().reset_index()
        grouped["Hour"] = hr
        grouped.rename(columns={fd_col: "Avg Orders", lh_col: "Avg Login Mins"}, inplace=True)
        grouped["Idle Ratio"] = grouped.apply(
            lambda row: (row["Avg Login Mins"] / (row["Avg Orders"] * 60)) if row["Avg Orders"] > 0 else np.nan, axis=1)
        hourly_data.append(grouped)

    zone_hour_df = pd.concat(hourly_data)

    st.markdown("## 🧭 Zone-Level Hourly Balance Report")
    st.dataframe(zone_hour_df.sort_values(by=["Zone", "Hour"]))

    st.markdown("## ⚠️ DEs at Churn Risk (Logged in > 3 hours, Orders < 2)")
    churn_df = df[(df["Total Login Mins"] >= 180) & (df["Total Orders"] < 2)]
    st.dataframe(churn_df[["DE Name", "Zone", "Total Login Mins", "Total Orders"]])

    st.markdown("## 📈 Demand Stress Report (High Orders, Low Login)")
    stress_zones = zone_hour_df[(zone_hour_df["Avg Orders"] > 2) & (zone_hour_df["Avg Login Mins"] < 20)]
    st.dataframe(stress_zones.sort_values(by="Hour"))

    st.download_button("📥 Download Zone-Level Report", zone_hour_df.to_csv(index=False), file_name="zonepulse_hourly_report.csv")

else:
    st.info("Please upload a Swiggy DE CSV file to begin analysis.")
