import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# Page config
st.set_page_config(page_title="ZonePulse – DE Supply Efficiency Monitor", layout="wide")

# Banner
st.markdown("""
# 🚦 ZonePulse – DE Supply Efficiency Monitor | Powered by Claude Sonnet 4
Track DE login vs orders. Fix idle time, prevent attrition, and balance demand-supply across zones.
""")

# File uploader
uploaded_file = st.file_uploader("📅 Upload your Swiggy DE CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    required_cols = [col for col in df.columns if "LH_" in col or "FD_" in col]
    if len(required_cols) == 0:
        st.error("❌ Your CSV must contain hourly login/order columns like LH_00, FD_01 etc.")
        st.stop()

    df["Vertical"] = df["DE_SHIFT"].apply(lambda x: "Instamart" if any(tag in str(x).upper() for tag in ["IM", "DDE"]) else "SwiggyFood")

    vertical = st.selectbox("🔃 Choose Vertical", ["SwiggyFood", "Instamart"])
    df = df[df["Vertical"] == vertical]

    if "CITY" in df.columns:
        cities = df["CITY"].dropna().unique()
        selected_city = st.selectbox("🏩 Choose City", sorted(cities))
        df = df[df["CITY"] == selected_city]
    else:
        st.error("❌ 'CITY' column missing.")
        st.stop()

    if "ZONE" in df.columns:
        zones = df["ZONE"].dropna().unique()
        selected_zone = st.selectbox("📍 Choose Zone", sorted(zones))
        df = df[df["ZONE"] == selected_zone]
    else:
        st.error("❌ 'ZONE' column missing.")
        st.stop()

    if "DT" in df.columns and "WEEK" in df.columns:
        df["DT"] = pd.to_datetime(df["DT"])
        min_date, max_date = df["DT"].min(), df["DT"].max()
        selected_dates = st.date_input("📆 Filter by Date Range", [min_date, max_date])
        if len(selected_dates) == 2:
            df = df[(df["DT"] >= selected_dates[0]) & (df["DT"] <= selected_dates[1])]

        weeks = sorted(df["WEEK"].dropna().unique())
        selected_weeks = st.multiselect("📅 Filter by Week(s)", weeks, default=weeks)
        df = df[df["WEEK"].isin(selected_weeks)]

    df["Total Login Mins"] = df[[f"LH_{str(i).zfill(2)}" for i in range(24) if f"LH_{str(i).zfill(2)}" in df.columns]].sum(axis=1)
    df["Total Orders"] = df[[f"FD_{str(i).zfill(2)}" for i in range(24) if f"FD_{str(i).zfill(2)}" in df.columns]].sum(axis=1)

    hourly_data = []
    for hr in range(24):
        fd_col = f"FD_{str(hr).zfill(2)}"
        lh_col = f"LH_{str(hr).zfill(2)}"

        if fd_col in df.columns and lh_col in df.columns:
            hour_df = df[df[lh_col] > 0]
            if hour_df.empty:
                continue

            zone_group = hour_df.groupby("ZONE")[[fd_col, lh_col]].mean().reset_index()
            zone_group["Hour"] = hr
            zone_group.rename(columns={fd_col: "Avg Orders", lh_col: "Avg Login Mins"}, inplace=True)
            zone_group["Idle Ratio"] = zone_group.apply(
                lambda row: (row["Avg Login Mins"] / (row["Avg Orders"] * 60)) if row["Avg Orders"] > 0 else np.nan,
                axis=1)
            hourly_data.append(zone_group)

    if hourly_data:
        zone_hour_df = pd.concat(hourly_data)
        st.markdown("## 📊 Zone-Level Hourly Report")
        st.dataframe(zone_hour_df.sort_values(by=["ZONE", "Hour"]))

        st.markdown("## ⚠️ Potential Churn Risk DEs (Login > 3hr, Orders < 2)")
        churn_df = df[(df["Total Login Mins"] >= 180) & (df["Total Orders"] < 2)]

        if churn_df.empty:
            st.info("✅ No churn risk DEs found for the selected filters.")
        else:
            st.dataframe(
                churn_df[["DE_NAME", "ZONE", "DT", "WEEK", "Total Login Mins", "Total Orders"]]
                    .sort_values(by=["ZONE", "DT", "DE_NAME"])
            )

            churn_csv = churn_df[["DE_ID", "DE_NAME", "ZONE", "DT", "WEEK", "Total Login Mins", "Total Orders"]]
            st.download_button(
                label="📅 Download Churn Risk Report (CSV)",
                data=churn_csv.to_csv(index=False),
                file_name="churn_risk_DEs.csv",
                mime="text/csv"
            )

        st.markdown("## 🚨 Stress Hours (High Orders, Low Login)")
        stress_df = zone_hour_df[(zone_hour_df["Avg Orders"] > 2) & (zone_hour_df["Avg Login Mins"] < 20)]
        st.dataframe(stress_df.sort_values(by="Hour"))

        st.download_button("📅 Download Zone Report", zone_hour_df.to_csv(index=False), file_name="zonepulse_hourly.csv")

        # Individual DE-wise View
        st.markdown("## 🤍 Individual DE-wise View")

        if "DE_ID" in df.columns:
            de_ids = df["DE_ID"].dropna().astype(str).unique()
            selected_de = st.selectbox("🧐 Choose DE ID to Explore", ["None"] + sorted(de_ids))
            selected_de_flag = selected_de != "None"
        else:
            st.error("❌ 'DE_ID' column missing.")
            st.stop()

        if selected_de_flag:
            de_data = df[df["DE_ID"].astype(str) == selected_de].copy()
            st.markdown(f"### DE: `{selected_de}` – {de_data['DE_NAME'].iloc[0]}")

            st.markdown(f"**📍 Zone:** {de_data['ZONE'].iloc[0]}  |  🏙️ **City:** {de_data['CITY'].iloc[0]}")

            # Summary stats
            total_days = de_data.shape[0]
            total_login = de_data["Total Login Mins"].sum()
            total_orders = de_data["Total Orders"].sum()
            avg_orders_per_hour = round(total_orders / (total_login / 60), 2) if total_login > 0 else 0
            idle_ratio = round(total_login / (total_orders * 60), 2) if total_orders > 0 else np.nan

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("🗕️ Active Days", total_days)
            col2.metric("⏱️ Total Login Hrs", round(total_login / 60, 1))
            col3.metric("🙵️ Total Orders", int(total_orders))
            col4.metric("⚖️ Idle Ratio", idle_ratio if not np.isnan(idle_ratio) else "∞")

            # Login vs Orders line chart
            trend_df = de_data[["DT", "Total Login Mins", "Total Orders"]].copy()
            trend_df["DT"] = pd.to_datetime(trend_df["DT"])
            trend_chart = alt.Chart(trend_df.melt("DT")).mark_line(point=True).encode(
                x="DT:T",
                y="value:Q",
                color="variable:N"
            ).properties(title="Login Mins vs Orders – Daily")
            st.altair_chart(trend_chart, use_container_width=True)

            # Weekly performance bar chart
            week_summary = de_data.groupby("WEEK")[["Total Login Mins", "Total Orders"]].sum().reset_index()
            week_summary["Total Login Hrs"] = week_summary["Total Login Mins"] / 60
            bar_chart = alt.Chart(week_summary).transform_fold(
                ["Total Login Hrs", "Total Orders"]
            ).mark_bar().encode(
                x="WEEK:N",
                y="value:Q",
                color="key:N",
                column=alt.Column("key:N")
            ).properties(title="Week-on-Week Performance")
            st.altair_chart(bar_chart, use_container_width=True)

            # Daily breakdown table
            breakdown = de_data[["DT", "WEEK", "Total Login Mins", "Total Orders"]].copy()
            breakdown["Idle Ratio"] = breakdown.apply(
                lambda row: round(row["Total Login Mins"] / (row["Total Orders"] * 60), 2) if row["Total Orders"] > 0 else "∞",
                axis=1)
            st.markdown("### 📅 Daily Breakdown")
            st.dataframe(breakdown.sort_values(by="DT"))

        else:
            st.info("ℹ️ Select a DE from the filter above to view detailed insights.")
    else:
        st.warning("No hourly data (FD_ / LH_) found to compute insights.")
else:
    st.info("👆 Upload your Swiggy DE CSV to get started.")
