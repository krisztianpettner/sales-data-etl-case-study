-- v_industry_summary
-- Iparág: TEÁOR bontás (partner join), PL szinten
-- Forrás: quotes + partners tábla
-- Használja: industry szekció
-- Kiszűri: ORDER_LINE, NO_QUOTE, NOT_RELEVANT státuszokat
-- Megjegyzés: TG2 partnerlistában nincs TEÁOR mező, ezért főleg TG1-re releváns

CREATE VIEW IF NOT EXISTS v_industry_summary AS
SELECT
    q.product_line,
    q.year,
    p.industry,
    p.teaor_code,
    COUNT(*)                             AS quote_count,
    COALESCE(SUM(q.total_value_eur), 0)  AS total_value_eur,
    SUM(CASE WHEN q.status = 'WON' THEN 1 ELSE 0 END) AS won_count,
    COALESCE(SUM(CASE WHEN q.status = 'WON' THEN q.total_value_eur ELSE 0 END), 0) AS won_value_eur
FROM quotes q
JOIN partners p ON q.partner_id = p.partner_id
WHERE p.industry IS NOT NULL
  AND q.status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')
GROUP BY q.product_line, q.year, p.industry, p.teaor_code;
