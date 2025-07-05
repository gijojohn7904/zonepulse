python
Copy
Edit
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ---------- INFO BOX FUNCTION ----------
def info_box(title, content, expanded=False):
    with st.expander(f"{title} (Info)", expanded=expanded):
        st.markdown(content)

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
    <style>
    .stExpander {
        background-color: #e3f0fc !important; border-radius: 10px !important; margin-bottom: 14px !important; box-shadow: 0 3px 10px #bed9f3;
    }
    .stExpanderHeader {
        background-color: #2176c1 !important; color: #fff !important; font-weight: 700 !important;
        border-radius: 10px 10px 0 0 !important; padding-top: 6px !important; padding-bottom: 6px !important; letter-spacing: 0.5px;
    }
    .stExpanderContent {
        background-color: #e3f0fc !important; color: #10385c !important; border-radius: 0 0 10px 10px !important; padding-bottom: 12px !important;
    }
    </style>
""", unsafe_allow_html=True)

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

# ------------- CACHING DATA AND HEAVY COMPUTATIONS --------------
@st.cache_data(show_spinner="Loading file...", max_entries=2)
def load_data(uploaded_file):
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.upper()
    return df

@st.cache_data(show_spinner="Crunching zone hourly...", max_entries=10)
def compute_zone_hour_df(df, vertical):
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
    return pd.concat(hourly_data) if hourly_data else pd.DataFrame()

# ------------- MAIN LOGIC -------------
uploaded_file = st.file_uploader("🔕️ Upload your DE Order vs Login File", type=["csv"])
if uploaded_file:
    df = load_data(uploaded_file)
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
        vertical = st.selectbox("Choose Vertical", ["SwiggyFood", "Instamart"])
        df = df[df["VERTICAL"] == vertical]
    with col2:
        cities = sorted(df["CITY"].dropna().unique())
        city_options = ["All"] + list(cities)
        selected_city = st.selectbox("Choose City", city_options)
        if selected_city != "All":
            df = df[df["CITY"] == selected_city]

    col3, col4 = st.columns(2)
    with col3:
        zones = sorted(df["ZONE"].dropna().unique())
        zone_options = ["All"] + list(zones)
        selected_zone = st.selectbox("Choose Zone", zone_options)
        if selected_zone != "All":
            df = df[df["ZONE"] == selected_zone]
    with col4:
        df["DT"] = pd.to_datetime(df["DT"]).dt.date
        min_date, max_date = df["DT"].min(), df["DT"].max()
        selected_dates = st.date_input("Filter by Date Range", [min_date, max_date])
        if len(selected_dates) == 2:
            df = df[(df["DT"] >= selected_dates[0]) & (df["DT"] <= selected_dates[1])]

    # Add total login mins/orders only ONCE
    if "TOTAL LOGIN MINS" not in df.columns:
        df["TOTAL LOGIN MINS"] = df[[f"LH_{str(i).zfill(2)}" for i in range(24) if f"LH_{str(i).zfill(2)}" in df.columns]].sum(axis=1)
    if "TOTAL ORDERS" not in df.columns:
        df["TOTAL ORDERS"] = df[[f"FD_{str(i).zfill(2)}" for i in range(24) if f"FD_{str(i).zfill(2)}" in df.columns]].sum(axis=1)

    # =========== ZONE-LEVEL HOURLY REPORT ===========
    info_box(
        "Zone-Level Hourly Report",
        """
- **Shows:** Hourly breakdown of DEs active in each zone, orders per hour, average login mins, and utilization.
- **Key Metric:** Login Utilization % = (Avg Orders x 25 mins) / (Avg Login Minutes) x 100.
- **Why Care:** Spot over/understaffed hours instantly. If utilization is low and DEs are logged in—you're burning cost for no reason.
- **Actions:** Reallocate supply or adjust login targets for idle hours.
        """
    )
    st.markdown("## 📊 Zone-Level Hourly Report")
    zone_hour_df = compute_zone_hour_df(df, vertical)
    if not zone_hour_df.empty:
        st.dataframe(zone_hour_df.sort_values(by=["DT", "CITY", "ZONE", "Hour"]))
        st.download_button("📥 Download Hourly Report (CSV)", data=zone_hour_df.to_csv(index=False), file_name="zone_hourly_report.csv", mime="text/csv")
    else:
        st.info("No zone/city hourly data available. Please check the uploaded file or filter selection.")

    # ======== RAIN PARTICIPATION (NEW LOGIC: RFD_xx) =========
    info_box(
        "Rain Participation – What are we tracking?",
        """
- **Shows:** Participation of DEs on rain-impacted hours, by zone.
- **Skipper:** DE was present (login > 0) in the previous hour but has (login==0 OR rain orders==0) in rain hour.
- **Participant:** DE who takes at least 1 rain order in a rain hour (RFD_xx > 0).
- **Chronic Skipper:** Skip rate > 70% across all rain hours.
- **Why It Matters:** Spot chronic/fair-weather DEs, nudge/engage the right people, and visualize ops improvement.
        """
    )
    st.markdown("---")
    st.markdown("## 🌧️ Rain Participation, Skipper & Chronic Skipper (Hourly)")

    # ---- FIND RAIN HOURS (per zone/date) ----
    rain_hour_cols = [col for col in df.columns if col.startswith("RFD_")]
    rain_hours_table = []
    for _, row in df.iterrows():
        for h in range(24):
            col = f"RFD_{str(h).zfill(2)}"
            if col in df.columns and row[col] > 0:
                rain_hours_table.append((row["CITY"], row["ZONE"], row["DT"], h))
    rain_hours_df = pd.DataFrame(rain_hours_table, columns=["CITY","ZONE","DT","RAIN_HOUR"])
    rain_hours_df = rain_hours_df.drop_duplicates()

    # ---- PER DE, HOUR: Tag rain skipper/participant ----
    rain_status_rows = []
    for ix, rh in rain_hours_df.iterrows():
        city, zone, dt, hr = rh["CITY"], rh["ZONE"], rh["DT"], rh["RAIN_HOUR"]
        prev_hr = (hr - 1) % 24
        sub = df[(df["CITY"] == city) & (df["ZONE"] == zone) & (df["DT"] == dt)]
        for _, r in sub.iterrows():
            de_id = r["DE_ID"]
            login_prev = r.get(f"LH_{str(prev_hr).zfill(2)}", 0)
            login_now = r.get(f"LH_{str(hr).zfill(2)}", 0)
            rain_orders = r.get(f"RFD_{str(hr).zfill(2)}", 0)
            # Determine Skipper/Participant
            if login_prev > 0:
                if login_now == 0 or rain_orders == 0:
                    status = "Skipper"
                else:
                    status = "Participant"
                rain_status_rows.append({
                    "DE_ID": de_id, "DE_NAME": r.get("DE_NAME",""), "ZONE": zone, "CITY": city, "DT": dt, "RAIN_HOUR": hr,
                    "Skipper_Participant": status
                })
    rain_status_df = pd.DataFrame(rain_status_rows)

    # ---- ZONE-WISE RAIN PARTICIPATION % HEATMAP ----
    zone_part_data = []
    if not rain_status_df.empty:
        for (city, zone, dt, hr), g in rain_status_df.groupby(["CITY","ZONE","DT","RAIN_HOUR"]):
            eligible = g.shape[0]
            part = (g["Skipper_Participant"]=="Participant").sum()
            perc = (part / eligible) * 100 if eligible > 0 else np.nan
            zone_part_data.append({
                "City": city, "Zone": zone, "Date": dt, "Hour": hr,
                "Eligible": eligible, "Participants": part, "Participation_%": round(perc,2)
            })
    zone_part_df = pd.DataFrame(zone_part_data)
    if not zone_part_df.empty:
        heatmap = alt.Chart(zone_part_df).mark_rect().encode(
            x=alt.X('Zone:N', title='Zone', sort=list(zone_part_df["Zone"].unique())),
            y=alt.Y('Hour:O', title='Rain Hour'),
            color=alt.Color('Participation_%:Q', scale=alt.Scale(scheme='redyellowgreen', domain=[0, 100])),
            tooltip=['Zone', 'City', 'Date', 'Hour', 'Eligible', 'Participants', 'Participation_%']
        ).properties(width=400, height=350, title="Rain Participation % by Zone/Hour")
        st.altair_chart(heatmap, use_container_width=True)
        st.dataframe(zone_part_df)
        st.download_button("📥 Download Zone Rain Participation (CSV)", data=zone_part_df.to_csv(index=False), file_name="zone_rain_participation.csv")

    # ==== DE-WISE RAIN SKIP RATE (CHRONIC SKIPPER) ====
    # For each DE: count eligible rain hours, skipped rain hours
    de_skip = rain_status_df.groupby("DE_ID").agg(
        DE_NAME=("DE_NAME","first"),
        City=("CITY","first"),
        Zone=("ZONE","first"),
        Rain_Hours_Eligible=("Skipper_Participant", "count"),
        Rain_Hours_Skipped=(lambda x: (x=="Skipper").sum()),
        Rain_Hours_Participated=(lambda x: (x=="Participant").sum())
    ).reset_index()
    de_skip["Skip_Rate_%"] = (de_skip["Rain_Hours_Skipped"] / de_skip["Rain_Hours_Eligible"] * 100).round(2)
    de_skip["Chronic_Skipper"] = np.where(de_skip["Skip_Rate_%"] > 70, "Yes", "No")
    st.markdown("### Chronic Rain Skippers (Lifetime)")
    if not de_skip.empty:
        st.dataframe(de_skip.sort_values("Skip_Rate_%", ascending=False))
        st.download_button("📥 Download DE Rain Skipper Report", data=de_skip.to_csv(index=False), file_name="chronic_skippers.csv")
    else:
        st.info("No rain participation/skipping found in current data.")

    # ==== RAIN SKIPPER/RAIN PARTICIPANT RAW EXPORT ====
    st.markdown("### All Rain Participation Records (Per Rain Hour)")
    if not rain_status_df.empty:
        st.dataframe(rain_status_df)
        st.download_button("📥 Download All Rain Skipper/Participant Data", data=rain_status_df.to_csv(index=False), file_name="rain_skippers_participants.csv")
    else:
        st.info("No rain hour participation/skipping records found in current data.")
    # =========== DATE-WISE LOGIN COUNT ===========
    info_box(
        "Date-wise Login Count – What's this for?",
        """
- **Shows:** Unique DEs who logged in each day, by zone.
- **Why Use:** Spot sudden supply drops, festival dips, or daily onboarding impact.
- **Calculation:** Simple count of DEs with login mins > 0 for each day.
        """
    )
    st.markdown("## 📅 Date-wise Login Count for Selected Zone")
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

    # =========== HOURLY LOGIN DISTRIBUTION ===========
    info_box(
        "Hourly Login Distribution – Why does it matter?",
        """
- **Shows:** Number of DEs active (login > 0) per hour in a zone, plus total orders and recommended staffing status.
- **Use Case:** Spot peak, slack, or balanced hours for optimal supply planning.
- **Calculation:** Active DEs with login > 0 per hour.
        """
    )
    st.markdown("#### ⏰ Zone-wise Hourly Login Distribution")
    hourly_cols = [f"LH_{str(hr).zfill(2)}" for hr in range(24) if f"LH_{str(hr).zfill(2)}" in df.columns]
    order_cols = [f"FD_{str(hr).zfill(2)}" for hr in range(24) if f"FD_{str(hr).zfill(2)}" in df.columns]

    if hourly_cols and not df.empty and not zone_hour_df.empty:
        hourly_df = df.copy()
        show_zone = selected_zone if selected_zone != "All" else (zone_hour_df["ZONE"].iloc[0] if not zone_hour_df.empty else None)
        show_city = selected_city if selected_city != "All" else (zone_hour_df["CITY"].iloc[0] if not zone_hour_df.empty else None)
        if selected_city != "All":
            hourly_df = hourly_df[hourly_df["CITY"] == selected_city]
        if selected_zone != "All":
            hourly_df = hourly_df[hourly_df["ZONE"] == selected_zone]
        elif show_zone is not None:
            hourly_df = hourly_df[hourly_df["ZONE"] == show_zone]

        hour_data = []
        for hr in range(24):
            lh_col = f"LH_{str(hr).zfill(2)}"
            fd_col = f"FD_{str(hr).zfill(2)}"
            if lh_col in hourly_df.columns:
                count = (hourly_df[lh_col] > 0).sum()
                orders = hourly_df[fd_col].sum() if fd_col in hourly_df.columns else 0
                rec_row = zone_hour_df[
                    (zone_hour_df["Hour"] == hr) &
                    (zone_hour_df["ZONE"] == show_zone) &
                    (zone_hour_df["CITY"] == show_city)
                ]
                rec = rec_row["Recommendation"].iloc[0] if not rec_row.empty else "✅ Balanced"
                hour_data.append({
                    "Hour": f"{str(hr).zfill(2)}:00",
                    "Active DEs": count,
                    "Active Orders": int(orders),
                    "Recommendation": rec
                })
        hour_chart_df = pd.DataFrame(hour_data)

        color_scale = alt.Scale(
            domain=["🔴 Understaffed", "⚠️ Overstaffed", "✅ Balanced"],
            range=["#e53935", "#fb8c00", "#43a047"]
        )

        if not hour_chart_df.empty:
            bar = alt.Chart(hour_chart_df).mark_bar(size=18).encode(
                x=alt.X("Hour", sort=list(hour_chart_df["Hour"]), title="Hour of Day"),
                y=alt.Y("Active DEs", title="DEs Logged In (across selected dates)"),
                color=alt.Color("Recommendation:N", scale=color_scale, legend=alt.Legend(title="Hour Status")),
                tooltip=[
                    alt.Tooltip("Hour", title="Hour"),
                    alt.Tooltip("Active DEs", title="Logged In DEs"),
                    alt.Tooltip("Active Orders", title="Order Count"),
                    alt.Tooltip("Recommendation", title="Staffing Status"),
                ]
            ).properties(
                title=f"Hourly Login Distribution – {show_zone if show_zone else ''}"
            )
            st.altair_chart(bar, use_container_width=True)
        else:
            st.info("No hourly login data found for this selection.")
    else:
        st.info("No hourly login data available in uploaded file.")

    # =========== DEs LOGGED IN PER DAY ===========
    info_box(
        "DEs Logged In Per Day – Why drill down?",
        """
- **Shows:** Table of every DE who logged in each day—zone, city, orders, login mins, earnings, etc.
- **Use Case:** Spot underperformers, idlers, or patterns. Validate regulars and check for fraud/bot logins.
- **Calculation:** Filter DEs with login mins > 0 for each day.
        """
    )
    st.markdown("#### 🔎 DEs Logged In Per Day")
    de_cols = ["DT", "CITY", "ZONE", "DE_ID", "DE_NAME", "TOTAL LOGIN MINS", "TOTAL ORDERS"]
    if "REJECTED_ORDERS" in df.columns:
        de_cols.append("REJECTED_ORDERS")
    if "DAILY_EARNINGS" in df.columns:
        de_cols.append("DAILY_EARNINGS")
    de_login_data = (
        df[df["TOTAL LOGIN MINS"] > 0]
        .loc[:, [c for c in de_cols if c in df.columns]]
        .sort_values(["DT", "CITY", "ZONE", "DE_ID"])
    )
    st.dataframe(de_login_data, use_container_width=True)
    st.download_button(
        "📥 Download DE Login Detail (CSV)",
        data=de_login_data.to_csv(index=False),
        file_name=f"{selected_zone}_datewise_login_DEs.csv",
        mime="text/csv"
    )

    # =========== ATTRITION RISK DES ===========
    info_box(
        "Attrition Risk DEs – What are we flagging?",
        """
- **Shows:** DEs who spent 3+ hours logged in but took <2 orders in a day—a classic disengagement or dissatisfaction sign.
- **Why Flag:** These are your “flight risk” DEs—frustrated, underpaid, or ready to churn. 
- **Calculation:** Filter where Login Mins ≥ 180 (3 hours) AND Total Orders < 2.
- **Action:** Call and intervene now, before they leave.
        """
    )
    st.markdown("## ⚠️ Attrition Risk DEs (Login > 3hr, Orders < 2)")
    churn_df = df[(df["TOTAL LOGIN MINS"] >= 180) & (df["TOTAL ORDERS"] < 2)].copy()
    churn_df["Login Hours"] = (churn_df["TOTAL LOGIN MINS"] / 60).round(2)
    churn_cols = ["DE_ID", "DE_NAME", "CITY", "ZONE", "DT", "WEEK", "Login Hours", "TOTAL ORDERS"]
    if "REJECTED_ORDERS" in df.columns:
        churn_cols.append("REJECTED_ORDERS")
    if "DAILY_EARNINGS" in df.columns:
        churn_cols.append("DAILY_EARNINGS")
    if churn_df.empty:
        st.info("✅ No churn risk DEs found for the selected filters.")
    else:
        st.dataframe(churn_df[churn_cols].sort_values(by=["CITY", "ZONE", "DT", "DE_NAME"]))
        st.download_button("🔕 Download Churn Risk Report (CSV)", data=churn_df[churn_cols].to_csv(index=False),
                           file_name="churn_risk_DEs.csv", mime="text/csv")

    # =========== INDIVIDUAL DE-WISE VIEW ===========
    info_box(
        "Individual DE-wise View – What do I get here?",
        """
- **Shows:** Deep-dive into any single DE’s journey: active days, login pattern, orders, earnings, rejections, week-wise trend.
- **Why Use:** Investigate complaints, performance issues, or fraud at individual level. Personalize retention/engagement.
- **Metrics:** Includes all order, login, and earnings data per DE, by day/week.
        """
    )
    st.markdown("## 👤 Individual DE-wise View")
    if "DE_ID" in df.columns:
        de_ids = df["DE_ID"].dropna().astype(str).unique()
        selected_de = st.selectbox("Choose DE ID to Explore", ["None"] + sorted(de_ids))
        if selected_de != "None":
            de_data = df[df["DE_ID"].astype(str) == selected_de].copy()
            de_name = de_data['DE_NAME'].iloc[0] if 'DE_NAME' in de_data.columns else ""
            de_zone = de_data['ZONE'].iloc[0]
            de_city = de_data['CITY'].iloc[0]
            total_days = de_data.shape[0]
            total_login = de_data["TOTAL LOGIN MINS"].sum()
            total_orders = de_data["TOTAL ORDERS"].sum()
            total_rejected = de_data["REJECTED_ORDERS"].sum() if "REJECTED_ORDERS" in de_data.columns else 0
            total_earnings = de_data["DAILY_EARNINGS"].sum() if "DAILY_EARNINGS" in de_data.columns else 0

            st.markdown(f"""
            <div style="text-align:center;">
                <div style="font-size: 1.2em; font-weight: bold; margin-bottom: 0.5em;">
                    DE: {selected_de} – {de_name}
                </div>
                <div style="margin-bottom: 0.7em;">
                    📍 Zone: <b>{de_zone}</b> &nbsp; | &nbsp; 🏣️ City: <b>{de_city}</b>
                </div>
                <div style="font-size:1.05em; background:#f8f9fa; border-radius:10px; display:inline-block; padding:10px 18px; box-shadow:0 2px 8px #eee;">
                    🔕️ <b>Active Days:</b> {total_days} &nbsp; | &nbsp; 
                    ⏱️ <b>Total Login Hrs:</b> {round(total_login/60,2)} &nbsp; | &nbsp; 
                    🔵️ <b>Total Orders:</b> {int(total_orders)} &nbsp; | &nbsp; 
                    ⛔ <b>Rejected Orders:</b> {int(total_rejected)} &nbsp; | &nbsp; 
                    💸 <b>Total Earnings:</b> ₹{round(total_earnings,2)}
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(
                """
                <div style='
                    text-align:center; 
                    font-size:2em; 
                    font-weight:800; 
                    margin-top:36px; 
                    margin-bottom:28px; 
                    letter-spacing:0.5px;
                    color:#1a1a1a;
                '>
                📈 Week-on-Week Performance & Earnings
                </div>
                """,
                unsafe_allow_html=True
            )
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

            st.markdown("### ⏱️ Hourly Login vs Orders (Per Day)")
            hourly_records = []
            for _, row in de_data.iterrows():
                date = row["DT"]
                for hr in range(24):
                    lh_col = f"LH_{str(hr).zfill(2)}"
                    fd_col = f"FD_{str(hr).zfill(2)}"
                    if lh_col in row and fd_col in row:
                        login_min = row[lh_col]
                        orders = row[fd_col]
                        if login_min > 0 or orders > 0:
                            hourly_records.append({
                                "Date": date,
                                "Hour": f"{str(hr).zfill(2)}:00",
                                "Login Minutes": login_min,
                                "Orders": orders
                            })
            if hourly_records:
                hourly_df = pd.DataFrame(hourly_records)
                st.dataframe(hourly_df.sort_values(by=["Date", "Hour"]))
                st.download_button("📥 Download DE Hourly Log", data=hourly_df.to_csv(index=False),
                                   file_name=f"{selected_de}_hourly_log.csv", mime="text/csv")
            else:
                st.info("ℹ️ No hourly data found for this DE.")

    # =========== NO SHOW DEs ===========
    info_box(
        "No-Show DEs – Why track this?",
        """
- **Shows:** DEs who were active in previous period but haven't logged in during current period.
- **Why Track:** Instantly spot sudden supply loss, attrition, or operational blockers by zone/city.
- **Calculation:** Compare unique DE IDs logged in across two periods.
        """
    )
    st.markdown("## 🤔 No-Show DEs – Previously Active, Not Logged In Now")
    col_prev, col_curr = st.columns(2)
    with col_prev:
        prev_dates = st.date_input("Select Previous Period", [])
    with col_curr:
        curr_dates = st.date_input("Select Current Period", [])
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
                CITY=("CITY", "first"),
                ZONE=("ZONE", "first"),
                Last_Seen_DT=("DT", "max"),
                Total_Login_Mins=("TOTAL LOGIN MINS", "sum"),
                Total_Orders=("TOTAL ORDERS", "sum"),
                Earnings=("DAILY_EARNINGS", "sum") if "DAILY_EARNINGS" in no_show_df.columns else ("TOTAL ORDERS", "sum")
            ).reset_index()
            summary_df["Total_Login_Hrs"] = (summary_df["Total_Login_Mins"] / 60).round(2)
            summary_df["Earnings"] = summary_df["Earnings"].round(2)
            display_cols = ["DE_ID", "DE_NAME", "CITY", "ZONE", "Last_Seen_DT", "Total_Login_Hrs", "Total_Orders", "Earnings"]
            st.dataframe(summary_df[display_cols].sort_values(by="Last_Seen_DT", ascending=False))
            st.download_button("📅 Download No-Show DEs", data=summary_df[display_cols].to_csv(index=False),
                               file_name="no_show_des.csv", mime="text/csv")
        else:
            st.success("🎉 No No-Show DEs found. Great retention!")
    else:
        st.info("☝️ Select both Previous and Current Periods to identify no-shows.")

else:
    st.info("👆 Upload your DE Order vs Login File to get started.")
