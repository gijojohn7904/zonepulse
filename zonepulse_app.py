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
uploaded_file = st.file_uploader("🔕️ Upload your DE Order vs Login File", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.upper()

    required_cols = [col for col in df.columns if "LH_" in col or "FD_" in col]
    if len(required_cols) == 0:
        st.error("❌ Your CSV must contain hourly login/order columns like LH_00, FD_01 etc.")
        st.stop()

    df["VERTICAL"] = df["DE_SHIFT"].apply(lambda x: "Instamart" if any(tag in str(x).upper() for tag in ["IM", "DDE"]) else "SwiggyFood")

    vertical = st.selectbox("🔃 Choose Vertical", ["SwiggyFood", "Instamart"])
    df = df[df["VERTICAL"] == vertical]

    if "CITY" in df.columns:
        cities = df["CITY"].dropna().unique()
        selected_city = st.selectbox("🏩 Choose City", sorted(cities))
        df = df[df["CITY"] == selected_city]
    else:
        st.error("❌ 'CITY' column missing.")
        st.stop()

    if "ZONE" in df.columns:
        zones = sorted(df["ZONE"].dropna().unique())
        selected_zone = st.selectbox("📍 Choose Zone", ["All"] + zones)
        if selected_zone != "All":
            df = df[df["ZONE"] == selected_zone]
    else:
        st.error("❌ 'ZONE' column missing.")
        st.stop()

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
                Avg_Orders=(fd_col, 'mean'),
                Avg_Login_Mins=(lh_col, 'mean'),
                Active_DEs=(lh_col, lambda x: (x > 10).sum())
            ).reset_index()

            zone_group["Hour"] = hr
            zone_group["Idle Ratio"] = zone_group.apply(
                lambda row: (row["Avg_Login_Mins"] / (row["Avg_Orders"] * 20)) if row["Avg_Orders"] > 0 else np.nan,
                axis=1)
            hourly_data.append(zone_group)

    if hourly_data:
        zone_hour_df = pd.concat(hourly_data)

        with st.expander("ℹ️ Column Logic Explanation"):
            st.markdown("""
            - **Avg Orders**: Average orders per DE in that hour (only for DEs logged in during that hour)
            - **Avg Login Mins**: Average login minutes of DEs who were active that hour
            - **Active DEs**: Number of DEs who logged in > 10 mins in that hour
            - **Idle Ratio**: Avg Login Mins ÷ (Avg Orders × 20). Higher means low efficiency.
            """)

        st.markdown("## 📊 Zone-Level Hourly Report")
        st.dataframe(zone_hour_df.sort_values(by=["ZONE", "Hour"]))

        st.markdown("## ⚠️ Potential Churn Risk DEs (Login > 3hr, Orders < 2)")
        churn_df = df[(df["TOTAL LOGIN MINS"] >= 180) & (df["TOTAL ORDERS"] < 2)]
        churn_df["Login Hours"] = (churn_df["TOTAL LOGIN MINS"] / 60).round(2)

        if churn_df.empty:
            st.info("✅ No churn risk DEs found for the selected filters.")
        else:
            churn_cols = ["DE_ID", "DE_NAME", "ZONE", "DT", "WEEK", "Login Hours", "TOTAL ORDERS"]
            if "REJECTED_ORDERS" in df.columns: churn_cols.append("REJECTED_ORDERS")
            if "DAILY_EARNINGS" in df.columns: churn_cols.append("DAILY_EARNINGS")

            st.dataframe(churn_df[churn_cols].sort_values(by=["ZONE", "DT", "DE_NAME"]))
            st.download_button("🔕 Download Churn Risk Report (CSV)", data=churn_df[churn_cols].to_csv(index=False), file_name="churn_risk_DEs.csv", mime="text/csv")

        st.markdown("## 🚨 Stress Hours (High Orders, Low Login)")
        stress_df = zone_hour_df[(zone_hour_df["Avg_Orders"] > 2) & (zone_hour_df["Avg_Login_Mins"] < 20)]
        st.dataframe(stress_df.sort_values(by="Hour"))
        st.download_button("🔕 Download Zone Report", zone_hour_df.to_csv(index=False), file_name="zonepulse_hourly.csv")

        st.markdown("## 🏍️ Individual DE-wise View")

        if "DE_ID" in df.columns:
            de_ids = df["DE_ID"].dropna().astype(str).unique()
            selected_de = st.selectbox("😮 Choose DE ID to Explore", ["None"] + sorted(de_ids))
            selected_de_flag = selected_de != "None"
        else:
            st.error("❌ 'DE_ID' column missing.")
            st.stop()

        if selected_de_flag:
            de_data = df[df["DE_ID"].astype(str) == selected_de].copy()
            st.markdown(f"### DE: `{selected_de}` – {de_data['DE_NAME'].iloc[0]}")
            st.markdown(f"**📍 Zone:** {de_data['ZONE'].iloc[0]}  |  🏣️ **City:** {de_data['CITY'].iloc[0]}")

            total_days = de_data.shape[0]
            total_login = de_data["TOTAL LOGIN MINS"].sum()
            total_orders = de_data["TOTAL ORDERS"].sum()
            avg_orders_per_hour = round(total_orders / (total_login / 60), 2) if total_login > 0 else 0
            idle_ratio = round(total_login / (total_orders * 20), 2) if total_orders > 0 else np.nan
            total_rejected = de_data["REJECTED_ORDERS"].sum() if "REJECTED_ORDERS" in de_data.columns else 0
            total_earnings = de_data["DAILY_EARNINGS"].sum() if "DAILY_EARNINGS" in de_data.columns else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("🔕️ Active Days", total_days)
            col2.metric("⏱️ Total Login Hrs", round(total_login / 60, 1))
            col3.metric("🔵️ Total Orders", int(total_orders))
            col4.metric("⚖️ Idle Ratio", idle_ratio if not np.isnan(idle_ratio) else "∞")

            col5, col6 = st.columns(2)
            col5.metric("⛔ Rejected Orders", int(total_rejected))
            col6.metric("💸 Total Earnings", f"₹{round(total_earnings, 2)}")

            trend_df = de_data[["DT", "TOTAL LOGIN MINS", "TOTAL ORDERS"]].copy()
            trend_df["DT"] = pd.to_datetime(trend_df["DT"])
            trend_chart = alt.Chart(trend_df.melt("DT")).mark_line(point=True).encode(
                x="DT:T", y="value:Q", color="variable:N"
            ).properties(title="Login Mins vs Orders – Daily")
            st.altair_chart(trend_chart, use_container_width=True)

            if not de_data.empty and all(col in de_data.columns for col in ["DT", "WEEK", "TOTAL LOGIN MINS", "TOTAL ORDERS"]):
                week_summary = de_data.groupby("WEEK")[["TOTAL LOGIN MINS", "TOTAL ORDERS"]].sum().reset_index()
                if "REJECTED_ORDERS" in de_data.columns:
                    week_summary["REJECTED_ORDERS"] = de_data.groupby("WEEK")["REJECTED_ORDERS"].sum().values
                if "DAILY_EARNINGS" in de_data.columns:
                    week_summary["DAILY_EARNINGS"] = de_data.groupby("WEEK")["DAILY_EARNINGS"].sum().values
                week_summary["Total Login Hrs"] = week_summary["TOTAL LOGIN MINS"] / 60

                metrics_to_plot = {
                    "Total Login Hrs": "Total Login Hours",
                    "TOTAL ORDERS": "Total Orders",
                }
                if "REJECTED_ORDERS" in week_summary.columns:
                    metrics_to_plot["REJECTED_ORDERS"] = "Rejected Orders"
                if "DAILY_EARNINGS" in week_summary.columns:
                    metrics_to_plot["DAILY_EARNINGS"] = "Daily Earnings (₹)"

                metric_keys = list(metrics_to_plot.keys())
                colors = ["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"]
                for i in range(0, len(metric_keys), 2):
                    cols = st.columns(2)
                    for j in range(2):
                        if i + j < len(metric_keys):
                            key = metric_keys[i + j]
                            title = metrics_to_plot[key]
                            color = colors[(i + j) % len(colors)]
                            chart = alt.Chart(week_summary).mark_bar(color=color).encode(
                                x=alt.X("WEEK:N", title="Week"),
                                y=alt.Y(f"{key}:Q", title=title),
                                tooltip=["WEEK", key]
                            ).properties(title=title).configure_legend(orient="top")
                            cols[j].altair_chart(chart, use_container_width=True)

                breakdown = de_data[["DT", "WEEK", "TOTAL LOGIN MINS", "TOTAL ORDERS"]].copy()
                if "REJECTED_ORDERS" in de_data.columns:
                    breakdown["REJECTED_ORDERS"] = de_data["REJECTED_ORDERS"]
                if "DAILY_EARNINGS" in de_data.columns:
                    breakdown["DAILY_EARNINGS"] = de_data["DAILY_EARNINGS"]
                breakdown["Idle Ratio"] = breakdown.apply(
                    lambda row: round(row["TOTAL LOGIN MINS"] / (row["TOTAL ORDERS"] * 20), 2) if row["TOTAL ORDERS"] > 0 else "∞", axis=1)
                st.markdown("### 🗓️ Daily Breakdown")
                st.dataframe(breakdown.sort_values(by="DT"))
            else:
                st.info("No data available for this DE.")
        else:
            st.info("ℹ️ Select a DE from the filter above to view detailed insights.")
else:
    st.info("👆 Upload your DE Order vs Login File to get started.")
