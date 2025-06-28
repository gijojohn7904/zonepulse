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
            zone_group["Orders_per_Hour"] = zone_group.apply(
                lambda row: row["Avg_Orders"] / (row["Avg_Login_Mins"] / 60) if row["Avg_Login_Mins"] > 0 else np.nan,
                axis=1)
            zone_group["Login_Utilization_%"] = zone_group.apply(
                lambda row: min(100, (row["Avg_Orders"] * 20 / row["Avg_Login_Mins"]) * 100) if row["Avg_Login_Mins"] > 0 else 0,
                axis=1)
            hourly_data.append(zone_group)

    if hourly_data:
        zone_hour_df = pd.concat(hourly_data)

        st.markdown("## 📊 Zone-Level Hourly Report")
        st.dataframe(zone_hour_df.sort_values(by=["ZONE", "Hour"]))

        st.markdown("## ⚠️ Potential Churn Risk DEs (Login > 3hr, Orders < 2)")
        churn_df = df[(df["TOTAL LOGIN MINS"] >= 180) & (df["TOTAL ORDERS"] < 2)]
        churn_df["Login Hours"] = (churn_df["TOTAL LOGIN MINS"] / 60).round(2)

        churn_cols = ["DE_ID", "DE_NAME", "ZONE", "DT", "WEEK", "Login Hours", "TOTAL ORDERS"]
        if "REJECTED_ORDERS" in df.columns: churn_cols.append("REJECTED_ORDERS")
        if "DAILY_EARNINGS" in df.columns: churn_cols.append("DAILY_EARNINGS")

        if churn_df.empty:
            st.info("✅ No churn risk DEs found for the selected filters.")
        else:
            st.dataframe(churn_df[churn_cols].sort_values(by=["ZONE", "DT", "DE_NAME"]))
            st.download_button("🔕 Download Churn Risk Report (CSV)", data=churn_df[churn_cols].to_csv(index=False), file_name="churn_risk_DEs.csv", mime="text/csv")

        st.markdown("## 🚨 Stress Hours (High Orders, Low Login)")
        stress_df = zone_hour_df[(zone_hour_df["Avg_Orders"] > 2) & (zone_hour_df["Avg_Login_Mins"] < 20)]
        st.dataframe(stress_df.sort_values(by="Hour"))
        st.download_button("🔕 Download Zone Report", zone_hour_df.to_csv(index=False), file_name="zonepulse_hourly.csv")

        # 🏍️ Individual DE-wise View
        st.markdown("## 🏍️ Individual DE-wise View")
        if "DE_ID" in df.columns:
            de_ids = df["DE_ID"].dropna().astype(str).unique()
            selected_de = st.selectbox("😮 Choose DE ID to Explore", ["None"] + sorted(de_ids))
            if selected_de != "None":
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
                col2.metric("⏱️ Total Login Hrs", round(total_login / 60, 2))
                col3.metric("🔵️ Total Orders", int(total_orders))
                col4.metric("⚖️ Idle Ratio", round(idle_ratio, 2) if not np.isnan(idle_ratio) else "∞")

                col5, col6 = st.columns(2)
                col5.metric("⛔ Rejected Orders", int(total_rejected))
                col6.metric("💸 Total Earnings", f"₹{round(total_earnings, 2)}")

                st.markdown("### 📈 Week-on-Week Performance (4 Metrics)")
                de_data["WEEK"] = de_data["WEEK"].astype(str)
                weekly_df = de_data.groupby("WEEK").agg(
                    Login_Hours=("TOTAL LOGIN MINS", lambda x: round(x.sum() / 60, 2)),
                    Orders=("TOTAL ORDERS", "sum"),
                    Rejections=("REJECTED_ORDERS", "sum") if "REJECTED_ORDERS" in de_data.columns else ("TOTAL ORDERS", "sum"),
                    Earnings=("DAILY_EARNINGS", "sum") if "DAILY_EARNINGS" in de_data.columns else ("TOTAL ORDERS", "sum")
                ).reset_index()

                metrics = ["Login_Hours", "Orders", "Rejections", "Earnings"]
                colors = ["#1f77b4", "#2ca02c", "#d62728", "#ff7f0e"]
                chart_cols = st.columns(2)
                for i, metric in enumerate(metrics):
                    col = chart_cols[i % 2]
                    chart = alt.Chart(weekly_df).mark_bar(color=colors[i]).encode(
                        x=alt.X("WEEK", sort=None),
                        y=alt.Y(metric, type="quantitative"),
                        tooltip=["WEEK", metric]
                    ).properties(title=f"📊 {metric} by Week")
                    col.altair_chart(chart, use_container_width=True)

                st.markdown("### 📈 Login Minutes vs Total Orders Over Time")
                chart_df = de_data.sort_values("DT")
                base = alt.Chart(chart_df).encode(x="DT:T")

                login_line = base.mark_line(color="#1f77b4").encode(
                    y=alt.Y("TOTAL LOGIN MINS", axis=alt.Axis(title="Login Minutes")),
                    tooltip=["DT", "TOTAL LOGIN MINS"]
                )

                order_line = base.mark_line(color="#ff7f0e").encode(
                    y=alt.Y("TOTAL ORDERS", axis=alt.Axis(title="Total Orders", orient="right")),
                    tooltip=["DT", "TOTAL ORDERS"]
                )

                st.altair_chart(
                    alt.layer(login_line, order_line).resolve_scale(y="independent"),
                    use_container_width=True
                )

    # ---------------- No Show Section ----------------
    st.markdown("## 🤔 No-Show DEs – Previously Active, Not Logged In Now")
    col_prev, col_curr = st.columns(2)
    with col_prev:
        prev_dates = st.date_input("🗕️ Select Previous Period", [])
    with col_curr:
        curr_dates = st.date_input("🗕️ Select Current Period", [])

    if len(prev_dates) == 2 and len(curr_dates) == 2:
        prev_df = df[(df["DT"] >= prev_dates[0]) & (df["DT"] <= prev_dates[1])]
        curr_df = df[(df["DT"] >= curr_dates[0]) & (df["DT"] <= curr_dates[1])]

        prev_logged_in = prev_df[prev_df["TOTAL LOGIN MINS"] > 0]["DE_ID"].unique()
        curr_logged_in = curr_df[curr_df["TOTAL LOGIN MINS"] > 0]["DE_ID"].unique()

        no_show_ids = set(prev_logged_in) - set(curr_logged_in)
        no_show_df = prev_df[prev_df["DE_ID"].isin(no_show_ids)]

        if not no_show_df.empty:
            summary_df = no_show_df.groupby("DE_ID").agg(
                DE_NAME=("DE_NAME", "first"),
                ZONE=("ZONE", "first"),
                CITY=("CITY", "first"),
                Last_Seen_DT=("DT", "max"),
                Total_Login_Mins=("TOTAL LOGIN MINS", "sum"),
                Total_Orders=("TOTAL ORDERS", "sum"),
                Earnings=("DAILY_EARNINGS", "sum") if "DAILY_EARNINGS" in no_show_df.columns else ("TOTAL ORDERS", "sum")
            ).reset_index()

            summary_df["Total_Login_Hrs"] = (summary_df["Total_Login_Mins"] / 60).round(2)
            summary_df["Earnings"] = summary_df["Earnings"].round(2)

            display_cols = ["DE_ID", "DE_NAME", "CITY", "ZONE", "Last_Seen_DT", "Total_Login_Hrs", "Total_Orders", "Earnings"]
            st.dataframe(summary_df[display_cols].sort_values(by="Last_Seen_DT", ascending=False))
            st.download_button("📅 Download No-Show DEs", data=summary_df[display_cols].to_csv(index=False), file_name="no_show_des.csv", mime="text/csv")
        else:
            st.success("🎉 No No-Show DEs found. Great retention!")
    else:
        st.info("☝️ Select both Previous and Current Periods to identify no-shows.")
else:
    st.info("👆 Upload your DE Order vs Login File to get started.")
