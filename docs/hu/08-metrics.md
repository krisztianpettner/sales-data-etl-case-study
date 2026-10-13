[English](../en/08-metrics.md) · **Magyar** · [↑ README](../../README.hu.md)

# Mérőszámok

Minden itteni számot **2026-10-13-án** mértünk az élő rendszeren, megnevezett módszerrel. Csak
darabszámok — a megbízó adatából semmilyen érték, név vagy azonosító. Ahol egy szám szűkebb dolgot
mér, mint amilyennek hangzik, a megjegyzés jelzi.

## A kód

| | | hogyan mértük |
|---|---:|---|
| Python | 7 612 sor | `git ls-files '*.py' \| xargs wc -l` (tartalmaz két segédszkriptet, amelyek nincsenek a kivonatban) |
| SQL-nézetek | 9 fájl, 250 sor | `sql/views/*.sql` |
| operátori webalkalmazás | 28 útvonal, 11 sablon (2 630 sor) | `grep -c "route("`; `admin/templates/**` |
| automatizált tesztek | **0** | lásd [Kimenet](09-outcome.md) |

## A forrás és az elcsúszása

| | | hogyan mértük |
|---|---:|---|
| munkafüzet-évek | 7 (2020–2026); ebből 4 betöltve (2023–2026) | `config.FILE_CONFIG`: 8 aktív bejegyzés + 4 archivált (az 1. termékcsoport három, a 2. egy éve) |
| oszloptérképek | 14 — 8 ajánlat-elrendezés, 5 partner-lap elrendezés, 1 kapcsolattartó-elrendezés | a `config.py`-ban a `_*_COLS_*` mintára illeszkedő nevek |
| státusz-szókészlet | 42 nyers írásmód → 10 állapot | `len(STATUS_MAP)`, különböző célértékek |
| cégforma-végződés minták | 31 | `len(COMPANY_SUFFIXES)` |
| országnév-térkép | 42 különböző kulcs | `len(COUNTRY_NAME_MAP)` (egy kulcs a forrásban duplán szerepelt) |

## Mennyiség (betöltött évek)

| | | hogyan mértük |
|---|---:|---|
| ajánlatkérések | 2 410 | `SELECT COUNT(*) FROM quotes` (2023–2026) |
| ajánlat-tételsorok | 3 405 | `quote_lines` |
| rendelés-nyilvántartó sorai | 597 | `work_orders` (rendelés × nyilvántartási év, három divízió) |

## Névegyesítés és operátori döntések

| | | hogyan mértük / megjegyzés |
|---|---:|---|
| kanonikus partnerek | 991 | `partner_master` |
| tárolt írásmódok (normalizálás után) | 1 146 | `partner_aliases`; partner + normalizált név szerint egyedi, így a *nyers* írásmódok ennél többen vannak |
| 2–9 írásmóddal rendelkező partnerek | 103 | aliasok partnerenként csoportosítva |
| utólagos partner-összevonások | 3 | `partner_merges` |
| import-menetek | 34 (16 befejezett, 2 megszakított, a többi egy lépésnél megállt) | `import_sessions`, 2026. március 4. – június 24. |
| név-ellenőrzések — zöld / sárga / piros | 6 131 / 17 / 906 | `staging_partners` zónánként — **ellenőrzések, nem cégek**: egy nevet minden olyan menetben újra ellenőrzünk, amelyben szerepel |
| operátori döntések a piros neveken | 79 meglévő partnerhez rendelve, 827 új partner | `staging_partners.decision` |
| minőségkapu-hibák | 1 918 — 347 blokkoló, 1 571 figyelmeztetés | `staging_issues` |
| blokkoló hibák az évenkénti első importnál | 104 / 167 / 26 / 0 / 1 / 9 / 0–1 (2020 → 2026) | `staging_issues` × `import_sessions.files_json` |
| ország-döntések | 774 — **331 kézi**, 443 rendszer-javaslat | `country_resolutions` módszer szerint; mérvadóként csak a kézieket alkalmazzuk |
| futásonként jelzett származtatott anomáliák | 108 | `anomalies` (évhatáron átnyúló, lassú reakció, hiányzó ország, munkaszám nélküli megnyert, hiányzó dátum, hibás munkaszám) |
| a rendelés-nyilvántartó hibajegyzéke | 112 tétel 8 kategóriában | a `scripts/extract_work_orders.py` kimenete |

## A 2026. októberi javítások

| | előtte | utána |
|---|---:|---:|
| származtatott alias-tábla | 13 701 sor (minden futáskor nőtt) | 4 475 sor, futásról futásra stabil |
| egy év kiadott értékének belföldi/külföldi bontása | ~16% a rossz oldalon | az országból származtatva, a kézi döntésekkel |
| az operátor által felvett státuszokat az ETL alkalmazza | nem | igen |

## Működés

| | |
|---|---|
| használatban | 2026 márciusa óta |
| frissítési ciklus | negyedéves; frissítésenként ~1 óra, plusz a riport megírása |
| banki riport | 7. változat; a v4 óta minden változat megvan, egymás mellett |

## Terv vs megépült

| terv | mérve |
|---|---|
| „az adat ki van tisztítva" | 1 918 kapu-hiba és 923 emberi név-döntés mutatja, mibe került |
| „a rendszer működik" | nincsenek automatizált tesztek — a helyesség a futásidejű keresztellenőrzéseken és a változatok közötti összevetésen nyugszik; első hiányként megnevezve |
