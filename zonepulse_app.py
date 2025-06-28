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

    # 🚨 Individual DE-wise View
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

        st.markdown("### 📈 Login Minutes vs Total Orders Over Time")
        if "DT" in de_data.columns:
            line_chart_df = de_data.sort_values("DT")
            base = alt.Chart(line_chart_df).encode(x="DT:T")

            login_line = base.mark_line(color="#1f77b4").encode(
                y=alt.Y("TOTAL LOGIN MINS", axis=alt.Axis(title="Login Minutes")),
                tooltip=["DT", "TOTAL LOGIN MINS"]
            )

            order_line = base.mark_line(color="#ff7f0e").encode(
                y=alt.Y("TOTAL ORDERS", axis=alt.Axis(title="Total Orders", titleColor="#ff7f0e")),
                tooltip=["DT", "TOTAL ORDERS"]
            ).encode(
                y=alt.Y("TOTAL ORDERS", axis=alt.Axis(title="Total Orders"), scale=alt.Scale(zero=True))
            )

            st.altair_chart(alt.layer(
                login_line,
                order_line.encode(y=alt.Y("TOTAL ORDERS", axis=alt.Axis(title="Total Orders", orient="right")))
            ).resolve_scale(y='independent'), use_container_width=True)

else:
    st.info("👆 Upload your DE Order vs Login File to get started.")
