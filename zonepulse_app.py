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

    # User filter: Rain DE, Non-Rain DE (rain day, no orders), Non-Rain DE (never worked on rain day), All
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
