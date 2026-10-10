

WITH routes AS (
    SELECT
        transport_mode,
        COUNT(*)             AS routes_count,
        SUM(distance_km)     AS total_distance_km,
        AVG(distance_km)     AS avg_distance_km,
        MIN(distance_km)     AS min_distance_km,
        MAX(distance_km)     AS max_distance_km
    FROM "dbt_db"."public"."stg_transport_routes"
    GROUP BY transport_mode
),
shipments AS (
    SELECT
        transport_mode,
        COUNT(*)             AS shipments_count,
        SUM(shipping_cost)   AS total_shipping_cost,
        AVG(shipping_cost)   AS avg_shipping_cost,
        SUM(weight_kg)       AS total_weight_kg
    FROM "dbt_db"."public"."stg_shipments"
    GROUP BY transport_mode
)
SELECT
    COALESCE(r.transport_mode, s.transport_mode) AS transport_mode,
    COALESCE(r.routes_count, 0)                  AS routes_count,
    COALESCE(r.total_distance_km, 0)             AS total_distance_km,
    COALESCE(r.avg_distance_km, 0)               AS avg_distance_km,
    COALESCE(s.shipments_count, 0)               AS shipments_count,
    COALESCE(s.total_shipping_cost, 0)           AS total_shipping_cost,
    COALESCE(s.avg_shipping_cost, 0)             AS avg_shipping_cost,
    COALESCE(s.total_weight_kg, 0)               AS total_weight_kg,
    CASE
        WHEN COALESCE(r.total_distance_km, 0) > 0
        THEN ROUND(COALESCE(s.total_shipping_cost, 0) / r.total_distance_km, 4)
        ELSE NULL
    END                                          AS cost_per_km
FROM routes r
FULL OUTER JOIN shipments s USING (transport_mode)