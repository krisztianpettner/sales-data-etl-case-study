-- v_ytd_comparison
-- YTD összesítés: PL x év szinten win rate, pipeline, nyert érték
-- Forrás: quotes tábla
-- Használja: ytd_comparison szekció, YTD KPI-k
-- Kiszűri: ORDER_LINE, NO_QUOTE, NOT_RELEVANT státuszokat

CREATE VIEW IF NOT EXISTS v_ytd_comparison AS
SELECT
    q.product_line,
    q.year,
    COUNT(*)                         AS total_quotes,
    SUM(CASE WHEN q.status = 'WON' THEN 1 ELSE 0 END)  AS won_count,
    SUM(CASE WHEN q.status IN ('LOST_COMPETITOR','LOST_CUSTOMER') THEN 1 ELSE 0 END) AS lost_count,
    SUM(CASE WHEN q.status = 'QUOTED' THEN 1 ELSE 0 END) AS open_count,
    SUM(CASE WHEN q.status = 'PREPARATION' THEN 1 ELSE 0 END) AS prep_count,
    SUM(q.total_value_eur)           AS total_value_eur,
    SUM(CASE WHEN q.status = 'WON' THEN q.total_value_eur ELSE 0 END) AS won_value_eur,
    SUM(CASE WHEN q.status = 'QUOTED' THEN q.total_value_eur ELSE 0 END) AS pipeline_value_eur,
    ROUND(
        CAST(SUM(CASE WHEN q.status = 'WON' THEN 1 ELSE 0 END) AS REAL) /
        NULLIF(SUM(CASE WHEN q.status IN ('WON','LOST_COMPETITOR','LOST_CUSTOMER') THEN 1 ELSE 0 END), 0)
        * 100, 1
    ) AS win_rate_pct,
    AVG(q.reaction_days)             AS avg_reaction_days
FROM quotes q
WHERE q.status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')
GROUP BY q.product_line, q.year;
