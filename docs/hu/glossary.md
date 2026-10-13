[English](../en/glossary.md) · **Magyar** · [↑ README](../../README.hu.md)

# Szójegyzék

| fogalom | jelentése itt |
|---|---|
| **alias** | egy partner nevének egyik írásmódja, ahogy egy forrásban begépelték; a kanonikus partner alatt tárolva |
| **blokkoló hiba** | a minőségkapu olyan találata, amely megállítja az importot, amíg nem javítják, vagy írásos indokkal felül nem bírálják |
| **elavult ajánlat** | az élő pipeline időablakánál régebbi nyitott ajánlat; a forrásban lezárandó |
| **elemzési DB** | `dashboard.db` — teljesen származtatott a munkafüzetekből és az operátori DB-ből; eldobható |
| **elrendezés-korszak** | évek sora, amelyben egy munkafüzet oszlopszerkezete nem változott |
| **harmadik divízió (S)** | egy harmadik üzletág, amely csak a rendelés-nyilvántartóban jelenik meg (négyjegyű munkaszám, nincs ajánlati funnel); külön soron szerepel |
| **élő pipeline** | kiajánlva, a megkeresés az adatbeli legutolsó megkereséstől számított 12 hónapon belül érkezett |
| **évhatáron átnyúló** | olyan üzlet, amelynek megkeresése az egyik évben érkezett, megnyerése (munkaszáma) egy másikban |
| **funnel** | megkeresések → kiajánlva → nyert / vesztett / elhalasztva / nyitott, a megkeresés éve szerint |
| **hibajegyzék** | a minőségkapu találatainak évenkénti listája, amelyet a táblák gazdái kapnak meg (angolul: *error list*) |
| **időbeli elhatárolás** | egy több éves rendelés minden nyilvántartási évben az arra az évre könyvelt résszel számít — évek között soha nincs deduplikálva |
| **kanonikus partner** | az az egyetlen rekord (`PM-xxxx`), amelyre egy cég összes írásmódja feloldódik |
| **kiadott érték** | az ajánlatok értékének összege, azon megkeresések nélkül, amelyekre soha nem készült ajánlat |
| **konverzió** | nyert érték ÷ kiadott érték |
| **megkeresés éve** | az év, amelyben az ajánlatkérés beérkezett — a funnel év-alapja |
| **munkaszám** | a megnyert ajánlathoz kiadott munkaszám; a kulcs az ajánlatok és a rendelés-nyilvántartó között |
| **normalizálás** | kisbetű, ékezet le, írásjel szóközzé, cégforma-végződés le — a név-egyezés első lépése |
| **operátor** | aki az import-varázslót futtatja és meghozza az ítéleteket |
| **operátori DB** | `admin.db` — minden emberi döntés tartós tárolója |
| **oszloptérkép** | a konfig-bejegyzés, amely megmondja, egy elrendezés-korszakban melyik oszlop melyik mezőt tartalmazza |
| **realizált árbevétel** | érték a rendelés-nyilvántartóból, a nyilvántartás éve szerint, időbeli elhatárolással |
| **rendelés-nyilvántartó** | a leszerződött rendelések éves munkafüzete; a realizált árbevétel forrása |
| **státusz-szótár** | az operátor által felvett nyers státuszok és normalizált állapotuk |
| **tételsor** | egy többtételes ajánlat egy tétele; az értéke az ajánlatba összegződik |
| **1. / 2. termékcsoport** | a megbízó két termékvonala (a kódban TG1 / TG2); hogy mik ezek, a módszer szempontjából mindegy |
| **válasz nélkül lezárt** | kiküldött ajánlat, amelyre 90–120 napig nem jött válasz, utólag lezárva; nem számít vesztettnek |
| **win rate** | nyert ÷ (nyert + vesztett), darabszám szerint |
| **zóna** | zöld (≥ 0,95, automatikus), sárga (0,85–0,95), piros (< 0,85) — a név-egyezés hasonlósági sávjai |
