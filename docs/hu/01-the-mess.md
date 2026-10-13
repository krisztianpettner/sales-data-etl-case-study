[English](../en/01-the-mess.md) · **Magyar** · [↑ README](../../README.hu.md)

# A káosz, soronként

A forrás ajánlatkövető munkafüzetek sora volt — évenként és termékcsoportonként egy —, éveken át
kézzel vezetve. Úgy viselkednek, mint egy **digitalizált papír-nyomtatvány**: valaki kitölt egy
sort, egyetlen mező sincs ellenőrizve, a szerkezet az, ami abban az évben észszerűnek tűnt. Alább a
csővezeték által megoldott összes problémaosztály, mindegyik egy **szintetikus példasorral**
(kitalált nevek és értékek, ugyanaz a *fajta* hiba) és a kódbeli hellyel, amely kezeli.

> Minden példa kitalált. „Cég 007", „Kapcsolattartó 03", az ajánlatszámok és az összegek nem
> léteznek. A valódi adat soha nem hagyta el a megbízó gépeit.

## A. Ugyanaz a cég, sok néven

| # | hogyan nézett ki | miért fáj | hogyan oldottuk meg | kód |
|---|---|---|---|---|
| A1 | `Cég 007 Kft.` · `Cég 007 kft` · `CÉG 007` | egy helyett három vevő: a vevőszám felfúvódik, a vevőnkénti árbevétel szétesik | **normalizálás**: kisbetű, ékezet le, írásjel → szóköz, cégforma-végződés le (31 minta a *Kft.*-től a *Sp. z o.o.*-ig) → mind a három `ceg 007` | `etl/transform.py::normalize_name`, `etl/config.py::COMPANY_SUFFIXES` |
| A2 | `Cég-Nyolc Zrt.` · `Ceg Nyolc` | ékezet és kötőjel következetlenül gépelve | ékezet-lehúzás + kötőjel mint elválasztó (`cég-nyolc` = `ceg nyolc`) | ugyanott |
| A3 | `Cég 012 Engineering` · `Cég 012 Enginering` | pontos egyezésnek egy elírás új cég | **hasonlósági pontszám** a normalizált neveken; ≥ 0,92 kötegben automatikusan összevon, 6 karakternél rövidebb nevet soha nem von össze automatikusan | `etl/transform.py` (fuzzy összevonás) |
| A4 | `Cég 021 (B telephely, 2. üzem)` · `Cég 021 – u.a. mint a 153-as ajánlat` | megjegyzés *a név mezőbe* gépelve | a normalizálás a zárójelet leveszi, a szavakat nem → **sárga/piros zónába** kerül, egyszer egy ember a jó partnerhez rendeli, az írásmód **aliasként** megmarad | `admin/etl_bridge.py` (staging), `admin/routes/import_wizard.py` |
| A5 | `Cég 030 Group` vs `Cég 030 Hungary Kft.` | egy vevő vagy kettő? a gép nem tudhatja | a zöld zóna alatt **soha nem automatikus**; az operátor dönt, a döntés az operátori DB-ben él és minden újraépítést túlél | `admin/routes/partners.py` (összevonás, aliasok) |

→ A teljes módszer: [Névegyesítés](03-entity-resolution.md)

## B. A szerkezet évente változik

| # | hogyan nézett ki | miért fáj | hogyan oldottuk meg | kód |
|---|---|---|---|---|
| B1 | 2023: a partner a D oszlopban, az érték az O-ban; 2025: két új oszlop a státusz elé | a rögzített oszlopindex csendben rossz mezőt olvas | **elrendezés-korszakonként oszloptérkép** (8 korszak) és évenként fájl-bejegyzés: fájl → lap → kezdősor → térkép | `etl/config.py::FILE_CONFIG`, `_TG1_COLS_*`, `_TG2_COLS_*` |
| B2 | régebbi évek: nincs státusz oszlop — helyette öt jelölőnégyzet-oszlop (nyert / vesztett / elhalasztva / nem ajánlottunk / nyitott) | a legfontosabb mező nem létezik | státusz **a jelölőnégyzetekből származtatva**, tartalékként a kiküldés dátumából | `etl/extract.py::_derive_tg1_status_bitmask` |
| B3 | a 2. termékcsoport egy régebbi éve: csak szabad szöveges visszajelzés-oszlop (`„lerendelték 03.12"`, `„drágák voltunk"`) | a státusz prózába rejtve | kulcsszó-szabályok (`rendel` → nyert; kiküldött ajánlat utáni bármilyen visszajelzés → vesztett; `visszamond` → nem ajánlottunk) | `etl/extract.py::_derive_tg2_status_feedback` |
| B4 | egy év két lapra bontva (első / második félév) | egy lapot olvasva fél év hiányzik | lap-*lista* a fájl-bejegyzésben | `etl/extract.py::extract_tg1_quotes` |
| B5 | 20 üres sor, aztán a 900. sorban egy elfelejtett tesztsor | túl korán áll meg az olvasás, vagy szemetet szed fel | 20 egymást követő üres sor után megáll; az azonosító **és** partner nélküli sort átugorja | `etl/extract.py::_read_sheet` |

→ [Beolvasás](02-ingestion.md)

## C. Szabad szöveges státusz

| # | hogyan nézett ki | miért fáj | hogyan oldottuk meg | kód |
|---|---|---|---|---|
| C1 | `megnyertük` · `Megnyertük ` · `megnyertuk` | ugyanaz az állapot, három kulcs | pontos egyezés vágás + kisbetű után, aztán ékezet nélküli egyezés | `etl/transform.py::normalize_status` |
| C2 | `>kiküldésre vár<` · `>>>kiküldésre vár<<<` | díszítés az értékbe gépelve | mindkét díszített forma bejegyzés a térképben | `etl/config.py::STATUS_MAP` |
| C3 | egy státusz, amit még senki nem látott | NULL státusz = az ajánlat eltűnik minden funnelből | az import-varázsló **külön lépést mutat az ismeretlen státuszoknak**; az operátor egyszer leképezi, a státusz-szótárba kerül, és onnantól érvényes | `admin/routes/status_dict.py`, `normalize_status` (2026 októbere óta — lásd [Kimenet](09-outcome.md)) |

42 nyers írásmód képeződik le 10 állapotra, mindegyik kifejezett *nyitott / nyert / vesztett* jelzővel.

## D. Sorok, amelyek nem azok, aminek látszanak

| # | hogyan nézett ki | miért fáj | hogyan oldottuk meg | kód |
|---|---|---|---|---|
| D1 | a `Q2-26-118` ajánlat négy soron: egy fejléc, három `[rendelés tételsora]` státuszú sor | négy ajánlatként számolva, az érték négyszer | a tételsorokat a státusz-jelölő választja le, az értékük **a fejlécbe összegződik** | `etl/extract.py::extract_tg2_quotes`, `etl/transform.py::transform_tg2_quotes` |
| D2 | régebbi év: a tételsoroknak **nincs ajánlatszáma** — csak a fejléc alatti sorok | azonosító nélküli szemétnek látszanak | a folytatósorok az utolsó fejléchez kapcsolódnak (előrekitöltés) | `etl/extract.py::extract_tg2_quotes` (régebbi elrendezés ága) |
| D3 | ugyanaz az ajánlatszám két év fájljában (januárban áthozva) | dupla számolás évek között | deduplikálás ajánlatszám szerint, **a későbbi év nyer** | `etl/transform.py::transform_all` (4. lépés) |
| D4 | egy 1,9 M értékű megkeresés, státusza *nem készült ajánlat* | egy soha ki nem ajánlott kérés felfújja a „kiadott értéket" | **a kiadott érték definíció szerint nem tartalmazza** a nem kiajánlott sorokat; a kérés keresletként továbbra is számít | `etl/export_json.py` (funnel), [Üzleti definíciók](06-business-definitions.md) |
| D5 | egy három éve „nyitott" ajánlat | a soha le nem zárt ajánlatok felfújják a pipeline-t | **élő pipeline = az utolsó 12 hónapban kiajánlott**; a régebbi nyitottak *elavultként* listázva, a forrásban lezárandók | `sql/views/04_pipeline.sql` |

## E. Értékek és azonosítók

| # | hogyan nézett ki | miért fáj | hogyan oldottuk meg | kód |
|---|---|---|---|---|
| E1 | `#REF!` · `#N/A` · `-` · `Hiányzik, add meg!` | a táblázat hibái szöveges értékként jönnek be | egyetlen **hiányzó-érték jelölő** készlet → mindenhol NULL | `etl/config.py::MISSING_MARKERS`, `transform.py::_clean_value` |
| E2 | `41 800 000` egy EUR-oszlopban, egy közepes megrendelésnél | a mértékegység HUF volt, az EUR-oszlopba gépelve | a minőségi átnézés kiugró értékként jelzi, **a forrásban javítja** a gazdája — nem a DB-ben | (folyamat — lásd [Operátori műhely](05-operator-workshop.md)) |
| E3 | munkaszám `26902`, `26902/1`, `W90126/A`, `2690` | a munkaszám köti a megnyert ajánlatot a rendelés-nyilvántartóhoz; termékcsoportonként más a formátum, alszám kerül a végére | termékcsoportonként egy regex: év + sorszám + opcionális rész; minden más anomáliaként naplózva | `etl/transform.py::parse_work_number` |
| E4 | 2025-ös megkeresés, 2026-os munkaszám | melyik évben „nyertük meg"? | **évhatáron átnyúlóként** jelölve; a funnel a megkeresés évét, a nyilvántartó a saját évét használja — sosem keverve | `transform.py::detect_crossyear`, [Üzleti definíciók](06-business-definitions.md) |
| E5 | státusz *megnyertük*, munkaszám nincs | az üzlet nem található meg a rendelés-nyilvántartóban | **blokkoló hiba** az import-varázslóban — az import nem megy tovább, amíg a forrást nem javítják, vagy az operátor írásos indokkal felül nem bírálja | `admin/etl_bridge.py::collect_blocking_issues` |
| E6 | üres megkeresés-dátum; vagy kiküldés 140 nappal a kérés után | a reakcióidő és az azonos időszaki számok elcsúsznak | figyelmeztetések a minőségi listán (hiányzó dátum, reakcióidő > 90 nap) | `transform.py::_collect_anomalies` |

## F. Országok

| # | hogyan nézett ki | miért fáj | hogyan oldottuk meg | kód |
|---|---|---|---|---|
| F1 | sok partnernél soha nem rögzítették az országot (egyes években partner-lap sem volt) | nincs belföldi/külföldi bontás — a banki riport alapkérdése | **ország-feloldó** hat rangsorolt stratégiával — korábbi operátori döntések, partner-azonosító kereszthivatkozás, egy év partner-lapja, a másik termékcsoport partnerlistája, a belföldi jelző, a cégforma-végződés —, mindegyik módszer- és bizonyosság-címkével; ami feloldatlan marad, CSV-ben emberhez megy, és kézi döntésként jön vissza | `scripts/resolve_countries.py` |
| F2 | `Lengyel` · `Lengyelország`; `Cseh Köztársaság` · `Csehország` | ugyanaz az ország, két kulcs | ország-térkép ISO-kódokra és régiókra | `etl/config.py::COUNTRY_NAME_MAP` |
| F3 | jelző *külföldi*, ország *Magyarország* | a jelző és a név ellentmond egymásnak | **a belföldi/külföldi mindig az ország nevéből származik**; a jelző csak tartalék (itt egy hibát 2026 októberében találtunk és javítottunk) | `etl/transform.py::transform_tg1_quotes` |
| F4 | `Cég 041 Kft.` — itthon bejegyezve, de minden kapcsolat, rendelés és számla a csoport külföldi üzeméhez megy | a cégjegyzék országa ≠ piaci valóság | szabály: **ország = akivel ténylegesen üzletelünk**; ember dönt, a döntés tárolva, és mindent felülír | `transform.py::load_country_overrides` |

## G. A második forrás: a rendelés-nyilvántartó

| # | hogyan nézett ki | miért fáj | hogyan oldottuk meg | kód |
|---|---|---|---|---|
| G1 | egy rendelés három soron: `26902/1`, `26902/2`, `26902/3` | egy helyett három rendelés | alszám le, összegek rendelésenként összeadva | `scripts/extract_work_orders.py` |
| G2 | egy kétéves projekt mindkét év nyilvántartásában, az adott évre eső résszel | duplikátumnak látszik | **szándékosan nincs deduplikálva**: minden év a saját elhatárolt részét viszi | ugyanott |
| G3 | belső rendelés: a 2. termékcsoport az 1. termékcsoport egyik munkájához gyárt | az árbevétel kétszer számolódna | a saját gyártású rendelés rendelés-szinten kizárva | ugyanott |
| G4 | ugyanaz a munkaszám két különböző vevőnél | elírás a kulcsban | ütközésként jelentve a nyilvántartó saját hibajegyzékén | ugyanott |
| G5 | egy EUR-összeg és mellette egy HUF-ban számlázott összeg | két pénznem egy rendelésre — melyik számít? | **az EUR vállalási ár az igazság forrása**; az EUR-ban számlázott összeg csak hiányt pótol; a HUF-oszlopot szándékosan sosem váltjuk át és nem használjuk | ugyanott |

## Terv vs megépült

| terv | megépült |
|---|---|
| „egyszer tisztítsuk ki az adatot" | megismételhető szabálykészlet + operátori kör, mert ugyanazokat a hibákat újra és újra begépelik |
| minden hasonló név automatikus összevonása | automatikusan csak a zöld zónában; minden bizonytalanról ember dönt |
| a rossz értékeket javítsuk az adatbázisban | a forrásban javítjuk — egy DB-folt a következő újraépítéskor elveszne |
