# ✅ Final ZonePulse App with Full Rain View & All Functional Blocks
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
        This tool is for **Swiggy internal use only**.<br>
        Please enter the access password provided by the Sourcing & Onboarding team.
        """, unsafe_allow_html=True)
        st.text_input("🔐 Enter password", type="password", on_change=password_entered, key="password")
        st.stop()
    elif not st.session_state["password_correct"]:
        st.markdown("""
        ## 🚧 Restricted Access
        This tool is for **Swiggy internal use only**.<br>
        Please enter the access password provided by the S&O team.
        """, unsafe_allow_html=True)
        st.text_input("🔐 Enter password", type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect password. Please try again.")
        st.stop()

check_password()

# ---------------------- PAGE HEADER ----------------------
st.set_page_config(page_title="ZonePulse – DE Supply Efficiencye Monitor", layout="wide")
st.markdown("""
<div style='background-color:#fff3cd;padding:15px;border-radius:5px;border:1px solid #ffeeba;margin-bottom:25px;'>
<b>⚠️ Confidentiality Notice by Swiggy:</b><br>
This tool is built using internal company data and is intended <b>strictly for internal use only</b>.<br>
Sharing, reproducing, or distributing this content outside the organization is <b>not permitted</b>.
</div>
""", unsafe_allow_html=True)

st.markdown("### 🚦 Fleet Efficiency & Attrition Risk Monitor | Swiggy")

# ---------------------- FILE UPLOAD ----------------------
uploaded_file = st.file_uploader("🔕 Upload your DE Order vs Login File", type=["csv"])

def render_stars(rating, max_stars=5):
    if rating is None or np.isnan(rating): return "No Ratings"
    full = int(rating)
    half = 1 if rating - full >= 0.5 else 0
    empty = max_stars - full - half
    return "⭐" * full + ("✭" if half else "") + "☆" * empty

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.upper()

    required_cols = [col for col in df.columns if "LH_" in col or "FD_" in col]
    if len(required_cols) == 0:
        st.error("❌ Your CSV must contain hourly login/order columns like LH_00, FD_01 etc.")
        st.stop()

    df["VERTICAL"] = df["DE_SHIFT"].apply(lambda x: "Instamart" if any(tag in str(x).upper() for tag in ["IM", "DDE"]) else "SwiggyFood")

    # ---------------------- FILTER BLOCK ----------------------
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

    # ---------------------- TOTALS ----------------------
    df["TOTAL LOGIN MINS"] = df[[f"LH_{str(i).zfill(2)}" for i in range(24) if f"LH_{str(i).zfill(2)}" in df.columns]].sum(axis=1)
    df["TOTAL ORDERS"] = df[[f"FD_{str(i).zfill(2)}" for i in range(24) if f"FD_{str(i).zfill(2)}" in df.columns]].sum(axis=1)

    # ---------------------- RAIN PARTICIPATION SECTION ----------------------
    st.markdown("## ☔️ Rain Day Participation Analysis")
    rain_required_cols = ["RAIN_FLAG", "DT", "DE_ID", "ZONE", "TOTAL LOGIN MINS"]
    missing = [col for col in rain_required_cols if col not in df.columns]
    if missing:
        st.warning(f"⚠️ Missing columns: {', '.join(missing)}")
    else:
        rain_days = df[df["RAIN_FLAG"] == 1]["DT"].unique()
        st.write(f"🗓️ Total Rain Days Detected: {len(rain_days)}")

        worked_on_rain_days = df[df["DT"].isin(rain_days) & (df["TOTAL LOGIN MINS"] > 0)]
        rain_workers = worked_on_rain_days[worked_on_rain_days["RAIN_FLAG"] == 1]

        st.markdown("### 🏅 Zone-wise Rain Day Participation Rate")
        if not worked_on_rain_days.empty:
            total_active = worked_on_rain_days.groupby("ZONE")["DE_ID"].nunique().reset_index(name="Total_DEs_On_Rain_Days")
            rain_participated = rain_workers.groupby("ZONE")["DE_ID"].nunique().reset_index(name="Rain_Workers")
            rain_participation = pd.merge(total_active, rain_participated, on="ZONE", how="left").fillna(0)
            rain_participation["Rain_Participation_%"] = (rain_participation["Rain_Workers"] / rain_participation["Total_DEs_On_Rain_Days"] * 100).round(2)
            st.dataframe(rain_participation)
            st.altair_chart(
                alt.Chart(rain_participation).mark_bar().encode(
                    x=alt.X("ZONE:N", sort="-y"),
                    y=alt.Y("Rain_Participation_%:Q"),
                    tooltip=["ZONE", "Rain_Workers", "Total_DEs_On_Rain_Days", "Rain_Participation_%"]
                ).properties(height=350),
                use_container_width=True
            )
            st.download_button("📅 Download Zone Rain Report", rain_participation.to_csv(index=False), "zone_rain_participation.csv", "text/csv")
        else:
            st.info("ℹ️ No DEs logged in during rain days.")
else:
    st.info("👆 Upload your DE Order vs Login File to get started.")

# ---------------------- FOOTER ----------------------
components.html("""
<link href="https://fonts.googleapis.com/css2?family=Inter&display=swap" rel="stylesheet">
<div style='
    background-color:#f8f9fa;
    padding:15px;
    border-radius:12px;
    margin-top:50px;
    text-align:center;
    font-family:"Inter", sans-serif;
    font-size:14px;
    color:#333;
    border:1px solid #ddd;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
'>
    Built by <b>Gijo Kochuparambil John</b> – Assistant Manager, Sourcing & Onboarding, Swiggy<br>
    <a href='mailto:gijo.j@swiggy.in' style='text-decoration:none;color:#0072b1;'>gijo.j@swiggy.in</a> |
    <a href='https://www.linkedin.com/in/gijojohn/' target='_blank' style='text-decoration:none;color:#0072b1;'>LinkedIn</a><br>
    <sub style='color:#666;'>#FleetFirst | Empowering Swiggy with data-driven fleet optimization</sub>
</div>
""", height=170)
