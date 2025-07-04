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

    # ============================
    # ZONE-LEVEL HOURLY REPORT
    # ============================
    with st.expander("ℹ️ 💡 Zone-Level Hourly Report: What does this mean?", expanded=False):
        st.markdown("""
        <div style='background-color:#e7f3fe;padding:16px;border-radius:6px;border:1px solid #b3d8f5;'>
        <b>Login Utilization %</b> = (Avg Orders × 25 min) / (Avg Login Minutes) × 100.<br>
        <b>Interpretation:</b><br>
        - Low Utilization + low Orders/hr → Overstaffed.<br>
        - High Utilization + high Orders/hr → Understaffed.<br>
        <b>Thresholds:</b><br>
        <u>Instamart</u>: Overstaffed if Orders/hr &lt; 1.2 &amp; Utilization &lt; 30%<br>
        Understaffed if Orders/hr &gt; 2.2 &amp; Utilization &gt; 70%<br>
        <u>SwiggyFood</u>: Overstaffed if Orders/hr &lt; 1.0 &amp; Utilization &lt; 50%<br>
        Understaffed if Orders/hr &gt; 1.2 &amp; Utilization &gt; 57%<br>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("## 📊 Zone-Level Hourly Report")
    hourly_data = []
    for hr in range(24):
        fd_col = f"FD_{str(hr).zfill(2)}"
        lh_col = f"LH_{str(hr).zfill(2)}"
        if fd_col in df.columns and lh_col in df.columns:
            hour_df = df[df[lh_col] > 10]
            if hour_df.empty: continue
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

    # ============================
    # RAIN PARTICIPATION ANALYSIS
    # ============================
    with st.expander("ℹ️ 💡 Rain Participation: Logic and Usage", expanded=False):
        st.markdown("""
        <div style='background-color:#e7f3fe;padding:16px;border-radius:6px;border:1px solid #b3d8f5;'>
        <b>Eligible Active:</b> DE present (login mins > 0) for ≥6/7 days before the rain day.<br>
        <b>Participation %:</b> (DEs who logged in on rain day) / (Eligible Actives).<br>
        <b>Purpose:</b> Filter out one-timers and spot core DEs who skip rain.<br>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("## 🌧️ Rain Participation Analysis (Zone & DE level)")
    LOOKBACK_DAYS = 7
    PARTICIPATION_THRESHOLD = 0.8  # 80%
    rain_flag_col = "RAIN_FLAG"
    if rain_flag_col not in df.columns:
        st.warning("No RAIN_FLAG column in uploaded file. Please include rain flag for this analysis.")
    else:
        rain_dates = sorted(df.loc[df[rain_flag_col] == 1, "DT"].unique())
        if not rain_dates:
            st.warning("No rain dates found in the selected period!")
        else:
            col_rain, col_zone = st.columns(2)
            with col_rain:
                selected_rain_date = st.selectbox(
                    "🌧️ Select Rain Date",
                    rain_dates,
                    format_func=lambda d: pd.to_datetime(d).strftime("%b %d, %Y") if hasattr(d, "strftime") else str(d)
                )
            impacted_zones = df[(df["DT"] == selected_rain_date) & (df[rain_flag_col] == 1)]["ZONE"].unique()
            impacted_zones = sorted([z for z in impacted_zones if pd.notnull(z)])
            with col_zone:
                zone_options = ["All"] + list(impacted_zones)
                selected_rain_zone = st.selectbox("🏴‍☠️ Select Zone (Rain Impacted Only)", zone_options)
            rain_day_df = df[(df["DT"] == selected_rain_date) & (df["ZONE"].isin(impacted_zones))]
            if selected_rain_zone != "All":
                rain_day_df = rain_day_df[rain_day_df["ZONE"] == selected_rain_zone]
                impacted_zones = [selected_rain_zone]
            last7_by_zone = {}
            for zone in impacted_zones:
                last7days = pd.date_range(end=pd.to_datetime(selected_rain_date)-pd.Timedelta(days=1), periods=LOOKBACK_DAYS).date
                mask7 = (df["ZONE"] == zone) & (df["DT"].isin(last7days)) & (df["TOTAL LOGIN MINS"] > 0)
                df7 = df.loc[mask7, ["DE_ID", "DT"]]
                count_days = df7.groupby("DE_ID")["DT"].nunique()
                eligible = set(count_days[count_days >= int(PARTICIPATION_THRESHOLD*LOOKBACK_DAYS)].index)
                last7_by_zone[zone] = eligible
            rain_part = []
            for zone in impacted_zones:
                city = rain_day_df[rain_day_df["ZONE"] == zone]["CITY"].iloc[0] if not rain_day_df[rain_day_df["ZONE"] == zone].empty else ""
                eligible_DEs = last7_by_zone[zone]
                rain_DEs = set(rain_day_df[(rain_day_df["ZONE"] == zone) &
                                        (rain_day_df[rain_flag_col] == 1) &
                                        (rain_day_df["TOTAL LOGIN MINS"] > 0)]["DE_ID"])
                rate = (len(rain_DEs) / len(eligible_DEs))*100 if eligible_DEs else np.nan
                rain_part.append({
                    "Zone": zone, "City": city,
                    "Eligible_Actives": len(eligible_DEs),
                    "Rain_Logins": len(rain_DEs),
                    "Rain_Participation_%": round(rate, 2) if not np.isnan(rate) else None
                })
            zone_part_df = pd.DataFrame(rain_part)
            zone_part_df = zone_part_df.sort_values(by="Rain_Participation_%", ascending=False)
            if not zone_part_df.empty:
                chart = alt.Chart(zone_part_df).mark_rect().encode(
                    x=alt.X('Zone:N', title='Zone', sort=list(zone_part_df["Zone"])),
                    y=alt.Y('Rain_Participation_%:Q', title='Rain Participation %'),
                    color=alt.Color('Rain_Participation_%:Q', scale=alt.Scale(scheme='redyellowgreen', domain=[0, 100])),
                    tooltip=['Zone', 'City', 'Eligible_Actives', 'Rain_Logins', 'Rain_Participation_%']
                ).properties(
                    width=400, height=350, title="Rain Participation % by Zone"
                )
                st.altair_chart(chart, use_container_width=True)
            def color_code(val):
                if pd.isnull(val): return "background-color: #eee"
                elif val < 50: return "background-color: #ffcccc"
                elif val < 80: return "background-color: #ffe699"
                else: return "background-color: #c6efce"
            st.dataframe(zone_part_df.style.applymap(color_code, subset=["Rain_Participation_%"]))
            st.download_button("📥 Download Zone Rain Participation (CSV)", data=zone_part_df.to_csv(index=False), file_name="zone_rain_participation.csv")
            all_de = []
            for zone in impacted_zones:
                eligible_DEs = last7_by_zone[zone]
                rain_DEs = set(rain_day_df[(rain_day_df["ZONE"] == zone) &
                                        (rain_day_df[rain_flag_col] == 1) &
                                        (rain_day_df["TOTAL LOGIN MINS"] > 0)]["DE_ID"])
                de_rows = df[df["DE_ID"].isin(eligible_DEs) & (df["ZONE"] == zone)]
                for de in eligible_DEs:
                    sub = de_rows[de_rows["DE_ID"] == de]
                    de_name = sub["DE_NAME"].iloc[0] if not sub.empty and "DE_NAME" in sub.columns else ""
                    city = sub["CITY"].iloc[0] if not sub.empty and "CITY" in sub.columns else ""
                    rain_login = "Yes" if de in rain_DEs else "No"
                    rain_skip = "Yes" if de not in rain_DEs else "No"
                    all_de.append({
                        "DE_ID": de,
                        "DE_NAME": de_name,
                        "Zone": zone,
                        "City": city,
                        "Was_Active_Last_7d": "Yes",
                        "Logged_in_on_Rain": rain_login,
                        "Rain_Skipper": rain_skip
                    })
            de_df = pd.DataFrame(all_de)
            st.markdown("### 🔎 DE-Level Rain Skippers Table")
            if not de_df.empty:
                st.dataframe(de_df)
                st.download_button("📥 Download Rain Skippers Table (CSV)", data=de_df.to_csv(index=False), file_name="rain_skippers_full.csv")
            else:
                st.info("No eligible DEs found for rain skippers participation criteria.")

    # ============================
    # DATE-WISE LOGIN COUNT
    # ============================
    with st.expander("ℹ️ 💡 Date-wise Login Count: What does this show?", expanded=False):
        st.markdown("""
        <div style='background-color:#e7f3fe;padding:16px;border-radius:6px;border:1px solid #b3d8f5;'>
        Tracks how many unique DEs logged in by date and zone.<br>
        Use to spot zone/period-specific drop-offs or recoveries.
        </div>
        """, unsafe_allow_html=True)
    st.markdown("## 📅 Date-wise Login Count for Selected Zone")
    if not df.empty:
        filter_mask = (df["TOTAL LOGIN MINS"] > 0)
        if selected_city != "All":
            filter_mask &= (df["CITY"] == selected_city)
        if selected_zone != "All":
            filter_mask &= (df["ZONE"] == selected_zone)
        filtered_df = df[filter_mask].copy()
        login_counts = (
            filtered_df.groupby(["DT", "ZONE"])
            .agg(Login_Count=('DE_ID', 'nunique'))
            .reset_index()
        )
        if selected_zone == "All":
            chart_zones = login_counts["ZONE"].unique()
            if len(chart_zones) == 0:
                st.info("No data for the selected filters.")
                login_counts = pd.DataFrame()
            else:
                show_zone = st.selectbox("Select Zone to Plot (for chart below):", sorted(chart_zones))
                login_counts = login_counts[login_counts["ZONE"] == show_zone]
        else:
            show_zone = selected_zone
            login_counts = login_counts[login_counts["ZONE"] == show_zone]
        if not login_counts.empty:
            chart = alt.Chart(login_counts).mark_line(point=True).encode(
                x=alt.X("DT:T", title="Date"),
                y=alt.Y("Login_Count", title="No. of DEs Logged In"),
                tooltip=[
                    alt.Tooltip("DT:T", title="Date"),
                    alt.Tooltip("Login_Count", title="Active DE Count"),
                    alt.Tooltip("ZONE", title="Zone")
                ]
            ).properties(
                title=f"Login Count per Day – {show_zone}"
            ).interactive()
            st.altair_chart(chart, use_container_width=True)
            st.download_button(
                "📥 Download Login Count (CSV)",
                data=login_counts.to_csv(index=False),
                file_name=f"{show_zone}_datewise_login_count.csv",
                mime="text/csv"
            )
        else:
            st.info("No login data for this city/zone selection.")

    # ... (other views can get the same style expander; just let me know if you want for every table/chart/view!)
else:
    st.info("👆 Upload your DE Order vs Login File to get started.")
