import streamlit as st
def login():
    st.title("🔐 Login to ZonePulse")
    password = st.text_input("Enter Password", type="password")
    if password != "Swiggy@7904":
        st.warning("Please enter the correct password to continue.")
        st.stop()

login()
import pandas as pd
import numpy as np
import altair as alt

# Page config
st.set_page_config(page_title="DE Supply Efficiency Monitor - Swiggy", layout="wide") 

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
# 🚦 DE Supply Efficiency Monitor | Swiggy 
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

            zone_group = zone_group.round({
                "Avg_Orders": 2,
                "Avg_Login_Mins": 2,
                "Orders_per_Hour": 2,
                "Login_Utilization_%": 2
            })

            hourly_data.append(zone_group)

    if hourly_data:
        zone_hour_df = pd.concat(hourly_data)

        with st.expander("ℹ️ Column Logic Explanation"):
            st.markdown("""
            - **Avg Orders**: Average orders per DE in that hour (only for DEs logged in during that hour)
            - **Avg Login Mins**: Average login minutes of DEs who were active that hour
            - **Active DEs**: Number of DEs who logged in > 10 mins in that hour
            - **Orders per Hour**: Avg Orders ÷ (Avg Login Mins ÷ 60). Higher = better productivity.
            - **Login Utilization %**: (Avg Orders × 20 ÷ Avg Login Mins) × 100. Cap at 100%.

            **How to Interpret:**
            - A higher **Orders per Hour** means DEs are efficiently utilized.
            - A higher **Login Utilization %** indicates that login hours are translating into deliveries.
            - Use these to identify underperforming hours or zones, and reallocate DEs more effectively.
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

else:
    st.info("👆 Upload your DE Order vs Login File to get started.")
