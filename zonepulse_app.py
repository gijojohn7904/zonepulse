import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# Page config
st.set_page_config(page_title="ZonePulse – DE Supply Efficiency Monitor", layout="wide")

# Confidentiality Notice
st.markdown("""
<div style='background-color:#fff3cd;padding:15px;border-radius:5px;border:1px solid #ffeeba;margin-bottom:25px;'>
<b>⚠️ Confidentiality Notice by Swiggy:</b><br>
This dashboard is built using internal company data and is intended <b>strictly for internal use only</b>.<br>
Sharing, reproducing, or distributing this content outside the organization is <b>not permitted</b>.<br>
Please handle this information responsibly, in accordance with company data policies.
</div>
""", unsafe_allow_html=True)

# Banner
st.markdown("""
# 🚦 Fleet Efficiency & Attrition Risk Monitor | Swiggy
Track DE login vs orders. Fix idle time, prevent attrition, and balance demand-supply across zones.
""")

# File uploader
uploaded_file = st.file_uploader("🔕️ Upload your DE Order vs Login File", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.upper()

    required_cols = [col for col in df.columns if "LH_" in col or "FD_" in col]
    if len(required_cols) == 0:
        st.error("❌ Your CSV must contain hourly login/order columns like LH_00, FD_01 etc.")
        st.stop()

    df["VERTICAL"] = df["DE_SHIFT"].apply(lambda x: "Instamart" if any(tag in str(x).upper() for tag in ["IM", "DDE"]) else "SwiggyFood")

    # 🔄 Two filters per row
    col1, col2 = st.columns(2)
    with col1:
        vertical = st.selectbox("🔃 Choose Vertical", ["SwiggyFood", "Instamart"])
        df = df[df["VERTICAL"] == vertical]

    with col2:
        if "CITY" in df.columns:
            cities = df["CITY"].dropna().unique()
            selected_city = st.selectbox("🏩 Choose City", sorted(cities))
            df = df[df["CITY"] == selected_city]
        else:
            st.error("❌ 'CITY' column missing.")
            st.stop()

    col3, col4 = st.columns(2)
    with col3:
        if "ZONE" in df.columns:
            zones = sorted(df["ZONE"].dropna().unique())
            selected_zone = st.selectbox("📍 Choose Zone", ["All"] + zones)
            if selected_zone != "All":
                df = df[df["ZONE"] == selected_zone]
        else:
            st.error("❌ 'ZONE' column missing.")
            st.stop()

    with col4:
        if "DT" in df.columns:
            df["DT"] = pd.to_datetime(df["DT"]).dt.date
            min_date, max_date = df["DT"].min(), df["DT"].max()
            selected_dates = st.date_input("🗓️ Filter by Date Range", [min_date, max_date])
            if len(selected_dates) == 2:
                df = df[(df["DT"] >= selected_dates[0]) & (df["DT"] <= selected_dates[1])]

    df["TOTAL LOGIN MINS"] = df[[f"LH_{str(i).zfill(2)}" for i in range(24) if f"LH_{str(i).zfill(2)}" in df.columns]].sum(axis=1)
    df["TOTAL ORDERS"] = df[[f"FD_{str(i).zfill(2)}" for i in range(24) if f"FD_{str(i).zfill(2)}" in df.columns]].sum(axis=1)

    hourly_data = []
    for hr in range(24):
        fd_col = f"FD_{str(hr).zfill(2)}"
        lh_col = f"LH_{str(hr).zfill(2)}"

        if fd_col in df.columns and lh_col in df.columns:
            hour_df = df[df[lh_col] > 10]
            if hour_df.empty:
                continue

            zone_group = hour_df.groupby("ZONE").agg(
                Total_Orders=(fd_col, 'sum'),
                Avg_Login_Mins=(lh_col, 'mean'),
                Active_DEs=(lh_col, lambda x: (x > 10).sum())
            ).reset_index()

            zone_group["Hour"] = hr
            zone_group["Orders_per_DE"] = zone_group.apply(
                lambda row: row["Total_Orders"] / row["Active_DEs"] if row["Active_DEs"] > 0 else 0,
                axis=1
            )
            zone_group["Login_Utilization_%"] = zone_group.apply(
                lambda row: min(100, ((row["Total_Orders"] * 25) / (row["Avg_Login_Mins"] * row["Active_DEs"])) * 100)
                if row["Avg_Login_Mins"] > 0 and row["Active_DEs"] > 0 else 0,
                axis=1
            )

            if vertical == "Instamart":
                zone_group["Recommendation"] = zone_group.apply(
                    lambda row: "⚠️ Overstaffed" if (row["Login_Utilization_%"] < 30 and row["Orders_per_DE"] < 1.2)
                    else "🔴 Understaffed" if (row["Login_Utilization_%"] > 70 and row["Orders_per_DE"] > 2.2)
                    else "✅ Balanced",
                    axis=1
                )
            else:
                zone_group["Recommendation"] = zone_group.apply(
                    lambda row: "⚠️ Overstaffed" if (row["Login_Utilization_%"] < 25 and row["Orders_per_DE"] < 0.6)
                    else "🔴 Understaffed" if (row["Login_Utilization_%"] > 57 and row["Orders_per_DE"] > 1.5)
                    else "✅ Balanced",
                    axis=1
                )

            hourly_data.append(zone_group)

    if hourly_data:
        zone_hour_df = pd.concat(hourly_data)
        st.markdown("## 📊 Zone-Level Hourly Report")
        st.dataframe(zone_hour_df.sort_values(by=["ZONE", "Hour"]))
