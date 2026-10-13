-- v_market_summary
-- Piac: ország + belföld/export bontás PL x év szinten
-- Forrás: quotes tábla
-- Használja: market szekció (piaci fókusz)
-- Kiszűri: ORDER_LINE, NO_QUOTE, NOT_RELEVANT státuszokat

CREATE VIEW IF NOT EXISTS v_market_summary AS
SELECT
    q.product_line,
    q.year,
    q.country,
    CASE
        WHEN q.is_domestic = 1 THEN 'Belföld'
        WHEN q.is_domestic = 0 THEN 'Export'
        ELSE 'Besorolatlan'
    END AS domestic_export,
    COUNT(*)                             AS quote_count,
    COALESCE(SUM(q.total_value_eur), 0)  AS total_value_eur,
    SUM(CASE WHEN q.status = 'WON' THEN 1 ELSE 0 END) AS won_count,
    COALESCE(SUM(CASE WHEN q.status = 'WON' THEN q.total_value_eur ELSE 0 END), 0) AS won_value_eur
FROM quotes q
WHERE q.status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')
GROUP BY q.product_line, q.year, q.country, domestic_export;
