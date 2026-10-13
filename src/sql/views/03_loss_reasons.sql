-- v_loss_reasons
-- Bukási okok: PL x év x státusz bontás, db + érték
-- Forrás: quotes tábla
-- Használja: loss szekció (hatékonyság)
-- Csak lezárt-negatív státuszokat tartalmazza

CREATE VIEW IF NOT EXISTS v_loss_reasons AS
SELECT
    q.product_line,
    q.year,
    q.status,
    q.loss_reason,
    COUNT(*)                         AS count,
    COALESCE(SUM(q.total_value_eur), 0) AS lost_value_eur
FROM quotes q
WHERE q.status IN ('LOST_COMPETITOR', 'LOST_CUSTOMER', 'POSTPONED', 'CLOSED_NO_RESPONSE')
GROUP BY q.product_line, q.year, q.status, q.loss_reason;
