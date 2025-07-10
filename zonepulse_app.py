import streamlit as st
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

# ---------------------- PAGE CONFIG & BANNERS ----------------------
st.set_page_config(page_title="ZonePulse – DE Supply Efficiency Monitor", layout="wide")
st.markdown("""
    <div style='background-color:#fff3cd;padding:15px;border-radius:5px;border:1px solid #ffeeba;margin-bottom:25px;'>
    <b>⚠️ Confidentiality Notice by Swiggy:</b><br>
    This tool is built using internal company data and is intended <b>strictly for internal use only</b>.<br>
    Sharing, reproducing, or distributing this content outside the organization is <b>not permitted</b>.<br>
    Please handle this information responsibly, in accordance with company data policies.
    </div>
    """, unsafe_allow_html=True)

st.markdown("""
# 🚦 Fleet Efficiency & Attrition Risk Monitor | Swiggy

Get zone-by-zone *clarity* on DE activity, eliminate idle supply, target churn risks, and drive reliable ops—*rain or shine*.
""")

# ---------------------- FILE UPLOAD ----------------------
uploaded_file = st.file_uploader("🔕️ Upload your DE Order vs Login File", type=["csv"])
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.upper()
    if "CITY" not in df.columns or "ZONE" not in df.columns:
        st.error("Missing CITY or ZONE column in file.")
        st.stop()

    required_cols = [col for col in df.columns if "LH_" in col or "FD_" in col]
    if len(required_cols) == 0:
        st.error("❌ Your CSV must contain hourly login/order columns like LH_00, FD_01 etc.")
        st.stop()

    # Detect vertical
    df["VERTICAL"] = df["DE_SHIFT"].apply(lambda x: "Instamart" if any(tag in str(x).upper() for tag in ["IM", "DDE"]) else "SwiggyFood")

    # ------ FILTERS ------
    col1, col2 = st.columns(2)
    with col1:
        vertical = st.selectbox("🔃 Choose Vertical", ["SwiggyFood", "Instamart"])
        df = df[df["VERTICAL"] == vertical]
    with col2:
        cities = sorted(df["CITY"].dropna().unique())
        city_options = ["All"] + list(cities)
        selected_city = st.selectbox("🏩 Choose City", city_options)
        if selected_city != "All":
            df = df[df["CITY"] == selected_city]

    col3, col4 = st.columns(2)
    with col3:
        zones = sorted(df["ZONE"].dropna().unique())
        zone_options = ["All"] + list(zones)
        selected_zone = st.selectbox("📍 Choose Zone", zone_options)
        if selected_zone != "All":
            df = df[df["ZONE"] == selected_zone]
    with col4:
        df["DT"] = pd.to_datetime(df["DT"]).dt.date
        min_date, max_date = df["DT"].min(), df["DT"].max()
        selected_dates = st.date_input("🗓️ Filter by Date Range", [min_date, max_date])
        if len(selected_dates) == 2:
            df = df[(df["DT"] >= selected_dates[0]) & (df["DT"] <= selected_dates[1])]

    # Add total login mins/orders
    df["TOTAL LOGIN MINS"] = df[[f"LH_{str(i).zfill(2)}" for i in range(24) if f"LH_{str(i).zfill(2)}" in df.columns]].sum(axis=1)
    df["TOTAL ORDERS"] = df[[f"FD_{str(i).zfill(2)}" for i in range(24) if f"FD_{str(i).zfill(2)}" in df.columns]].sum(axis=1)

    # ---------------------- LOGIN UTILIZATION INFOBOX ----------------------
    with st.expander("💡 Login Utilization % Explained (click to expand)", expanded=False):
        st.markdown("""
**Login Utilization %** shows how efficiently DEs are being used in a zone/hour.

- Formula: (Avg Orders × 25 min) / (Avg Login Minutes) × 100
- High = DEs are busy (possible understaffing).
- Low = DEs are idle (possible overstaffing).

**Thresholds**:
- Instamart: Overstaffed <1.2 orders/hr & <30% utilization; Understaffed >2.2 orders/hr & >70% utilization.
- SwiggyFood: Overstaffed <1.0 orders/hr & <50% utilization; Understaffed >1.2 orders/hr & >57% utilization.
        """)

    # ---------------------- ZONE-LEVEL HOURLY REPORT ----------------------
    st.markdown("## 📊 Zone-Level Hourly Report")
    with st.expander("💡 How to read this report (click to expand)", expanded=False):
        st.markdown("""
**Each row shows:**  
- Hour-wise stats for every city/zone.
- Overstaffed: Too many DEs, not enough orders.
- Understaffed: DEs are busy, too few for the demand.
- Balanced: All good.  
Look for repeated 'Overstaffed' hours to trim idle supply, or 'Understaffed' to ramp up hiring/incentives.
        """)

    hourly_data = []
    for hr in range(24):
        fd_col = f"FD_{str(hr).zfill(2)}"
        lh_col = f"LH_{str(hr).zfill(2)}"
        if fd_col in df.columns and lh_col in df.columns:
            hour_df = df[df[lh_col] > 10]
            if hour_df.empty:
                continue
            group_cols = ["DT", "CITY", "ZONE"]
            zone_group = hour_df.groupby(group_cols).agg(
                Total_Orders=(fd_col, 'sum'),
                Avg_Orders=(fd_col, 'mean'),
                Avg_Login_Mins=(lh_col, 'mean'),
                Active_DEs=(lh_col, lambda x: (x > 10).sum())
            ).reset_index()
            zone_group["Hour"] = hr
            zone_group["Login_Utilization_%"] = zone_group.apply(
                lambda row: min(100, (row["Avg_Orders"] * 25 / row["Avg_Login_Mins"]) * 100) if row["Avg_Login_Mins"] > 0 else 0, axis=1
            )
            if vertical == "Instamart":
                zone_group["Recommendation"] = zone_group.apply(
                    lambda row: "⚠️ Overstaffed" if (row["Avg_Orders"] / (row["Avg_Login_Mins"] / 60) < 1.2 and row["Login_Utilization_%"] < 30)
                    else "🔴 Understaffed" if (row["Avg_Orders"] / (row["Avg_Login_Mins"] / 60) > 2.2 and row["Login_Utilization_%"] > 70)
                    else "✅ Balanced",
                    axis=1
                )
            else:
                zone_group["Recommendation"] = zone_group.apply(
                    lambda row: "⚠️ Overstaffed" if (row["Avg_Orders"] / (row["Avg_Login_Mins"] / 60) < 1 and row["Login_Utilization_%"] < 50)
                    else "🔴 Understaffed" if (row["Avg_Orders"] / (row["Avg_Login_Mins"] / 60) > 1.2 and row["Login_Utilization_%"] > 57)
                    else "✅ Balanced",
                    axis=1
                )
            hourly_data.append(zone_group)
    if hourly_data:
        zone_hour_df = pd.concat(hourly_data)
        st.dataframe(zone_hour_df.sort_values(by=["DT", "CITY", "ZONE", "Hour"]))
        st.download_button("📥 Download Hourly Report (CSV)", data=zone_hour_df.to_csv(index=False), file_name="zone_hourly_report.csv", mime="text/csv")
    else:
        zone_hour_df = pd.DataFrame()
        st.info("No zone/city hourly data available. Please check the uploaded file or filter selection.")

    # ================= RAIN PARTICIPATION ANALYSIS (BY RAIN HOUR) ==================
    st.markdown("---")
    st.markdown("## 🌧️ Rain Participation Analysis (Zone & DE Level)")
    with st.expander("💡 Rain Participation % Explained (click to expand)", expanded=False):
        st.markdown("""
- **Eligible Actives:** DEs logged in at/just before the rain started in that zone.
- **Rain DE:** Among those, who actually took a rain-tagged order.
- **Participation %:** Rain DEs / Eligible Actives × 100
- Why? Only those present _during_ rain can be counted as committed for surge/peak incentives.
        """)

    # ... keep the rest of your rain participation, zone heatmap, and DE-level logic the same ...

    # ---------------------- DATE-WISE LOGIN COUNT (POINTED LINE CHART W/ TOOLTIP) ----------------------
    st.markdown("## 📅 Date-wise Login Count for Selected Zone")
    with st.expander("💡 Datewise Login Explained (click to expand)", expanded=False):
        st.markdown("""
This chart shows, for each date, how many DEs logged in to the selected zone.  
Sharp dips = supply gaps. Spikes = excess idle.
        """)

    # ... keep the rest of your login count logic as is ...

    # ---------------------- HOURLY LOGIN DISTRIBUTION FOR SELECTED ZONE ----------------------
    st.markdown("#### ⏰ Zone-wise Hourly Login Distribution")
    with st.expander("💡 Hourly Login Distribution Explained (click to expand)", expanded=False):
        st.markdown("""
- Shows how many DEs are logged in by hour (across all dates), with zone status color.
- Green = Balanced. Orange = Overstaffed (trim supply). Red = Understaffed (ramp up!).
        """)

    # ... keep your hourly chart logic ...

    # ---------------------- TABLE OF DEs LOGGED IN PER DAY ----------------------
    st.markdown("#### 🔎 DEs Logged In Per Day")
    with st.expander("💡 DE Login Table Explained (click to expand)", expanded=False):
        st.markdown("""
Full DE-wise view for each day:  
See login mins, orders, and other stats.  
Filter, sort, or download for detailed ops action.
        """)

    # ... keep DE login data table logic ...

    # ---------------------- ATTRITION RISK DES ----------------------
    st.markdown("## ⚠️ Attrition Risk DEs (Login > 3hr, Orders < 2, or Negative Earnings)")
    with st.expander("💡 Attrition Risk Logic (click to expand)", expanded=False):
        st.markdown("""
Flags DEs with >3hr login but <2 orders, or negative earnings.  
Great for targeting those likely to quit, or at risk of disengagement!
        """)

    # ... keep churn logic ...

    # ---------------------- INDIVIDUAL DE-WISE VIEW ----------------------
    st.markdown("## 👤 Individual DE-wise View")
    with st.expander("💡 DE-wise Drilldown Explained (click to expand)", expanded=False):
        st.markdown("""
Pick any DE and see their entire journey—login trends, order trends, week-on-week stats, and more.
        """)

    # ... keep DE drilldown logic ...

    # ---------------------- NO SHOW DEs ----------------------
    st.markdown("## 🤔 No-Show DEs – Previously Active, Not Logged In Now")
    with st.expander("💡 No-Show DEs Logic (click to expand)", expanded=False):
        st.markdown("""
Find DEs who were present last period, but missing in the current period.  
Perfect for win-back, reactivation calls, and targeted support.
        """)

    # ... keep your no-show logic ...

else:
    st.info("👆 Upload your DE Order vs Login File to get started.")
