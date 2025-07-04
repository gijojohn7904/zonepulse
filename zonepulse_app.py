import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ---------------------- PASSWORD GATE ----------------------
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

check_password()  # 🔒 Enforce password before running further

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
        city_options = ["All"] + cities
        selected_city = st.selectbox("🏩 Choose City", city_options)
        if selected_city != "All":
            df = df[df["CITY"] == selected_city]

    col3, col4 = st.columns(2)
    with col3:
        zones = sorted(df["ZONE"].dropna().unique())
        zone_options = ["All"] + zones
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
                    lambda row: "Overstaffed" if (row["Avg_Orders"] / (row["Avg_Login_Mins"] / 60) < 1.2 and row["Login_Utilization_%"] < 30)
                    else "Understaffed" if (row["Avg_Orders"] / (row["Avg_Login_Mins"] / 60) > 2.2 and row["Login_Utilization_%"] > 70)
                    else "Balanced",
                    axis=1
                )
            else:
                zone_group["Recommendation"] = zone_group.apply(
                    lambda row: "Overstaffed" if (row["Avg_Orders"] / (row["Avg_Login_Mins"] / 60) < 1 and row["Login_Utilization_%"] < 50)
                    else "Understaffed" if (row["Avg_Orders"] / (row["Avg_Login_Mins"] / 60) > 1.2 and row["Login_Utilization_%"] > 57)
                    else "Balanced",
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

    # ---------------------- DATE-WISE LOGIN COUNT (POINTED LINE CHART W/ TOOLTIP) ----------------------
    st.markdown("## 📅 Date-wise Login Count for Selected Zone")
    if not zone_hour_df.empty:
        group_fields = ["DT", "CITY", "ZONE"]
        login_chart_rows = []
        all_dates = sorted(df["DT"].unique())
        all_zones = [selected_zone] if selected_zone != "All" else sorted(df["ZONE"].unique())
        all_cities = [selected_city] if selected_city != "All" else sorted(df["CITY"].unique())
        for city in all_cities:
            for zone in all_zones:
                for dt in all_dates:
                    hours = zone_hour_df[(zone_hour_df["DT"] == dt) & (zone_hour_df["ZONE"] == zone) & (zone_hour_df["CITY"] == city)]
                    hour_status_list = [f"Hour {h}: {rec}" for h, rec in zip(hours["Hour"], hours["Recommendation"])]
                    count_under = sum("Understaffed" in rec for rec in hours["Recommendation"])
                    count_over = sum("Overstaffed" in rec for rec in hours["Recommendation"])
                    count_bal = sum("Balanced" in rec for rec in hours["Recommendation"])
                    n_hours = count_under + count_over + count_bal
                    if n_hours == 0:
                        maj_status = ""
                    elif count_under > 12:
                        maj_status = "Understaffed"
                    elif count_over > 12:
                        maj_status = "Overstaffed"
                    else:
                        maj_status = "Balanced"
                    n_logged_in = df[(df["DT"] == dt) & (df["ZONE"] == zone) & (df["CITY"] == city) & (df["TOTAL LOGIN MINS"] > 0)]["DE_ID"].nunique()
                    login_chart_rows.append({
                        "DT": dt, "CITY": city, "ZONE": zone,
                        "Login Count": n_logged_in,
                        "Day Status": maj_status if maj_status else "No Data",
                        "Hourly Detail": "\n".join(hour_status_list)
                    })
        chart_df = pd.DataFrame(login_chart_rows)
        chart_df = chart_df[(chart_df["Login Count"] > 0) & (chart_df["Day Status"] != "No Data")]
        if not chart_df.empty:
            chart = alt.Chart(chart_df).mark_line(point={"filled": True, "fill": "red", "size": 80}).encode(
                x=alt.X("DT:T", title="Date"),
                y=alt.Y("Login Count", title="No. of DEs Logged In"),
                color=alt.Color("Day Status:N", legend=alt.Legend(title="Staffing Status")),
                tooltip=[
                    alt.Tooltip("DT:T", title="Date"),
                    alt.Tooltip("CITY", title="City"),
                    alt.Tooltip("ZONE", title="Zone"),
                    alt.Tooltip("Login Count", title="DEs Logged In"),
                    alt.Tooltip("Day Status", title="Day Status"),
                    alt.Tooltip("Hourly Detail", title="Hour-wise Status", format="string")
                ]
            ).properties(
                title=f"Login Count per Day – {selected_zone if selected_zone != 'All' else 'All Zones'}"
            ).interactive()
            st.altair_chart(chart, use_container_width=True)
            st.download_button(
                "📥 Download Login Status Detail (CSV)",
                data=chart_df.to_csv(index=False),
                file_name=f"{selected_zone if selected_zone != 'All' else 'All'}_{selected_city if selected_city != 'All' else 'All'}_datewise_login_status.csv",
                mime="text/csv"
            )
        else:
            st.info("No login or staffing data for this selection.")

        # Table of DEs logged in per day
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
            file_name=f"{selected_zone if selected_zone != 'All' else 'All'}_{selected_city if selected_city != 'All' else 'All'}_datewise_login_DEs.csv",
            mime="text/csv"
        )
    else:
        st.info("No login data for chart/table.")

    # ---------------------- ATTRITION RISK DES ----------------------
    st.markdown("## ⚠️ Attrition Risk DEs (Login > 3hr, Orders < 2)")
    churn_df = df[(df["TOTAL LOGIN MINS"] >= 180) & (df["TOTAL ORDERS"] < 2)]
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

    # ---------------------- INDIVIDUAL DE-WISE VIEW ----------------------
    st.markdown("## 👤 Individual DE-wise View")
    if "DE_ID" in df.columns:
        de_ids = df["DE_ID"].dropna().astype(str).unique()
        selected_de = st.selectbox("😮 Choose DE ID to Explore", ["None"] + sorted(de_ids))
        if selected_de != "None":
            de_data = df[df["DE_ID"].astype(str) == selected_de].copy()
            de_name = de_data['DE_NAME'].iloc[0]
            de_zone = de_data['ZONE'].iloc[0]
            de_city = de_data['CITY'].iloc[0]

            total_days = de_data.shape[0]
            total_login = de_data["TOTAL LOGIN MINS"].sum()
            total_orders = de_data["TOTAL ORDERS"].sum()
            total_rejected = de_data["REJECTED_ORDERS"].sum() if "REJECTED_ORDERS" in de_data.columns else 0
            total_earnings = de_data["DAILY_EARNINGS"].sum() if "DAILY_EARNINGS" in de_data.columns else 0

            # Centered DE header
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

            # --- BIG & BOLD Week-on-Week Performance header ---
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

            # --- Login Minutes vs Total Orders ---
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

            # --- Hourly Login vs Orders (Per Day) ---
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

    # ---------------------- NO SHOW DEs ----------------------
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
