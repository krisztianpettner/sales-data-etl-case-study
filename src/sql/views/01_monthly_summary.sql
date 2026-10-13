-- v_monthly_summary
-- Havi bontás: ajánlat db, nyert, vesztett, érték, reakcióidő
-- Forrás: quotes tábla
-- Használja: monthly_trend szekció, KPI beérkezett/kiadott
-- Kiszűri: ORDER_LINE, NO_QUOTE, NOT_RELEVANT státuszokat

CREATE VIEW IF NOT EXISTS v_monthly_summary AS
SELECT
    q.product_line,
    q.year,
    SUBSTR(q.request_date, 1, 7)    AS month,
    COUNT(*)                         AS quote_count,
    SUM(CASE WHEN q.status = 'WON' THEN 1 ELSE 0 END)  AS won_count,
    SUM(CASE WHEN q.status IN ('LOST_COMPETITOR','LOST_CUSTOMER') THEN 1 ELSE 0 END) AS lost_count,
    SUM(CASE WHEN q.status = 'QUOTED' THEN 1 ELSE 0 END) AS open_count,
    SUM(q.total_value_eur)           AS total_value_eur,
    SUM(CASE WHEN q.status = 'WON' THEN q.total_value_eur ELSE 0 END) AS won_value_eur,
    AVG(q.reaction_days)             AS avg_reaction_days,
    -- Kiadott (sent_date alapján)
    SUM(CASE WHEN SUBSTR(q.sent_date, 1, 7) = SUBSTR(q.request_date, 1, 7) THEN 1 ELSE 0 END) AS sent_same_month
FROM quotes q
WHERE q.status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')
  AND q.request_date IS NOT NULL
GROUP BY q.product_line, q.year, SUBSTR(q.request_date, 1, 7);
