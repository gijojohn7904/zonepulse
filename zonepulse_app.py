import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Wipe after use
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


check_password()  # 🔒 Call this function to enforce password

# Page config
st.set_page_config(page_title="ZonePulse – DE Supply Efficiency Monitor", layout="wide")

# Confidentiality Notice
st.markdown("""
<div style='background-color:#fff3cd;padding:15px;border-radius:5px;border:1px solid #ffeeba;margin-bottom:25px;'>
<b>⚠️ Confidentiality Notice by Swiggy:</b><br>
This tool is built using internal company data and is intended <b>strictly for internal use only</b>.<br>
Sharing, reproducing, or distributing this content outside the organization is <b>not permitted</b>.<br>
Please handle this information responsibly, in accordance with company data policies.
</div>
""", unsafe_allow_html=True)

# Banner
st.markdown("""
# 🚦 Fleet Efficiency & Attrition Risk Monitor | Swiggy
Monitor DE behavior, optimize login-to-order ratios, and ensure supply-demand harmony across every zone.
""")

# File uploader
uploaded_file = st.file_uploader("🔕️ Upload your DE Order vs Login File", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.upper()

    # ...all your current main logic goes here...
    # (zone-level report, churn risk, DE view, etc.)

    # 🌧️ Rain Day Participation Analysis
    st.markdown("## 🌧️ Rain Day Participation Analysis")
    if "RAIN_FLAG" in df.columns and "DE_ID" in df.columns:
        rain_dates = df[df["RAIN_FLAG"] == 1]["DT"].unique()
        total_rain_days = len(rain_dates)

        # Subset: All rows that are rain days (RAIN_FLAG == 1)
        rain_day_df = df[(df["DT"].isin(rain_dates)) & (df["RAIN_FLAG"] == 1)]

        # DEs who worked on rain days (logged in)
        logged_in_rain_df = rain_day_df[rain_day_df["TOTAL LOGIN MINS"] > 0]

        # Rain DEs: Logged in AND handled at least one order (delivered or rejected)
        rain_de_df = logged_in_rain_df[
            (logged_in_rain_df["TOTAL ORDERS"] > 0) | 
            (logged_in_rain_df["REJECTED_ORDERS"] > 0 if "REJECTED_ORDERS" in df.columns else False)
        ]
        rain_de_participation = rain_de_df.groupby("DE_ID").agg(
            DE_NAME=("DE_NAME", "first"),
            Rain_Days_Worked=("DT", "nunique")
        ).reset_index()
        rain_de_participation["Rain_DE_Type"] = "Rain DE"

        # Non-Rain DEs (who logged in on rain days but took no orders)
        non_rain_but_loggedin_df = logged_in_rain_df[
            ~(
                (logged_in_rain_df["TOTAL ORDERS"] > 0) |
                (logged_in_rain_df["REJECTED_ORDERS"] > 0 if "REJECTED_ORDERS" in df.columns else False)
            )
        ]
        non_rain_but_loggedin_part = non_rain_but_loggedin_df.groupby("DE_ID").agg(
            DE_NAME=("DE_NAME", "first"),
            Rain_Days_Worked=("DT", "nunique")
        ).reset_index()
        non_rain_but_loggedin_part["Rain_DE_Type"] = "Non-Rain DE (Rain day, no orders)"

        # DEs who never worked on rain days at all
        all_des = df[["DE_ID", "DE_NAME"]].drop_duplicates()
        de_worked_on_rain_day = pd.concat([rain_de_participation, non_rain_but_loggedin_part], ignore_index=True)["DE_ID"].unique()
        never_rain_de = all_des[~all_des["DE_ID"].isin(de_worked_on_rain_day)]
        never_rain_de = never_rain_de.assign(
            Rain_Days_Worked=0,
            Rain_DE_Type="Non-Rain DE (Never worked on rain day)"
        )

        # Combine all categories
        all_participation = pd.concat([
            rain_de_participation,
            non_rain_but_loggedin_part,
            never_rain_de
        ], ignore_index=True)

        all_participation["Total_Rain_Days"] = total_rain_days
        all_participation["Participation_%"] = (
            (all_participation["Rain_Days_Worked"] / total_rain_days) * 100
        ).round(2) if total_rain_days > 0 else 0

        filter_type = st.selectbox(
            "Filter by Rain Participation",
            [
                "Rain DE",
                "Non-Rain DE (Rain day, no orders)",
                "Non-Rain DE (Never worked on rain day)",
                "All"
            ]
        )
        if filter_type != "All":
            show_df = all_participation[all_participation["Rain_DE_Type"] == filter_type]
        else:
            show_df = all_participation

        st.dataframe(show_df.sort_values("Participation_%", ascending=False))
        st.download_button(
            "🌧️ Download Rain Day Participation",
            data=show_df.to_csv(index=False),
            file_name="rain_day_participation.csv",
            mime="text/csv"
        )
    else:
        st.info("Rain data (RAIN_FLAG) or DE_ID not available in the uploaded file.")

    # ...all your other logic (No-Show, DE View, etc.) goes here...

else:
    st.info("👆 Upload your DE Order vs Login File to get started.")
