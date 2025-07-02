# ✅ FINAL FULL VERSION OF ZONEPULSE DASHBOARD
# Includes: Rain Analysis, DE Profile, Star Rating, Footer Branding, All Views

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import altair as alt

# ---------------------- PASSWORD GATE ----------------------
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("""
        ## 🚧 Restricted Access
        This tool is for **Swiggy internal use only**.
        """, unsafe_allow_html=True)
        st.text_input("🔐 Enter password", type="password", on_change=password_entered, key="password")
        st.stop()
    elif not st.session_state["password_correct"]:
        st.markdown("## 🚧 Restricted Access", unsafe_allow_html=True)
        st.text_input("🔐 Enter password", type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect password. Please try again.")
        st.stop()

check_password()

# ---------------------- PAGE HEADER ----------------------
st.set_page_config(page_title="ZonePulse – DE Supply Efficiency Monitor", layout="wide")
st.markdown("""
<div style='background-color:#fff3cd;padding:15px;border-radius:5px;border:1px solid #ffeeba;margin-bottom:25px;'>
<b>⚠️ Confidentiality Notice by Swiggy:</b><br>
This tool is built using internal company data and is intended <b>strictly for internal use only</b>.
</div>
""", unsafe_allow_html=True)

st.markdown("# 🚦 Fleet Efficiency & Attrition Risk Monitor | Swiggy")

# ---------------------- FILE UPLOAD ----------------------
uploaded_file = st.file_uploader("📂 Upload DE Order vs Login File", type=["csv"])

# ---------------------- STAR RENDER ----------------------
def render_stars(rating, max_stars=5):
    if rating is None or np.isnan(rating): return "No Ratings"
    full = int(rating)
    half = 1 if rating - full >= 0.5 else 0
    empty = max_stars - full - half
    return "⭐" * full + ("✰" if half else "") + "☆" * empty

# ---------------------- MAIN BLOCK ----------------------
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.upper()

    df["VERTICAL"] = df["DE_SHIFT"].apply(lambda x: "Instamart" if any(tag in str(x).upper() for tag in ["IM", "DDE"]) else "SwiggyFood")

    st.sidebar.header("🔎 Filter Data")
    vertical = st.sidebar.selectbox("Vertical", ["SwiggyFood", "Instamart"])
    df = df[df["VERTICAL"] == vertical]

    if "CITY" in df.columns:
        cities = df["CITY"].dropna().unique()
        selected_city = st.sidebar.selectbox("City", sorted(cities))
        df = df[df["CITY"] == selected_city]

    if "ZONE" in df.columns:
        zones = df["ZONE"].dropna().unique()
        selected_zone = st.sidebar.selectbox("Zone", ["All"] + sorted(zones))
        if selected_zone != "All":
            df = df[df["ZONE"] == selected_zone]

    if "DT" in df.columns:
        df["DT"] = pd.to_datetime(df["DT"]).dt.date
        min_date, max_date = df["DT"].min(), df["DT"].max()
        date_range = st.sidebar.date_input("Date Range", [min_date, max_date])
        if len(date_range) == 2:
            df = df[(df["DT"] >= date_range[0]) & (df["DT"] <= date_range[1])]

    # ---------------------- COMPUTE TOTALS ----------------------
    df["TOTAL LOGIN MINS"] = df[[c for c in df.columns if c.startswith("LH_")]].sum(axis=1)
    df["TOTAL ORDERS"] = df[[c for c in df.columns if c.startswith("FD_")]].sum(axis=1)

    # ---------------------- RAIN PARTICIPATION ----------------------
    st.markdown("## 🌧️ Rain Day Participation Analysis")
    if all(col in df.columns for col in ["RAIN_FLAG", "DT", "DE_ID", "ZONE", "TOTAL LOGIN MINS"]):
        rain_days = df[df["RAIN_FLAG"] == 1]["DT"].unique()
        st.write(f"🗓️ Total Rain Days: {len(rain_days)}")
        rain_df = df[df["DT"].isin(rain_days)]
        rain_active = rain_df[rain_df["TOTAL LOGIN MINS"] > 0]
        rain_workers = rain_active[rain_active["RAIN_FLAG"] == 1]
        if not rain_active.empty:
            active_summary = rain_active.groupby("ZONE")["DE_ID"].nunique().reset_index(name="Total_DEs_On_Rain_Days")
            participated = rain_workers.groupby("ZONE")["DE_ID"].nunique().reset_index(name="Rain_Workers")
            rain_stats = pd.merge(active_summary, participated, on="ZONE", how="left").fillna(0)
            rain_stats["Rain_Participation_%"] = (rain_stats["Rain_Workers"] / rain_stats["Total_DEs_On_Rain_Days"]) * 100
            st.dataframe(rain_stats.sort_values("Rain_Participation_%", ascending=False))
            chart = alt.Chart(rain_stats).mark_bar().encode(
                x=alt.X("ZONE:N", sort="-y"),
                y=alt.Y("Rain_Participation_%:Q"),
                tooltip=["Rain_Participation_%", "Rain_Workers"]
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No DEs worked on rain days.")
    else:
        st.warning("Required rain columns missing in data.")

    # ---------------------- DE PROFILE METRICS ----------------------
    st.markdown("## 👤 Individual DE Profile")
    if "DE_ID" in df.columns:
        selected_de = st.selectbox("Choose DE ID", ["None"] + sorted(df["DE_ID"].astype(str).unique()))
        if selected_de != "None":
            de_data = df[df["DE_ID"].astype(str) == selected_de].copy()
            de_name = de_data["DE_NAME"].iloc[0] if "DE_NAME" in de_data.columns else "Unknown"
            st.subheader(f"{de_name} ({selected_de})")
            total_days = de_data.shape[0]
            total_login = de_data["TOTAL LOGIN MINS"].sum()
            total_orders = de_data["TOTAL ORDERS"].sum()
            avg_oph = round(total_orders / (total_login / 60), 2) if total_login > 0 else 0
            idle_ratio = round(total_login / (total_orders * 25), 2) if total_orders > 0 else np.nan
            earnings = de_data["DAILY_EARNINGS"].sum() if "DAILY_EARNINGS" in de_data.columns else 0
            rejections = de_data["REJECTED_ORDERS"].sum() if "REJECTED_ORDERS" in de_data.columns else 0
            total_deduction = 0
            if "WEEKLY_DEDUCTIONS" in de_data.columns:
                total_deduction += de_data["WEEKLY_DEDUCTIONS"].sum()
            if "OTHER_DAILY_DEDUCTIONS" in de_data.columns:
                total_deduction += de_data["OTHER_DAILY_DEDUCTIONS"].sum()
            net = earnings - total_deduction
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Active Days", total_days)
            col2.metric("Total Login Hrs", round(total_login / 60, 2))
            col3.metric("Total Orders", int(total_orders))
            col4.metric("Idle Ratio", round(idle_ratio, 2) if not np.isnan(idle_ratio) else "∞")
            col5, col6, col7, col8 = st.columns(4)
            col5.metric("Rejected Orders", int(rejections))
            col6.metric("Total Earnings", f"₹{round(earnings, 2)}")
            col7.metric("Deductions", f"₹{round(total_deduction, 2)}")
            col8.metric("Net Earnings", f"₹{round(net, 2)}")
            if "TOTAL_RATING" in de_data.columns and "TOTAL_ORDERS_RATED" in de_data.columns:
                total_rating = de_data["TOTAL_RATING"].sum()
                total_rated = de_data["TOTAL_ORDERS_RATED"].sum()
                avg_rating = round(total_rating / total_rated, 2) if total_rated > 0 else None
                stars = render_stars(avg_rating)
                st.markdown(f"### ⭐ Rating: {stars} ({avg_rating})" if avg_rating else "### ⭐ No Ratings")

# ---------------------- FOOTER ----------------------
components.html("""
<link href='https://fonts.googleapis.com/css2?family=Inter&display=swap' rel='stylesheet'>
<div style='font-family:Inter,sans-serif;font-size:14px;color:#333;padding:15px;margin-top:50px;text-align:center;border-top:1px solid #eee;'>
  Built by <b>Gijo Kochuparambil John</b> – Assistant Manager, Sourcing & Onboarding, Swiggy<br>
  <a href='mailto:gijo.j@swiggy.in'>gijo.j@swiggy.in</a> |
  <a href='https://www.linkedin.com/in/gijojohn/' target='_blank'>LinkedIn</a><br>
  <sub style='color:#888;'>#FleetFirst | Empowering Swiggy with data-driven fleet optimization</sub>
</div>
""", height=160)
