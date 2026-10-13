[English](../en/07-how-i-worked.md) · **Magyar** · [↑ README](../../README.hu.md)

# Hogyan dolgoztam

## A munkamegosztás

| | |
|---|---|
| **Én** | átvettem a feladatot; a „kérünk egy havi dashboardot", majd később a „számok kellenek a banknak" igényből tervet csináltam — miből áll a csővezeték, hol lakik az igazság, mi automatizált és mi nem; a megbízóval meghoztam az üzleti definíciókat; minden importot és minden frissítést én futtattam; minden számot átnéztem, mielőtt kiment |
| **Claude** (AI kódoló ágens) | megírta a kódot e terv szerint — a tervezésért, az átnézésért és minden kiadott számért én feleltem; megvalósításokat javasolt; lefuttatta a kért méréseket és összevetéseket; jelezte, ami rossznak tűnt |
| **A táblák gazdái** | tovább gépelték az adatot, és a hibajegyzékekből javították a forrásukat |

Közösen építettük; a kód a Claude-é. Az [Áttekintés](00-at-a-glance.md) döntései az enyémek.

## Idővonal

| mikor (2026) | mi |
|---|---|
| március eleje | az igény (havi KPI-áttekintés) → írásos elvárás-specifikáció (öt fő KPI) → a terv |
| március 3–12. | ETL, SQL-nézetek, az operátori alkalmazás az import-varázslóval; az első importok évről évre; hibajegyzékek a táblák gazdáinak; megérkezik a banki riport megbízása; a riport v4 |
| június | a rendelés-nyilvántartó bekötése (csak olvasó beolvasó → egyeztetés → élesítés); a riport v5 |
| október | negyedéves frissítés; a dashboard újratervezése egyetlen „történet"-oldallá; a nyilvántartó beépítése az ETL-be; a riport v6; másnap egy státusz-frissítés, közben az ország-hiba megtalálása és javítása → v7 változásnaplóval |

Március óta a rendszer **negyedéves ciklusban** fut: megérkeznek az új munkafüzetek → az előzőek
archiválódnak → ETL → az új partnerek országának ellenőrzése → a riport számainak újraszámolása, és
megírjuk a következő változatot. Nagyjából egy óra frissítés, plusz az írás.

## A szabályok, amelyeket az ágensnek szabtam

Ezek nem stílusbeli preferenciák voltak; mindegyik azért létezik, mert nélküle valami elromlott.

| szabály | miért |
|---|---|
| **Minden számot az adatbázisból kell újraszámolni; sosem az előző változatból másolni.** | Júniusban egy táblázat újraszámolás helyett átkerült az előző riportból. Az átnézésnél elkaptam; onnantól ez kemény szabály volt. |
| **Kiadott változatot soha nem írunk felül.** Minden riport-változatnak saját, dátumozott fájlja van. | Egy banki egyeztetés visszautal arra, amit elküldtünk; annak pontosan úgy kell léteznie, ahogy elment. |
| **Nincs becsült adat.** Ha nincs meg a lefedettség, nincs grafikon sem. | Az iparági bontás inkább kikerült, mintsem becslésekkel töltsük ki. |
| **Az üzleti definíciókról én döntök.** Az ágens javasol, jelzi a következményt, és kérdez. | Az, hogy a válasz nélküli ajánlat vesztettnek számít-e, érdemben megváltoztatja a win rate-et — ez nem technikai döntés. |
| **Jelezni, nem felülbírálni.** A gyanús érték egy listára kerül egy embernek; a kód nem „javítja ki". | Egy hihetőnek látszó automatikus javítás az a hiba, amit később a legnehezebb megtalálni. |
| **Először az új forrást kell összevetni az előzővel.** | Tudni akarom, mi változott, mielőtt megnézem, mit mondanak a számok. |
| **Egy újra levezetett számítást először az előző változathoz kell mérni.** | Amikor egy elveszett szkriptet újra kellett építeni, előbb a régi számokat kellett visszaadnia, mielőtt az újaknak hittünk. |
| **Amíg egy munkaágnak nincs stabil rutinja, nem automatizáljuk.** | A banki riport kézzel írt maradt, amíg a formája még mozgott. |

## Kód és adat, külön tartva

A kód saját repóban él, és — **csak a kód** — át van szinkronizálva egy külön munkamappába, ahol a
valódi adat él (a `sync_code.sh` a Pythont, az SQL-t és a sablonokat másolja; adatbázist, feltöltést
vagy adatfájlt soha). Az adatbázisok, a feltöltések, a generált oldalak és a forrás-munkafüzetek ki
vannak zárva a verziókezelésből.

Ez az esettanulmány egy lépéssel tovább megy: a megbízó adatából semmi nincs benne — lásd
[Adatvédelem](10-data-protection.md).

## Terv vs megépült

| terv | megépült |
|---|---|
| egy egyszeri dashboard-projekt | egy negyedéves működési rutin, amely március óta fut |
| az ágens ír, én átnézem a kimenetet | az ágens ír, én átnézem a kimenetet, **és a számokat az előző változathoz mérve** — ott akadtak fenn a valódi hibák |
