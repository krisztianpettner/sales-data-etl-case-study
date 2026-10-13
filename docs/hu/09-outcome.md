[English](../en/09-outcome.md) · **Magyar** · [↑ README](../../README.hu.md)

# Kimenet

## Hol tart (2026-10-13)

- **2026 márciusa óta használatban**, negyedévente frissül. Egy frissítés — új munkafüzetek be,
  ETL-futás, az új partnerek országának ellenőrzése, a riport számainak újraszámolása — kb. egy óra.
- **A bank elfogadta a számokat.** Az adatbázisra épülő riport a bankhoz került, és a bank elégedett
  volt vele; az ügylet célja nem része ennek az esettanulmánynak.
- **A banki riport** a **hetedik változatánál** tart. A v4 óta minden
  változat megvan, egymás mellett.
- **A kapu folyamatosan dolgozik.** Az évenkénti első import megmutatta, hol a kosz: 104, 167 és
  26 blokkoló hiba a legrégebbi, CRM-korszakos években (2020–2022), 0–9 a 2023–2026-os években. A
  legrégebbi évek később kikerültek a betöltésből. Az aktív években a kapu importonként még ma is
  megállít néhány sort — szinte mindig munkaszám nélkül begépelt megnyert üzletet —, ezek
  visszamennek a forrásba, és egy napon belül javulnak.
- **A második kör** (a rendelés-nyilvántartó, 2026 június) saját hibajegyzéket adott — ajánlat nélküli
  rendelés, munkaszám nélküli megnyert ajánlat —, ennek ledolgozása a megbízó oldalán folyik.

## Ami bevált

| | miért számított |
|---|---|
| a hibát a forrásban javítjuk, nem a DB-ben | az adat a gyökerénél javult; újraépítés után semmit nem kellett újrafoltozni |
| az operátori DB mint az ítéletek otthona | minden összevonás és ország-döntés túlélt több tucat újraépítést |
| zónák egyetlen küszöb helyett | az operátor csak azokat a neveket látta, amelyekhez ember kellett |
| „újraszámolni, sosem másolni" | elkapott olyan valódi változásokat a változatok között, amelyeket egy átmásolt tábla elrejtett volna |
| kifejezett üzleti definíciók | a riport minden száma visszavezethető egy leírt szabályra |

## Őszinte hiányok — és mi lett velük

| hiány | mikor derült ki | állapot |
|---|---|---|
| **Nincsenek automatizált tesztek.** A helyességet az ETL-futás végén kiírt keresztellenőrzések és a riportok előző változattal való összevetése tartja. | kezdettől | nyitott — az első jelöltek a névnormalizáló és a státusz-leképező, szintetikus esetekkel |
| **A táblázat belföldi/külföldi jelzője felülírta az ország nevét**, és az operátor kézi ország-döntései nem jutottak el az ajánlat-szintű átalakításig. Egy teljes év belföldi/külföldi bontása a kiadott érték ~16%-ával tévedett. | 2026-10-13, riport készítése közben | **javítva**; minden korábbi riport-változatban egy év belföldi/külföldi bontását érintette; a v7 változásnaplóval javítja |
| **Az operátor által felvett státuszokat elmentettük, de sosem alkalmaztuk** — az átalakítás csak a beépített térképet olvasta. | 2026-10-13, kód-átnézés ehhez az esettanulmányhoz | **javítva** |
| **A származtatott alias-tábla minden futáskor nőtt** (nem volt egyedi kulcs, így az „insert or ignore" sosem hagyott ki semmit). 13,7 ezer sor ~4,5 ezer valódi aliasra. | 2026-10-13, kód-átnézés | **javítva** (deduplikálás + egyedi index) |
| **Az inkrementális betöltés nem volt atomi.** Az SQLite `executescript` implicit commitot végez, így az évenkénti törlés utáni hiba elveszíthette az adott évet. | 2026-10-13, az esettanulmány hiring-manager átnézése | **javítva** (pillanatkép + visszaállítás; kikényszerített hibával tesztelve) |
| **A felülbírálási indokot csak az űrlap kérte**, a szerver nem. | 2026-10-13, ugyanaz az átnézés | **javítva** |
| **Két partner-azonosító séma él egymás mellett** a származtatott DB-ben (önálló futás vs. varázsló); a nem használt partnersorok nem törlődnek. | 2026-10-13, kód-átnézés | nyitott — a számokat nem érinti (az ajánlatok a jó azonosítóra mutatnak), csak rendetlen |
| **Elveszett egy egyszeri elemző szkript.** Az „új partner évente" táblát egy munkamenet-szkript számolta, amit nem mentettünk el; a visszafejtés az egyik termékcsoportot pontosan, a másikat évente ±3 partneren belül adta vissza. | 2026-10-13 | tanulság levonva — most, hogy a rutin stabil, a lekérdezései verziózott szkriptbe valók |
| **Dokumentáció-csúszás.** Néhány docstring és a projektjegyzet korábbi állapotot írt le (teljes újraépítés inkrementális betöltés helyett, régebbi JSON-forma). | 2026-10-13, kód-átnézés | javítás alatt |
| **Kért, de nem szállított:** iparági bontás, elvesztés okai ok szerint, partner-dúsítás az országon túl. | — | tudatosan parkolópályán (lásd [Áttekintés](00-at-a-glance.md#terv-vs-megépült)) |

## Mit csinálnék másképp

1. **Elsőként tesztek a rendszer két szívére** — a névnormalizálóra és a státusz-leképezőre —, a
   valódi hibatípusok szintetikus készletére építve. A státusz-szótár hibáját a leképező tesztje,
   az ország-hibát egy olyan teszt kapta volna el, amely kimondja: a belföldi/külföldi mindig az
   ország nevéből következik. Egyikhez sem kellett volna néhány sornál több.
2. **Egyetlen partner-azonosító séma az első naptól.** Az önálló ETL és az operátori varázsló saját
   azonosító-előtagot növesztett; működik, de varrat.
3. **Egy rutint abban a pillanatban kódba emelni, amikor ismétlődik.** A banki riportot szándékosan
   tartottam kézi munkának, amíg a formája mozgott — ez helyes volt —, de a harmadik negyedéves
   frissítés volt a jel, hogy a lekérdezéseit szkriptbe mentsem, és ezt egy negyedévvel később léptem meg.

## Terv vs megépült

| terv | megépült |
|---|---|
| egy dashboard | egy dashboard, és ami megbízhatóvá tette: a tisztító csővezeték és az operátori kör |
| egyszeri tisztítás | megismételhető negyedéves rutin |
| automatikus riport | kézzel írt riport automatikus számokra — szándékosan, amíg a forma meg nem állapodott |
