

WITH invoices AS (
    SELECT
        DATE_TRUNC('month', invoice_date)  AS invoice_month,
        currency,
        payment_status,
        COUNT(*)                           AS invoices_count,
        SUM(total_price)                   AS invoices_total
    FROM "dbt_db"."public"."stg_invoices"
    GROUP BY 1, 2, 3
),
payments AS (
    SELECT
        DATE_TRUNC('month', payment_date)  AS payment_month,
        currency,
        payment_status,
        COUNT(*)                           AS payments_count,
        SUM(total_price)                   AS payments_total
    FROM "dbt_db"."public"."stg_payments"
    GROUP BY 1, 2, 3
)
SELECT
    COALESCE(i.invoice_month, p.payment_month) AS month,
    COALESCE(i.currency, p.currency)           AS currency,
    COALESCE(i.invoices_count, 0)              AS invoices_count,
    COALESCE(i.invoices_total, 0)              AS invoices_total,
    COALESCE(p.payments_count, 0)              AS payments_count,
    COALESCE(p.payments_total, 0)              AS payments_total,
    CASE
        WHEN COALESCE(i.invoices_total, 0) > 0
        THEN ROUND(COALESCE(p.payments_total, 0) / i.invoices_total * 100, 2)
        ELSE NULL
    END                                        AS payment_ratio_pct
FROM invoices i
FULL OUTER JOIN payments p
    ON i.invoice_month = p.payment_month
   AND i.currency = p.currency