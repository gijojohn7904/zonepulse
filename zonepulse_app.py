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

check_password()  # 🔒 Enforce password before running further

# ---------------------- PAGE CONFIG & BANNERS ----------------------
st.set_page_config(page_title="ZonePulse – DE Supply Efficiencye Monitor", layout="wide")
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
    Monitor DE behavior, optimize login-to-order ratios, and ensure supply-demand harmony across every zone.
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

    # ---------------------- ZONE-LEVEL HOURLY REPORT ----------------------
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

    # =========================== 🌧️ RAIN PARTICIPATION SECTION ==========================
    st.markdown("---")
    st.markdown("## 🌧️ Rain Participation Analysis (Zone & DE level)")
    LOOKBACK_DAYS = 14
    rain_flag_col = "RAIN_FLAG"

    if rain_flag_col not in df.columns:
        st.warning("No RAIN_FLAG column in uploaded file. Please include rain flag for this analysis.")
    else:
        rain_dates = sorted(df.loc[df[rain_flag_col] == 1, "DT"].unique())
        if not rain_dates:
            st.warning("No rain dates found in the selected period!")
        else:
            selected_rain_date = st.selectbox(
                "🌧️ Select Rain Date for Rain Analytics Section",
                rain_dates,
                format_func=lambda d: pd.to_datetime(d).strftime("%b %d, %Y") if hasattr(d, "strftime") else str(d)
            )
            rain_day_df = df[df["DT"] == selected_rain_date]

            # -- ZONE LEVEL PARTICIPATION RATE LOGIC --
            zone_participation = []
            for zone, city in rain_day_df[["ZONE", "CITY"]].drop_duplicates().values:
                # All DEs active in this zone in last LOOKBACK_DAYS before rain day
                lookback_start = pd.to_datetime(selected_rain_date) - pd.Timedelta(days=LOOKBACK_DAYS)
                base_DEs = df[(df["ZONE"] == zone) & (df["CITY"] == city) & 
                              (df["DT"] >= lookback_start.date()) & (df["DT"] < selected_rain_date) & (df["TOTAL LOGIN MINS"] > 0)]["DE_ID"].unique()
                # DEs who logged in on rain day
                rain_DEs = rain_day_df[(rain_day_df["ZONE"] == zone) & (rain_day_df["CITY"] == city) & (rain_day_df[rain_flag_col] == 1) & (rain_day_df["TOTAL LOGIN MINS"] > 0)]["DE_ID"].unique()
                rate = (len(rain_DEs) / len(base_DEs)) * 100 if len(base_DEs) else np.nan
                zone_participation.append({
                    "Zone": zone, "City": city, "Recent_Actives": len(base_DEs),
                    "Rain_Logins": len(rain_DEs),
                    "Rain_Participation_%": round(rate, 2) if not np.isnan(rate) else None
                })
            zone_part_df = pd.DataFrame(zone_participation)
            def color_code(val):
                if pd.isnull(val):
                    return "background-color: #eee"
                elif val < 50:
                    return "background-color: #ffcccc"   # Red
                elif val < 80:
                    return "background-color: #ffe699"   # Orange
                else:
                    return "background-color: #c6efce"   # Green
            st.dataframe(zone_part_df.style.applymap(color_code, subset=["Rain_Participation_%"]))
            st.download_button("📥 Download Zone Rain Participation (CSV)", data=zone_part_df.to_csv(index=False), file_name="zone_rain_participation.csv")

            # Bar chart: Rain Participation %
            if not zone_part_df.empty:
                bar_chart = alt.Chart(zone_part_df).mark_bar().encode(
                    x=alt.X("Zone:N", sort="-y", title="Zone"),
                    y=alt.Y("Rain_Participation_%:Q", title="Rain Participation %"),
                    color=alt.Color("Rain_Participation_%:Q",
                        scale=alt.Scale(domain=[0, 50, 80, 100], range=["#e53935", "#fb8c00", "#43a047", "#43a047"]),
                        legend=None),
                    tooltip=["Zone", "City", "Recent_Actives", "Rain_Logins", "Rain_Participation_%"]
                ).properties(height=360, title="Rain Participation % by Zone")
                st.altair_chart(bar_chart, use_container_width=True)

            # -- INDIVIDUAL LEVEL LOGIC: Rain Skippers --
            all_recent = df[(df["DT"] >= (pd.to_datetime(selected_rain_date) - pd.Timedelta(days=LOOKBACK_DAYS)).date()) &
                            (df["DT"] < selected_rain_date) & (df["TOTAL LOGIN MINS"] > 0)]
            recent_de_ids = all_recent["DE_ID"].unique()
            de_table = []
            for de_id in recent_de_ids:
                de_rows = df[df["DE_ID"] == de_id]
                zones = de_rows["ZONE"].unique()
                city = de_rows["CITY"].iloc[0] if "CITY" in de_rows.columns else ""
                de_name = de_rows["DE_NAME"].iloc[0] if "DE_NAME" in de_rows.columns else ""
                was_active = (de_rows[(de_rows["DT"] >= (pd.to_datetime(selected_rain_date) - pd.Timedelta(days=LOOKBACK_DAYS)).date()) & 
                                      (de_rows["DT"] < selected_rain_date) & (de_rows["TOTAL LOGIN MINS"] > 0)]).shape[0] > 0
                rain_login = (de_rows[(de_rows["DT"] == selected_rain_date) & (de_rows[rain_flag_col] == 1) & (de_rows["TOTAL LOGIN MINS"] > 0)]).shape[0] > 0
                rain_skip = "Yes" if (was_active and not rain_login) else "No"
                de_table.append({
                    "DE_ID": de_id,
                    "DE_NAME": de_name,
                    "Zone(s)": ', '.join(zones),
                    "City": city,
                    "Was_Active_Last_14d": "Yes" if was_active else "No",
                    "Logged_in_on_Rain": "Yes" if rain_login else "No",
                    "Rain_Skipper": rain_skip
                })
            de_df = pd.DataFrame(de_table)
            st.markdown("### 🔎 DE-Level Rain Skippers Table")
            st.dataframe(de_df)
            st.download_button("📥 Download Rain Skippers Table (CSV)", data=de_df.to_csv(index=False), file_name="rain_skippers_full.csv")

    # ---------------------- REST OF YOUR APP (UNCHANGED) ----------------------
    # --- All your original views remain below: DEs Logged In Per Day, Attrition Risk, DE-wise View, No-Shows, etc. ---
    # [Place all those blocks here, unchanged. If you want me to append ALL those code blocks in this answer, just ask and I'll paste them in full.]

else:
    st.info("👆 Upload your DE Order vs Login File to get started.")
