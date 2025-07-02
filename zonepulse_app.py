import streamlit.components.v1 as components
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

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

uploaded_file = st.file_uploader("🔕️ Upload your DE Order vs Login File", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip().str.upper()

    required_cols = [col for col in df.columns if "LH_" in col or "FD_" in col]
    if len(required_cols) == 0:
        st.error("❌ Your CSV must contain hourly login/order columns like LH_00, FD_01 etc.")
        st.stop()

    df["VERTICAL"] = df["DE_SHIFT"].apply(lambda x: "Instamart" if any(tag in str(x).upper() for tag in ["IM", "DDE"]) else "SwiggyFood")

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

    df["TOTAL LOGIN MINS"] = df[[f"LH_{str(i).zfill(2)}" for i in range(24) if f"LH_{str(i).zfill(2)}" in df.columns]].sum(axis=1)
    df["TOTAL ORDERS"] = df[[f"FD_{str(i).zfill(2)}" for i in range(24) if f"FD_{str(i).zfill(2)}" in df.columns]].sum(axis=1)

    # -------------------- ZONE LEVEL HOURLY REPORT --------------------
    hourly_data = []
    for hr in range(24):
        fd_col = f"FD_{str(hr).zfill(2)}"
        lh_col = f"LH_{str(hr).zfill(2)}"

        if fd_col in df.columns and lh_col in df.columns:
            hour_df = df[df[lh_col] > 10]
            if hour_df.empty:
                continue

            zone_group = hour_df.groupby("ZONE").agg(
                Total_Orders=(fd_col, 'sum'),
                Avg_Orders=(fd_col, 'mean'),
                Avg_Login_Mins=(lh_col, 'mean'),
                Active_DEs=(lh_col, lambda x: (x > 10).sum())
            ).reset_index()

            zone_group["Hour"] = hr
            zone_group["Login_Utilization_%"] = zone_group.apply(
                lambda row: min(100, (row["Avg_Orders"] * 25 / row["Avg_Login_Mins"]) * 100) if row["Avg_Login_Mins"] > 0 else 0,
                axis=1)

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
        st.markdown("## 📊 Zone-Level Hourly Report")
        st.dataframe(zone_hour_df.sort_values(by=["ZONE", "Hour"]))

    # ------------------- ATTRITION RISK DEs -------------------
    st.markdown("## ⚠️ Attrition Risk DEs (Login > 3hr, Orders < 2)")
    churn_df = df[(df["TOTAL LOGIN MINS"] >= 180) & (df["TOTAL ORDERS"] < 2)]
    churn_df["Login Hours"] = (churn_df["TOTAL LOGIN MINS"] / 60).round(2)
    churn_cols = ["DE_ID", "DE_NAME", "ZONE", "DT", "WEEK", "Login Hours", "TOTAL ORDERS"]
    if "REJECTED_ORDERS" in df.columns:
        churn_cols.append("REJECTED_ORDERS")
    if "DAILY_EARNINGS" in df.columns:
        churn_cols.append("DAILY_EARNINGS")

    if churn_df.empty:
        st.info("✅ No churn risk DEs found for the selected filters.")
    else:
        st.dataframe(churn_df[churn_cols].sort_values(by=["ZONE", "DT", "DE_NAME"]))
        st.download_button("🔕 Download Churn Risk Report (CSV)", data=churn_df[churn_cols].to_csv(index=False), file_name="churn_risk_DEs.csv", mime="text/csv")

    # ------------------- INDIVIDUAL DE-WISE VIEW -------------------
    st.markdown("## 👤 Individual DE-wise View")
    if "DE_ID" in df.columns:
        de_ids = df["DE_ID"].dropna().astype(str).unique()
        selected_de = st.selectbox("😮 Choose DE ID to Explore", ["None"] + sorted(de_ids))
        if selected_de != "None":
            de_data = df[df["DE_ID"].astype(str) == selected_de].copy()
            st.markdown(f"### DE: {selected_de} – {de_data['DE_NAME'].iloc[0]}")
            st.markdown(f"**📍 Zone:** {de_data['ZONE'].iloc[0]}  |  🏣️ **City:** {de_data['CITY'].iloc[0]}")

            total_days = de_data.shape[0]
            total_login = de_data["TOTAL LOGIN MINS"].sum()
            total_orders = de_data["TOTAL ORDERS"].sum()
            avg_orders_per_hour = round(total_orders / (total_login / 60), 2) if total_login > 0 else 0
            idle_ratio = round(total_login / (total_orders * 25), 2) if total_orders > 0 else np.nan
            total_rejected = de_data["REJECTED_ORDERS"].sum() if "REJECTED_ORDERS" in de_data.columns else 0
            total_earnings = de_data["DAILY_EARNINGS"].sum() if "DAILY_EARNINGS" in de_data.columns else 0
            weekly_ded = de_data["WEEKLY_DEDUCTIONS"].fillna(0).sum() if "WEEKLY_DEDUCTIONS" in de_data.columns else 0
            daily_ded = de_data["OTHER_DAILY_DEDUCTIONS"].fillna(0).sum() if "OTHER_DAILY_DEDUCTIONS" in de_data.columns else 0
            total_deductions = weekly_ded + daily_ded

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("🔕️ Active Days", total_days)
            col2.metric("⏱️ Total Login Hrs", round(total_login / 60, 2))
            col3.metric("🔵️ Total Orders", int(total_orders))
            col4.metric("⚖️ Idle Ratio", round(idle_ratio, 2) if not np.isnan(idle_ratio) else "∞")

            col5, col6, col7 = st.columns(3)
            col5.metric("⛔ Rejected Orders", int(total_rejected))
            col6.metric("💸 Total Earnings", f"₹{round(total_earnings, 2)}")
            col7.metric("🧾 Total Deductions", f"₹{round(total_deductions, 2)}")

            st.markdown("### 📈 Week-on-Week Performance (4 Metrics)")
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
                st.download_button("📥 Download DE Hourly Log", data=hourly_df.to_csv(index=False), file_name=f"{selected_de}_hourly_log.csv", mime="text/csv")
            else:
                st.info("ℹ️ No hourly data found for this DE.")

    # ---------------- RAIN DAY PARTICIPATION WITH NO-SHOW LOGIC ----------------
    st.markdown("## 🌧️ Rain Day Participation Analysis")
    if "RAIN_FLAG" in df.columns and "DE_ID" in df.columns:
        # Ensure WEEK is present for weekwise logic
        df["WEEK"] = pd.to_datetime(df["DT"]).astype("datetime64[W]")

        rain_dates = df[df["RAIN_FLAG"] == 1]["DT"].unique()
        total_rain_days = len(rain_dates)

        # --- Rain DE: Worked and took at least one order (delivered or rejected) on rain day
        rain_day_df = df[(df["DT"].isin(rain_dates)) & (df["RAIN_FLAG"] == 1) & (df["TOTAL LOGIN MINS"] > 0)]
        rain_de_df = rain_day_df[
            (rain_day_df["TOTAL ORDERS"] > 0) |
            (rain_day_df["REJECTED_ORDERS"] > 0 if "REJECTED_ORDERS" in df.columns else False)
        ]
        rain_de_participation = rain_de_df.groupby("DE_ID").agg(
            DE_NAME=("DE_NAME", "first"),
            Rain_Days_Worked=("DT", "nunique")
        ).reset_index()
        rain_de_participation["Rain_DE_Type"] = "Rain DE"

        # --- Non-Rain DE: Logged in on rain day, but no orders
        non_rain_de_df = rain_day_df[
            ~(
                (rain_day_df["TOTAL ORDERS"] > 0) |
                (rain_day_df["REJECTED_ORDERS"] > 0 if "REJECTED_ORDERS" in df.columns else False)
            )
        ]
        non_rain_de_participation = non_rain_de_df.groupby("DE_ID").agg(
            DE_NAME=("DE_NAME", "first"),
            Rain_Days_Worked=("DT", "nunique")
        ).reset_index()
        non_rain_de_participation["Rain_DE_Type"] = "Non-Rain DE"

        # --- No-Show DE: Never logged in on rain day, but active in the same week before rain day
        no_show_rows = []
        rain_days_df = df[df["DT"].isin(rain_dates)].copy()
        for rain_dt in rain_dates:
            rain_dt = pd.to_datetime(rain_dt)
            week_start = rain_dt - pd.to_timedelta(rain_dt.weekday(), unit='D')
            week_df = df[(df["WEEK"] == week_start)]
            rain_day_ids = week_df[(week_df["DT"] == rain_dt.date()) & (week_df["TOTAL LOGIN MINS"] == 0)]["DE_ID"].unique()
            for de in rain_day_ids:
                # Check if DE was active earlier that week before rain day
                prior_days = week_df[
                    (week_df["DE_ID"] == de) &
                    (week_df["DT"] < rain_dt.date()) &
                    (week_df["TOTAL LOGIN MINS"] > 0)
                ]
                if not prior_days.empty:
                    no_show_rows.append({"DE_ID": de, "Rain_DT": rain_dt.date()})

        no_show_de_ids = pd.DataFrame(no_show_rows)["DE_ID"].unique() if no_show_rows else []

        # --- Participation Table
        all_des = df[["DE_ID", "DE_NAME"]].drop_duplicates()
        all_participation = pd.concat([rain_de_participation, non_rain_de_participation], ignore_index=True)
        all_participation = all_des.merge(all_participation, on=["DE_ID", "DE_NAME"], how="left")
        all_participation["Rain_Days_Worked"] = all_participation["Rain_Days_Worked"].fillna(0).astype(int)

        def rain_type(row):
            if row["DE_ID"] in rain_de_participation["DE_ID"].values:
                return "Rain DE"
            elif row["DE_ID"] in non_rain_de_participation["DE_ID"].values:
                return "Non-Rain DE"
            elif row["DE_ID"] in no_show_de_ids:
                return "No-Show DE (Never logged in on rain day, but active in week)"
            else:
                return "No Rain Login"

        all_participation["Rain_DE_Type"] = all_participation.apply(rain_type, axis=1)
        all_participation["Total_Rain_Days"] = total_rain_days
        all_participation["Participation_%"] = (
            (all_participation["Rain_Days_Worked"] / total_rain_days) * 100
        ).round(2) if total_rain_days > 0 else 0

        filter_type = st.selectbox(
            "Filter by Rain Participation",
            ["Rain DE", "Non-Rain DE", "No-Show DE (Never logged in on rain day, but active in week)", "All DEs"]
        )
        if filter_type == "Rain DE":
            show_df = all_participation[all_participation["Rain_DE_Type"] == "Rain DE"]
        elif filter_type == "Non-Rain DE":
            show_df = all_participation[all_participation["Rain_DE_Type"] == "Non-Rain DE"]
        elif filter_type == "No-Show DE (Never logged in on rain day, but active in week)":
            show_df = all_participation[all_participation["Rain_DE_Type"] == "No-Show DE (Never logged in on rain day, but active in week)"]
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

    # ---------------- NO-SHOW DEs SECTION ----------------
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
                ZONE=("ZONE", "first"),
                CITY=("CITY", "first"),
                Last_Seen_DT=("DT", "max"),
                Total_Login_Mins=("TOTAL LOGIN MINS", "sum"),
                Total_Orders=("TOTAL ORDERS", "sum"),
                Earnings=("DAILY_EARNINGS", "sum") if "DAILY_EARNINGS" in no_show_df.columns else ("TOTAL ORDERS", "sum")
            ).reset_index()

            summary_df["Total_Login_Hrs"] = (summary_df["Total_Login_Mins"] / 60).round(2)
            summary_df["Earnings"] = summary_df["Earnings"].round(2)

            display_cols = ["DE_ID", "DE_NAME", "CITY", "ZONE", "Last_Seen_DT", "Total_Login_Hrs", "Total_Orders", "Earnings"]
            st.dataframe(summary_df[display_cols].sort_values(by="Last_Seen_DT", ascending=False))
            st.download_button("📅 Download No-Show DEs", data=summary_df[display_cols].to_csv(index=False), file_name="no_show_des.csv", mime="text/csv")
        else:
            st.success("🎉 No No-Show DEs found. Great retention!")
    else:
        st.info("☝️ Select both Previous and Current Periods to identify no-shows.")

else:
    st.info("👆 Upload your DE Order vs Login File to get started.")
