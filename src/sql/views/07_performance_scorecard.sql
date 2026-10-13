-- v_performance_scorecard
-- Összesítő scorecard: PL szinten minden fő metrika
-- Forrás: quotes tábla
-- Használja: scorecard szekció (árajánlatadási teljesítmény)
-- Kiszűri: ORDER_LINE, NO_QUOTE, NOT_RELEVANT státuszokat

CREATE VIEW IF NOT EXISTS v_performance_scorecard AS
SELECT
    q.product_line,
    COALESCE(q.work_number_year, q.year) AS outcome_year,
    COUNT(*)                             AS total_quotes,
    COALESCE(SUM(q.total_value_eur), 0)  AS total_value_eur,
    SUM(CASE WHEN q.status = 'WON' THEN 1 ELSE 0 END) AS won_count,
    COALESCE(SUM(CASE WHEN q.status = 'WON' THEN q.total_value_eur ELSE 0 END), 0) AS won_value_eur,
    SUM(CASE WHEN q.status IN ('LOST_COMPETITOR','LOST_CUSTOMER') THEN 1 ELSE 0 END) AS lost_count,
    SUM(CASE WHEN q.status = 'QUOTED' THEN 1 ELSE 0 END) AS open_count,
    COALESCE(SUM(CASE WHEN q.status = 'QUOTED' THEN q.total_value_eur ELSE 0 END), 0) AS pipeline_value_eur,
    SUM(CASE WHEN q.status IN ('WON','LOST_COMPETITOR','LOST_CUSTOMER') THEN 1 ELSE 0 END) AS decided_count,
    ROUND(
        CAST(SUM(CASE WHEN q.status = 'WON' THEN 1 ELSE 0 END) AS REAL) /
        NULLIF(SUM(CASE WHEN q.status IN ('WON','LOST_COMPETITOR','LOST_CUSTOMER') THEN 1 ELSE 0 END), 0)
        * 100, 1
    ) AS win_rate_pct,
    AVG(q.reaction_days) AS avg_reaction_days,
    AVG(CASE WHEN q.status = 'WON' THEN q.total_value_eur END) AS avg_won_value_eur
FROM quotes q
WHERE q.status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')
GROUP BY q.product_line, outcome_year;
