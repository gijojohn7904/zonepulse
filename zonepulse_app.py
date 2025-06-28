WITH de_hourly_perf AS (
    SELECT 
        pa.de_id,
        TO_DATE(pa.date, 'YYYY-MM-DD') AS perf_date,
        pa.hour,
        c.name AS zone,
        COALESCE(CAST(JSON_VALUE(pa.PERF_BLOB, '$.login_minutes') AS FLOAT), 0) AS login_mins,
        ARRAY_SIZE(PARSE_JSON(pa.PERF_BLOB):delivered_order_ids) AS orders
    FROM "ALCHEMIST"."ALCHEMIST"."DE_PERFORMANCE_DAILY" pa
    LEFT JOIN "DE"."SWIGGY"."DE_INFO" di ON pa.de_id = di.de_id
    LEFT JOIN "DE"."SWIGGY"."CITY" c ON di.city_id = c.id
    WHERE TO_DATE(pa.date, 'YYYY-MM-DD') BETWEEN '2025-06-01' AND CURRENT_DATE - 1
      AND c.name IN ('Madurai', 'Pondicherry', 'Tirupur', 'Palladam', 'Mettupalayam')
)

SELECT
    zone AS ZONE,
    hour AS Hour,
    ROUND(SUM(orders)::NUMERIC / COUNT(DISTINCT CASE WHEN login_mins > 0 THEN de_id END), 6) AS Avg_Orders,
    ROUND(SUM(login_mins)::NUMERIC / COUNT(DISTINCT CASE WHEN login_mins > 0 THEN de_id END), 6) AS Avg_Login_Mins,
    ROUND(SUM(login_mins)::NUMERIC / NULLIF(SUM(orders), 0), 6) AS Idle_Ratio
FROM de_hourly_perf
WHERE login_mins > 0  -- only include DEs who were active
GROUP BY zone, hour
ORDER BY zone, hour;
