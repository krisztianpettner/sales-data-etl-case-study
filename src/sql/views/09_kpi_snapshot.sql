-- v_kpi_snapshot
-- KPI: beérkezett/kiadott havonta + előkészítés + reakcióidő
-- Forrás: quotes tábla
-- Használja: kpi szekció (top 5 KPI kártyák)
-- Kiszűri: ORDER_LINE, NO_QUOTE, NOT_RELEVANT státuszokat

CREATE VIEW IF NOT EXISTS v_kpi_snapshot AS
SELECT
    SUBSTR(q.request_date, 1, 7) AS month,
    q.product_line,
    -- Beérkezett
    COUNT(*) AS incoming_count,
    -- Kiadott (sent_date-ből)
    SUM(CASE WHEN q.sent_date IS NOT NULL THEN 1 ELSE 0 END) AS sent_count,
    -- Értékek
    COALESCE(SUM(q.total_value_eur), 0) AS total_value_eur,
    -- Nyert
    SUM(CASE WHEN q.status = 'WON' THEN 1 ELSE 0 END) AS won_count,
    COALESCE(SUM(CASE WHEN q.status = 'WON' THEN q.total_value_eur ELSE 0 END), 0) AS won_value_eur,
    -- Pipeline
    SUM(CASE WHEN q.status = 'QUOTED' THEN 1 ELSE 0 END) AS pipeline_count,
    COALESCE(SUM(CASE WHEN q.status = 'QUOTED' THEN q.total_value_eur ELSE 0 END), 0) AS pipeline_value_eur,
    -- Előkészítés
    SUM(CASE WHEN q.status = 'PREPARATION' THEN 1 ELSE 0 END) AS prep_count,
    -- Reakcióidő
    AVG(q.reaction_days) AS avg_reaction_days,
    -- Win rate alap
    SUM(CASE WHEN q.status IN ('WON','LOST_COMPETITOR','LOST_CUSTOMER') THEN 1 ELSE 0 END) AS decided_count
FROM quotes q
WHERE q.status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')
  AND q.request_date IS NOT NULL
GROUP BY SUBSTR(q.request_date, 1, 7), q.product_line;
