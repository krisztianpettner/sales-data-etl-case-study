-- v_data_quality
-- Adatminőség: hiányzó mezők száma, lefedettség
-- Forrás: quotes + partners tábla
-- Használja: data_quality szekció
-- Kiszűri: ORDER_LINE, NO_QUOTE, NOT_RELEVANT státuszokat

CREATE VIEW IF NOT EXISTS v_data_quality AS
SELECT
    'total_active_quotes' AS metric,
    COUNT(*) AS value,
    NULL AS product_line
FROM quotes WHERE status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')

UNION ALL
SELECT 'null_country', COUNT(*), NULL
FROM quotes WHERE country IS NULL AND status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')

UNION ALL
SELECT 'null_domestic', COUNT(*), NULL
FROM quotes WHERE is_domestic IS NULL AND status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')

UNION ALL
SELECT 'null_partner', COUNT(*), NULL
FROM quotes WHERE partner_id IS NULL AND status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')

UNION ALL
SELECT 'null_status', COUNT(*), NULL
FROM quotes WHERE status IS NULL

UNION ALL
SELECT 'null_request_date', COUNT(*), NULL
FROM quotes WHERE request_date IS NULL AND status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')

UNION ALL
SELECT 'null_value', COUNT(*), NULL
FROM quotes WHERE total_value_eur IS NULL AND status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')

UNION ALL
SELECT 'has_industry', COUNT(*), q.product_line
FROM quotes q
JOIN partners p ON q.partner_id = p.partner_id
WHERE p.industry IS NOT NULL AND q.status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')
GROUP BY q.product_line

UNION ALL
SELECT 'total_by_pl', COUNT(*), product_line
FROM quotes WHERE status NOT IN ('ORDER_LINE', 'NO_QUOTE', 'NOT_RELEVANT')
GROUP BY product_line;
