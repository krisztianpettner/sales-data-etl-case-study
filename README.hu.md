[English](README.md) · **Magyar**

# A táblázat-káosztól a banki minőségű adatbázisig — egy értékesítési ETL esettanulmánya

**[Pettner Krisztián](https://github.com/krisztianpettner)** · rendszertervező · [LinkedIn](https://www.linkedin.com/in/krisztian-pettner/)

> Egy gyártócég éveken át szabad formájú Excel-táblákban vezette az ajánlatkéréseit: kézzel,
> beviteli ellenőrzés nélkül. A feladat: legyen ebből olyan adatbázis, amely alkalmas elemzésre,
> üzleti döntések előkészítésére és **banki ügylet alátámasztására**. Az igényből én csináltam
> tervet, és én feleltem a tervezésért, az átnézésért és minden számért, ami a rendszert elhagyta;
> a kódot Claude írta, a rendszert közösen építettük. 2026 márciusa óta
> használatban van, negyedévente frissül. Ez a repó azt mutatja meg, **hogyan lett az adat
> megbízható** — magát az adatot nem.

## 30 másodpercben

**A káosz.** Hét év (2020–2026) ajánlatkövető munkafüzete, két termékcsoportra. Az oszlopszerkezet
minden évben változott. A státusz szabad szöveg volt (10 állapotra 40+ írásmód). Ugyanaz a vevő
sokféle néven szerepelt: cégformával vagy anélkül, ékezettel vagy anélkül, rövidítve, elírva. Egyes
sorok valójában rendelési tételsorok voltak, egyes értékek rossz pénznemben, és sok partnernél senki
nem rögzítette az országot.

**Mit kezd ezzel a rendszer:**

| probléma | válasz az architektúrában |
|---|---|
| az oszlopszerkezet évente változik | egy konfigurációs regiszter: elrendezés-korszakonként oszloptérkép, évenként fájl-bejegyzés — egy új év konfig-bejegyzés, nem új kód |
| ugyanaz a cég sokféle néven | normalizálás → hasonlósági egyezés → **zöld / sárga / piros zóna** → a bizonytalanokról ember dönt → kanonikus partner + alias-tábla |
| az emberi döntéseknek túl kell élniük az újraépítést | **két adatbázis**: egy eldobható, teljesen származtatott elemzési DB és egy tartós operátori DB minden emberi döntésnek |
| a hiba a forrásban van, nem a kódban | import-varázsló **blokkoló minőségkapuval**; a hibajegyzék visszamegy a táblák gazdáihoz, ők javítják a forrást, mi újraimportálunk |
| a számoknak meg kell állniuk egy bank előtt | kifejezetten meghozott és leírt üzleti definíciók (mi „nyitott", mi „elveszett", melyik évhez tartozik egy üzlet), és minden szám minden alkalommal az adatbázisból újraszámolva |

**Az elv mögötte.** Egy kimaradt összevonás két hasonló névként látszik egy listában; egy hibás
összevonás csendben bevételt tesz át egyik vevőről a másikra. Ezért a rendszer **az olcsó hibát
automatizálja, a drágát emberre hagyja** — a név-egyeztetésben, a minőségkapuban és az üzleti
definíciókban is. → [Névegyesítés](docs/hu/03-entity-resolution.md)

**Mi lett vele.** A számok a bankhoz kerültek, és a bank elégedett volt velük — az adatbázis
elvégezte, amire épült. Ma is használatban van: egy negyedéves frissítés kb. egy óra, a ráépülő
banki riport a hetedik változatánál tart. → [Kimenet](docs/hu/09-outcome.md)

## A megbízó adatai szándékosan kimaradnak

A repóban minden cégnév, személy, termék, fájlnév, érték és azonosító **szintetikus**. Maga az
esettanulmány is egy gyakorlat abban, hogyan kell egy megbízó adatait kezelni: maszkoló térkép,
gépi keresés a valódi nevek teljes listájával, és egy második, kézi átnézés a publikálás előtt.
→ [Hogyan anonimizáltuk ezt a repót](docs/hu/10-data-protection.md)

## Futtasd két perc alatt — szintetikus adaton

```bash
pip install openpyxl
python samples/generate_synthetic.py      # rendetlen munkafüzetek minden beállított elrendezésben → src/data/
# harmadik fél, nincs mellékelve: Chart.js 4.4.x, src/etl/chart.umd.min.js néven
cd src && python etl/run_etl.py           # beolvasás → átalakítás → betöltés → nyilvántartó → JSON → dashboard.html
```

A futás a csővezeték saját keresztellenőrzéseivel zárul; az [Üzleti definíciók](docs/hu/06-business-definitions.md)
fejezet dashboard-képe ennek a futásnak a kimenete.

## A fejezetek

Kevés az idő? Olvasd el a [00](docs/hu/00-at-a-glance.md)-t és a [01](docs/hu/01-the-mess.md)-et — tizenöt perc. Ha
az is érdekel, hogyan maradt ki a megbízó adata, jöhet a [10](docs/hu/10-data-protection.md).

| # | fejezet | mire felel | kód |
|---|---|---|---|
| 00 | [Áttekintés](docs/hu/00-at-a-glance.md) | a rendszer egy képen, és a tizennégy döntés soronként egy mondatban | |
| 01 | [A káosz, soronként](docs/hu/01-the-mess.md) | az adat minden problémaosztálya, mindegyikhez szintetikus példa és a megoldás | |
| 02 | [Beolvasás](docs/hu/02-ingestion.md) | hogyan olvassuk az évente változó szerkezetű táblákat | [`etl/config.py`](src/etl/config.py), [`etl/extract.py`](src/etl/extract.py) |
| 03 | [Névegyesítés](docs/hu/03-entity-resolution.md) | hogyan lesz egy cég húsz írásmódjából egy partner — és ki dönt | [`etl/transform.py`](src/etl/transform.py), [`admin/etl_bridge.py`](src/admin/etl_bridge.py) |
| 04 | [Adatmodell](docs/hu/04-data-model.md) | két adatbázis — mi származtatott, mire emlékezni kell; nézetek; a JSON-szerződés | [`etl/load.py`](src/etl/load.py), [`sql/views`](src/sql/views) |
| 05 | [Operátori műhely](docs/hu/05-operator-workshop.md) | az import-varázsló, a minőségkapu, a hibajegyzék-kör azokkal, akik az adatot gépelik | [`admin/routes`](src/admin/routes) |
| 06 | [Üzleti definíciók](docs/hu/06-business-definitions.md) | hogyan lesz egy szám védhető egy bank előtt | [`etl/export_json.py`](src/etl/export_json.py) |
| 07 | [Hogyan dolgoztam](docs/hu/07-how-i-worked.md) | a munka megosztása köztem és az AI között, és a szabályok, amiket felállítottam | |
| 08 | [Mérőszámok](docs/hu/08-metrics.md) | minden szám, dátummal és módszerrel | |
| 09 | [Kimenet](docs/hu/09-outcome.md) | hol tart, mi nem tökéletes még, mit csinálnék másképp | |
| 10 | [Adatvédelem](docs/hu/10-data-protection.md) | hogyan anonimizáltuk ezt a repót — és mit kaptak el a szkennelések | [`samples/`](samples/generate_synthetic.py) |
| A | [Döntés-rekordok](docs/hu/adr.md) | a tizenöt döntés teljes terjedelmében | |
| B | [Szójegyzék](docs/hu/glossary.md) | az itt használt fogalmak | |

A [`src/`](src/README.md) mappa negyven fájlos, maszkolt, kurált kódkivonat — olvasásra készült, és a
szintetikus adaton le is fut.

## Amit én döntöttem el

| | |
|---|---|
| **A terv** | a „kérünk egy dashboardot / banki riportot" igényből egy csővezeték regiszterrel, két adatbázissal, minőségkapuval és operátori körrel |
| **Hol lakik az igazság** | a forráshibát a forrástáblában javítja a gazdája; az emberi ítéletek az operátori DB-ben élnek; minden más származtatott és eldobható |
| **Üzleti definíciók** | mi számít nyitott, elveszett vagy élő ajánlatnak; melyik évhez tartozik egy üzlet; hol „van" egy multinacionális vevő |
| **Mi *nincs* automatizálva** | a bizonytalan név-egyezések és az üzleti definíciók embernél maradnak; az a munkaág, amelynek még nincs stabil rutinja, kézi marad, amíg ki nem alakul |
| **Szabályok az AI-nak** | minden számot az adatbázisból kell újraszámolni, sosem az előző riportból másolni; kiadott változatot nem írunk felül; nincs becsült adat — inkább kimarad |

## A számok

*Mérve 2026-10-13-án az élő rendszeren; források: [Mérőszámok](docs/hu/08-metrics.md).*

| | |
|---|---|
| Használatban | 2026 márciusa óta, negyedéves frissítéssel (~1 óra) |
| Forrás | 7 év munkafüzete (2020–2026), ebből 4 betöltve (2023–2026); 2 termékcsoport, 8 oszlopelrendezés-korszak |
| Kód | ~7,6 ezer sor Python a teljes rendszerben (~6,8 ezer ebben a kivonatban), 9 SQL-nézet, 28 útvonalas operátori webalkalmazás |
| Státusz-szótár | 42 nyers írásmód → 10 normalizált állapot |
| Partnernevek | 1 146 különböző írásmód (normalizálás után) → 991 kanonikus partner; 103 partnernek 2–9 írásmódja volt |
| Operátori döntések | 34 import-menet; 906 piros + 17 sárga név-ellenőrzésről ember döntött (menetenkénti ellenőrzések, nem különböző cégek); 331 kézi ország-döntés |
| Minőségkapu | évenkénti első import: 104 / 167 / 26 blokkoló hiba a legrégebbi években (2020–2022), importonként 0–9 a 2023–2026-os években — szinte mind munkaszám nélkül begépelt megnyert üzlet, amit a kapu elkap |

---

*A repó kódját Claude írta, az én tervem szerint. A terv az enyém — mindenekelőtt a szétválasztás aközött,
ami származtatott, és ami emberi döntés, és a kör, amely a hibákat visszaküldi azokhoz, akik az adatot
gépelik. Ugyanígy az üzleti definíciók, minden szám átnézése és a dokumentáció.*

<sub>© 2026 Pettner Krisztián. Áttekintésre megosztva; minden jog fenntartva.</sub>
