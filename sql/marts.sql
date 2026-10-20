DROP VIEW IF EXISTS mart_mom_change;
DROP VIEW IF EXISTS mart_top_merchants;
DROP VIEW IF EXISTS mart_budget_vs_actual;
DROP VIEW IF EXISTS mart_monthly_income;
DROP VIEW IF EXISTS mart_monthly_spend;

CREATE VIEW mart_monthly_spend AS
SELECT printf('%04d-%02d', d.year, d.month) AS month_key,
       c.name                               AS category,
       ROUND(-SUM(f.amount_zar), 2)         AS spend_zar,
       COUNT(*)                             AS txn_count
FROM fact_transactions f
JOIN dim_date d     ON d.date_key = f.date_key
JOIN dim_category c ON c.category_key = f.category_key
WHERE c.type = 'expense'
GROUP BY month_key, c.name;

CREATE VIEW mart_monthly_income AS
SELECT printf('%04d-%02d', d.year, d.month) AS month_key,
       ROUND(SUM(f.amount_zar), 2)          AS income_zar
FROM fact_transactions f
JOIN dim_date d     ON d.date_key = f.date_key
JOIN dim_category c ON c.category_key = f.category_key
WHERE c.type = 'income'
GROUP BY month_key;

CREATE VIEW mart_budget_vs_actual AS
SELECT m.month_key,
       m.category,
       c.monthly_budget                              AS budget_zar,
       m.spend_zar                                   AS actual_zar,
       ROUND(c.monthly_budget - m.spend_zar, 2)      AS variance_zar,
       CASE WHEN c.monthly_budget > 0
            THEN ROUND(100.0 * m.spend_zar / c.monthly_budget, 1) END AS pct_used
FROM mart_monthly_spend m
JOIN dim_category c ON c.name = m.category;

CREATE VIEW mart_top_merchants AS
SELECT f.merchant,
       c.name                        AS category,
       COUNT(*)                      AS txn_count,
       ROUND(-SUM(f.amount_zar), 2)  AS total_spend_zar
FROM fact_transactions f
JOIN dim_category c ON c.category_key = f.category_key
WHERE c.type = 'expense'
GROUP BY f.merchant, c.name
ORDER BY total_spend_zar DESC
LIMIT 15;

CREATE VIEW mart_mom_change AS
WITH t AS (
    SELECT month_key, SUM(spend_zar) AS total
    FROM mart_monthly_spend
    GROUP BY month_key
)
SELECT month_key,
       ROUND(total, 2) AS total_spend_zar,
       ROUND(total - LAG(total) OVER (ORDER BY month_key), 2) AS change_zar,
       ROUND(100.0 * (total - LAG(total) OVER (ORDER BY month_key))
             / LAG(total) OVER (ORDER BY month_key), 1)       AS change_pct
FROM t;
