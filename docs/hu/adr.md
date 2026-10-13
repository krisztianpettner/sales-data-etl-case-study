[English](../en/adr.md) · **Magyar** · [↑ README](../../README.hu.md) · [Áttekintés](00-at-a-glance.md)

# Döntés-rekordok

Tizenöt döntés, amely a rendszert alakította, kötött formában: **kontextus · döntés · elvetett
alternatívák · következmények · állapot**. A számozás megegyezik az [Áttekintés](00-at-a-glance.md)
számozásával.

> A projekt futása közben nem vezettünk formális döntés-rekordokat; maguk a döntések a
> kódkommentekben és a projektjegyzetekben vannak dokumentálva. Ezek a rekordok ehhez az
> esettanulmányhoz készültek, az *elvetett* sorok pedig az akkor elhangzott érvelést foglalják
> össze — nem egy formális értékelés jegyzőkönyvei.

---

### ADR-01 — A szerkezet-tudás egyetlen konfig-regiszterben él

- **Kontextus.** Minden év munkafüzetének más volt az oszlopszerkezete; a régebbi években nem volt
  státusz oszlop.
- **Döntés.** Elrendezés-korszakonként oszloptérkép, évenként fájl-bejegyzés (fájl, lap vagy lapok,
  kezdősor, térkép). A beolvasó általános.
- **Elvetve.** Évenkénti olvasófüggvények (másolás-beillesztéses elcsúszás); fejlécnév-felismerés (a
  fejléceket átfogalmazták, összevonták, többsorosak voltak — kevésbé megbízható, mint ha egy ember
  egyszer ránéz).
- **Következmények.** Egy új év egy konfig-bejegyzés; egy új elrendezés egy rövid térkép. Valakinek
  továbbra is meg kell néznie a lapot.
- **Állapot.** Bevált. → [Beolvasás](02-ingestion.md)

### ADR-02 — Két adatbázis: származtatott vs megőrzött

- **Kontextus.** Az összevonási döntések, az ország-döntések és az új státuszok emberi ítéletek; az
  elemzési táblák a munkafüzetekből újraépülnek.
- **Döntés.** Az elemzési DB teljesen származtatott és eldobható; az operátori DB-ben él minden
  emberi döntés, és minden újraépítést túlél. Az elemzési DB-ben semmit nem szerkesztünk kézzel.
- **Elvetve.** Egyetlen adatbázis „védett" táblákkal (egyetlen rossz visszaállítás, és hónapok
  döntései vesznek el).
- **Következmények.** Az ETL minden futáskor olvassa az operátori DB-t; két fájlt kell megérteni;
  egyet kell menteni.
- **Állapot.** Bevált. → [Adatmodell](04-data-model.md)

### ADR-03 — A hibát a forrásban javítjuk

- **Kontextus.** A hibákat folyamatosan gépelik be azok, akik a munkafüzeteket vezetik.
- **Döntés.** A minőségkapu hibajegyzéket állít elő a táblák gazdáinak; ők javítják a forrást; a
  fájlokat újraimportáljuk.
- **Elvetve.** Az értékek javítása az adatbázisban vagy egy tisztító szkriptben (újraépítéskor
  elveszik, és láthatatlan azoknak, akik ugyanazt a hibát újra elkövetik).
- **Következmények.** A kör mások idejére vár; a forrás a gyökerénél javul.
- **Állapot.** Bevált. → [Operátori műhely](05-operator-workshop.md)

### ADR-04 — Név-egyezés zónákban, a bizonytalanról ember dönt

- **Kontextus.** A kimaradt összevonás duplikál egy vevőt (látható); a hibás összevonás bevételt
  tesz át vevők között (láthatatlan).
- **Döntés.** Normalizálás, hasonlósági pontszám, ≥ 0,95 automatikusan elfogadva, minden alatta az
  operátorhoz kerül. Rövid nevet soha nem vonunk össze automatikusan.
- **Elvetve.** Egyetlen automatikus küszöb; ML-alapú egyeztetés (az operátornak megmagyarázhatatlan,
  nincs címkézett adat, és a mennyiség nem indokolta).
- **Következmények.** Az első importnál több száz döntés, később csak néhány.
- **Állapot.** Bevált. → [Névegyesítés](03-entity-resolution.md)

### ADR-05 — Minden nyers írásmód aliasként megmarad

- **Döntés.** Minden valaha látott írásmódot a kanonikus partnere alatt tárolunk, a forrásával együtt.
- **Elvetve.** A nevek felülírása a kanonikussal (elveszik a nyomvonal; jövőre ugyanaz az elírás
  újra kérdést vet fel).
- **Következmények.** A jövő évi elírás pontos találat; az alias-táblát tisztán kell tartani (egyszer
  futásonként nőtt — 2026 októberében egyedi kulccsal javítva).
- **Állapot.** Bevált.

### ADR-06 — Blokkoló minőségkapu, indokolt felülbírálással

- **Döntés.** Két súlyossági szint. Blokkoló: megnyert üzlet munkaszám nélkül, egyeztetetlen
  partner. Figyelmeztetés: hiányzó ország, hiányzó dátum, lassú reakció. Blokkoló hibát csak írásos
  indokkal lehet felülbírálni, amely a menettel együtt tárolódik.
- **Elvetve.** Csak figyelmeztetés (a munkaszám nélküli megnyert üzlet egyenesen a realizált
  árbevétel egyeztetésébe folyna); mindent blokkolni (minden import elakadna).
- **Állapot.** Bevált.

### ADR-07 — A státusz leképező tábla, az operátor bővítheti

- **Döntés.** 42 nyers írásmód → 10 állapot, kifejezett nyitott / nyert / vesztett jelzőkkel a
  kódban; az új írásmódokat az operátor veszi fel egy státusz-szótárba, az ETL alkalmazza őket.
- **Következmények.** Két helyen kell nézni. 2026 októberéig az ETL figyelmen kívül hagyta az
  operátor szótárát — ez a hiány ennek az összefoglalónak az írása közben derült ki, és javítva lett.
- **Állapot.** Bevált, javítva.

### ADR-08 — Inkrementális betöltés termékcsoport × év szerint

- **Döntés.** Csak az aktuális importban szereplő (termékcsoport, év) párokat cseréljük.
- **Elvetve.** Teljes újraépítés minden futáskor (az újraimport a lezárt évekhez is hozzányúl;
  lassabb; egy részleges feltöltés eltüntetné a többit).
- **Következmények.** Egy év eltávolításához kifejezett törlés kell.
- **Állapot.** Bevált.

### ADR-09 — Logika SQL-nézetekben, verziózott JSON-szerződés az oldal felé

- **Döntés.** Számozott SQL-nézetek hordozzák az üzleti logikát; az oldal egyetlen dolgot lát: egy
  JSON-fájlt szerződésverzióval és szakaszonkénti forrástérképpel.
- **Elvetve.** A metrikák számolása az oldal JavaScriptjében (visszakövethetetlen; elcsúszik a
  riporttól).
- **Következmények.** Egy metrika módosítása SQL-módosítás; a riport és az oldal közös definíciókat
  használ.
- **Állapot.** Bevált; 2026 októbere óta v2-es szerződés.

### ADR-10 — Ország = akivel üzletelünk

- **Kontextus.** A belföldi/külföldi bontás a banki riport alapkérdése; multinacionális cégeknél a
  cégjegyzéki ország és a piaci valóság eltér.
- **Döntés.** Az ország az a szereplő, akivel ténylegesen üzletelünk; a belföldi/külföldi mindig
  ebből származik; a kézi döntések mindent felülírnak; a rendszer javaslatai csak javaslatok.
- **Elvetve.** Cégjegyzéki/központi ország (erre a kérdésre elemzési szempontból hibás); a táblázat
  belföldi jelzőjében való bizalom (ellentmondott az ország nevének).
- **Következmények.** Minden külső országbontáshoz módszertani megjegyzés.
- **Állapot.** Bevált; a „jelző felülírja a nevet" hiba 2026 októberében javítva.

### ADR-11 — Kétféle év-alap, sosem összemosva

- **Döntés.** A funnel a megkeresés éve szerint; a realizált rendelés a nyilvántartás éve szerint,
  időbeli elhatárolással; a win rate a kimenet éve szerint. Egymás mellett mutatva, megmagyarázva.
- **Elvetve.** Egyetlen „nyert" szám (egyszerűbb, és a bank két kérdése közül az egyikre hibás).
- **Állapot.** Bevált. → [Üzleti definíciók](06-business-definitions.md)

### ADR-12 — Élő pipeline = 12 hónapon belül kiajánlott

- **Döntés.** A 12 hónapnál régebbi nyitott ajánlatok (az adatbeli legutolsó megkereséstől
  visszaszámolva) elavultak — lezárásra listázva, nem számolva.
- **Elvetve.** Minden nyitott ajánlat (az évekkel korábbi ajánlatok felfújták a pipeline-t);
  ajánlatonkénti lejárati dátum (a forrásban nincs rögzítve).
- **Állapot.** 2026 októbere óta érvényes.

### ADR-13 — Nincs becsült adat

- **Döntés.** Ha nincs adat, nincs grafikon sem.
- **Következmények.** Az iparági bontás kikerült, amikor kiderült, hogy a dúsító adat lefedettsége ~0%.
- **Állapot.** Bevált.

### ADR-14 — Amíg nincs rutin, nem automatizálunk

- **Döntés.** A munkaágak abban a módban futnak, amit az érettségük megenged: a dashboard
  kódvezérelt, a banki riport kézzel írt, DB-ből számolt számokra épül, a cégjegyzék-alapú elemzés
  feltáró jellegű.
- **Elvetve.** A riport generálása az első naptól (a formája minden változatban változott).
- **Következmények.** Negyedévente kézi munka; a lekérdezéseket most már szkriptbe kellene emelni
  (lásd [Kimenet](09-outcome.md)).
- **Állapot.** Bevált.

### ADR-15 — SQLite-fájlok és egy kis Flask-alkalmazás, egy operátor

- **Kontextus.** Egy operátor, negyedéves ciklus, néhány ezer ajánlat, munkafüzetek helyi lemezen.
  *(Nincs az áttekintő táblában — az átnézés után került be, mert ez az első kérdés, amit feltesznek.)*
- **Döntés.** Két SQLite-fájl, egy Python ETL két külső függőséggel (openpyxl, Flask), egyetlen
  HTML-fájlból álló oldal — az operátor Windows-gépén dupla kattintással futtatható.
- **Nem választott.** Adatbázis-szerver, BI-platform, transzformációs keretrendszer: sem a volumen,
  sem az egy-operátoros használat nem kívánta, és mindegyik üzemeltetendő infrastruktúrát hozott volna.
- **Következmények.** Egyszerre egy operátorra tervezve — a párhuzamos importok nincsenek védve; az
  elemzési DB egy fájl, amely percek alatt törölhető és újraépíthető.
- **Állapot.** Bevált.
