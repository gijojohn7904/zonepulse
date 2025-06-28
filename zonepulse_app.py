import streamlit as st
import pandas as pd
import numpy as np

# Page config
st.set_page_config(page_title="ZonePulse – DE Supply Efficiency Monitor", layout="wide")

# Banner
st.markdown("""
# 🚦 ZonePulse – DE Supply Efficiency Monitor | Powered by Claude Sonnet 4
Track DE login vs orders. Fix idle time, prevent attrition, and balance demand-supply across zones.
""")

# File uploader
uploaded_file = st.file_uploader("📥 Upload your Swiggy DE CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Check required columns
    required_cols = [col for col in df.columns if "LH_" in col or "FD_" in col]
    if len(required_cols) == 0:
        st.error("❌ Your CSV must contain hourly login/order columns like LH_00, FD_01 etc.")
        st.stop()

    # Add vertical label
    df["Vertical"] = df["DE_SHIFT"].apply(lambda x: "Instamart" if any(tag in str(x).upper() for tag in ["IM", "DDE"]) else "SwiggyFood")

    # Filter: Vertical
    vertical = st.selectbox("🔃 Choose Vertical", ["SwiggyFood", "Instamart"])
    df = df[df["Vertical"] == vertical]

    # Filter: City
    if "CITY" in df.columns:
        cities = df["CITY"].dropna().unique()
        selected_city = st.selectbox("🏙️ Choose City", sorted(cities))
        df = df[df["CITY"] == selected_city]
    else:
        st.error("❌ 'CITY' column missing.")
        st.stop()

    # Filter: Zone
    if "ZONE" in df.columns:
        zones = df["ZONE"].dropna().unique()
        selected_zone = st.selectbox("📍 Choose Zone", sorted(zones))
        df = df[df["ZONE"] == selected_zone]
    else:
        st.error("❌ 'ZONE' column missing.")
        st.stop()

    # Filter: DE ID
    if "DE_ID" in df.columns:
        de_ids = df["DE_ID"].dropna().astype(str).unique()
        selected_de = st.selectbox("🧍 Choose DE ID (optional)", ["All"] + sorted(de_ids))
        if selected_de != "All":
            df = df[df["DE_ID"].astype(str) == selected_de]
    else:
        st.error("❌ 'DE_ID' column missing.")
        st.stop()

    # Total login and orders
    df["Total Login Mins"] = df[[f"LH_{str(i).zfill(2)}" for i in range(24) if f"LH_{str(i).zfill(2)}" in df.columns]].sum(axis=1)
    df["Total Orders"] = df[[f"FD_{str(i).zfill(2)}" for i in range(24) if f"FD_{str(i).zfill(2)}" in df.columns]].sum(axis=1)

    # Hourly analysis (include DEs with login_minutes > 0)
    hourly_data = []
    for hr in range(24):
        fd_col = f"FD_{str(hr).zfill(2)}"
        lh_col = f"LH_{str(hr).zfill(2)}"

        if fd_col in df.columns and lh_col in df.columns:
            hour_df = df[df[lh_col] > 0]  # only DEs logged in that hour
            if hour_df.empty:
                continue

            zone_group = hour_df.groupby("ZONE")[[fd_col, lh_col]].mean().reset_index()
            zone_group["Hour"] = hr
            zone_group.rename(columns={fd_col: "Avg Orders", lh_col: "Avg Login Mins"}, inplace=True)
            zone_group["Idle Ratio"] = zone_group.apply(
                lambda row: (row["Avg Login Mins"] / (row["Avg Orders"] * 60)) if row["Avg Orders"] > 0 else np.nan,
                axis=1)
            hourly_data.append(zone_group)

    # Display insights
    if hourly_data:
        zone_hour_df = pd.concat(hourly_data)
        st.markdown("## 📊 Zone-Level Hourly Report")
        st.dataframe(zone_hour_df.sort_values(by=["ZONE", "Hour"]))

        # Churn risk DEs
        st.markdown("## ⚠️ Potential Churn Risk DEs (Login > 3hr, Orders < 2)")
        churn_df = df[(df["Total Login Mins"] >= 180) & (df["Total Orders"] < 2)]
        st.dataframe(churn_df[["DE_NAME", "ZONE", "Total Login Mins", "Total Orders"]])

        # Understaffed zones
        st.markdown("## 🚨 Stress Hours (High Orders, Low Login)")
        stress_df = zone_hour_df[(zone_hour_df["Avg Orders"] > 2) & (zone_hour_df["Avg Login Mins"] < 20)]
        st.dataframe(stress_df.sort_values(by="Hour"))

        # Download button
        st.download_button("📥 Download Zone Report", zone_hour_df.to_csv(index=False), file_name="zonepulse_hourly.csv")
    else:
        st.warning("No hourly data (FD_ / LH_) found to compute insights.")
else:
    st.info("👆 Upload your Swiggy DE CSV to get started.")
