-- v_pipeline
-- Nyitott ajánlatok (QUOTED = kiajánlott, PREPARATION = előkészítés alatt) kor-számítással.
-- Élő pipeline szabály (2026-10-12, user döntés): is_live = a megkeresés az adatbázis
-- legfrissebb request_date-jétől számított 12 hónapon belüli. A régebbi nyitottak
-- "elavult nyitott" tételek: a dashboard külön mutatja, a hibalistára valók (lezárandók).
-- Forrás: quotes + partners tábla
-- Használja: pipeline szekció, KPI pipeline, adatminőség (elavult nyitott)

CREATE VIEW IF NOT EXISTS v_pipeline AS
SELECT
    q.quote_id,
    q.product_line,
    q.year,
    q.status,
    q.partner_name_raw  AS partner,
    COALESCE(q.country, p.country) AS country,
    q.is_domestic,
    q.subject,
    q.total_value_eur,
    q.request_date,
    q.sent_date,
    q.handler_name,
    q.reaction_days,
    CAST(julianday((SELECT MAX(request_date) FROM quotes)) - julianday(q.request_date) AS INTEGER) AS age_days,
    CASE WHEN q.request_date >= date((SELECT MAX(request_date) FROM quotes), '-12 months')
         THEN 1 ELSE 0 END AS is_live
FROM quotes q
LEFT JOIN partners p ON q.partner_id = p.partner_id
WHERE q.status IN ('QUOTED', 'PREPARATION');
